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

"""TorchTitan TPU Supervised Fine-Tuning (SFT) extension package.

Registers missing Gemma 4 model flavors (12B), LoRA adapter Hugging Face export
mappings, chat template prefix-safe label masking, and SplashAttention + Pallas
fused cross-entropy job configurations at import time without modifying
upstream TorchTitan source files.
"""

from torch.distributed.checkpoint._consolidate_hf_safetensors import (
    consolidate_safetensors_files_on_every_rank,
)
from torchtitan.components.checkpointer import dcp as dcp_module

# Work around google-pytorch/torchtitan dcp.py commenting out the
# consolidate_safetensors_files_on_every_rank import while calling it on
# multi-shard Hugging Face checkpoint exports.
if not hasattr(dcp_module, "consolidate_safetensors_files_on_every_rank"):
    dcp_module.consolidate_safetensors_files_on_every_rank = (  # type: ignore[attr-defined]
        consolidate_safetensors_files_on_every_rank
    )
