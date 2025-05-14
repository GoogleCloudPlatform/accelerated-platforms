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

start_timestamp=$(date +%s)

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# Set repository values
export ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../../../)"
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
export ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch"

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="inference-ref-arch/terraform"
export TF_VAR_resource_name_prefix="inf"

# Set execution specific values
export ACP_TEARDOWN_CORE_PLATFORM=${ACP_TEARDOWN_CORE_PLATFORM:-"true"}

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh" "${ACP_PLATFORM_BASE_DIR}/_shared_config" "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config"

# shellcheck disable=SC2154
cd "${ACP_PLATFORM_CORE_DIR}/initialize" &&
  echo "Current directory: $(pwd)" &&
  sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket" &&
  cp backend.tf.bucket backend.tf &&
  terraform init &&
  terraform plan -input=false -out=tfplan &&
  terraform apply -input=false tfplan || exit 1
rm tfplan

declare -a use_case_terraservices=(
  "cloud_storage"
  "initialize"
)
for terraservice in $(echo "${use_case_terraservices[@]}" | tac -s " "); do
  cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    terraform init &&
    terraform destroy -auto-approve || exit 1
  rm -rf .terraform/ \
    "terraform.tfstate"*
done

if [ "${ACP_TEARDOWN_CORE_PLATFORM}" = "true" ]; then
  declare -a CORE_TERRASERVICES_DESTROY=(
    "workloads/kueue"
    "workloads/priority_class"
    "workloads/lws"
    "workloads/jobset"
    "workloads/inference_gateway"
    "workloads/auto_monitoring"
    "custom_compute_class"
    "workloads/cluster_credentials"
    "container_cluster"
    "networking"
    "initialize"
  )
  CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY[*]}" "${ACP_PLATFORM_CORE_DIR}/teardown.sh"
else
  echo "Skipping core platform teardown."
fi

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "inference-ref-arch teardown total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
