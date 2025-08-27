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

STEP_ID=${1:-"Create a GitHub repository"}

exit_handler() {
  exit_code=$?

  if [ ${exit_code} -ne 0 ]; then
    echo "- ${STEP_ID}" >>/workspace/build-failed.lock
  fi

  exit 0
}
trap exit_handler EXIT

eval export NAMESPACE=\"${NAMESPACE}\"
eval export REPOSITORY=\"${REPOSITORY}\"

echo "Configure git credentials..."
git config --global user.email "github-ci@accelerated-platforms.joonix.net"
git config --global user.name "ci-accelerated-platforms"

echo "Configuring git credential helper..."
gh auth setup-git

echo "Creating GitHub repository '${NAMESPACE}/${REPOSITORY}'..."
gh repo create "${NAMESPACE}/${REPOSITORY}" \
--add-readme \
--private
