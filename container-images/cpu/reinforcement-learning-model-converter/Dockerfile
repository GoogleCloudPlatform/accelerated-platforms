# syntax=docker.io/docker/dockerfile:1.17.1

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

# ==========================================
# Stage 1: Builder
# ==========================================
FROM python:3.12.13-slim-trixie AS builder

# Install build dependencies and git
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Clone the MaxText repository and immediately remove the hidden .git folder
RUN git clone https://github.com/AI-Hypercomputer/maxtext.git . \
    && rm -rf .git

# Create a virtual environment to isolate dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install 'uv' (the fast Python package installer)
RUN pip install --no-cache-dir uv

# Install MaxText with the [tpu] dependency group 
# (This includes absl-py, jax, etc., which are needed for conversion)
RUN uv pip install .[tpu] --resolution=lowest

# MaxText uses a custom CLI command to install unreleased dependencies from GitHub
RUN install_maxtext_tpu_github_deps

# Explicitly install CPU-only PyTorch (Required to read HF Checkpoints)
RUN uv pip install torch --index-url https://download.pytorch.org/whl/cpu

# ==========================================
# Stage 2: Final Runtime
# ==========================================
FROM python:3.12.13-slim-trixie

WORKDIR /workspace

# Copy the pre-built virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy the necessary source code from the builder stage
COPY --from=builder /workspace /workspace

# Activate the virtual environment by default
ENV PATH="/opt/venv/bin:$PATH"

# Set PYTHONPATH so Python can locate the maxtext modules
ENV PYTHONPATH="/workspace/src:${PYTHONPATH}"

# Set the entrypoint to the checkpoint conversion script
ENTRYPOINT ["python", "src/maxtext/checkpoint_conversion/to_maxtext.py"]

# Fallback command to display help flags
CMD ["--help"]
