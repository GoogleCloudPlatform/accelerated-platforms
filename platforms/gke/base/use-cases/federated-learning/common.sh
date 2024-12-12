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

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh" "${ACP_PLATFORM_BASE_DIR}/_shared_config"

FEDERATED_LEARNING_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR="${FEDERATED_LEARNING_USE_CASE_DIR}/terraform"

# shellcheck disable=SC2034 # Variable is used in other scripts
FEDERATED_LEARNING_USE_CASE_INITIALIZE_SERVICE_DIR="${FEDERATED_LEARNING_USE_CASE_TERRAFORM_DIR}/initialize"

# shellcheck disable=SC2034 # Variable is used in other scripts
federated_learning_terraservices=(
  "initialize"
  "container_image_repository"
)
