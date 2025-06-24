#!/usr/bin/env bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../)"

cd "${ACP_REPO_DIR}/.github/workflows/dictionary" ||
  {
    echo "Dictionary folder '${ACP_REPO_DIR}/.github/workflows/dictionary' does not exist, exiting!" >&2
    exit 1
  }

return_code=0
for file in *.txt; do
  echo "Checking ${file}..."

  file_content=$(<"${file}")
  lowercase_content=${file_content,,}

  sorted_content=$(echo "${lowercase_content}" | sort)
  sorted_count=$(echo "${sorted_content}" | wc -l)

  unique_content=$(echo "${sorted_content}" | uniq)
  unique_count=$(echo "${unique_content}" | wc -l)

  if [[ "${file_content}" != "${lowercase_content}" ]]; then
    echo -e "  - The content of '${file}' contains uppercase characters." >&2
    return_code=$((return_code + 1))
  fi

  if [[ "${file_content}" != "${sorted_content}" ]]; then
    echo -e "  - The content of '${file}' is not sorted." >&2
    return_code=$((return_code + 1))
  fi

  if [[ "${sorted_count}" != "${unique_count}" ]]; then
    echo -e "  - The content of '${file}' contains non-unique values." >&2
    return_code=$((return_code + 1))
  fi
done
echo -e "\nError(s) detected: ${return_code}"

exit ${return_code}
