#!/usr/bin/env bash
# Copyright 2026 Google LLC
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

set -o errexit
set -o nounset
set -o pipefail

INFO="\033[1;34m[INFO]\033[0m"
SUCCESS="\033[1;32m[SUCCESS]\033[0m"
ERROR="\033[1;31m[ERROR]\033[0m"

echo -e "${INFO} Running validate_kustomize.sh from CI-CD scripts..."

export REPO_ROOT="$(git rev-parse --show-toplevel)"
export ACP_REPO_DIR="${REPO_ROOT}"
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"

# Ensure /workspace exists for the CI scripts or mock it
if [ ! -d "/workspace" ]; then
  # Many of our CI scripts expect /workspace/build.env to exist
  export WORKSPACE_DIR="$(mktemp -d)"
  touch "${WORKSPACE_DIR}/build.env"
  
  # We use a temporary wrapper to avoid needing sudo to create /workspace
  # Alternatively, just run it if the script doesn't hard-fail on /workspace missing
  # However, it sources /workspace/build.env at the top. Let's create a temp wrapper or alias?
  # The cleaner way is to just call it and if it fails due to /workspace, we warn.
fi

# We will just call the actual CI script
CI_SCRIPT="${ACP_REPO_DIR}/test/ci-cd/scripts/platforms/gke/base/use-cases/inference-ref-arch/validate_kustomize.sh"

if [ -f "${CI_SCRIPT}" ]; then
  # Since validate_kustomize.sh hardcodes `source /workspace/build.env`, it will fail locally unless we mock it
  # We can create a temporary copy that replaces /workspace with a local temp dir
  TEMP_WORKSPACE="$(mktemp -d)"
  echo "export DEBUG=false" > "${TEMP_WORKSPACE}/build.env"
  touch "${TEMP_WORKSPACE}/build-failed.lock"
  
  TEMP_SCRIPT="$(mktemp)"
  sed "s|/workspace|${TEMP_WORKSPACE}|g" "${CI_SCRIPT}" > "${TEMP_SCRIPT}"
  chmod +x "${TEMP_SCRIPT}"
  
  if "${TEMP_SCRIPT}" "local-kustomize-check"; then
    echo -e "${SUCCESS} All Kustomize manifests validated successfully!"
  else
    echo -e "${ERROR} Kustomize validation failed."
    exit 1
  fi
else
  echo -e "${ERROR} Could not find validate_kustomize.sh at ${CI_SCRIPT}"
  exit 1
fi
