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

import datetime
import os

import jax
import MaxText
from huggingface_hub import login
from maxtext.trainers.post_train.rl.train_rl import rl_train, setup_configs_and_devices

# Environment variables for cleaner logging
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "0"
os.environ["SKIP_JAX_PRECOMPILE"] = "1"
os.environ["VLLM_LOGGING_LEVEL"] = "ERROR"

HF_TOKEN = os.environ.get("HF_TOKEN", "")
if HF_TOKEN:
    login(token=HF_TOKEN)

MAXTEXT_PKG_DIR = os.path.dirname(MaxText.__file__)
MAXTEXT_REPO_ROOT = os.sep.join(
    ["maxtext" if p == "MaxText" else p for p in MAXTEXT_PKG_DIR.split(os.sep)]
)

MODEL_NAME = "llama3.1-8b"
TOKENIZER_PATH = "meta-llama/Llama-3.1-8B-Instruct"
RUN_NAME = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
LOSS_ALGO = "grpo"

CHAT_TEMPLATE_PATH = f"{MAXTEXT_REPO_ROOT}/examples/chat_templates/gsm8k_rl.json"
MODEL_CHECKPOINT_PATH = "/workspace/llama_checkpoint"
OUTPUT_DIRECTORY = "/workspace/rl_llama3_output"

config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/rl.yml",
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"chat_template_path={CHAT_TEMPLATE_PATH}",
    f"load_parameters_path={MODEL_CHECKPOINT_PATH}/0/items",
    f"base_output_directory={OUTPUT_DIRECTORY}",
    f"hf_access_token={HF_TOKEN}",
    "debug.rl=False",
    f"rl.loss_algo={LOSS_ALGO}",
    "use_pathways=False",
]

trainer_config, sampler_config, trainer_devices, sampler_devices = (
    setup_configs_and_devices(config_argv)
)

print(f"🚀 Starting {LOSS_ALGO} Training...")
try:
    rl_train(trainer_config, sampler_config, trainer_devices, sampler_devices)
    print("✅ Training Completed Successfully!")
except Exception as e:
    print(f"❌ Training Failed: {str(e)}")
    raise
