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

if [ "${DEBUG,,}" == "true" ]; then
  set -o xtrace
fi

ACP_REPO_DIR="/workspace"

# Use the truncated BUILD_ID as project suffix.
# Truncate it at 8 characters similar to short build ID
PROJECT_SUFFIX="${BUILD_ID:0:8}"

cat >/workspace/build.env <<EOT
#export NO_COLOR="1"
export TERM="xterm"
#export TF_CLI_ARGS="-no-color"
#export TF_IN_AUTOMATION="1"

export ACP_REPO_DIR="${ACP_REPO_DIR}"
export ACP_PLATFORM_BASE_DIR="\${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_CORE_DIR="\${ACP_PLATFORM_BASE_DIR}/core"
export PROJECT_SUFFIX=${PROJECT_SUFFIX}

EOT

while [ $# -gt 0 ]; do
  echo "export $1" >>/workspace/build.env
  shift
done

cat /workspace/build.env
source /workspace/build.env

source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh"

# Create a dedicated project
export NEW_PROJECT_ID="${cluster_project_id}"
${ACP_REPO_DIR}/test/ci-cd/scripts/create_project.sh
