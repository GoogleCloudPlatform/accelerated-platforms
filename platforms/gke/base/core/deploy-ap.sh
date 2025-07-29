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

declare -a CORE_TERRASERVICES_APPLY_ARRAY=(
  "networking"
  "container_cluster_ap"
  "gke_enterprise/fleet_membership"
  "workloads/cluster_credentials"
  "custom_compute_class"
  "workloads/auto_monitoring"
  "workloads/kueue"
)
export CORE_TERRASERVICES_APPLY="${CORE_TERRASERVICES_APPLY_ARRAY[*]}"

"${MY_PATH}/deploy.sh"

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime (core/deploy-ap): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
