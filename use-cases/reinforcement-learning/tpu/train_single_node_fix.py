import os
import sys
import datetime
import subprocess
import jax
import jax.numpy as jnp
from huggingface_hub import login
from etils import epath
import mlflow
import clu.metric_writers
from google.cloud import storage

# --- 1. SYSTEM & CACHING ---
os.environ.update({
    "PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python",
    "VLLM_WORKER_MULTIPROC_METHOD": "spawn",
    "PYTHONUNBUFFERED": "1",
    "JAX_PLATFORMS": "tpu" 
})

# --- 2. SETUP PATHS ---
from maxtext.trainers.post_train.rl.train_rl import rl_train, setup_configs_and_devices
import maxtext.checkpoint_conversion.to_maxtext as to_maxtext_module
from maxtext.utils.globals import MAXTEXT_PKG_DIR

HF_TOKEN = os.environ.get("HF_TOKEN")
login(token=HF_TOKEN)

MODEL_NAME = "llama3.1-8b"
TOKENIZER_PATH = "meta-llama/Llama-3.1-8B-Instruct"

# Safely grab the native bucket path from Kubernetes, fallback to local if testing
YOUR_GCS_BUCKET = os.environ.get("GCS_OUTPUT_PATH", f"{MAXTEXT_PKG_DIR}/fallback_output")

# Pull the run name from K8s. If running locally, fall back to a timestamp.
RUN_NAME = os.environ.get("RUN_NAME", datetime.datetime.now().strftime("%Y-%m-%d-%H-%M"))

# Send the massive converted model and checkpoints directly to the cloud bucket
MODEL_CHECKPOINT_PATH = f"{YOUR_GCS_BUCKET}/llama_checkpoint" 

# MaxText uses `base_output_directory` as the root. 
# It will automatically append `RUN_NAME/checkpoints/` to it.
OUTPUT_DIRECTORY = YOUR_GCS_BUCKET
CHAT_TEMPLATE_PATH = "/deps/llama3_rl.json"

# TODO: Check if this is still needed when upgrading MaxText/Tunix past v0.2.1!
# JAX pads prompts to static lengths, but vLLM halts if it sees padding/EOT tokens.
# This strips those tokens before generation. Remove once MaxText handles this natively.
from transformers import AutoTokenizer

# Add this near where you defined TOKENIZER_PATH
hf_tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_PATH, token=HF_TOKEN)

# Automatically gather the model's specific padding and End-of-Sequence tokens
UNIVERSAL_PAD_TOKENS = set()
if hf_tokenizer.pad_token_id is not None:
    UNIVERSAL_PAD_TOKENS.add(hf_tokenizer.pad_token_id)
if hf_tokenizer.eos_token_id is not None:
    # eos_token_id can sometimes be a list in newer models like Llama 3
    if isinstance(hf_tokenizer.eos_token_id, list):
        UNIVERSAL_PAD_TOKENS.update(hf_tokenizer.eos_token_id)
    else:
        UNIVERSAL_PAD_TOKENS.add(hf_tokenizer.eos_token_id)

# Add standard 0 just in case JAX is using it as a hardcoded 0-pad mask
UNIVERSAL_PAD_TOKENS.add(0)

# --- 3. CONVERSION (Runs every time for consistency) ---
print("🚀 Starting local conversion...")

# Patch to_maxtext.py for float32 precision
to_maxtext_path = to_maxtext_module.__file__
with open(to_maxtext_path, "r") as f:
    content = f.read()
if "v.numpy()" in content:
    with open(to_maxtext_path, "w") as f:
        f.write(content.replace("v.numpy()", "v.float().numpy()"))

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

# --- MONKEY PATCHES (For MaxText v0.2.1 / Tunix) ---
# TODO: Check if this is still needed when upgrading MaxText/Tunix past v0.2.1!
# JAX pads prompts to static lengths, but vLLM halts if it sees padding/EOT tokens.
# This strips those tokens before generation. Remove once MaxText handles this natively.

from maxtext.inference.vllm_decode import VllmRollout as MaxText_VllmRollout
import jax.numpy as jnp # Ensure this is imported for the patch
try:
    from tunix.rl.rollout.vllm_rollout import VllmRollout as Tunix_VllmRollout
except ImportError:
    Tunix_VllmRollout = None

def apply_universal_patches(TargetClass):
    orig_logps = TargetClass.get_per_token_logps
    orig_gen = TargetClass.generate

    def patched_logps(self, *args, **kwargs):
        mask = kwargs.pop('completion_mask', None)
        results = orig_logps(self, *args, **kwargs)
        
        # FIX: Changed fallback from 1024 to 1792. 
        # This matches the Trainer's expected shape: 2048 (max_target) - 256 (prefill) = 1792
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

    def patched_gen(self, *args, **kwargs):
        # Use the dynamically loaded tokens instead of LLaMA magic numbers
        if kwargs.get('prompt_token_ids'):
            kwargs['prompt_token_ids'] = [
                [t for t in p if t not in UNIVERSAL_PAD_TOKENS] 
                for p in kwargs['prompt_token_ids']
            ]
        return orig_gen(self, *args, **kwargs)

    TargetClass.get_per_token_logps = patched_logps
    TargetClass.generate = patched_gen

