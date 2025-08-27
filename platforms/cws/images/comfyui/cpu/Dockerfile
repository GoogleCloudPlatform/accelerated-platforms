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

FROM us-central1-docker.pkg.dev/cloud-workstations-images/predefined/base:latest

ENV COMFY_VERSION="0.3.45"
ENV PYTORCH_VERSION="2.7.0"

ARG GID=1000
ARG UID=1000
ARG USER=user

# Set the working directory for the application
ENV COMFY_DIR="/comfy"
WORKDIR ${COMFY_DIR}

SHELL ["/bin/bash", "-c"]

RUN pip install --break-system-packages --no-cache-dir uv && \ 
  uv venv

ENV COMFYUI_HOME="${COMFY_DIR}/ComfyUI"
ENV PATH="/home/${USER}/.local/bin:${PATH}"

RUN source ${COMFY_DIR}/.venv/bin/activate && \
  uv pip install --no-cache-dir comfy-cli pip && \
  uv pip install torch==${PYTORCH_VERSION} torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
  comfy --skip-prompt --workspace=${COMFY_DIR} tracking disable && \
  comfy --skip-prompt --workspace=${COMFYUI_HOME} install --cpu --version=${COMFY_VERSION} && \
  comfy --skip-prompt set-default ${COMFYUI_HOME} && \
  comfy node install ComfyUI-VideoHelperSuite@nightly && \
  comfy node install ComfyUI-Custom-Scripts@nightly

ARG COMFYUI_CUSTOM_NODE_PATH="${COMFYUI_HOME}/custom_nodes"
ENV INPUT_DIR="${COMFYUI_HOME}/input"
ENV MODEL_DIR="${COMFYUI_HOME}/models"
ENV OUTPUT_DIR="${COMFYUI_HOME}/output"
ENV WORKFLOWS_DIR="${COMFYUI_HOME}/user/default/workflows"

COPY --chmod=700 custom-nodes/google-genmedia ${COMFYUI_CUSTOM_NODE_PATH}/google-genmedia 

RUN uv pip install -r ${COMFYUI_CUSTOM_NODE_PATH}/google-genmedia/requirements.txt

COPY --chmod=700 110_start-comfyui.sh /etc/workstation-startup.d/
