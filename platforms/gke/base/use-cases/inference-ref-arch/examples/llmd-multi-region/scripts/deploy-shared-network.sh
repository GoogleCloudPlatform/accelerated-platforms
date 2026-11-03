#!/usr/bin/env bash
#
# Copyright 2026 Google LLC
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

# Creates the shared VPC network and the GLOBAL_MANAGED_PROXY proxy-only
# subnets that every regional cluster uses.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"
# shellcheck source=/dev/null
source "${MY_PATH}/tf.sh"

mr_require_tools
mr_log "Project: ${MR_PROJECT_ID}, network: ${MR_NETWORK_NAME}, regions: ${MR_REGION_KEYS}"

for key in ${MR_REGION_KEYS}; do
  mr_validate_region_key "${key}"
done

mr_stage "shared_state_bucket" "global" mr_ensure_shared_state_bucket
tfvars="$(mr_write_shared_network_tfvars)"
mr_stage "shared_network" "global" mr_tf shared_network apply "${tfvars}"
