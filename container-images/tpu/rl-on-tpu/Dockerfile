# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM python:3.12-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y wget curl build-essential git && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install the incredibly fast 'uv' package manager
RUN pip install --upgrade pip uv

# 1. Install standard Torch CPU and specific JAX TPU drivers first (Our safety net!)
RUN uv pip install --system torch torchvision --index-url https://download.pytorch.org/whl/cpu
RUN uv pip install --system "jax[tpu]==0.4.25" -f https://storage.googleapis.com/jax-releases/libtpu_releases.html --prerelease=allow

# 2. Clone the repo
RUN git clone https://github.com/google/maxtext.git /workspace/maxtext

# Shift Docker's working directory INSIDE the repo
WORKDIR /workspace/maxtext

# 3. Apply the lowest flag (no 'cd' needed anymore!)
RUN uv pip install --system -e ".[tpu-post-train]" --resolution=lowest

# 4. Run the script (it will natively find the 'src' folder now!)
RUN install_maxtext_tpu_post_train_extra_deps

# Shift back to your main workspace for your custom files
WORKDIR /workspace

# 5. Install our specific MLOps tracking tools
RUN uv pip install --system mlflow huggingface_hub math_verify

# 6. Download the chat template directly
RUN wget https://raw.githubusercontent.com/google/maxtext/main/src/maxtext/examples/chat_templates/gsm8k_rl.json -O /workspace/gsm8k_rl.json

# Copy our training script
COPY train.py /workspace/app.py

# Execute the script
CMD ["python3", "app.py"]
