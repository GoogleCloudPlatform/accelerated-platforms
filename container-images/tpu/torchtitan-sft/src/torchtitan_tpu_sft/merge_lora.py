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

"""Merges TorchTitan PEFT-named LoRA safetensors into a Hugging Face checkpoint.

Writes under ``--out``:
  - ``adapter/``: PEFT-compatible ``adapter_model.safetensors`` + ``adapter_config.json``
  - ``merged/``: Full BF16 Hugging Face checkpoint (``W + (alpha / rank) * B @ A``)
    along with ``config.json``, ``processor_config.json``, ``tokenizer*``, and
    ``chat_template.jinja`` ready for ``vllm-torchtpu`` serving.
"""

import argparse
import glob
import json
import os
import shutil
import sys
import tempfile
from typing import Any

import safetensors.torch
import torch

PEFT_PREFIX = "base_model.model."
A_SUFFIX = ".lora_A.weight"
B_SUFFIX = ".lora_B.weight"
COPIED_FILES = (
    "config.json",
    "generation_config.json",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "chat_template.jinja",
)


def load_adapter(path: str) -> dict[str, torch.Tensor]:
    """Loads LoRA adapter tensors from a file or checkpoint step directory."""
    files = (
        [path]
        if os.path.isfile(path)
        else sorted(glob.glob(os.path.join(path, "*.safetensors")))
    )
    if not files:
        raise FileNotFoundError(
            f"No .safetensors files found under {path!r}. Ensure training "
            "completed with --checkpoint.last_save_in_hf."
        )
    tensors: dict[str, torch.Tensor] = {}
    for file_path in files:
        tensors.update(safetensors.torch.load_file(file_path))
    lora = {k: v for k, v in tensors.items() if k.endswith((A_SUFFIX, B_SUFFIX))}
    if not lora:
        raise ValueError(
            f"Checkpoint {files} contains no LoRA tensors (sample keys: "
            f"{sorted(tensors)[:3]})."
        )
    return lora


def pair_adapters(
    lora: dict[str, torch.Tensor],
) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    """Pairs ``(lora_A, lora_B)`` tensors keyed by target Hugging Face weight FQN."""
    modules: dict[str, dict[str, torch.Tensor]] = {}
    for key, value in lora.items():
        if not key.startswith(PEFT_PREFIX):
            raise ValueError(f"Adapter key {key!r} is missing prefix {PEFT_PREFIX!r}.")
        name = key[len(PEFT_PREFIX) :]
        if name.endswith(A_SUFFIX):
            modules.setdefault(name[: -len(A_SUFFIX)], {})["A"] = value
        elif name.endswith(B_SUFFIX):
            modules.setdefault(name[: -len(B_SUFFIX)], {})["B"] = value
    pairs: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for module, halves in modules.items():
        if set(halves) != {"A", "B"}:
            raise ValueError(
                f"Incomplete LoRA pair for {module!r}: found {sorted(halves)}"
            )
        pairs[module + ".weight"] = (halves["A"], halves["B"])
    return pairs


def merge_into_base(
    base: dict[str, torch.Tensor],
    pairs: dict[str, tuple[torch.Tensor, torch.Tensor]],
    alpha: float,
) -> dict[str, Any]:
    """Applies ``W + (alpha / rank) * (B @ A)`` in-place onto ``base`` tensors."""
    stats: dict[str, Any] = {
        "merged": 0,
        "rank": None,
        "zero_delta": 0,
        "max_rel_delta": 0.0,
    }
    for key, (lora_a, lora_b) in pairs.items():
        if key not in base:
            raise KeyError(
                f"LoRA adapter targets {key!r}, which is absent from base checkpoint."
            )
        weight = base[key]
        rank = int(lora_a.shape[0])
        if lora_b.shape[1] != rank or (
            lora_b.shape[0],
            lora_a.shape[1],
        ) != tuple(weight.shape):
            raise ValueError(
                f"Shape mismatch on {key}: base={tuple(weight.shape)}, "
                f"lora_B={tuple(lora_b.shape)}, lora_A={tuple(lora_a.shape)}."
            )
        if stats["rank"] not in (None, rank):
            raise ValueError(f"Mixed LoRA ranks: {stats['rank']} vs {rank}.")
        stats["rank"] = rank
        delta = (alpha / rank) * (lora_b.float() @ lora_a.float())
        delta_norm = float(delta.norm())
        if delta_norm == 0.0:
            stats["zero_delta"] += 1
        rel = delta_norm / max(float(weight.float().norm()), 1e-30)
        stats["max_rel_delta"] = max(stats["max_rel_delta"], rel)
        base[key] = (weight.float() + delta).to(weight.dtype)
        stats["merged"] += 1
    return stats


