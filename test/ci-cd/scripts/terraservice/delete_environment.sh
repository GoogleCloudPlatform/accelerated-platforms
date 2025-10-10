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

source "${ACP_PLATFORM_DIR}/_shared_config/scripts/set_environment_variables.sh"

export DELETE_PROJECT_ID="${cluster_project_id}"
${ACP_REPO_DIR}/test/ci-cd/scripts/delete_project.sh
