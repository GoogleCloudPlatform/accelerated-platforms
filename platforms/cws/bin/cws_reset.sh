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
MY_NAME=$(basename "${0}" .sh)

declare -A start_timestamp["${MY_NAME}"]
start_timestamp["${MY_NAME}"]=$(date +%s)

ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../")"
ACP_PLATFORM_DIR="${ACP_REPO_DIR}/platforms/cws"

source "${ACP_PLATFORM_DIR}/_shared_config/scripts/set_environment_variables.sh"


cd "${ACP_PLATFORM_DIR}/_shared_config/initialize" &&
  echo "Current directory: $(pwd)" &&
  if [ ! -f "terraform.tfstate" ]; then
    if gcloud storage ls "gs://${terraform_bucket_name}/terraform/cws/_shared_config/initialize/default.tfstate" &>/dev/null; then
      sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" "${ACP_PLATFORM_DIR}/_shared_config/initialize/backend.tf.bucket" &&
      cp backend.tf.bucket backend.tf
    else
      rm --force --recursive backend.tf
    fi
  fi
  rm --force --recursive .terraform/ &&
  terraform init &&
  terraform plan -input=false -out=tfplan &&
  terraform apply -input=false tfplan || exit 1
rm tfplan

rm --force --recursive backend.tf &&
  terraform init -force-copy -lock=false -migrate-state || exit 1

gcloud storage rm --recursive "gs://${terraform_bucket_name}/terraform/cws" || echo "No Terraform files to remove"
terraform destroy -auto-approve || exit 1

rm --force --recursive \
  "${ACP_PLATFORM_DIR}/_shared_config/.terraform/" \
  "${ACP_PLATFORM_DIR}/_shared_config"/terraform.tfstate* \
  "${ACP_PLATFORM_DIR}/_shared_config/initialize/.terraform" \
  "${ACP_PLATFORM_DIR}/_shared_config/initialize"/terraform.tfstate*

git restore \
  "${ACP_PLATFORM_DIR}/_shared_config/"
  
declare -A end_timestamp["${MY_NAME}"]
end_timestamp["${MY_NAME}"]=$(date +%s)
total_runtime_value=$((end_timestamp["${MY_NAME}"] - start_timestamp["${MY_NAME}"]))
echo
echo "Total runtime (${MY_NAME}): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
