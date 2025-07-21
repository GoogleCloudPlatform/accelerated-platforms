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

ARG cuda_version=12.6
ARG pytorch_version=2.7.0

FROM pytorch/pytorch:${pytorch_version}-cuda${cuda_version}-cudnn9-runtime

ENV CMAKE_BUILD_PARALLEL_LEVEL "8"
ENV COMFY_VERSION "0.3.39"
ENV CUDA_VERSION "12.6"
ENV DEBIAN_FRONTEND "noninteractive"
ENV PIP_PREFER_BINARY "1"

# Set a non-root user and group
ARG UID=10000
ARG GID=10000
ARG USER=comfyuser
ARG GROUP=comfygroup

# Set the working directory for the application
ENV COMFY_DIR "/home/${USER}/comfy"
WORKDIR ${COMFY_DIR}

# Create the group and user
RUN groupadd --gid ${GID} ${GROUP} \ 
  && useradd --uid ${UID} --gid ${GID} -m ${USER} \
  && chown -R ${USER}:${GROUP} /home/${USER}

SHELL ["/bin/bash", "-c"]

RUN apt-get update \
  && apt-get install --yes \
  curl \
  gettext \
  git \
  libglib2.0-0 \
  unzip \
  wget \
  && apt clean --yes \ 
  && rm --force --recursive /var/lib/apt/lists/* \
  && pip install --no-cache-dir uv \ 
  && uv pip install --no-cache-dir --system comfy-cli

USER ${USER}

ENV COMFY_HOME "${COMFY_DIR}/ComfyUI"
ENV PATH "/home/${USER}/.local/bin:${PATH}"

RUN comfy --skip-prompt --workspace=${COMFY_DIR} tracking disable \
  && comfy --skip-prompt --workspace=${COMFY_HOME} install --cuda-version=${CUDA_VERSION} --nvidia --version=${COMFY_VERSION} \
  && comfy --skip-prompt set-default ${COMFY_HOME}

COPY --chown=${USER}:${GROUP} --chmod=700 entrypoint.sh ./

ENV BASE ""
ENV INPUT_DIR "${COMFY_HOME}/input"
ENV MODEL_DIR "${COMFY_HOME}/models"
ENV OUTPUT_DIR "${COMFY_HOME}/output"
ENV WORKFLOWS_DIR "${COMFY_HOME}/user/default/workflows"

ENV COMFYUI_HOST "0.0.0.0"
ENV COMFYUI_PORT "8188"

ARG COMFYUI_CUSTOM_NODE_PATH="${COMFY_HOME}/custom_nodes"
ARG VHS_REPO="https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite"
ARG VHS_CUSTOM_NODE_DIR_NAME="${COMFYUI_CUSTOM_NODE_PATH}/ComfyUI-VideoHelperSuite"
ARG CUSTOM_SCRIPTS_REPO="https://github.com/pythongosssss/ComfyUI-Custom-Scripts"
ARG CUSTOM_SCRIPTS_CUSTOM_NODE_DIR_NAME="${COMFYUI_CUSTOM_NODE_PATH}/ComfyUI-Custom-Scripts"

COPY --chown=${USER}:${GROUP} --chmod=700 custom-nodes/gemini ${COMFYUI_CUSTOM_NODE_PATH}/gemini
COPY --chown=${USER}:${GROUP} --chmod=700 custom-nodes/imagen3 ${COMFYUI_CUSTOM_NODE_PATH}/imagen3
COPY --chown=${USER}:${GROUP} --chmod=700 custom-nodes/imagen4 ${COMFYUI_CUSTOM_NODE_PATH}/imagen4
COPY --chown=${USER}:${GROUP} --chmod=700 custom-nodes/veo2 ${COMFYUI_CUSTOM_NODE_PATH}/veo2
COPY --chown=${USER}:${GROUP} --chmod=700 custom-nodes/veo3 ${COMFYUI_CUSTOM_NODE_PATH}/veo3
RUN pip install -r ${COMFYUI_CUSTOM_NODE_PATH}/gemini/requirements.txt \
  -r ${COMFYUI_CUSTOM_NODE_PATH}/imagen3/requirements.txt \
  -r ${COMFYUI_CUSTOM_NODE_PATH}/imagen4/requirements.txt \
  -r ${COMFYUI_CUSTOM_NODE_PATH}/veo2/requirements.txt \
  -r ${COMFYUI_CUSTOM_NODE_PATH}/veo3/requirements.txt \
  && git clone ${VHS_REPO} ${VHS_CUSTOM_NODE_DIR_NAME} \
  && pip install -r ${VHS_CUSTOM_NODE_DIR_NAME}/requirements.txt \
  && git clone ${CUSTOM_SCRIPTS_REPO} ${CUSTOM_SCRIPTS_CUSTOM_NODE_DIR_NAME}


ENTRYPOINT  [ "./entrypoint.sh" ]
CMD ["--", "--listen=${COMFYUI_HOST}", "--port=${COMFYUI_PORT}"]