apply_universal_patches(MaxText_VllmRollout)
if Tunix_VllmRollout:
    apply_universal_patches(Tunix_VllmRollout)

# --- 3. FLAX NNX STATIC ATTRIBUTE PATCH ---
import maxtext.models.models as max_models
orig_transformer_init = max_models.Transformer.__init__
def patched_transformer_init(self, *args, **kwargs):
    orig_transformer_init(self, *args, **kwargs)
    if hasattr(self, 'decoder'):
        object.__setattr__(self, 'decoder', self.decoder)
max_models.Transformer.__init__ = patched_transformer_init

# --- 4. MLFLOW LOGGING INTERCEPTOR ---
original_write_scalars = clu.metric_writers.MultiWriter.write_scalars
def patched_write_scalars(self, step: int, scalars: dict):
    original_write_scalars(self, step, scalars)
    mlflow_metrics = {k: float(v) for k, v in scalars.items() if isinstance(v, (jnp.ndarray, float, int))}
    try:
        mlflow.log_metrics(mlflow_metrics, step=int(step))
    except Exception: pass
clu.metric_writers.MultiWriter.write_scalars = patched_write_scalars

original_write_texts = clu.metric_writers.MultiWriter.write_texts
def patched_write_texts(self, step: int, texts: dict):
    original_write_texts(self, step, texts)
    try:
        # MaxText passes the text arrays here. Let's intercept and print them!
        if "prompts" in texts and "completions" in texts:
            print(f"\n" + "="*20 + f" 🧠 STEP {step} GENERATION SAMPLE " + "="*20)
            
            # Grab just the very first example from the batch so we don't spam the console
            prompt = texts["prompts"][0] 
            completion = texts["completions"][0]
            
            # Clean up numpy string formatting
            import numpy as np
            if isinstance(prompt, np.ndarray):
                prompt = prompt.item() if prompt.size == 1 else str(prompt)
            if isinstance(completion, np.ndarray):
                completion = completion.item() if completion.size == 1 else str(completion)
                
            print(f"❓ [PROMPT]:\n{prompt}\n")
            print(f"🤖 [COMPLETION]:\n{completion}\n")
            print("="*70 + "\n", flush=True) # flush=True forces it to print immediately
    except Exception as e:
        pass
clu.metric_writers.MultiWriter.write_texts = patched_write_texts

# --- 4. TRAINING CONFIGURATION ---
# POINT EXACTLY TO /0/items AS PER THE DEMO NOTEBOOK
LOAD_PATH = f"{MODEL_CHECKPOINT_PATH}/0/items"

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
    "hbm_utilization_vllm=0.4",     
    
    "rl.reasoning_start_token='<reasoning>'",
    "rl.reasoning_end_token='</reasoning>'",
    "rl.solution_start_token='<answer>'",
    "rl.solution_end_token='</answer>'",

    # --- FIXED BATCHING ---
    "batch_size=1", # Explicitly override the YAML's batch_size=1
    "num_batches=50", # Short 100-batch test run
    
    # --- FIXED RL PARAMS (To prevent model explosion) ---
    "rl.num_generations=8",
    "rl.num_iterations=2",
    "learning_rate=5e-7",                 # Keep it low
    "gradient_clipping_threshold=1.0",    # MaxText's native clipping flag
    "rl.penalty_reward=-0.5",             # Soften the penalty for formatting errors
    "rl.grpo_beta=0.15",  # Added to strictly penalize forgetting English
    
    "add_eos=True" ,
    "log_period=10",
    "return_log_prob=True",

    "checkpoint_period=25",
    "save_checkpoint_on_completion=True",
    "max_target_length=2048",
    
    # --- EVALUATION ---
    "num_test_batches=5", 
    "eval_interval=25", 
]

# --- 5. EXECUTION ---
trainer_config, sampler_config, trainer_devices, sampler_devices = setup_configs_and_devices(config_argv)

# MLflow logging
mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow-service:5000"))
mlflow.set_experiment("MaxText-RL-GRPO")

with mlflow.start_run(run_name=f"Llama3.1-8B-GRPO-{RUN_NAME}"):
    print(f"🔥 Training starting on {len(jax.devices())} TPUs...")
    rl_train(trainer_config, sampler_config, trainer_devices, sampler_devices)

print("🏁 Training successfully completed.")
