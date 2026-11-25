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

"""Build-time unit tests for ``torchtitan_tpu_sft``."""

import json
import os
import tempfile
import unittest

import safetensors.torch
import torch
from torchtitan.components.checkpointer import dcp as dcp_module
from torchtitan.experiments.tpu.examples import gemma4 as g4
from torchtitan.experiments.tpu.examples.gemma4.model import (
    SlidingWindowScaledDotProductAttention,
)
from torchtitan_tpu_sft import config_registry, data, flavors
from torchtitan_tpu_sft.lora_adapter import lora_export_adapter
from torchtitan_tpu_sft.merge_lora import main as merge_lora_main


class TorchTitanTpuSftTest(unittest.TestCase):
    """Verifies Gemma 4 12B flavor, LoRA pins, PEFT export, and merge round-trip."""

    def test_dcp_consolidation_symbol_registered(self) -> None:
        self.assertTrue(
            hasattr(dcp_module, "consolidate_safetensors_files_on_every_rank")
        )

    def test_gemma4_12b_flavor_registered(self) -> None:
        self.assertIn(flavors.FLAVOR_12B, g4._gemma4_factories)
        spec = g4.model_registry(
            flavors.FLAVOR_12B, attn_backend="sdpa", enable_weight_tying=False
        )
        self.assertEqual(spec.model.vocab_size, 262144)
        self.assertEqual(spec.model.dim, 3840)
        self.assertEqual(len(spec.model.layers), 48)
        lora_cfg = config_registry.gemma4_12b_lora_sft()
        self.assertEqual(len(lora_cfg.model_spec.model.layers), 48)

    def test_tiny_lora_preserves_sliding_window_attention_and_peft_export(
        self,
    ) -> None:
        spec = config_registry.build_gemma4_spec(
            flavors.FLAVOR_12B_TINY,
            lora_rank=4,
            lora_alpha=8.0,
            expect_initial_hf_load=False,
            fused_loss=False,
        )
        model = spec.model.build()
        for name, module in model.named_modules():
            if name.endswith("attention.inner_attention"):
                self.assertIsInstance(module, SlidingWindowScaledDotProductAttention)

        adapter_cls = lora_export_adapter(expect_initial_hf_load=False)
        adapter = adapter_cls(spec.model, None)
        peft_sd = adapter.to_hf(model.state_dict())
        self.assertGreater(len(peft_sd), 0)
        self.assertTrue(
            all(
                k.startswith("base_model.model.model.language_model.")
                and (k.endswith(".lora_A.weight") or k.endswith(".lora_B.weight"))
                for k in peft_sd
            )
        )

    def test_shared_prefix_masking_handles_thinking_channel_divergence(
        self,
    ) -> None:
        # Simulate Gemma 4 12B generation prompt ending in empty thinking tags
        # `[10, 20, 30, 900, 901]` vs rendered conversation `[10, 20, 30, 42, 43]`.
        full_tokens = [10, 20, 30, 42, 43, 2]
        prompt_tokens = [10, 20, 30, 900, 901]
        self.assertEqual(data.shared_prefix_length(full_tokens, prompt_tokens), 3)

    def test_merge_lora_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = os.path.join(tmpdir, "base")
            ckpt_dir = os.path.join(tmpdir, "ckpt")
            out_dir = os.path.join(tmpdir, "export")
            os.makedirs(base_dir)
            os.makedirs(ckpt_dir)

            w0 = torch.ones((8, 4), dtype=torch.bfloat16)
            safetensors.torch.save_file(
                {"model.language_model.layers.0.self_attn.q_proj.weight": w0},
                os.path.join(base_dir, "model.safetensors"),
            )
            with open(
                os.path.join(base_dir, "config.json"), "w", encoding="utf-8"
            ) as cfg_file:
                json.dump({"dtype": "bfloat16"}, cfg_file)

            lora_a = torch.full((2, 4), 0.5, dtype=torch.float32)
            lora_b = torch.full((8, 2), 0.25, dtype=torch.float32)
            safetensors.torch.save_file(
                {
                    "base_model.model.model.language_model.layers.0.self_attn.q_proj.lora_A.weight": lora_a,
                    "base_model.model.model.language_model.layers.0.self_attn.q_proj.lora_B.weight": lora_b,
                },
                os.path.join(ckpt_dir, "model-00001-of-00001.safetensors"),
            )

            rc = merge_lora_main(
                [
                    "--base",
                    base_dir,
                    "--adapter",
                    ckpt_dir,
                    "--alpha",
                    "4.0",
                    "--out",
                    out_dir,
                ]
            )
            self.assertEqual(rc, 0)
            merged = safetensors.torch.load_file(
                os.path.join(out_dir, "merged", "model.safetensors")
            )
            # W + (4 / 2) * (B @ A) = 1.0 + 2.0 * (2 * 0.5 * 0.25) = 1.5
            expected = torch.full((8, 4), 1.5, dtype=torch.bfloat16)
            torch.testing.assert_close(
                merged["model.language_model.layers.0.self_attn.q_proj.weight"],
                expected,
            )


if __name__ == "__main__":
    unittest.main()
