#!/bin/bash
#
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
MY_PATH_IRA_ENV="$(
  cd "$(dirname "${BASH_SOURCE}")" >/dev/null 2>&1
  pwd -P
)"

ACP_REPO_DIR="$(realpath ${MY_PATH_IRA_ENV}/../../../../../../../../)"
ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch"

declare -a SHARED_CONFIG_PATHS=(
  "${ACP_PLATFORM_BASE_DIR}/_shared_config"
  "${ACP_PLATFORM_USE_CASE_DIR}/terraform/_shared_config"
)
export SHARED_CONFIG_PATHS

source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh"

if [[ -v HF_MODEL_ID ]]; then
  export HF_MODEL_ID_HASH=$(echo "${HF_MODEL_ID}" | md5sum | cut -c1-8)

  HF_MODEL_NAME="${HF_MODEL_ID##*/}"
  export HF_MODEL_NAME="${HF_MODEL_NAME,,}"
fi
