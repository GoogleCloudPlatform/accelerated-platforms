#!/usr/bin/env python3
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Evaluates base vs LoRA-merged Hugging Face checkpoints on held-out SFT rows."""

import argparse
import json
import os
import sys
import time
from typing import Any

import datasets
import safetensors.torch
import torch
import torch.nn.functional as F
import transformers
from torchtitan_tpu_sft.data import (
    DEFAULT_ALPACA_DATASET,
    DEFAULT_HOLDOUT_ROWS,
    format_chat_sample,
    shared_prefix_length,
)

PEFT_PREFIX = "base_model.model."


def build_examples(
    tokenizer: Any, rows: Any, max_tokens: int
) -> list[tuple[list[int], int]]:
    """Tokenizes rows and computes shared prompt prefix lengths."""
    eos = tokenizer.eos_token_id
    examples: list[tuple[list[int], int]] = []
    for row in rows:
        messages = format_chat_sample(row)
        full_text = tokenizer.apply_chat_template(messages, tokenize=False).rstrip("\n")
        ids = list(tokenizer(full_text, add_special_tokens=False).input_ids)
        if ids[-1] != eos:
            ids.append(eos)
        if len(ids) - 1 > max_tokens:
            continue
        prompt_text = tokenizer.apply_chat_template(
            messages[:-1], tokenize=False, add_generation_prompt=True
        )
        prompt_ids = list(tokenizer(prompt_text, add_special_tokens=False).input_ids)
        shared = shared_prefix_length(ids, prompt_ids)
        examples.append((ids, shared))
    return examples


@torch.no_grad()
def score_model(model: Any, examples: list[tuple[list[int], int]]) -> dict[str, Any]:
    """Computes mean response cross-entropy and top-1 token accuracy."""
    loss, tokens, top1 = 0.0, 0, 0
    start = time.time()
    for ids, shared in examples:
        inputs = torch.tensor([ids[:-1]])
        labels = torch.tensor(ids[1:])
        labels[: max(shared - 1, 0)] = -100
        logits = model(input_ids=inputs).logits[0].float()
        loss += float(
            F.cross_entropy(logits, labels, ignore_index=-100, reduction="sum")
        )
        keep = labels != -100
        tokens += int(keep.sum())
        top1 += int((logits.argmax(-1)[keep] == labels[keep]).sum())
    return {
        "conversations": len(examples),
        "response_tokens": tokens,
        "mean_cross_entropy": round(loss / max(tokens, 1), 4),
        "next_token_accuracy": round(top1 / max(tokens, 1), 4),
        "seconds": round(time.time() - start, 1),
    }


def _load_peft_pairs(
    adapter_dir: str,
) -> tuple[dict[str, tuple[torch.Tensor, torch.Tensor]], float]:
    with open(
        os.path.join(adapter_dir, "adapter_config.json"), encoding="utf-8"
    ) as cfg_file:
        cfg = json.load(cfg_file)
    tensors = safetensors.torch.load_file(
        os.path.join(adapter_dir, "adapter_model.safetensors")
    )
    halves: dict[str, dict[str, torch.Tensor]] = {}
    for key, value in tensors.items():
        name = key[len(PEFT_PREFIX) :]
        for tag in ("A", "B"):
            suffix = f".lora_{tag}.weight"
            if name.endswith(suffix):
                weight_key = name[: -len(suffix)] + ".weight"
                halves.setdefault(weight_key, {})[tag] = value.float()
    pairs = {k: (v["A"], v["B"]) for k, v in halves.items()}
    return pairs, float(cfg["lora_alpha"]) / int(cfg["r"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--adapter", help="PEFT adapter directory.")
    parser.add_argument("--merged", help="Merged HF checkpoint directory.")
    parser.add_argument("--out", required=True, help="JSON output path.")
    parser.add_argument("--dataset", default=DEFAULT_ALPACA_DATASET)
    parser.add_argument("--rows", type=int, default=32)
    parser.add_argument("--holdout", type=int, default=DEFAULT_HOLDOUT_ROWS)
    parser.add_argument("--max-tokens", type=int, default=2048)
    args = parser.parse_args(argv)

    tokenizer = transformers.AutoTokenizer.from_pretrained(args.base)
    train_ds = datasets.load_dataset(args.dataset, split="train")
    total_rows = len(train_ds)
    splits = {
        "train_rows": train_ds.select(range(min(args.rows, total_rows))),
        "heldout_rows": train_ds.select(
            range(
                max(total_rows - args.holdout, 0),
                min(total_rows - args.holdout + args.rows, total_rows),
            )
        ),
    }
    examples = {
        k: build_examples(tokenizer, v, args.max_tokens) for k, v in splits.items()
    }

    report: dict[str, Any] = {
        "base": args.base,
        "adapter": args.adapter,
        "merged": args.merged,
        "dataset": args.dataset,
        "dataset_rows": total_rows,
        "models": {},
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    model = transformers.AutoModelForCausalLM.from_pretrained(
        args.base, dtype=torch.float32
    )
    model.eval()
    report["models"]["base"] = {k: score_model(model, v) for k, v in examples.items()}
    print(
        f"[eval_export] base: {json.dumps(report['models']['base'])}",
        file=sys.stderr,
        flush=True,
    )

    if args.adapter:
        with open(os.path.join(args.base, "config.json"), encoding="utf-8") as cfg_file:
            raw_cfg = json.load(cfg_file)
        dtype_name = raw_cfg.get("dtype") or raw_cfg.get("torch_dtype", "bfloat16")
        stored_dtype = getattr(torch, dtype_name)
        pairs, scale = _load_peft_pairs(args.adapter)
        params = dict(model.named_parameters())
        with torch.no_grad():
            for key, (lora_a, lora_b) in pairs.items():
                weight = params[key]
                exact = weight.data + scale * (lora_b @ lora_a)
                weight.data.copy_(exact.to(stored_dtype).float())
        report["models"]["merged_adapter"] = {
            k: score_model(model, v) for k, v in examples.items()
        }
        print(
            "[eval_export] merged_adapter: "
            f"{json.dumps(report['models']['merged_adapter'])}",
            file=sys.stderr,
            flush=True,
        )

    if args.merged:
        del model
        merged_model = transformers.AutoModelForCausalLM.from_pretrained(
            args.merged, dtype=torch.float32
        )
        merged_model.eval()
        report["models"]["merged_from_disk"] = {
            k: score_model(merged_model, v) for k, v in examples.items()
        }
        print(
            "[eval_export] merged_from_disk: "
            f"{json.dumps(report['models']['merged_from_disk'])}",
            file=sys.stderr,
            flush=True,
        )

    with open(args.out, "w", encoding="utf-8") as out_file:
        json.dump(report, out_file, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
