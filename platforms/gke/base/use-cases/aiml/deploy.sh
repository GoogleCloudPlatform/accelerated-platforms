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

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="aiml/terraform"
export TF_VAR_resource_name_prefix="aiml"

declare -a CORE_TERRASERVICES_APPLY=(
  "networking"
  "container_cluster"
  "container_node_pool"
  "gke_enterprise/fleet_membership"
  "workloads/cluster_credentials"
  "workloads/kuberay"
  "workloads/kueue"
)
CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY[*]}" ${ACP_PLATFORM_CORE_DIR}/deploy.sh

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "aiml deploy total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
