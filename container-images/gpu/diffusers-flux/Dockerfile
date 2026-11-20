# syntax=mirror.gcr.io/docker/dockerfile:1.17.1

# Copyright 2025 Google LLC
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

# Official NVIDIA CUDA base image (Ubuntu 24.04 provides Python 3.12; CUDA 13.2 aligns with PyTorch 2.15 cu13 runtime)
FROM nvcr.io/nvidia/cuda:13.2.1-cudnn-runtime-ubuntu24.04

ENV PATH=/opt/venv/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set up the working directory
WORKDIR /app

# Copy application code
COPY --from=primary requirements.txt .

# Install Python into an isolated virtual environment and verify runtime imports at build time
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m venv --upgrade-deps /opt/venv && \
    pip install --no-cache-dir -r requirements.txt && \
    python3 -c "import accelerate, diffusers, fastapi, PIL, google.protobuf, sentencepiece, torch, transformers, uvicorn; from diffusers import FluxPipeline"

COPY --from=primary app.py .

# Expose the port for your web server (e.g., FastAPI or Flask)
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
