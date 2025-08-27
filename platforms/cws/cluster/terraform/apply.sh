#!/bin/bash

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

start_timestamp=$(date +%s)

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../)"
ACP_PLATFORM_DIR="${ACP_REPO_DIR}/platforms/cws"
ACP_PLATFORM_TF_DIR="${ACP_PLATFORM_DIR}/cluster/terraform"

source "${ACP_PLATFORM_DIR}/cluster/_shared_config/scripts/set_environment_variables.sh"

declare -a terraservices=(
  "initialize"
  "network"
  "workstation_cluster"
)

for terraservice in "${terraservices[@]}"; do
  cd "${ACP_PLATFORM_TF_DIR}/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  rm tfplan
done

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))

echo
echo "Total runtime (cws/cluster): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
