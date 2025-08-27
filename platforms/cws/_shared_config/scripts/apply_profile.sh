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

MY_PATH="$(
  cd "$(dirname "${0}")" >/dev/null 2>&1
  pwd -P
)"
MY_NAME=$(basename "${0}" .sh)

ACP_REPO_DIR=$(realpath "${MY_PATH}/../../../../")
ACP_CWS_PROFILE_DIR="${ACP_REPO_DIR}/platforms/cws/_shared_config/profile"

declare -a required_tfvars_files=(
  "build.auto.tfvars"
  "comfyui.auto.tfvars"
  "networking.auto.tfvars"
  "platform.auto.tfvars"
  "workstation_cluster.auto.tfvars"
)

profile_name=${1:-"default"}
echo "Verifying '${profile_name}' profile..."
if [[ ! -d "${ACP_CWS_PROFILE_DIR}/${profile_name}" ]]; then
  echo "Profile ${profile_name}(${ACP_CWS_PROFILE_DIR}/${profile_name}) does not exists, exiting!"
  exit 1
fi

missing_required_file=false
for required_tfvars_file in "${required_tfvars_files[@]}"; do
  if [[ ! -f "${ACP_CWS_PROFILE_DIR}/${profile_name}/${required_tfvars_file}" ]]; then
    echo "Missing required .tfvars file '${ACP_CWS_PROFILE_DIR}/${profile_name}/${required_tfvars_file}'"
    missing_required_file=true
  fi
done

if ${missing_required_file}; then
  echo "Required .tfvars file(s) are missing, exiting!"
  exit 2
fi

echo "Applying '${profile_name}' profile..."
cd "${MY_PATH}/.."
ln --force --symbolic "profile/${profile_name}"/* ./

echo "Initializing the platform..."
"${ACP_REPO_DIR}/platforms/cws/bin/cws_initialize.sh"
