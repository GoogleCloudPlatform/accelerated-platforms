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

"""Gemma 4 12B flavor registration for TorchTitan's native TPU Gemma 4 model.

Upstream ``torchtitan.experiments.tpu.examples.gemma4`` ships factory entries
for ``31B`` and ``26B-A4B``. ``google/gemma-4-12B-it`` shares the same text
decoder layout with 12B dimensions from its Hugging Face ``config.json``
(``text_config``):

  hidden_size=3840, intermediate_size=15360, num_hidden_layers=48,
  num_attention_heads=16, num_key_value_heads=8, head_dim=256,
  num_global_key_value_heads=1, global_head_dim=512, sliding_window=1024,
  global_attn_every_n_layers=6 (K=V full attention), vocab_size=262144.
"""

from functools import partial

from torchtitan.experiments.tpu.examples import gemma4 as g4

FLAVOR_12B = "12B"
FLAVOR_12B_TINY = "12B-tiny"


def _register_flavor(
    name: str,
    *,
    vocab_size: int,
    dim: int,
    hidden_dim: int,
    n_layers: int,
    n_heads: int,
    n_kv_heads: int,
    n_global_kv_heads: int,
    head_dim: int,
    global_head_dim: int,
    max_seq_len: int,
    sliding_window_size: int,
    global_attn_every_n_layers: int = 6,
) -> None:
    g4._gemma4_factories[name] = partial(
        g4.Gemma4Model.Config,
        vocab_size=vocab_size,
        dim=dim,
        sliding_window_size=sliding_window_size,
        tok_embeddings=g4.Gemma4Embedding.Config(
            num_embeddings=vocab_size,
            embedding_dim=dim,
        ),
        norm=g4._gemma4_norm(dim, eps=1e-6),
        lm_head=g4._gemma4_lm_head(dim, vocab_size),
        layers=partial(
            g4._build_gemma4_layers,
            n_layers=n_layers,
            dim=dim,
            hidden_dim=hidden_dim,
            n_heads=n_heads,
            n_kv_heads=n_kv_heads,
            n_global_kv_heads=n_global_kv_heads,
            head_dim=head_dim,
            global_head_dim=global_head_dim,
            norm_eps=1e-6,
            max_seq_len=max_seq_len,
            sliding_window_size=sliding_window_size,
            global_attn_every_n_layers=global_attn_every_n_layers,
        ),
    )


def register_flavors() -> None:
    """Registers the Gemma 4 12B and 12B-tiny flavors (idempotent)."""
    _register_flavor(
        FLAVOR_12B,
        vocab_size=262144,
        dim=3840,
        hidden_dim=15360,
        n_layers=48,
        n_heads=16,
        n_kv_heads=8,
        n_global_kv_heads=1,
        head_dim=256,
        global_head_dim=512,
        # Bounds per-layer RoPE buffer allocation on each TPU chip while
        # covering 8192-token packed SFT sequences.
        max_seq_len=8192,
        sliding_window_size=1024,
    )
    _register_flavor(
        FLAVOR_12B_TINY,
        vocab_size=2048,
        dim=256,
        hidden_dim=1024,
        n_layers=6,
        n_heads=16,
        n_kv_heads=8,
        n_global_kv_heads=1,
        head_dim=16,
        global_head_dim=32,
        max_seq_len=4096,
        sliding_window_size=64,
    )


register_flavors()
