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

# --- SYSTEM SHIELDS (Must be at the very top!) ---
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"


import datetime
import subprocess
import sys

import jax
import jax.numpy as jnp
import mlflow
from huggingface_hub import login

# --- Replace the old tunix import with this ---
from maxtext.inference.vllm_decode import VllmRollout

# 1. Save the original method
original_get_logps = VllmRollout.get_per_token_logps


def patched_get_per_token_logps(self, *args, **kwargs):
    # Fix A: Intercept the mask to use as a blueprint
    completion_mask = kwargs.pop("completion_mask", None)

    # Call the actual vLLM execution
    results = original_get_logps(self, *args, **kwargs)

    # Extract target length (defaults to 768 if mask is missing)
    target_len = completion_mask.shape[-1] if completion_mask is not None else 768

    def pad_sequence(seq):
        seq_arr = jnp.array(seq)

        # If vLLM returned an empty array, return a zeroed array of correct shape
        if seq_arr.size == 0:
            return jnp.zeros(target_len)

        # Pad with zeros if too short, or truncate if too long
        pad_amount = target_len - seq_arr.shape[0]
        if pad_amount > 0:
            return jnp.pad(seq_arr, (0, pad_amount), constant_values=0.0)
        elif pad_amount < 0:
            return seq_arr[:target_len]
        return seq_arr

    # Fix B: Process ragged lists and perfectly pad them into a rigid JAX block
    if isinstance(results, list):
        padded_results = [pad_sequence(seq) for seq in results]
        return jnp.stack(padded_results)

    elif isinstance(results, dict):
        return {
            k: jnp.stack([pad_sequence(seq) for seq in v]) if isinstance(v, list) else v
            for k, v in results.items()
        }

    return results


# 2. Apply the patch
VllmRollout.get_per_token_logps = patched_get_per_token_logps

print(
    "🔧 Applied Monkey Patch v3: Intercepted kwargs and perfectly padded ragged JAX arrays."
)

try:
    import vllm

    print(f"✅ vLLM Version: {vllm.__version__}")
    print(f"✅ JAX TPU Devices: {len(jax.devices())}")
except ImportError as e:
    print(f"🚨 FATAL: vLLM is not installed correctly: {e}")

# --- CORE IMPORTS ---
import maxtext
import maxtext.checkpoint_conversion.to_maxtext as to_maxtext_module
from etils import epath
from maxtext.trainers.post_train.rl.train_rl import rl_train, setup_configs_and_devices

HF_TOKEN = os.environ.get("HF_TOKEN")
if not HF_TOKEN:
    raise ValueError("HF_TOKEN environment variable not set.")
login(token=HF_TOKEN)
# Delete this line:
# MAXTEXT_PKG_DIR = os.path.dirname(maxtext.__file__)

# Replace it with the hardcoded absolute path where we cloned the repo:
MAXTEXT_PKG_DIR = "/workspace/maxtext/src/maxtext"

MODEL_NAME = "llama3.1-8b"
TOKENIZER_PATH = "meta-llama/Llama-3.1-8B-Instruct"
RUN_NAME = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
LOSS_ALGO = "grpo"

# Paths are localized to the workspace
CHAT_TEMPLATE_PATH = "/workspace/gsm8k_rl.json"
MODEL_CHECKPOINT_PATH = "/workspace/llama_checkpoint"
OUTPUT_DIRECTORY = "/workspace/rl_llama3_output"

mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
mlflow.set_experiment("MaxText-RL-GRPO")

# --- CHECKPOINT CONVERSION (With FP32 casting patch) ---
target_checkpoint_items = f"{MODEL_CHECKPOINT_PATH}/0/items"

