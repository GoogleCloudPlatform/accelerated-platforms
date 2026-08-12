#!/usr/bin/env bash

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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

source "${MY_PATH}/../../../terraform/_shared_config/scripts/set_environment_variables.sh"

"${MY_PATH}/../configure_deployment.sh"

if [[ "${HF_MODEL_ID}" == "black-forest-labs/flux.1-schnell" ]]; then
  DIFFUSERS_CONTAINER_IMAGE_URL="${ira_online_gpu_diffusers_flux_image_url}"
  DIFFUSERS_INFERENCE_SERVER="diffusers"
elif [[ "${HF_MODEL_ID}" == "black-forest-labs/flux.2-klein-4b" ]]; then
  DIFFUSERS_CONTAINER_IMAGE_URL="${ira_online_gpu_diffusers_sglang_diffusers_image_url}"
  DIFFUSERS_INFERENCE_SERVER="sglang"
else
  echo "[ERROR] Set a container image URL for model: ${HF_MODEL_ID:-"no model set"}"
  return 1
fi

export DIFFUSERS_CONTAINER_IMAGE_URL
export DIFFUSERS_INFERENCE_SERVER

envsubst <"${MY_PATH}/base/templates/diffusers.tpl.env" | sponge "${MY_PATH}/base/diffusers.env"

echo "Configurations for ${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"

echo "Deployment configuration:"
cat "${MY_PATH}/base/diffusers.env"
echo

echo "Runtime configuration:"
cat "${MY_PATH}/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}/runtime.env"
