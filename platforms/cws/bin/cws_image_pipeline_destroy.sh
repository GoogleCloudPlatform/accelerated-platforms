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
# limitations under the License.\
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
MY_NAME=$(basename "${0}" .sh)

declare -A start_timestamp["${MY_NAME}"]
start_timestamp["${MY_NAME}"]=$(date +%s)

ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../")"
ACP_PLATFORM_DIR="${ACP_REPO_DIR}/platforms/cws"
ACP_PLATFORM_STACK_DIR="${ACP_PLATFORM_DIR}/image_pipeline"

# shellcheck source=/dev/null
source "${ACP_PLATFORM_STACK_DIR}/_shared_config/scripts/set_environment_variables.sh"

declare -a terraservices=(
  "images/comfyui/nvidia"
  "images/comfyui/cpu"
  "images/comfyui/models"
  "images/code-oss"
  "cloudbuild"
  "github.com"
  "registry"
  "initialize"
)

for terraservice in "${terraservices[@]}"; do
  cd "${ACP_PLATFORM_STACK_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    rm --force --recursive .terraform/ &&
    terraform init &&
    terraform destroy -auto-approve || exit 1
    rm --force backend.tf
    gcloud storage rm --recursive "gs://${terraform_bucket_name:?}/terraform/cws/image_pipeline/${terraservice}" || echo "No Terraform files to remove"
    rm --force --recursive .terraform/ terraform.tfstate*
done

cd "${ACP_PLATFORM_STACK_DIR}/_shared_config" &&
  echo "Current directory: $(pwd)" &&
  rm --force --recursive .terraform/ terraform.tfstate*

declare -A end_timestamp["${MY_NAME}"]
end_timestamp["${MY_NAME}"]=$(date +%s)
total_runtime_value=$((end_timestamp["${MY_NAME}"] - start_timestamp["${MY_NAME}"]))
echo
echo "Total runtime (${MY_NAME}): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
