#!/bin/bash
#
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

start_timestamp=$(date +%s)

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

export TF_VAR_initialize_backend_use_case_name="inference-ref-arch/terraform"

declare -a CORE_TERRASERVICES_APPLY_ARRAY=(
  "networking"
  "container_cluster"
  "workloads/cluster_credentials"
  "huggingface/initialize"
  "huggingface/hub_downloader"
  "custom_compute_class"
  "workloads/auto_monitoring"
  "../use-cases/inference-ref-arch/terraform/online_tpu"
)
export CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY_ARRAY[*]}"

"${MY_PATH}/../../core/deploy.sh"

source "${MY_PATH}/../../use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

${cluster_credentials_command}

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime (tutorials/hf-gpu-model): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
