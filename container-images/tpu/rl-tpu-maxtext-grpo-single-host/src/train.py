# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
from types import ModuleType

# Prevent PyTorch/vLLM from invoking NVIDIA Triton C++ GPU driver queries on Cloud TPU
if "triton._C" not in sys.modules:
    sys.modules["triton._C"] = ModuleType("triton._C")

# --- 1. SYSTEM & CACHING ---
os.environ.update(
    {
        "CUDA_VISIBLE_DEVICES": "-1",
        "TF_CPP_MIN_LOG_LEVEL": "3",
        "TF_ENABLE_ONEDNN_OPTS": "0",
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "VLLM_ENABLE_V1_MULTIPROCESSING": "1",
        "PYTHONUNBUFFERED": "1",
        "JAX_PLATFORMS": "tpu",
        "VLLM_TARGET_DEVICE": "tpu",
        "TRITON_DISABLE": "1",
        "TRITON_INTERPRET": "1",
    }
)

import torch
import torch._ops

# Generic fix for PyTorch 2.5+ overload removals breaking torchax/vLLM on TPU (GitHub Issue #3363)
_orig_op_getattr = torch._ops.OpOverloadPacket.__getattr__
def _safe_op_getattr(self, key):
    try:
        return _orig_op_getattr(self, key)
    except AttributeError:
        return getattr(self, "default", self)
torch._ops.OpOverloadPacket.__getattr__ = _safe_op_getattr

import vllm
import vllm.platforms

try:
    _cp = vllm.platforms.current_platform
    print("✅ Successfully initialized vllm.platforms.current_platform:", _cp, flush=True)
except Exception as e:
    print("⚠️ Exception during vllm.platforms.current_platform access:", e, flush=True)
    import traceback
    traceback.print_exc()

import datetime
import logging
import subprocess
import sys
sys.stdout.reconfigure(line_buffering=True)

# Patch subprocess.run so internal to_maxtext and vLLM calls inherit the triton._C stub & PyTorch op overload fixes
_orig_subprocess_run = subprocess.run
def _patched_subprocess_run(cmd, *args, **kwargs):
    if isinstance(cmd, list) and len(cmd) > 1 and "python" in cmd[0]:
        if len(cmd) > 2 and cmd[1] == "-m" and "to_maxtext" in cmd[2]:
            patch_code = (
                "import sys, os, types, traceback\n"
                "sys.modules['triton._C'] = types.ModuleType('triton._C')\n"
                "import torch\n"
                "_orig = torch._ops.OpOverloadPacket.__getattr__\n"
                "def _safe_op_getattr(self, key):\n"
                "    try:\n"
                "        return _orig(self, key)\n"
                "    except AttributeError:\n"
                "        return getattr(self, 'default', self)\n"
                "torch._ops.OpOverloadPacket.__getattr__ = _safe_op_getattr\n"
                "import maxtext\n"
                "base_yml = os.path.join(os.path.dirname(maxtext.__file__), 'configs', 'base.yml')\n"
                "from maxtext.checkpoint_conversion import to_maxtext\n"
                "raw_args = [a for a in sys.argv[1:] if not (a.startswith('--lazy_load_tensors') or a.startswith('--simulated_cpu_devices_count'))]\n"
                "if not any('base.yml' in a for a in raw_args):\n"
                "    raw_args = [base_yml] + raw_args\n"
                "print(f'🚀 Running to_maxtext with cleaned args: {raw_args}', flush=True)\n"
                "try:\n"
                "    to_maxtext.main(raw_args)\n"
                "except Exception as e:\n"
                "    print('💥 EXCEPTION IN SUBPROCESS TO_MAXTEXT:', flush=True)\n"
                "    print(traceback.format_exc(), flush=True)\n"
                "    sys.exit(1)\n"
            )
            cmd = [cmd[0], "-c", patch_code] + cmd[3:]
            print(f"🔧 Patched subprocess call to to_maxtext: {cmd}", flush=True)
        elif len(cmd) > 2 and cmd[1] == "-m":
            module_name = cmd[2]
            patch_code = (
                "import sys, types\n"
                "sys.modules['triton._C'] = types.ModuleType('triton._C')\n"
                "import torch\n"
                "_orig = torch._ops.OpOverloadPacket.__getattr__\n"
                "def _safe_op_getattr(self, key):\n"
                "    try:\n"
                "        return _orig(self, key)\n"
                "    except AttributeError:\n"
                "        return getattr(self, 'default', self)\n"
                "torch._ops.OpOverloadPacket.__getattr__ = _safe_op_getattr\n"
                "import runpy\n"
                f"runpy.run_module('{module_name}', run_name='__main__')\n"
            )
            cmd = [cmd[0], "-c", patch_code] + cmd[3:]
            print(f"🔧 Patched python -m subprocess call for {module_name}: {cmd}", flush=True)
    return _orig_subprocess_run(cmd, *args, **kwargs)
subprocess.run = _patched_subprocess_run

from huggingface_hub import login

from maxtext.utils.globals import MAXTEXT_PKG_DIR

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

MODEL_NAME = "llama3.1-8b-Instruct"
TOKENIZER_PATH = "meta-llama/Llama-3.1-8B-Instruct"

# Safely grab the native bucket path from Kubernetes, fallback to local if testing
YOUR_GCS_BUCKET = os.environ.get(
    "GCS_OUTPUT_PATH", f"{MAXTEXT_PKG_DIR}/fallback_output"
)

# Pull the base name from K8s, or use a timestamp
base_name = os.environ.get(
    "RUN_NAME", datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
)