def _atomic_save_safetensors(tensors: dict[str, torch.Tensor], dest_path: str) -> None:
    """Stages safetensors locally before copying to GCSFuse/destination with 0644 mode."""
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix="safetensors_", suffix=".tmp", delete=False
    ) as tmp:
        tmp_path = tmp.name
    try:
        safetensors.torch.save_file(tensors, tmp_path, metadata={"format": "pt"})
        os.chmod(tmp_path, 0o644)
        shutil.copyfile(tmp_path, dest_path)
        os.chmod(dest_path, 0o644)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Base HF checkpoint directory.")
    parser.add_argument(
        "--adapter",
        required=True,
        help="TorchTitan checkpoint step directory.",
    )
    parser.add_argument(
        "--alpha", type=float, required=True, help="LoRA scaling alpha."
    )
    parser.add_argument("--out", required=True, help="Export root directory.")
    parser.add_argument(
        "--skip-merged",
        action="store_true",
        help="Write only the PEFT adapter directory without merging base weights.",
    )
    args = parser.parse_args(argv)

    lora = load_adapter(args.adapter)
    pairs = pair_adapters(lora)
    rank = int(next(iter(pairs.values()))[0].shape[0])
    print(
        f"[merge_lora] Loaded {len(pairs)} adapted modules (rank={rank}, "
        f"alpha={args.alpha})",
        file=sys.stderr,
    )

    adapter_dir = os.path.join(args.out, "adapter")
    os.makedirs(adapter_dir, exist_ok=True)
    adapter_file = os.path.join(adapter_dir, "adapter_model.safetensors")
    _atomic_save_safetensors({k: v.contiguous() for k, v in lora.items()}, adapter_file)
    target_modules = sorted({k.rsplit(".", 2)[-2] for k in pairs})
    with open(
        os.path.join(adapter_dir, "adapter_config.json"),
        "w",
        encoding="utf-8",
    ) as cfg_file:
        json.dump(
            {
                "peft_type": "LORA",
                "task_type": "CAUSAL_LM",
                "base_model_name_or_path": args.base,
                "r": rank,
                "lora_alpha": args.alpha,
                "lora_dropout": 0.0,
                "bias": "none",
                "target_modules": target_modules,
                "fan_in_fan_out": False,
                "inference_mode": True,
            },
            cfg_file,
            indent=2,
        )
    print(f"[merge_lora] Wrote PEFT adapter to {adapter_dir}", file=sys.stderr)
    if args.skip_merged:
        return 0

    base_files = sorted(glob.glob(os.path.join(args.base, "*.safetensors")))
    if not base_files:
        raise FileNotFoundError(
            f"No .safetensors files found under base path {args.base!r}."
        )
    base: dict[str, torch.Tensor] = {}
    for file_path in base_files:
        base.update(safetensors.torch.load_file(file_path))

    stats = merge_into_base(base, pairs, args.alpha)
    if stats["zero_delta"] == stats["merged"]:
        print(
            "ERROR: All LoRA adapter deltas are zero; adapters were not updated.",
            file=sys.stderr,
        )
        return 1

    merged_dir = os.path.join(args.out, "merged")
    os.makedirs(merged_dir, exist_ok=True)
    merged_file = os.path.join(merged_dir, "model.safetensors")
    _atomic_save_safetensors(base, merged_file)

    for filename in COPIED_FILES:
        src = os.path.join(args.base, filename)
        if os.path.exists(src):
            shutil.copyfile(src, os.path.join(merged_dir, filename))

    with open(
        os.path.join(merged_dir, "merge_report.json"), "w", encoding="utf-8"
    ) as report_file:
        json.dump(
            {
                "base": args.base,
                "adapter": args.adapter,
                "alpha": args.alpha,
                **stats,
            },
            report_file,
            indent=2,
        )
    print(
        f"[merge_lora] Wrote merged checkpoint to {merged_dir}: "
        f"{json.dumps(stats)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
