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

"""Instruction chat data loaders and prefix-safe label masking for Gemma 4 SFT.

Gemma 4 unified chat templates append an empty ``<|channel>thought\\n<channel|>``
block when ``add_generation_prompt=True`` that may differ from rendered
multi-turn conversations without explicit reasoning blocks. Upstream
``ChatProcessor`` masks by ``len(prompt_tokens)``, which can over-mask the
first assistant response tokens. ``PrefixSafeChatProcessor`` masks strictly up
to the longest shared token prefix between ``full_tokens`` and ``prompt_tokens``.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from torchtitan.components.data import (
    FirstFitPackingConfig,
    GrainDataLoader,
    HuggingFaceRandomAccessSource,
    SingleDatasetConfig,
    TextSequence,
)
from torchtitan.components.loss import IGNORE_INDEX
from torchtitan.hf_datasets.text_datasets import ChatProcessor

DEFAULT_ALPACA_DATASET = "iamtarun/python_code_instructions_18k_alpaca"
DEFAULT_HOLDOUT_ROWS = 512


def shared_prefix_length(seq_a: list[int], seq_b: list[int]) -> int:
    """Returns the count of leading identical token IDs shared by two sequences."""
    shared = 0
    for tok_a, tok_b in zip(seq_a, seq_b):
        if tok_a != tok_b:
            break
        shared += 1
    return shared


def format_chat_sample(sample: dict[str, Any]) -> list[dict[str, str]]:
    """Normalizes an instruction row (`messages` or Alpaca schema) into chat messages."""
    if "messages" in sample and isinstance(sample["messages"], list):
        return [
            {"role": str(m["role"]), "content": str(m["content"])}
            for m in sample["messages"]
        ]
    instruction = (sample.get("instruction") or "").strip()
    inp = (sample.get("input") or "").strip()
    output = (sample.get("output") or "").strip()
    user_content = (
        f"{instruction}\n\n### Input:\n{inp}"
        if inp and inp.lower() != "not applicable"
        else instruction
    )
    return [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": output},
    ]


class PrefixSafeChatProcessor(ChatProcessor):
    """ChatProcessor that masks user prompt tokens using shared-prefix matching."""

    @dataclass(kw_only=True, slots=True)
    class Config(ChatProcessor.Config):
        pass

    def _tokenize_sample(self, sample: dict[str, Any]) -> TextSequence | None:
        messages = self._messages_fn(sample)
        self._validate_messages(messages)

        full_text = self._tokenizer.apply_chat_template(messages).rstrip("\n")
        full_tokens = self._tokenizer.encode(full_text, add_bos=True, add_eos=False)
        if full_tokens[-1] != self._eos_id:
            full_tokens.append(self._eos_id)
        if len(full_tokens) - 1 > self._max_context_length:
            return None

        prompt_text = self._tokenizer.apply_chat_template(
            messages[:-1], add_generation_prompt=True
        )
        prompt_tokens = self._tokenizer.encode(prompt_text, add_bos=True, add_eos=False)
        shared = shared_prefix_length(full_tokens, prompt_tokens)

        tokens = np.asarray(full_tokens, dtype=np.int64)
        labels = tokens[1:].copy()
        labels[: max(shared - 1, 0)] = IGNORE_INDEX
        return TextSequence(input_ids=tokens[:-1], labels=labels)


def build_hf_sft_loader(
    *,
    dataset_path: str = DEFAULT_ALPACA_DATASET,
    dataset_split: str | None = None,
    holdout_rows: int = DEFAULT_HOLDOUT_ROWS,
) -> GrainDataLoader.Config:
    """Builds a first-fit packed Grain SFT dataloader for Hugging Face datasets."""
    if dataset_split is None:
        dataset_split = f"train[:-{holdout_rows}]" if holdout_rows > 0 else "train"
    return GrainDataLoader.Config(
        dataset=FirstFitPackingConfig(
            dataset=SingleDatasetConfig(
                source=HuggingFaceRandomAccessSource.Config(
                    path=dataset_path,
                    split=dataset_split,
                ),
                processor=PrefixSafeChatProcessor.Config(
                    messages_fn=format_chat_sample
                ),
                post_filters=(lambda sample: sample is not None,),
            ),
        ),
    )
