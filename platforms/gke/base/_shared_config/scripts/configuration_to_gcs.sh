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
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

echo "Uploading Kubernetes files..."
gcloud storage cp \
  --preserve-posix \
  --preserve-symlinks \
  --recursive \
  "${MY_PATH}/../../kubernetes" \
  "gs://${terraform_bucket_name}/terraform/configuration/kubernetes"

if [[ ! -v SHARED_CONFIG_PATHS ]]; then
  SHARED_CONFIG_PATHS=("${@}")
fi

for SHARED_CONFIG_PATH in "${SHARED_CONFIG_PATHS[@]}"; do
  echo "Uploading configurations(${SHARED_CONFIG_PATH})..."
  bucket_folder=${SHARED_CONFIG_PATH#*/gke/base/}
  gcloud storage cp \
    --preserve-posix \
    --preserve-symlinks \
    "${SHARED_CONFIG_PATH}/*" \
    "gs://${terraform_bucket_name}/terraform/configuration/${bucket_folder}"
done
