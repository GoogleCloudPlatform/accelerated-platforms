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

ENV COMFY_DIR="/comfy"
WORKDIR $${COMFY_DIR}

ENV DEBIAN_FRONTEND="noninteractive"

RUN  wget -qO - https://packages.cloud.google.com/apt/doc/apt-key.gpg | gpg --dearmor -o /usr/share/keyrings/packages.cloud.google.com_apt-key.gpg && \
  echo "deb [signed-by=/usr/share/keyrings/packages.cloud.google.com_apt-key.gpg] https://packages.cloud.google.com/apt gcsfuse-$(lsb_release -c -s) main" > /etc/apt/sources.list.d/gcsfuse.list && \
  apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y gcsfuse && \
  rm -rf /var/lib/apt/lists/* && \
  pip install --break-system-packages --no-cache-dir uv && \
  uv venv

ARG GID=1000
ARG UID=1000
ARG USER=user

# Set Bash as the default shell
SHELL ["/bin/bash", "-c"]

ENV COMFY_VERSION="0.3.62"
ENV PYTORCH_VERSION="2.7.0"

COPY --chmod=700 --from=my_context ./ /

ENV COMFYUI_DIR_NAME="ComfyUI"
ENV USER_HOME_DIR="/home/$${USER}"

ENV COMFYUI_DIR="$${COMFY_DIR}/$${COMFYUI_DIR_NAME}"
ENV PATH="$${USER_HOME_DIR}/.local/bin:$${PATH}:/var/lib/nvidia/bin:/var/lib/nvidia/bin"
ENV USER_COMFYUI_DIR="$${USER_HOME_DIR}/$${COMFYUI_DIR_NAME}"

RUN source $${COMFY_DIR}/.venv/bin/activate && \
  uv pip install --no-cache-dir comfy-cli pip && \
  uv pip install torch==$${PYTORCH_VERSION} torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
  comfy --skip-prompt --workspace=$${COMFY_DIR} tracking disable && \
  comfy --skip-prompt --workspace=$${COMFYUI_DIR} install --cpu --fast-deps --version=$${COMFY_VERSION} && \
  comfy --skip-prompt set-default $${COMFYUI_DIR} && \
  comfy node install comfyui-browser && \
  comfy node install ComfyUI-Custom-Scripts@nightly && \
  comfy node install ComfyUI-VideoHelperSuite@nightly

ARG COMFYUI_CUSTOM_NODE_DIR="custom_nodes"
ENV COMFYUI_INPUT_DIR="input"
ENV COMFYUI_MODELS_DIR="models"
ENV COMFYUI_OUTPUT_DIR="output"
ENV COMFYUI_WORKFLOWS_DIR="user/default/workflows"

COPY --chmod=700 --from=custom_nodes ./google_genmedia $${COMFYUI_DIR}/$${COMFYUI_CUSTOM_NODE_DIR}/google_genmedia

RUN source $${COMFY_DIR}/.venv/bin/activate && \
  uv pip install -r $${COMFYUI_DIR}/$${COMFYUI_CUSTOM_NODE_DIR}/google_genmedia/requirements.txt
