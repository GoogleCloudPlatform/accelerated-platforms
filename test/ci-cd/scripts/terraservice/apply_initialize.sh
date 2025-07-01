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
set -o pipefail

source /workspace/build.env
if [ "${DEBUG,,}" == "true" ]; then
  set -o xtrace
fi

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

TERRASERVICE_DIR="${1}"
TERRASERVICE_FOLDER="${2}"

set --
source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh"

STATE_MIGRATED="false"
if gcloud storage ls "gs://${terraform_bucket_name}/terraform" &>/dev/null; then
  STATE_MIGRATED="true"
fi

"${MY_PATH}/apply.sh" "${TERRASERVICE_DIR}" "${TERRASERVICE_FOLDER}"

if [ "${STATE_MIGRATED}" == "false" ]; then
  cd "${TERRASERVICE_DIR}/${TERRASERVICE_FOLDER}"
  terraform init -force-copy -migrate-state
  rm -rf terraform.tfstate*
fi