# Unconditionally force "v5e" onto the front of it
RUN_NAME = f"v6e-{base_name}"

# Send the converted model and checkpoints directly to the cloud bucket
MODEL_CHECKPOINT_PATH = f"{YOUR_GCS_BUCKET}/llama_checkpoint_converted"

# MaxText uses `base_output_directory` as the root.
OUTPUT_DIRECTORY = MODEL_CHECKPOINT_PATH

CHAT_TEMPLATE_PATH = f"{MAXTEXT_PKG_DIR}/examples/chat_templates/gsm8k_rl.json"

# Leave empty so MaxText's automatic converter runs if checkpoint isn't converted yet
LOAD_PATH = ""

# --- 3. CONVERSION (Runs only if needed, before JAX TPU initialization) ---
# --- 3. CONVERSION ---
print("⏩ Bypassing local CPU conversion. Initializing MaxText GRPO Trainer directly on 8x TPU v6e chips...", flush=True)

# --- 4. IMPORT JAX & MAXTEXT TRAINER AFTER CONVERSION ---
os.environ["JAX_PLATFORMS"] = "tpu"
import clu.metric_writers
import jax
import jax.numpy as jnp
from maxtext.trainers.post_train.rl.train_rl import rl_train
from maxtext.utils.model_creation_utils import setup_configs_and_devices

# Mute the noisy vLLM TPU runner warnings
logging.getLogger("tpu_runner").setLevel(logging.ERROR)



original_write_texts = clu.metric_writers.MultiWriter.write_texts


def patched_write_texts(self, step: int, texts: dict):
    original_write_texts(self, step, texts)
    try:
        # Dynamically find the keys, handling prefixes like "eval/" or "train/"
        prompt_key = next((k for k in texts.keys() if "prompt" in k.lower()), None)
        comp_key = next((k for k in texts.keys() if "completion" in k.lower()), None)

        if prompt_key and comp_key:
            # Tag it visually so you know exactly which phase is printing
            phase = "🧪 EVALUATION" if "eval" in prompt_key.lower() else "🧠 TRAINING"
            print(f"\n" + "=" * 20 + f" {phase} STEP {step} SAMPLE " + "=" * 20)

            prompt = texts[prompt_key][0]
            completion = texts[comp_key][0]

            import numpy as np

            if isinstance(prompt, np.ndarray):
                prompt = prompt.item() if prompt.size == 1 else str(prompt)
            if isinstance(completion, np.ndarray):
                completion = (
                    completion.item() if completion.size == 1 else str(completion)
                )

            print(f"❓ [{prompt_key.upper()}]:\n{prompt}\n")
            print(f"🤖 [{comp_key.upper()}]:\n{completion}\n")
            print("=" * 70 + "\n", flush=True)
    except Exception:
        pass


clu.metric_writers.MultiWriter.write_texts = patched_write_texts

import jax.numpy as jnp

# --- 5. TRAINING CONFIGURATION ---
config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/rl.yml",
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    f"load_parameters_path=gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models/llama_checkpoint_converted/0/items",
    f"hf_access_token={HF_TOKEN}",
    f"chat_template_path={CHAT_TEMPLATE_PATH}",
    f"vllm_hf_config_path={TOKENIZER_PATH}",
    "rl.loss_algo=grpo",
    "use_pathways=False",
    "debug.rl=True",
    "rl.rollout_engine=vllm",
    "rollout_tensor_parallelism=8",
    "rollout_data_parallelism=1",
    "rl.reasoning_start_token='<reasoning>'",
    "rl.reasoning_end_token='</reasoning>'",
    "rl.solution_start_token='<answer>'",
    "rl.solution_end_token='</answer>'",
    # --- BATCHING & MEMORY FIXES ---
    "batch_size=2",  # Down from 4 to save memory
    "rl.num_generations=8",
    "max_target_length=1024",  # Restored to MaxText's default
    "hbm_utilization_vllm=0.37",  # The v5e "Goldilocks" zone we calculated
    "num_batches=150",  # Quick test run
    # --- CATASTROPHIC FORGETTING FIXES ---
    "learning_rate=5e-7",  # Much slower than the 3e-6 default
    "rl.grpo_beta=0.25",  # Stronger leash than the 0.08 default
    "rl.penalty_reward=-0.1",  # A gentle nudge instead of a harsh -0.5 punishment
    # --- FIXED RL PARAMS ---
    "rl.num_iterations=1",
    "gradient_clipping_threshold=1.0",
    "add_eos=True",
    "scan_layers=True",
    "log_period=10",
    "return_log_prob=True",
    "checkpoint_period=25",
    "save_checkpoint_on_completion=True",
    # --- EVALUATION ---
    "num_test_batches=25",
    "eval_interval=100",
    # --- ML DIAGNOSTICS CONFIGURATION ---
    "managed_mldiagnostics=True",  # Enable the managed ML Diagnostics platform
    "managed_mldiagnostics_run_group=GRPO_RL",  # (Optional) Group multiple runs under this category
    "profiler=xplane",  # Enable Google Cloud profiling traces
    "upload_all_profiler_results=True",  # Capture and upload multi-host profiles from all TPU hosts
]

# --- 6. EXECUTION ---
print("🔥 Training starting on MaxText GRPO Trainer...", flush=True)
try:
    rl_train(config_argv, {})
except Exception as e:
    import traceback
    print("❌ EXCEPTION IN RL_TRAIN:", flush=True)
    traceback.print_exc()
    sys.exit(1)

print("🏁 Training successfully completed.", flush=True)
