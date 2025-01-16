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

export ACP_REPO_DIR=$(git rev-parse --show-toplevel)
export ACP_PLATFORM_BASE_DIR="$ACP_REPO_DIR/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="$ACP_PLATFORM_BASE_DIR/core"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/use-cases/gke-batchref-arch/common.sh"

start_timestamp_batchref_arch=$(date +%s)

echo "Initializing the core platform"
# Don't provision any core platform terraservice becuase we just need
# to initialize the terraform environment and remote backend
# shellcheck disable=SC1091,SC2154
CORE_TERRASERVICES_APPLY="${core_platform_init_terraservices[*]}" \
  "${ACP_PLATFORM_CORE_DIR}/deploy.sh"

echo "Provisioning the core platform"
# shellcheck disable=SC1091,SC2034,SC2154 # Variable is used in other scripts
CORE_TERRASERVICES_APPLY="${core_platform_terraservices[*]}" \
  "${ACP_PLATFORM_CORE_DIR}/deploy.sh"