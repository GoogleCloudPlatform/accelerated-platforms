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

"""State-dict adapter for LoRA SFT runs on TorchTitan's native Gemma 4 model.

Upstream ``Gemma4StateDictAdapter.to_hf`` maps base weights between TorchTitan
and Hugging Face names and skips keys absent from its static table, which omits
``.lora_a.weight`` and ``.lora_b.weight`` tensors on ``--checkpoint.last_save_in_hf``.

``LoraExportAdapter`` preserves base weight loading via ``from_hf`` and exports
trained LoRA adapter tensors under standard PEFT key names
(``base_model.model.<hf_module>.lora_A.weight`` / ``.lora_B.weight``) so
``merge_lora`` can produce both a PEFT adapter directory and a merged Hugging
Face checkpoint.
"""

from typing import Any

from torchtitan.experiments.tpu.examples.gemma4.state_dict_adapter import (
    Gemma4StateDictAdapter,
)

LORA_A = ".lora_a.weight"
LORA_B = ".lora_b.weight"
PEFT_PREFIX = "base_model.model."


def is_lora_key(key: str) -> bool:
    """Returns True if ``key`` names a TorchTitan LoRA adapter weight."""
    return key.endswith(LORA_A) or key.endswith(LORA_B)


class LoraExportAdapter(Gemma4StateDictAdapter):
    """Loads base HF checkpoints and exports trained LoRA tensors in PEFT format."""

    expect_initial_hf_load: bool = True

    def __init__(self, model_config: Any, hf_assets_path: str | None) -> None:
        super().__init__(model_config, hf_assets_path)
        self._initial_load_pending = self.expect_initial_hf_load
        self._base_fqn_to_index_mapping = self.fqn_to_index_mapping

    def _hf_name_of(self, titan_weight_key: str) -> str:
        """Resolves the Hugging Face weight FQN for one TorchTitan base weight."""
        mapped = Gemma4StateDictAdapter.to_hf(self, {titan_weight_key: None})
        if len(mapped) != 1:
            raise KeyError(
                f"No Hugging Face weight mapping for {titan_weight_key!r}; "
                "cannot map LoRA adapter tensor to PEFT format."
            )
        return next(iter(mapped))

    def lora_to_peft(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        """Converts TorchTitan LoRA tensors in ``state_dict`` to PEFT keys."""
        out: dict[str, Any] = {}
        for key, value in state_dict.items():
            if key.endswith(LORA_A):
                base, suffix = key[: -len(LORA_A)], ".lora_A.weight"
            elif key.endswith(LORA_B):
                base, suffix = key[: -len(LORA_B)], ".lora_B.weight"
            else:
                continue
            hf_weight = self._hf_name_of(base + ".weight")
            out[PEFT_PREFIX + hf_weight[: -len(".weight")] + suffix] = value
        return out

    def to_hf(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        has_lora = any(is_lora_key(k) for k in state_dict)
        if self._initial_load_pending or not has_lora:
            return super().to_hf(state_dict)
        # Consolidate all adapter tensors into a single safetensors file rather
        # than inheriting a multi-shard base model index.
        self.fqn_to_index_mapping = None
        return self.lora_to_peft(state_dict)

    def from_hf(self, hf_state_dict: dict[str, Any]) -> dict[str, Any]:
        self._initial_load_pending = False
        return super().from_hf(hf_state_dict)


def lora_export_adapter(*, expect_initial_hf_load: bool) -> type[LoraExportAdapter]:
    """Returns a ``LoraExportAdapter`` subclass configured for initial HF load mode."""

    class _BoundLoraExportAdapter(LoraExportAdapter):
        pass

    _BoundLoraExportAdapter.expect_initial_hf_load = expect_initial_hf_load
    _BoundLoraExportAdapter.__name__ = (
        "LoraExportAdapterAfterHfLoad"
        if expect_initial_hf_load
        else "LoraExportAdapterNoHfLoad"
    )
    return _BoundLoraExportAdapter
