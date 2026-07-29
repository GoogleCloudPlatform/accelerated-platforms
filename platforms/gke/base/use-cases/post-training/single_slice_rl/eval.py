# Copyright 2026 Google LLC
# MaxText v0.2.3 RL Checkpoint Evaluation Script (GSM8K Math Benchmark)

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
from maxtext.trainers.post_train.rl.train_rl import rl_train
from maxtext.utils.globals import MAXTEXT_PKG_DIR

logging.getLogger("tpu_runner").setLevel(logging.ERROR)

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1-8b-Instruct")
TOKENIZER_PATH = os.environ.get("HF_MODEL_ID", "meta-llama/Llama-3.1-8B-Instruct")
LOAD_PATH = os.environ.get(
    "LOAD_PARAMETERS_PATH",
    "gs://accelerated-platforms-dev-rl-kr-single-dataset/llama3-1-8b-instruct-grpo-v6e-run7-resume50/checkpoints/actor/25/model_params",
)
OUTPUT_DIRECTORY = os.environ.get(
    "BASE_OUTPUT_DIRECTORY", "gs://accelerated-platforms-dev-rl-kr-single-dataset"
)
RUN_NAME = os.environ.get(
    "RUN_NAME", f"eval-rl-ckpt50-{datetime.datetime.now().strftime('%Y%m%d-%H%M')}"
)

CHAT_TEMPLATE_PATH = f"{MAXTEXT_PKG_DIR}/examples/chat_templates/gsm8k_rl.json"

# --- GSM8K EVALUATION CONFIGURATION ---
config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/rl.yml",
    f"run_name={RUN_NAME}",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    f"model_name={MODEL_NAME}",
    f"load_parameters_path={LOAD_PATH}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"vllm_hf_config_path={TOKENIZER_PATH}",
    f"chat_template_path={CHAT_TEMPLATE_PATH}",
    f"hf_access_token={HF_TOKEN}",
    "rl.loss_algo=grpo",
    "use_pathways=False",
    "debug.rl=False",
    "rl.rollout_engine=vllm",
    "rollout_tensor_parallelism=8",
    "rollout_data_parallelism=1",
    "rl.reasoning_start_token='<reasoning>'",
    "rl.reasoning_end_token='</reasoning>'",
    "rl.solution_start_token='<answer>'",
    "rl.solution_end_token='</answer>'",
    "batch_size=2",
    "rl.num_generations=8",
    "max_target_length=1024",
    "max_prefill_predict_length=256",
    "hbm_utilization_vllm=0.37",
    "num_batches=0",  # num_batches=0 runs pre-evaluation without training steps
    "reward_function_names=['gsm8k_accuracy']",
    "checkpoint_period=25",
    "num_test_batches=25",
    "eval_interval=100",
    "skip_jax_distributed_system=True",
    "checkpoint_storage_use_zarr3=0",
    "checkpoint_storage_use_ocdbt=0",
    "managed_mldiagnostics=False",
    "upload_all_profiler_results=False",
]

if __name__ == "__main__":
    print(f"🔥 Starting GSM8K Evaluation on {len(jax.devices())} TPUs...", flush=True)
    rl_train(config_argv, {})
    print("🏁 Evaluation completed successfully.", flush=True)
