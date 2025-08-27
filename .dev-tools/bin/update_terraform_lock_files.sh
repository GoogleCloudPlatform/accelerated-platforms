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

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

ACP_REPO_DIR=$(realpath "${MY_PATH}/../../")

terraform_version_files=$(find "${ACP_REPO_DIR}/platforms/gke/base" -name "versions.tf" -printf "\"%p\"\n" | sort)

echo "Found the following providers and versions:"
terraform_providers=$(grep --no-filename 'source' $(find "${ACP_REPO_DIR}/platforms/gke/base" -name "versions.tf") | awk '{print $3}' | sort -u)
for provider in ${terraform_providers}; do
  echo "  ${provider}"
  grep --after-context=1 --no-filename ${provider} $(find "${ACP_REPO_DIR}/platforms/gke/base" -name "versions.tf") | grep 'version' | sort -u
done
echo

for version_file in ${terraform_version_files}; do
  directory=$(dirname "${version_file//\"/}")
  echo "Updating '${directory}'..."
  cd "${directory}"
  rm -f .terraform.lock.hcl
  terraform init >/dev/null
  git add .terraform.lock.hcl versions.tf 
done
