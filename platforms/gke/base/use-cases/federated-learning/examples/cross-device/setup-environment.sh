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

# Don't set errexit because we might source this script from an interactive
# shell, and we don't want to exit the shell on errors
# set -o errexit
set -o nounset
set -o pipefail

if [[ ! -v ACP_REPO_DIR ]]; then
  SCRIPT_DIRECTORY_PATH="$(cd -P "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

  echo "This script directory path is: ${SCRIPT_DIRECTORY_PATH}"

  ACP_REPO_DIR="$(readlink -f "${SCRIPT_DIRECTORY_PATH}/../../../../../../../")"
  export ACP_REPO_DIR
  export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"

  echo "ACP_REPO_DIR: ${ACP_REPO_DIR}"
  echo "ACP_PLATFORM_BASE_DIR: ${ACP_PLATFORM_BASE_DIR}"

  export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
  echo "ACP_PLATFORM_CORE_DIR: ${ACP_PLATFORM_CORE_DIR}"
fi

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

echo "Setting up the environment for the cross-device federated learning example"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_CROSS_DEVICE_EXAMPLE_CONFIG_AUTO_VARS_FILE="${FEDERATED_LEARNING_SHARED_CONFIG_DIR}/uc_federated_learning_cross_device_example.auto.tfvars"

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_INIT_CONFIGURATION_VARIABLES=(
)

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_FEDERATED_LEARNING_USE_CASE_CONFIGURATION_VARIABLES=(
)

# shellcheck disable=SC2034 # Variable is used in other scripts
CROSS_DEVICE_EXAMPLE_TERRAFORM_CONFIGURATION_VARIABLES=(
)

# shellcheck disable=SC2034 # Variable is used in other scripts
cross_device_example_terraservices=(
  "secret-manager"
)

load_fl_terraform_outputs() {
}
