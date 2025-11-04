#!/bin/bash
#
# Copyright 2024 Google LLC
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

# Set repository values
ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../../../../)"
ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"

declare -a CORE_TERRASERVICES_APPLY_ARRAY=(
  "networking"
  "container_cluster"
  "container_node_pool"
  "cloudbuild/initialize"
  "gke_enterprise/fleet_membership"
  "gke_enterprise/configmanagement/oci"
  "gke_enterprise/policycontroller"
  "gke_enterprise/servicemesh"
  "workloads/cluster_credentials"
  "custom_compute_class"
  "huggingface/initialize"
  "nvidia/initialize"
  "workloads/auto_monitoring"
  "workloads/custom_metrics_adapter"
  "workloads/inference_gateway"
  "workloads/jobset"
  "workloads/kueue"
  "workloads/lws"
)
export CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY_ARRAY[*]}"

"${ACP_PLATFORM_CORE_DIR}/deploy.sh"

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime (core/standard-full-deploy): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
