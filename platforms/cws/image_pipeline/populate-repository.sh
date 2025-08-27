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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "${0}")" >/dev/null 2>&1
  pwd -P
)"
MY_NAME=$(basename "${0}" .sh)

ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../")"
ACP_PLATFORM_DIR="${ACP_REPO_DIR}/platforms/cws"
ACP_PLATFORM_STACK_DIR="${ACP_PLATFORM_DIR}/image_pipeline"

template_dir=${1:-"${ACP_PLATFORM_STACK_DIR}/repository-template"}
repository_dir=${2:-"${ACP_PLATFORM_STACK_DIR}/repository"}

# shellcheck source=/dev/null
source "${ACP_PLATFORM_STACK_DIR}/_shared_config/scripts/set_environment_variables.sh"

cd "${MY_PATH}" || exit 1
files=$(find "${template_dir}" -type f)

export skip="$"
for file in ${files}; do
  file_path=${file#"${template_dir}/"}
  file_dirname=$(dirname "${file_path}")
  new_file_dir="${repository_dir}/${file_dirname}"
  new_file_name=$(basename "${file_path}")
  new_file="${new_file_dir}/${new_file_name}"

  echo "Processing ${file_path}"
  mkdir -p "${new_file_dir}"
  envsubst < "${file}" > "${new_file}"
done
