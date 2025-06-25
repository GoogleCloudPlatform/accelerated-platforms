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

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

source "${MY_PATH}/helpers/git.sh"

ACP_REPO_DIR="$(realpath ${MY_PATH}/../../)"

for file in "${git_assume_unchanged_files[@]}"; do
  echo "no-assume-unchanged ${file}"
  git update-index --no-assume-unchanged ${ACP_REPO_DIR}/${file}
done

echo "Removing the .dev-tools/.gitignore file"
cd "${ACP_REPO_DIR}" &&
  git config core.excludesfile "" &&
  cd - &>/dev/null
