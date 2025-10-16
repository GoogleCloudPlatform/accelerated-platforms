# syntax=docker.io/docker/dockerfile:1.17.1

# Copyright 2025 Google LLC
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

ARG AR_PROJECT_ID
ARG AR_LOCATION

FROM $${AR_LOCATION}-docker.pkg.dev/$${AR_PROJECT_ID}/${cloudbuild_cws_image_registry_upstream_name}/base:latest

ENV COMFY_VERSION="0.3.45"
ENV CUDA_VERSION "12.6"
ENV PYTORCH_VERSION="2.7.0"

ARG GID=1000
ARG UID=1000
ARG USER=user

# Set the working directory for the application
ENV COMFY_DIR="/comfy"
WORKDIR $${COMFY_DIR}

SHELL ["/bin/bash", "-c"]

COPY --chmod=700 --from=my_context ./ /

RUN pip install --break-system-packages --no-cache-dir uv && \ 
  uv venv

ENV USER_HOME_DIR="/home/$${USER}"
ENV COMFYUI_DIR="$${COMFY_DIR}/ComfyUI"
ENV LD_LIBRARY_PATH="/var/lib/nvidia/lib64"
ENV PATH="/home/$${USER}/.local/bin:$${PATH}:/var/lib/nvidia/bin:/var/lib/nvidia/bin"

RUN source $${COMFY_DIR}/.venv/bin/activate && \
  uv pip install --no-cache-dir comfy-cli pip && \
  uv pip install torch==$${PYTORCH_VERSION} torchvision torchaudio --index-url https://download.pytorch.org/whl/cu$${CUDA_VERSION//.} && \
  comfy --skip-prompt --workspace=$${COMFY_DIR} tracking disable && \
  comfy --skip-prompt --workspace=$${COMFYUI_DIR} install --cuda-version=$${CUDA_VERSION} --fast-deps --nvidia --version=$${COMFY_VERSION} && \
  comfy --skip-prompt set-default $${COMFYUI_DIR} && \
  comfy node install ComfyUI-VideoHelperSuite@nightly && \
  comfy node install ComfyUI-Custom-Scripts@nightly

ARG COMFYUI_CUSTOM_NODE_PATH="$${COMFYUI_HOME}/custom_nodes"
ENV INPUT_DIR="$${COMFYUI_HOME}/input"
ENV MODEL_DIR="$${COMFYUI_HOME}/models"
ENV OUTPUT_DIR="$${COMFYUI_HOME}/output"
ENV WORKFLOWS_DIR="$${COMFYUI_HOME}/user/default/workflows"

COPY --chmod=700 --from=custom_nodes ./google_genmedia $${COMFYUI_CUSTOM_NODE_PATH}/google_genmedia

RUN uv pip install -r $${COMFYUI_CUSTOM_NODE_PATH}/google_genmedia/requirements.txt
