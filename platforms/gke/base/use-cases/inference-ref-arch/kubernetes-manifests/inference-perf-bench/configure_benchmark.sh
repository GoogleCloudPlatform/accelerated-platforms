#!/usr/bin/env bash

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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# Update benchmarking namespace depending on TPU or GPU selection 
TARGET_FILE="${MY_PATH}/templates/benchmarking.tpl.env"
GPU_NS="${ira_online_gpu_kubernetes_namespace_name}"
TPU_NS="${ira_online_tpu_kubernetes_namespace_name}"
ACCELERATOR=$(echo "$1" | tr '[:lower:]' '[:upper:]')

# 3. Determine the correct namespace
if [[ "$ACCELERATOR" == "GPU" ]]; then
    SELECTED_NS=$GPU_NS
elif [[ "$ACCELERATOR" == "TPU" ]]; then
    SELECTED_NS=$TPU_NS
else
    echo "Error: Please specify 'GPU' or 'TPU'"
    exit 1
fi

# 4. Use sed to update the value
if grep -q "BENCHMARKING_KUBERNETES_NAMESPACE=" "$TARGET_FILE"; then
    sed -i "s/^BENCHMARKING_KUBERNETES_NAMESPACE=.*/BENCHMARKING_KUBERNETES_NAMESPACE=$SELECTED_NS/" "$TARGET_FILE"
    echo "Successfully updated $TARGET_FILE: BENCHMARKING_KUBERNETES_NAMESPACE=$SELECTED_NS"
else
    # If the variable doesn't exist yet, append it
    echo "BENCHMARKING_KUBERNETES_NAMESPACE=$SELECTED_NS" >> "$TARGET_FILE"
    echo "Variable not found. Appended to $TARGET_FILE."
fi

source "${MY_PATH}/../../terraform/_shared_config/scripts/set_environment_variables.sh"

envsubst < "${MY_PATH}/templates/benchmarking.tpl.env" | sponge "${MY_PATH}/benchmarking.env"

envsubst < "${MY_PATH}/templates/secretproviderclass-huggingface-tokens.tpl.yaml" | sponge "${MY_PATH}/secretproviderclass-huggingface-tokens.yaml"


cd "${MY_PATH}"
kustomize edit set nameprefix "${HF_MODEL_ID_HASH}-"
