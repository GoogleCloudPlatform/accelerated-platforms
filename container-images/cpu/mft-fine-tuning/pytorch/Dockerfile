# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# The PyTorch version of the base images must match the torch version in
# src/requirements.txt. The base images provide the torchvision and torchaudio
# builds for that PyTorch version, a different torch version breaks them.

# DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT
# DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT
# DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT DEVELOPMENT
FROM pytorch/pytorch:2.15.0-cuda13.2-cudnn9-devel AS devel

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace/

RUN apt-get update && \
  apt-get install -y \
  git && \
  rm -rf /var/lib/apt/lists/* && \
  mkdir -p /workspace/wheels

COPY --from=primary requirements.txt /workspace/

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /workspace/wheels -r /workspace/requirements.txt





# FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL
# FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL
# FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL FINAL
FROM pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime

WORKDIR /workspace/

RUN apt-get update && \
  apt-get install -y \
  git && \
  rm -rf /var/lib/apt/lists/*

COPY --from=devel /workspace/wheels /workspace/wheels
COPY --from=primary requirements.txt /workspace/

# The Python environment of the base image is marked as externally managed
# (PEP 668). The packages are installed into that environment. pip replaces the
# torch build of the base image with the wheel of the same version from PyPI,
# and keeps the torchvision and torchaudio builds of the base image.
RUN pip install --break-system-packages --no-cache /workspace/wheels/*

# Fail the build if the packages used for fine-tuning can't be imported, for
# example when the torch version doesn't match the base image.
RUN python -c "import accelerate, peft, torch, torchvision, transformers, trl"

COPY --from=primary fine_tune.py fsdp_config.yaml logging.conf /workspace/
