# Copyright 2026 Google LLC
# MaxText v0.2.3 Single-Slice SFT Runner Script

import datetime
import logging
import os
import sys

sys.stdout.reconfigure(line_buffering=True)

# Environment configuration for Cloud TPU
os.environ.update(
    {
        "CUDA_VISIBLE_DEVICES": "-1",
        "TF_CPP_MIN_LOG_LEVEL": "3",
        "TF_ENABLE_ONEDNN_OPTS": "0",
        "PYTHONUNBUFFERED": "1",
        "JAX_PLATFORMS": "tpu",
        "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    }
)

import jax
from huggingface_hub import login
from maxtext.trainers.post_train.sft.train_sft import sft_train
from maxtext.utils.globals import MAXTEXT_PKG_DIR

logging.getLogger("tpu_runner").setLevel(logging.ERROR)

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1-8b-Instruct")
TOKENIZER_PATH = os.environ.get("HF_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
LOAD_PATH = os.environ.get(
    "LOAD_PARAMETERS_PATH",
    "gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models/llama3_1_8b_instruct_v023/0/items",
)
OUTPUT_DIRECTORY = os.environ.get(
    "BASE_OUTPUT_DIRECTORY", "gs://accelerated-platforms-dev-rl-kr-single-dataset"
)
RUN_NAME = os.environ.get(
    "RUN_NAME", f"llama3-8b-sft-run-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}"
)

# --- MAXTEXT SFT CONFIGURATION ---
config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/sft.yml",
    f"run_name={RUN_NAME}",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    f"model_name={MODEL_NAME}",
    f"load_parameters_path={LOAD_PATH}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"hf_access_token={HF_TOKEN}",
    "per_device_batch_size=1",
    "steps=1000",
    "hf_path=HuggingFaceH4/ultrachat_200k",
    "train_split=train_sft",
    "train_data_columns=['messages']",
    "skip_jax_distributed_system=True",
    "checkpoint_storage_use_zarr3=0",
    "checkpoint_storage_use_ocdbt=0",
    "managed_mldiagnostics=False",
    "upload_all_profiler_results=False",
]

if __name__ == "__main__":
    print(f"🔥 Single-Slice SFT Training starting on {len(jax.devices())} TPUs...", flush=True)
    sft_train(config_argv, {})
    print("🏁 Single-Slice SFT Training completed successfully.", flush=True)
