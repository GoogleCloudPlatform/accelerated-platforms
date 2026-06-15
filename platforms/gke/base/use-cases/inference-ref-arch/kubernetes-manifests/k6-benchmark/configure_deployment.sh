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
MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

source "${MY_PATH}/../../terraform/_shared_config/scripts/set_environment_variables.sh"

if [[ -z "${ACCELERATOR_TYPE:-}" ]]; then
  echo "ACCELERATOR_TYPE is not set"
  return 1
fi

if [[ -z "${HF_MODEL_NAME:-}" ]]; then
  echo "HF_MODEL_NAME is not set"
  echo "If the HF_MODEL_NAME variable is not set, ensure that HF_MODEL_ID is set and source the set_environment_variables.sh script:"
  echo "source \"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh\""
  return 1
fi

if [[ -z "${K6_SCENARIOS_JSON:-}" ]]; then
  echo "K6_SCENARIOS_JSON is not set."
  return 1
fi
export K6_SCENARIOS_JSON

echo "Configuring deployment for ${HF_MODEL_NAME} running on ${ACCELERATOR_TYPE}"

if [[ "${HF_MODEL_NAME:-}" == "flux-2-klein-4b" ]]; then
  K6_TARGET_URL="http://diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}:8000"
  K6_INFERENCE_SERVER_TYPE="sglang"
elif [[ "${HF_MODEL_NAME:-}" == "flux-1-schnell" ]]; then
  K6_TARGET_URL="http://diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}:8000/generate"
  K6_INFERENCE_SERVER_TYPE="diffusers"
else
  echo "Model not supported: ${HF_MODEL_NAME:-"HF_MODEL_NAME variable not set"}"
  return 1
fi

export K6_TARGET_URL
export K6_INFERENCE_SERVER_TYPE

envsubst <"${MY_PATH}/base/templates/deployment.tpl.env" | sponge "${MY_PATH}/base/deployment.env"

echo "Deployment configuration:"
cat "${MY_PATH}/base/deployment.env"
