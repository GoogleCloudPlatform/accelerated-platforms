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
export TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-inf}"

declare -a CORE_TERRASERVICES_APPLY=(
  "networking"
  "container_cluster"
  "workloads/cluster_credentials"
  "cloudbuild/initialize"
  "huggingface/initialize"
  "huggingface/hub_downloader"
  "custom_compute_class"
  "workloads/auto_monitoring"
  "workloads/custom_metrics_adapter"
  "workloads/inference_gateway"
  "workloads/jobset"
  "workloads/lws"
  "workloads/priority_class"
  "workloads/kueue"
)
CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY[*]}" "${ACP_PLATFORM_CORE_DIR}/deploy.sh"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config/scripts/set_environment_variables.sh"

declare -a use_case_terraservices=(
  "initialize"
)
for terraservice in "${use_case_terraservices[@]}"; do
  cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    rm -rf .terraform/ &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  if [ ${terraservice} == "comfyui" ]; then
    terraform output -raw environment_configuration >${ACP_REPO_DIR}/env_vars
  fi
  rm tfplan
done

# shellcheck disable=SC2154
gcloud container clusters get-credentials "${cluster_name}" \
  --region "${cluster_region}" \
  --project "${cluster_project_id}" \
  --dns-endpoint

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "inference-ref-arch deploy total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
