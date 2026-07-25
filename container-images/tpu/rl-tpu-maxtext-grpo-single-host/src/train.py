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
import gc
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
        "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
        "VLLM_ENABLE_V1_MULTIPROCESSING": "0",
        "PYTHONUNBUFFERED": "1",
        "JAX_PLATFORMS": "tpu",
        "VLLM_TARGET_DEVICE": "tpu",
        "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    }
)

import jax
import numpy as np
from huggingface_hub import login
from maxtext.utils.globals import MAXTEXT_PKG_DIR

# Mute noisy vLLM logs
logging.getLogger("tpu_runner").setLevel(logging.ERROR)

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

MODEL_NAME = "llama3.1-8b-Instruct"
TOKENIZER_PATH = "meta-llama/Llama-3.1-8B-Instruct"

YOUR_GCS_BUCKET = os.environ.get(
    "GCS_OUTPUT_PATH", f"{MAXTEXT_PKG_DIR}/fallback_output"
)
base_name = os.environ.get(
    "RUN_NAME", datetime.datetime.now().strftime("%Y-%m-%d-%H-%M")
)
RUN_NAME = f"v6e-{base_name}"
MODEL_CHECKPOINT_PATH = f"{YOUR_GCS_BUCKET}/llama_checkpoint_converted"
OUTPUT_DIRECTORY = MODEL_CHECKPOINT_PATH
CHAT_TEMPLATE_PATH = f"{MAXTEXT_PKG_DIR}/examples/chat_templates/gsm8k_rl.json"


def setup_sample_interceptor():
    import clu.metric_writers

    original_write_texts = clu.metric_writers.MultiWriter.write_texts

    def patched_write_texts(self, step: int, texts: dict):
        original_write_texts(self, step, texts)
        try:
            gc.collect()
            prompt_key = next((k for k in texts.keys() if "prompt" in k.lower()), None)
            comp_key = next(
                (k for k in texts.keys() if "completion" in k.lower()), None
            )

            if prompt_key and comp_key:
                phase = (
                    "🧪 EVALUATION" if "eval" in prompt_key.lower() else "🧠 TRAINING"
                )
                print(f"\n" + "=" * 20 + f" {phase} STEP {step} SAMPLE " + "=" * 20)

                prompt = texts[prompt_key][0]
                completion = texts[comp_key][0]

                print(f"\n[PROMPT]\n{prompt}")
                print(f"\n[MODEL OUTPUT]\n{completion}")
                print("=" * 60 + "\n", flush=True)
        except Exception as e:
            print(f"Error printing sample: {e}", flush=True)

    clu.metric_writers.MultiWriter.write_texts = patched_write_texts


setup_sample_interceptor()

# --- TRAINING CONFIGURATION ---
config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/rl.yml",
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    "load_parameters_path=gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models/llama_checkpoint_converted/0/items",
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
    "batch_size=2",
    "rl.num_generations=8",
    "max_target_length=1024",
    "hbm_utilization_vllm=0.37",
    "num_batches=150",
    "learning_rate=5e-7",
    "rl.grpo_beta=0.25",
    "rl.penalty_reward=-0.1",
    "rl.num_iterations=1",
    "gradient_clipping_threshold=1.0",
    "add_eos=True",
    "scan_layers=True",
    "log_period=10",
    "return_log_prob=True",
    "checkpoint_period=25",
    "save_checkpoint_on_completion=True",
    "num_test_batches=0",
    "eval_interval=0",
    "managed_mldiagnostics=False",
    "upload_all_profiler_results=False",
]

# --- EXECUTION ---
print("🔥 Training starting on MaxText GRPO Trainer...", flush=True)
try:
    from maxtext.trainers.post_train.rl.train_rl import rl_train

    rl_train(config_argv, {})
except Exception as e:
    import traceback

    print("❌ EXCEPTION IN RL_TRAIN:", flush=True)
    traceback.print_exc()
    sys.exit(1)

print("🏁 Training successfully completed.", flush=True)
