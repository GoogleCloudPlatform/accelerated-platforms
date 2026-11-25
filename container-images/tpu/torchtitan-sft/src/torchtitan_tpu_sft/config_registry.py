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

"""TorchTitan TPU job configurations for Gemma 4 LoRA and full SFT on GKE.

Invoke with TorchTitan's TPU trainer:

  torchrun --nproc_per_node=4 -m torchtitan.experiments.tpu.train \\
      --module=torchtitan_tpu_sft --config=gemma4_12b_lora_sft
"""

import os
from typing import Any

from torchtitan.components.checkpointer.dcp import CheckpointManager
from torchtitan.components.lora import LoRAConverter
from torchtitan.components.loss import CrossEntropyLoss
from torchtitan.components.metrics import MetricsProcessor
from torchtitan.components.optimizer import LRSchedulersContainer, default_adamw
from torchtitan.components.validate import Validator
from torchtitan.config import derive
from torchtitan.experiments.tpu.examples import gemma4 as g4
from torchtitan.experiments.tpu.examples.gemma4 import config_registry as g4_configs
from torchtitan.experiments.tpu.examples.gemma4.model import (
    SlidingWindowScaledDotProductAttention,
)
from torchtitan.experiments.tpu.overrides.fused_loss import (
    FusedLossLinearWrapper,
)
from torchtitan.experiments.tpu.tpu_job_config import (
    SplashAttentionKernelConfig,
    TPUTrainerConfig,
)
from torchtitan.experiments.transformers_modeling_backend.tokenizer import (
    HFBackendTokenizer,
)
from torchtitan.models.common.attention import ScaledDotProductInnerAttention
from torchtitan.tools.logging import logger
from torchtitan_tpu_sft import data, flavors
from torchtitan_tpu_sft.lora_adapter import is_lora_key, lora_export_adapter

LORA_TARGETS = ("wq", "wkv", "wo", "w1", "w2", "w3")
DEFAULT_LORA_RANK = 16
DEFAULT_LORA_ALPHA = 32.0


def _verify_lora_trainable_and_attention(
    optimizers: Any, model_parts: list[Any], parallel_dims: Any
) -> None:
    """Asserts that only LoRA adapters are trainable and sliding-window attention stays active."""
    trainable, frozen = 0, 0
    unexpected_trainable: list[str] = []
    plain_attention_layers: list[str] = []

    for model in model_parts:
        for name, param in model.named_parameters():
            if not param.requires_grad:
                frozen += param.numel()
            elif is_lora_key(name) or ".lora_a." in name or ".lora_b." in name:
                trainable += param.numel()
            else:
                unexpected_trainable.append(name)

        for name, module in model.named_modules():
            if (
                name.endswith("attention.inner_attention")
                and type(module) is ScaledDotProductInnerAttention
            ):
                plain_attention_layers.append(name)

    if unexpected_trainable:
        raise RuntimeError(
            f"Found {len(unexpected_trainable)} non-LoRA trainable parameters: "
            f"{unexpected_trainable[:5]}"
        )
    if trainable == 0:
        raise RuntimeError("Zero LoRA parameters marked requires_grad=True.")
    if plain_attention_layers:
        raise RuntimeError(
            f"{len(plain_attention_layers)} layers degraded to plain "
            f"ScaledDotProductInnerAttention without sliding-window/packed-doc "
            f"masks: {plain_attention_layers[:3]}"
        )

    logger.info(
        "[torchtitan_tpu_sft] Verified LoRA setup: trainable=%s, frozen=%s",
        f"{trainable:,}",
        f"{frozen:,}",
    )
    g4.register_moe_load_balancing_hook(optimizers, model_parts, parallel_dims)


