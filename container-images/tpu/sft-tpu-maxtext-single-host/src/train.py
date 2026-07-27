# Copyright 2026 Google LLC
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

import datetime
import logging
import os
import runpy
import subprocess
import sys

import clu.metric_writers
import jax
import jax.numpy as jnp
import mlflow
from huggingface_hub import login
from mlflow.tracking import MlflowClient

# --- 1. SYSTEM & CACHING ---
os.environ.update(
    {
        "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "PYTHONUNBUFFERED": "1",
        "JAX_PLATFORMS": "tpu",
    }
)

# --- 2. SETUP PATHS ---
from maxtext.utils.globals import MAXTEXT_PKG_DIR

HF_TOKEN = os.environ.get("HF_TOKEN")
login(token=HF_TOKEN)

MODEL_NAME = "llama3.1-8b"
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
RUN_NAME = f"v5e-{base_name}"

# Send the massive converted model and checkpoints directly to the cloud bucket
MODEL_CHECKPOINT_PATH = f"{YOUR_GCS_BUCKET}/llama_checkpoint"

# MaxText uses `base_output_directory` as the root.
# It will automatically append `RUN_NAME/checkpoints/` to it.
OUTPUT_DIRECTORY = YOUR_GCS_BUCKET

# POINT EXACTLY TO /0/items AS PER THE DEMO NOTEBOOK
LOAD_PATH = f"{MODEL_CHECKPOINT_PATH}/0/items"

# --- 3. CONVERSION (Runs only if needed) ---
if not os.path.exists(LOAD_PATH):
    print("🚀 Starting local conversion...")

    # Use subprocess for the conversion
    conversion_cmd = (
        f"JAX_PLATFORMS=cpu python3 -m maxtext.checkpoint_conversion.to_maxtext "
        f"{MAXTEXT_PKG_DIR}/configs/base.yml "
        f"model_name={MODEL_NAME} "
        f"base_output_directory={MODEL_CHECKPOINT_PATH} "
        f"hf_access_token={HF_TOKEN} "
        f"use_multimodal=false scan_layers=true skip_jax_distributed_system=True"
    )

    result = subprocess.run(conversion_cmd, shell=True, executable="/bin/bash")
    if result.returncode != 0:
        raise RuntimeError("Conversion failed!")
else:
    print(f"✅ Checkpoint already exists at {LOAD_PATH}. Skipping conversion!")

# --- 4. MLFLOW SETUP & LOGGING INTERCEPTOR ---
# Initialize MLflow strictly on the main thread
mlflow.set_tracking_uri(
    os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-service-v5e:5000")
)
mlflow.set_experiment("sft-tpu-maxtext-single-host")

print("🔌 Connecting to MLflow database...")
active_run = mlflow.start_run(run_name=f"Llama3.1-8B-SFT-{RUN_NAME}")
MLFLOW_RUN_ID = active_run.info.run_id
mlflow_client = MlflowClient()

original_write_scalars = clu.metric_writers.MultiWriter.write_scalars


def patched_write_scalars(self, step: int, scalars: dict):
    original_write_scalars(self, step, scalars)
    mlflow_metrics = {
        k: float(v)
        for k, v in scalars.items()
        if isinstance(v, (jnp.ndarray, float, int))
    }
    try:
        # Pass the entire dictionary at once using the thread-safe client
        mlflow_client.log_metrics(MLFLOW_RUN_ID, mlflow_metrics, step=int(step))
    except Exception as e:
        pass  # Silently pass so we don't break the TPU training loop


clu.metric_writers.MultiWriter.write_scalars = patched_write_scalars

original_write_texts = clu.metric_writers.MultiWriter.write_texts


def patched_write_texts(self, step: int, texts: dict):
    original_write_texts(self, step, texts)
    try:
        # Dynamically find keys like instruction or completion
        prompt_key = next(
            (
                k
                for k in texts.keys()
                if "prompt" in k.lower()
                or "input" in k.lower()
                or "instruction" in k.lower()
            ),
            None,
        )
        comp_key = next(
            (
                k
                for k in texts.keys()
                if "completion" in k.lower() or "output" in k.lower()
            ),
            None,
        )

        if prompt_key and comp_key:
            phase = "🧠 TRAINING"
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

# --- 5. SFT CONFIGURATION & RUN ---
config_argv = [
    sys.argv[0],  # module name placeholder
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"load_parameters_path={LOAD_PATH}",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    f"hf_access_token={HF_TOKEN}",
    "use_pathways=False",
    "per_device_batch_size=2",
    "steps=150",
    "hf_path=tatsu-lab/alpaca",
    "train_split=train",
    "train_data_columns=[instruction,input,output]",
    "learning_rate=5e-7",
    "max_target_length=1024",
    "checkpoint_period=25",
    "save_checkpoint_on_completion=True",
]

# Override system argv so the imported trainer parses these configuration flags
sys.argv = config_argv

print(f"🔥 Training starting on {len(jax.devices())} TPUs...")
try:
    # Run the maxtext.trainers.post_train.sft.train_sft module using runpy
    runpy.run_module("maxtext.trainers.post_train.sft.train_sft", run_name="__main__")
finally:
    # Ensure the MLflow run is safely closed even if an error occurs
    mlflow.end_run()

print("🏁 Training successfully completed.")
