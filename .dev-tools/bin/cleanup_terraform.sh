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

source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh"

echo "Removing .terraform directories..."
find "${ACP_REPO_DIR}" -name ".terraform" -type d
find "${ACP_REPO_DIR}" -name ".terraform" -type d -exec rm -r {} +
echo

initialize_backend_file="${ACP_REPO_DIR}/platforms/gke/base/core/initialize/backend.tf"
echo "Checking ${initialize_backend_file} file..."
if [ -f "${initialize_backend_file}" ]; then
  bucket_name=$(grep bucket "${initialize_backend_file}" | cut -d'"' -f2)

  if [[ "${bucket_name}" != "${terraform_bucket_name}" ]]; then
    echo "Bucket '${bucket_name}' does no match the configured value '${terraform_bucket_name}'"
  fi

  if gcloud storage buckets describe gs://${bucket_name} >/dev/null 2>&1; then
    echo "Bucket '${bucket_name}' exists, NOT removing backend.tf file"
  else
    echo "Removing backend file '${initialize_backend_file}'"
    rm -f "${initialize_backend_file}"
  fi
fi
echo

echo "==================================================================================="
echo "If any terraform.tfstate files are found, review and delete any unnecessary files. "
echo "==================================================================================="
echo "Searching for terraform.tfstate files..."
find "${ACP_REPO_DIR}" -name "terraform.tfstate*" -type f
