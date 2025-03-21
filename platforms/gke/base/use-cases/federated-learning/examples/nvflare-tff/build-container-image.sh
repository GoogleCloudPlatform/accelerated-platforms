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
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/common.sh"

start_timestamp_federated_learning=$(date +%s)

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
load_fl_terraform_outputs

NVFLARE_EXAMPLE_CONTAINER_IMAGE_BUILD_CONTEXT_PATH="${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/container-image"

echo "Building: ${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}"

docker build \
  --file "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_BUILD_CONTEXT_PATH}/Dockerfile" \
  --tag "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" \
  "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_BUILD_CONTEXT_PATH}"

end_timestamp_federated_learning=$(date +%s)
total_runtime_value_federated_learning=$((end_timestamp_federated_learning - start_timestamp_federated_learning))
echo "Total runtime (Federated learning NVIDIA FLARE example container image build): $(date -d@${total_runtime_value_federated_learning} -u +%H:%M:%S)"
