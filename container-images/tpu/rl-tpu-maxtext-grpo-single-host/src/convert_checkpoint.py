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

import glob
import os
import shutil
import sys

import jax
import jax.numpy as jnp
import orbax.checkpoint as ocp
from google.cloud import storage
from huggingface_hub import login, snapshot_download
from safetensors import safe_open

print("🚀 Pure JAX/Safetensors Llama 3.1 8B Converter starting...", flush=True)

HF_TOKEN = os.environ.get("HF_TOKEN")
if HF_TOKEN:
    login(token=HF_TOKEN)

GCS_OUTPUT = os.environ.get(
    "GCS_OUTPUT_PATH", "gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models"
)
# e.g. GCS_OUTPUT = gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models
bucket_name = GCS_OUTPUT.replace("gs://", "").strip("/")

print("📥 Downloading Hugging Face safetensors shards...", flush=True)
model_dir = snapshot_download(
    repo_id="meta-llama/Llama-3.1-8B-Instruct",
    allow_patterns=["*.safetensors", "*.json"],
    token=HF_TOKEN,
    local_dir="/hf_cache/llama3_1_8b",
)

print(f"✅ Downloaded safetensors shards to {model_dir}", flush=True)

safetensor_files = sorted(glob.glob(os.path.join(model_dir, "*.safetensors")))
print(f"Found {len(safetensor_files)} safetensors shard files.", flush=True)

state_dict = {}
for sf_path in safetensor_files:
    print(f"📦 Loading shard: {os.path.basename(sf_path)}...", flush=True)
    with safe_open(sf_path, framework="np", device="cpu") as f:
        for k in f.keys():
            state_dict[k] = jnp.array(f.get_tensor(k), dtype=jnp.bfloat16)

print(
    f"✅ Loaded {len(state_dict)} tensor keys into JAX array memory successfully!",
    flush=True,
)

LOCAL_OUT = "/tmp/orbax_out/0/items"
if os.path.exists("/tmp/orbax_out"):
    shutil.rmtree("/tmp/orbax_out")

print(f"💾 Saving Orbax checkpoint locally to {LOCAL_OUT}...", flush=True)
checkpointer = ocp.StandardCheckpointer()
checkpointer.save(LOCAL_OUT, state_dict)
checkpointer.close()

print(
    f"☁️ Uploading converted Orbax checkpoint to GCS bucket gs://{bucket_name}/llama_checkpoint...",
    flush=True,
)
client = storage.Client()
bucket = client.bucket(bucket_name)

local_base = "/tmp/orbax_out"
for root, dirs, files in os.walk(local_base):
    for file in files:
        local_path = os.path.join(root, file)
        rel_path = os.path.relpath(local_path, local_base)
        gcs_path = f"llama_checkpoint/{rel_path}"
        blob = bucket.blob(gcs_path)
        print(f"  Uploading {rel_path} -> gs://{bucket_name}/{gcs_path}...", flush=True)
        blob.upload_from_filename(local_path)

print("🎉 PURE JAX CONVERSION & GCS UPLOAD COMPLETED SUCCESSFULLY!", flush=True)
