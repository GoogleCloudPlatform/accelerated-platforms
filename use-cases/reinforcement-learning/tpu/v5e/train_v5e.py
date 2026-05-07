import os
import sys
import datetime
import subprocess
import jax
import jax.numpy as jnp
from huggingface_hub import login
import mlflow
from mlflow.tracking import MlflowClient
import clu.metric_writers
import logging
# Mute the noisy vLLM TPU runner warnings
logging.getLogger("tpu_runner").setLevel(logging.ERROR)

# --- 1. SYSTEM & CACHING ---
os.environ.update({
    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
    "PYTHONUNBUFFERED": "1",
    "JAX_PLATFORMS": "tpu" 
})

# --- 2. SETUP PATHS ---
from maxtext.trainers.post_train.rl.train_rl import rl_train, setup_configs_and_devices
from maxtext.utils.globals import MAXTEXT_PKG_DIR

HF_TOKEN = os.environ.get("HF_TOKEN")
login(token=HF_TOKEN)

MODEL_NAME = "llama3.1-8b"
TOKENIZER_PATH = "meta-llama/Llama-3.1-8B-Instruct"

# Safely grab the native bucket path from Kubernetes, fallback to local if testing
YOUR_GCS_BUCKET = os.environ.get("GCS_OUTPUT_PATH", f"{MAXTEXT_PKG_DIR}/fallback_output")