if not epath.Path(target_checkpoint_items).exists():
    print(f"Downloading and converting Llama 3.1 to MaxText format...")
    to_maxtext_path = to_maxtext_module.__file__

    with open(to_maxtext_path, "r") as f:
        script_content = f.read()

    if "v.numpy()" in script_content:
        script_content = script_content.replace("v.numpy()", "v.float().numpy()")

    with open(to_maxtext_path, "w") as f:
        f.write(script_content)

    conversion_command = (
        f"JAX_PLATFORMS=cpu python3 -m maxtext.checkpoint_conversion.to_maxtext "
        f"{MAXTEXT_PKG_DIR}/configs/base.yml "
        f"model_name={MODEL_NAME} "
        f"base_output_directory={MODEL_CHECKPOINT_PATH} "
        f"hf_access_token={HF_TOKEN} "
        f"use_multimodal=false scan_layers=true skip_jax_distributed_system=True"
    )

    result = subprocess.run(conversion_command, shell=True, executable="/bin/bash")
    if result.returncode != 0:
        raise RuntimeError("Checkpoint conversion failed! Check the logs above.")
else:
    print(f"✅ Found existing checkpoint at {target_checkpoint_items}")

# --- MAXTEXT RL CONFIGURATION ---
config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/rl.yml",
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"chat_template_path={CHAT_TEMPLATE_PATH}",
    f"load_parameters_path={MODEL_CHECKPOINT_PATH}/0/items",
    # f"base_output_directory={OUTPUT_DIRECTORY}",
    # --- DIRECT TO GCS ROUTING ---
    f"base_output_directory=gs://accelerated-platforms-dev-trn-rl-gpu-hf-hub-models/my-grpo-checkpoints/rl_llama3_output/{RUN_NAME}",
    f"hf_access_token={HF_TOKEN}",
    "debug.rl=False",
    f"rl.loss_algo={LOSS_ALGO}",
    "rl.rollout_engine=vllm",
    "use_pathways=False",
    "rollout_expert_parallelism=1",
    # --- THE MESH & MEMORY FIX ---
    # 1. We keep vLLM sliced across all 8 chips
    "rollout_tensor_parallelism=8",
    # 2. DELETE the ici_tensor_parallelism line! We let MaxText default to FSDP.
    # 3. Restrict vLLM to 40% memory so MaxText has room to train
    "hbm_utilization_vllm=0.4",
    # 4. Give vLLM the blueprint it needs to build its mesh scaffolding
    f"vllm_hf_config_path={TOKENIZER_PATH}",
    # --- SCALING UP FOR GRPO ---
    # "per_device_batch_size=4",  # Increased from 1 to test micro-batching
    # "rl.num_generations=4",     # Crucial for GRPO: Generates 4 reasoning chains per prompt
    # --- THE SCALE UP (Real Training Run) ---
    "per_device_batch_size=2",  # Doubling the throughput (pushes your 60% HBM limit)
    "num_batches=200",  # Process 200 batches instead of the tiny default
    "rl.num_generations=8",  # GRPO magic: vLLM generates 8 different answers per prompt to compare
    "rl.num_iterations=2",  # Train the actor model for 2 iterations on those 8 answers
    "learning_rate=1e-6",  # A standard, safe learning rate for RL fine-tuning
    "save_checkpoint_on_completion=True",  # Ensure the final weights are saved!
    "return_log_prob=True",  # <-- The crucial GRPO math flag!
    # --- THE MLFLOW FIX ---
    "log_period=10",  # Force TensorBoard to write metrics to disk every 10 steps
    "checkpoint_period=50",
    "profiler=True",
    "profiler_steps=100,110",  # Takes a massive hardware snapshot between step 100 and 110
]

trainer_config, sampler_config, trainer_devices, sampler_devices = (
    setup_configs_and_devices(config_argv)
)

# --- EXECUTE TRAINING ---
with mlflow.start_run(run_name=f"Llama3.1-8B-{LOSS_ALGO}"):
    mlflow.log_params(
        {
            "model_name": MODEL_NAME,
            "loss_algo": LOSS_ALGO,
            "tpu_devices": len(jax.devices()),
            "rollout_engine": "vllm",
        }
    )

    print(f"🚀 Starting {LOSS_ALGO} Training on {len(jax.devices())} TPUs...")
    rl_train(trainer_config, sampler_config, trainer_devices, sampler_devices)

    mlflow.log_artifacts(
        trainer_config.tensorboard_dir, artifact_path="tensorboard_logs"
    )
    print("✅ Training Completed and Logged to MLflow!")
    mlflow.log_artifacts(
        trainer_config.tensorboard_dir, artifact_path="tensorboard_logs"
    )
    print("✅ Training Completed and Logged to MLflow!")
