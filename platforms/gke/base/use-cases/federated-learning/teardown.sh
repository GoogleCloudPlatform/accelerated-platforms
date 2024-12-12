#!/usr/bin/env bash
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

start_timestamp_federated_learning=$(date +%s)

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

# shellcheck disable=SC2154 # variable defined in common.sh
for terraservice in "${federated_learning_terraservices[@]}"; do
  if [ "${terraservice:-}" == "initialize" ]; then
    echo "Skip destroying ${terraservice} to avoid removing backend configuration files"
    continue
  fi
  echo "Destroying ${terraservice}"
  cd "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    terraform init -backend-config="backend.config" &&
    terraform destroy -auto-approve || exit 1

  rm -rf \
    "${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/${terraservice}/.terraform"
done

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning use case provisioning and configuration): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
