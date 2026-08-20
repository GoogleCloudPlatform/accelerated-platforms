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
    }
)

# Do not overwrite JAX_PLATFORMS if already set (e.g. to "proxy" in Pathways mode)
if "JAX_PLATFORMS" not in os.environ:
    os.environ["JAX_PLATFORMS"] = "tpu"

# --- 2. SETUP PATHS ---
from maxtext.utils.globals import MAXTEXT_PKG_DIR

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

MODEL_NAME = os.environ.get("MODEL_NAME", "gemma3-4b")
TOKENIZER_PATH = os.environ.get("TOKENIZER_PATH", "google/gemma-3-4b-it")

# Safely grab the native bucket path from Kubernetes, fallback to local if testing
YOUR_GCS_BUCKET = os.environ.get(
    "GCS_OUTPUT_PATH", f"{MAXTEXT_PKG_DIR}/fallback_output"
)

# Pull the base name from K8s, or use a timestamp
base_name = os.environ.get(
    "RUN_NAME", datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
)

RUN_NAME = f"sft-{base_name}"

# Send the massive converted model and checkpoints directly to the cloud bucket
MODEL_CHECKPOINT_PATH = f"{YOUR_GCS_BUCKET}/{MODEL_NAME}_checkpoint"

# MaxText uses `base_output_directory` as the root.
# It will automatically append `RUN_NAME/checkpoints/` to it.
OUTPUT_DIRECTORY = YOUR_GCS_BUCKET

# POINT EXACTLY TO /0/items AS PER THE DEMO NOTEBOOK
LOAD_PATH = f"{MODEL_CHECKPOINT_PATH}/0/items"

SCAN_LAYERS = os.environ.get("SCAN_LAYERS", "true")
USE_MULTIMODAL = os.environ.get(
    "USE_MULTIMODAL", "true" if "gemma" in MODEL_NAME.lower() else "false"
)


def path_exists(path: str) -> bool:
    if path.startswith("gs://"):
        parts = path[5:].split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        try:
            from google.cloud import storage

            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blobs = list(bucket.list_blobs(prefix=prefix, max_results=1))
            return len(blobs) > 0
        except Exception as e:
            print(f"Warning checking GCS path {path}: {e}")
            return False
    return os.path.exists(path)


# --- 3. CONVERSION (Runs only if needed) ---
if not path_exists(LOAD_PATH):
    print("Starting local conversion...")

    # Use subprocess for the conversion
    conversion_cmd = (
        f"JAX_PLATFORMS=cpu python3 -m maxtext.checkpoint_conversion.to_maxtext "
        f"{MAXTEXT_PKG_DIR}/configs/base.yml "
        f"model_name={MODEL_NAME} "
        f"base_output_directory={MODEL_CHECKPOINT_PATH} "
        f"hf_access_token={HF_TOKEN} "
        f"use_multimodal={USE_MULTIMODAL} scan_layers={SCAN_LAYERS} skip_jax_distributed_system=True"
    )

    result = subprocess.run(conversion_cmd, shell=True, executable="/bin/bash")
    if result.returncode != 0:
        raise RuntimeError("Conversion failed!")
else:
    print(f"Checkpoint already exists at {LOAD_PATH}. Skipping conversion.")

# --- 4. MLFLOW SETUP & LOGGING INTERCEPTOR ---
# Initialize MLflow strictly on the main thread
mlflow.set_tracking_uri(
    os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-service:5000")
)
mlflow.set_experiment("sft-tpu-maxtext-multi-host")

print("Connecting to MLflow database...")
active_run = mlflow.start_run(run_name=f"{MODEL_NAME}-SFT-{RUN_NAME}")
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
            phase = "TRAINING"
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

            print(f"[{prompt_key.upper()}]:\n{prompt}\n")
            print(f"[{comp_key.upper()}]:\n{completion}\n")
            print("=" * 70 + "\n", flush=True)
    except Exception:
        pass


clu.metric_writers.MultiWriter.write_texts = patched_write_texts

# --- 5. SFT CONFIGURATION & RUN ---
DATASET_NAME = os.environ.get("DATASET_NAME", "HuggingFaceH4/ultrachat_200k")
TRAIN_SPLIT = os.environ.get("TRAIN_SPLIT", "train_sft")
TRAIN_DATA_COLUMNS = os.environ.get("TRAIN_DATA_COLUMNS", "['messages']")
STEPS = os.environ.get("STEPS", "1000")
PER_DEVICE_BATCH_SIZE = os.environ.get("PER_DEVICE_BATCH_SIZE", "1")
LEARNING_RATE = os.environ.get("LEARNING_RATE", "5e-7")

config_argv = [
    sys.argv[0],  # module name placeholder
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"load_parameters_path={LOAD_PATH}",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    f"hf_access_token={HF_TOKEN}",
    "use_pathways=True",
    "checkpoint_storage_use_zarr3=False",
    "checkpoint_storage_use_ocdbt=False",
    "enable_single_controller=True",
    f"per_device_batch_size={PER_DEVICE_BATCH_SIZE}",
    f"steps={STEPS}",
    f"hf_path={DATASET_NAME}",
    f"train_split={TRAIN_SPLIT}",
    f"train_data_columns={TRAIN_DATA_COLUMNS}",
    f"learning_rate={LEARNING_RATE}",
    "max_target_length=1024",
    "checkpoint_period=100",
    "save_checkpoint_on_completion=True",
]

# Override system argv so the imported trainer parses these configuration flags
sys.argv = config_argv

print(f"Training starting in Multi-Host Pathways mode...")
try:
    # Run the maxtext.trainers.post_train.sft.train_sft module using runpy
    runpy.run_module("maxtext.trainers.post_train.sft.train_sft", run_name="__main__")
finally:
    # Ensure the MLflow run is safely closed even if an error occurs
    mlflow.end_run()

print("Training successfully completed.")