def pin_inner_attention(model_config: Any) -> int:
    """Replaces ``ScaledDotProductInnerAttention.Config`` prior to ``LoRAConverter``.

    ``LoRAConverter`` wraps unadapted ``Configurable.Config`` nodes in dynamic
    ``_Frozen*`` subclasses, which causes exact ``type(...) is`` checks inside
    ``Gemma4Attention`` to miss and fall back to causal-only attention. Pinning
    ``SlidingWindowScaledDotProductAttention.Config`` beforehand preserves both
    sliding-window and packed-sequence document masks.
    """
    pinned = 0
    for layer in model_config.layers:
        inner = layer.attention.inner_attention
        if type(inner) is ScaledDotProductInnerAttention.Config:
            layer.attention.inner_attention = (
                SlidingWindowScaledDotProductAttention.Config(
                    param_init=inner.param_init,
                    sharding_config=inner.sharding_config,
                )
            )
            pinned += 1
    return pinned


def pin_fused_loss_head(model_config: Any) -> None:
    """Swaps ``SoftCappedLinear.Config`` for ``FusedLossLinearWrapper.Config`` before LoRA."""
    head = model_config.lm_head
    model_config.lm_head = derive(
        head,
        FusedLossLinearWrapper.Config,
        soft_cap=head.output_soft_cap_temp,
        output_multiplier=head.output_multiplier,
    )


def build_gemma4_spec(
    flavor: str,
    *,
    lora_rank: int,
    lora_alpha: float = DEFAULT_LORA_ALPHA,
    expect_initial_hf_load: bool = True,
    fused_loss: bool = True,
) -> Any:
    """Builds a Gemma 4 ``ModelSpec`` with optional LoRA adapters and TPU kernel pins."""
    spec = g4.model_registry(
        flavor,
        attn_backend="sdpa",
        enable_weight_tying=False,
    )
    if lora_rank > 0:
        pin_inner_attention(spec.model)
        if fused_loss:
            pin_fused_loss_head(spec.model)
        converter = LoRAConverter.Config(
            rank=lora_rank,
            alpha=lora_alpha,
            target_modules=list(LORA_TARGETS),
        )
        spec.model = converter.build().convert(spec.model)
        spec.state_dict_adapter = lora_export_adapter(
            expect_initial_hf_load=expect_initial_hf_load
        )
        spec.post_optimizer_build_fn = _verify_lora_trainable_and_attention
    return spec


def _build_sft_config(
    flavor: str,
    *,
    lora_rank: int,
    lora_alpha: float = DEFAULT_LORA_ALPHA,
    splash: bool = True,
    fused_loss: bool = True,
    lr: float = 1e-4,
) -> TPUTrainerConfig:
    dataset_path = os.environ.get("HF_DATASET_PATH", data.DEFAULT_ALPACA_DATASET)
    dataset_split = os.environ.get("HF_DATASET_SPLIT") or None
    holdout_rows = int(os.environ.get("HOLDOUT_ROWS", str(data.DEFAULT_HOLDOUT_ROWS)))

    cfg = g4_configs.gemma4_31b()
    cfg.hf_assets_path = os.environ.get(
        "HF_ASSETS_PATH", "/gcs/hf-models/google/gemma-4-12B-it"
    )
    cfg.dump_folder = os.environ.get("DUMP_FOLDER", "/gcs/runs/gemma4-lora-sft")
    cfg.training.num_tokens_per_microbatch_per_dp_rank = 2048
    cfg.training.max_context_length = 2048
    cfg.training.steps = 100
    cfg.tokenizer = HFBackendTokenizer.Config()
    cfg.dataloader = data.build_hf_sft_loader(
        dataset_path=dataset_path,
        dataset_split=dataset_split,
        holdout_rows=holdout_rows,
    )
    cfg.optimizer = default_adamw(lr=lr, implementation="foreach")
    cfg.lr_scheduler = LRSchedulersContainer.Config(
        warmup_steps=10,
        decay_ratio=0.8,
        decay_type="cosine",
        min_lr_factor=0.1,
    )
    cfg.metrics = MetricsProcessor.Config(log_freq=5, enable_tensorboard=True)
    cfg.checkpoint = CheckpointManager.Config(
        enable=True,
        initial_load_in_hf=True,
        initial_load_model_only=True,
        interval=1_000_000,
        last_save_model_only=True,
        last_save_in_hf=True,
        export_dtype="float32" if lora_rank > 0 else "bfloat16",
    )

    if not splash:
        cfg.splash_attention_kernel = SplashAttentionKernelConfig()

    fused_override = g4_configs._FUSED_LOSS_OVERRIDE
    cfg.override.imports = [
        imp for imp in cfg.override.imports if imp != fused_override
    ]
    if fused_loss:
        cfg.model_spec = build_gemma4_spec(
            flavor, lora_rank=0, expect_initial_hf_load=True, fused_loss=False
        )
        g4_configs._enable_pallas_cross_entropy(cfg)
        if lora_rank > 0:
            cfg.override.imports = [
                imp for imp in cfg.override.imports if imp != fused_override
            ]
    else:
        cfg.loss = CrossEntropyLoss.Config()

    cfg.model_spec = build_gemma4_spec(
        flavor,
        lora_rank=lora_rank,
        lora_alpha=lora_alpha,
        expect_initial_hf_load=True,
        fused_loss=fused_loss,
    )
    return cfg