# Pull the base name from K8s, or use a timestamp
base_name = os.environ.get("RUN_NAME", datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"))

# Unconditionally force "v5e" onto the front of it
RUN_NAME = f"v5e-{base_name}"

# Send the massive converted model and checkpoints directly to the cloud bucket
MODEL_CHECKPOINT_PATH = f"{YOUR_GCS_BUCKET}/llama_checkpoint" 

# MaxText uses `base_output_directory` as the root. 
# It will automatically append `RUN_NAME/checkpoints/` to it.
OUTPUT_DIRECTORY = YOUR_GCS_BUCKET

CHAT_TEMPLATE_PATH = f"{MAXTEXT_PKG_DIR}/examples/chat_templates/gsm8k_rl.json"

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

    result = subprocess.run(conversion_cmd, shell=True, executable='/bin/bash')
    if result.returncode != 0:
        raise RuntimeError("Conversion failed!")
else:
    print(f"✅ Checkpoint already exists at {LOAD_PATH}. Skipping conversion!")

# --- 4. MLFLOW SETUP & LOGGING INTERCEPTOR ---
# Initialize MLflow strictly on the main thread
mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-service-v5e:5000"))
mlflow.set_experiment("MaxText-RL-GRPO-v5e")

print("🔌 Connecting to MLflow database...")
active_run = mlflow.start_run(run_name=f"Llama3.1-8B-GRPO-{RUN_NAME}")
MLFLOW_RUN_ID = active_run.info.run_id
mlflow_client = MlflowClient()

original_write_scalars = clu.metric_writers.MultiWriter.write_scalars
def patched_write_scalars(self, step: int, scalars: dict):
    original_write_scalars(self, step, scalars)
    mlflow_metrics = {k: float(v) for k, v in scalars.items() if isinstance(v, (jnp.ndarray, float, int))}
    try:
        # Pass the entire dictionary at once using the thread-safe client
        mlflow_client.log_metrics(MLFLOW_RUN_ID, mlflow_metrics, step=int(step))
    except Exception as e: 
        pass # Silently pass so we don't break the TPU training loop
clu.metric_writers.MultiWriter.write_scalars = patched_write_scalars

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
            print(f"\n" + "="*20 + f" {phase} STEP {step} SAMPLE " + "="*20)
            
            prompt = texts[prompt_key][0] 
            completion = texts[comp_key][0]
            
            import numpy as np
            if isinstance(prompt, np.ndarray):
                prompt = prompt.item() if prompt.size == 1 else str(prompt)
            if isinstance(completion, np.ndarray):
                completion = completion.item() if completion.size == 1 else str(completion)
                
            print(f"❓ [{prompt_key.upper()}]:\n{prompt}\n")
            print(f"🤖 [{comp_key.upper()}]:\n{completion}\n")
            print("="*70 + "\n", flush=True) 
    except Exception:
        pass
clu.metric_writers.MultiWriter.write_texts = patched_write_texts

# --- MONKEY PATCHES (For MaxText v0.2.1 / Tunix) ---
from maxtext.inference.vllm_decode import VllmRollout as MaxText_VllmRollout
import jax.numpy as jnp

try:
    from tunix.rl.rollout.vllm_rollout import VllmRollout as Tunix_VllmRollout
except ImportError:
    Tunix_VllmRollout = None

def apply_universal_patches(TargetClass):
    orig_logps = TargetClass.get_per_token_logps

    def patched_logps(self, *args, **kwargs):
        mask = kwargs.pop('completion_mask', None)
        results = orig_logps(self, *args, **kwargs)
        
        target_len = mask.shape[-1] if mask is not None else 1792 
        
        def pad_sequence(seq):
            seq_arr = jnp.array(seq)
            if seq_arr.size == 0: return jnp.zeros(target_len)
            pad_amount = target_len - seq_arr.shape[0]
            if pad_amount > 0: return jnp.pad(seq_arr, (0, pad_amount), constant_values=0.0)
            return seq_arr[:target_len]

        if isinstance(results, list):
            return jnp.stack([pad_sequence(s) for s in results])
        elif isinstance(results, dict):
            return {k: jnp.stack([pad_sequence(s) for s in v]) if isinstance(v, list) else v 
                    for k, v in results.items()}
        return results

    TargetClass.get_per_token_logps = patched_logps

apply_universal_patches(MaxText_VllmRollout)
if Tunix_VllmRollout:
    apply_universal_patches(Tunix_VllmRollout)
    
# --- 5. TRAINING CONFIGURATION ---
config_argv = [
    "",
    f"{MAXTEXT_PKG_DIR}/configs/post_train/rl.yml",
    f"model_name={MODEL_NAME}",
    f"tokenizer_path={TOKENIZER_PATH}",
    f"run_name={RUN_NAME}",
    f"load_parameters_path={LOAD_PATH}", 
    f"base_output_directory={OUTPUT_DIRECTORY}",
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
    "batch_size=2",                # Down from 4 to save memory
    "rl.num_generations=8", 
    "max_target_length=1024",      # Restored to MaxText's default
    "hbm_utilization_vllm=0.37",   # The v5e "Goldilocks" zone we calculated
    "num_batches=150",             # Quick test run
    
    # --- CATASTROPHIC FORGETTING FIXES ---
    "learning_rate=5e-7",          # Much slower than the 3e-6 default
    "rl.grpo_beta=0.25",           # Stronger leash than the 0.08 default
    "rl.penalty_reward=-0.1",      # A gentle nudge instead of a harsh -0.5 punishment
    
    # --- FIXED RL PARAMS ---
    "rl.num_iterations=1",                  
    "gradient_clipping_threshold=1.0",    
    
    "add_eos=True" ,
    "log_period=10",
    "return_log_prob=True",

    "checkpoint_period=25",
    "save_checkpoint_on_completion=True",
    
    # --- EVALUATION ---
    "num_test_batches=25", 
    "eval_interval=100", 
]

# --- 6. EXECUTION ---
trainer_config, sampler_config, trainer_devices, sampler_devices = setup_configs_and_devices(config_argv)

print(f"🔥 Training starting on {len(jax.devices())} TPUs...")
try:
    rl_train(trainer_config, sampler_config, trainer_devices, sampler_devices)
finally:
    # Ensure the MLflow run is safely closed even if an error occurs
    mlflow.end_run()

print("🏁 Training successfully completed.")
