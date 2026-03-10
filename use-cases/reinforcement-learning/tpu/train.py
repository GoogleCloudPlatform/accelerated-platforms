import os
# --- SYSTEM SHIELDS (Must be at the very top!) ---
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
os.environ["VLLM_WORKER_MULTIPROC_METHOD"] = "spawn"

import sys
import datetime
import subprocess
import mlflow
import jax
from huggingface_hub import login

            
try:
    import vllm
    print(f"✅ vLLM Version: {vllm.__version__}")
    print(f"✅ JAX TPU Devices: {len(jax.devices())}")
except ImportError as e:
    print(f"🚨 FATAL: vLLM is not installed correctly: {e}")

# --- CORE IMPORTS ---
import maxtext
from maxtext.trainers.post_train.rl.train_rl import rl_train, setup_configs_and_devices
import maxtext.checkpoint_conversion.to_maxtext as to_maxtext_module
from etils import epath

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
    
    result = subprocess.run(conversion_command, shell=True, executable='/bin/bash')
    if result.returncode != 0:
        raise RuntimeError("Checkpoint conversion failed! Check the logs above.")
else:
    print(f"✅ Found existing Orbax checkpoint at {target_checkpoint_items}")

# --- MAXTEXT RL CONFIGURATION ---
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

    "per_device_batch_size=1"

]

trainer_config, sampler_config, trainer_devices, sampler_devices = setup_configs_and_devices(config_argv)

# --- EXECUTE TRAINING ---
with mlflow.start_run(run_name=f"Llama3.1-8B-{LOSS_ALGO}"):
    mlflow.log_params({
        "model_name": MODEL_NAME,
        "loss_algo": LOSS_ALGO,
        "tpu_devices": len(jax.devices()),
        "rollout_engine": "vllm"
    })
    
    print(f"🚀 Starting {LOSS_ALGO} Training on {len(jax.devices())} TPUs...")
    rl_train(trainer_config, sampler_config, trainer_devices, sampler_devices)
    
    mlflow.log_artifacts(trainer_config.tensorboard_dir, artifact_path="tensorboard_logs")
    print("✅ Training Completed and Logged to MLflow!")
    