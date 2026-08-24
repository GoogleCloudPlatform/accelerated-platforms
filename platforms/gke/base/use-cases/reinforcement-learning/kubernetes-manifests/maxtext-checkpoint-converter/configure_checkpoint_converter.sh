#!/usr/bin/env bash

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
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

if [[ ! -v HF_MODEL_ID ]]; then
  echo "HF_MODEL_ID is not set, exiting!"
  exit 1
fi

source "${MY_PATH}/../../terraform/_shared_config/scripts/set_environment_variables.sh"

secret_version_found=$(gcloud secrets versions list "${huggingface_hub_access_token_read_secret_manager_secret_name}" \
--project="${huggingface_secret_manager_project_id}" 2>/dev/null | grep "enabled" | wc -l)

if [[ ${secret_version_found} == 0 ]]; then
  echo "Hugging Face Hub read token secret '${huggingface_hub_access_token_read_secret_manager_secret_name}' version is missing or not enabled! Please add the token to the secret, exiting."
  exit 1
fi

if [[ ! -v USE_MULTIMODAL ]]; then
  if [[ "${HF_MODEL_ID}" =~ gemma3|gemma-3|vl|vision ]]; then
    export USE_MULTIMODAL="True"
  else
    export USE_MULTIMODAL="False"
  fi
fi

if [[ ! -v LAZY_LOAD_TENSORS ]]; then
  if [[ "${USE_MULTIMODAL}" == "True" ]]; then
    export LAZY_LOAD_TENSORS="False"
  else
    export LAZY_LOAD_TENSORS="True"
  fi
fi

if [[ ! -v EAGER_LOAD_METHOD ]]; then
  if [[ "${USE_MULTIMODAL}" == "True" ]]; then
    export EAGER_LOAD_METHOD="transformers"
  else
    export EAGER_LOAD_METHOD="safetensors"
  fi
fi

envsubst < "${MY_PATH}/checkpoint-converter/templates/converter.tpl.env" | sponge "${MY_PATH}/checkpoint-converter/converter.env"

envsubst < "${MY_PATH}/checkpoint-converter/templates/secretproviderclass-huggingface-tokens.tpl.yaml" | sponge "${MY_PATH}/checkpoint-converter/secretproviderclass-huggingface-tokens.yaml"

cd "${MY_PATH}/checkpoint-converter"
if grep -q "^namePrefix:" kustomization.yaml; then
  sed -i "s/^namePrefix:.*/namePrefix: ${HF_MODEL_ID_HASH}-/" kustomization.yaml
else
  sed -i "/^kind: Kustomization/a namePrefix: ${HF_MODEL_ID_HASH}-" kustomization.yaml
fi