def gemma4_12b_lora_sft() -> TPUTrainerConfig:
    """Gemma 4 12B LoRA SFT with SplashAttention and Pallas fused cross-entropy."""
    rank = int(os.environ.get("LORA_RANK", str(DEFAULT_LORA_RANK)))
    alpha = float(os.environ.get("LORA_ALPHA", str(DEFAULT_LORA_ALPHA)))
    lr = float(os.environ.get("LEARNING_RATE", "1e-4"))
    return _build_sft_config(
        flavors.FLAVOR_12B,
        lora_rank=rank,
        lora_alpha=alpha,
        splash=True,
        fused_loss=True,
        lr=lr,
    )


def gemma4_12b_lora_sft_sdpa() -> TPUTrainerConfig:
    """Gemma 4 12B LoRA SFT using reference SDPA and standard cross-entropy."""
    rank = int(os.environ.get("LORA_RANK", str(DEFAULT_LORA_RANK)))
    alpha = float(os.environ.get("LORA_ALPHA", str(DEFAULT_LORA_ALPHA)))
    lr = float(os.environ.get("LEARNING_RATE", "1e-4"))
    return _build_sft_config(
        flavors.FLAVOR_12B,
        lora_rank=rank,
        lora_alpha=alpha,
        splash=False,
        fused_loss=False,
        lr=lr,
    )


def gemma4_12b_full_sft() -> TPUTrainerConfig:
    """Gemma 4 12B full-parameter SFT on multi-host TPU v6e (16+ chips)."""
    lr = float(os.environ.get("LEARNING_RATE", "2e-5"))
    return _build_sft_config(
        flavors.FLAVOR_12B,
        lora_rank=0,
        splash=True,
        fused_loss=True,
        lr=lr,
    )


def gemma4_31b_lora_sft() -> TPUTrainerConfig:
    """Gemma 4 31B LoRA SFT on multi-host TPU v6e (16+ chips)."""
    rank = int(os.environ.get("LORA_RANK", str(DEFAULT_LORA_RANK)))
    alpha = float(os.environ.get("LORA_ALPHA", str(DEFAULT_LORA_ALPHA)))
    lr = float(os.environ.get("LEARNING_RATE", "1e-4"))
    return _build_sft_config(
        "31B",
        lora_rank=rank,
        lora_alpha=alpha,
        splash=True,
        fused_loss=True,
        lr=lr,
    )


def gemma4_tiny_lora() -> TPUTrainerConfig:
    """Tiny 12B-shaped Gemma 4 LoRA configuration for CPU/TPU unit verification."""
    cfg = g4_configs.gemma4_debugmodel()
    cfg.model_spec = build_gemma4_spec(
        flavors.FLAVOR_12B_TINY,
        lora_rank=4,
        lora_alpha=8.0,
        expect_initial_hf_load=False,
        fused_loss=False,
    )
    cfg.validator = Validator.Config(enable=False)
    cfg.checkpoint = CheckpointManager.Config(
        enable=True,
        interval=1_000_000,
        last_save_model_only=True,
        last_save_in_hf=True,
        export_dtype="float32",
    )
    return cfg
