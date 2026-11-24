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
FROM nvcr.io/nvidia/cuda:13.2.1-cudnn-runtime-ubuntu24.04@sha256:1c0c68dbf3258d32b446a02cb4be05c8478b65d320d7856ad33c4bbdf898ca86

ENV PATH=/opt/venv/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set up the working directory
WORKDIR /app

# Copy application code
COPY --from=primary requirements.txt .

# Install Python into an isolated virtual environment and verify runtime imports at build time.
# The NVIDIA apt source is removed first, so `apt-get upgrade` patches Ubuntu
# packages only and the CUDA libraries stay at the versions of the pinned base image.
# python3-venv is only needed to create the virtual environment. It is removed
# afterwards together with the bundled wheels that it depends on, which image
# scanners report.
RUN rm /etc/apt/sources.list.d/cuda-*.list && \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends python3 python3-venv && \
    python3 -m venv --upgrade-deps /opt/venv && \
    apt-get purge -y --auto-remove python3-venv && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt && \
    python3 -c "import accelerate, diffusers, fastapi, PIL, google.protobuf, sentencepiece, torch, transformers, uvicorn; from diffusers import FluxPipeline"

COPY --from=primary app.py .

# Expose the port for your web server (e.g., FastAPI or Flask)
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
