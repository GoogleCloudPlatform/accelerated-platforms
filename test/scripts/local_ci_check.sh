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

export AUTO_FIX=${AUTO_FIX:-false}
export RUN_PRETTIER=${RUN_PRETTIER:-true}
export RUN_LICENSE=${RUN_LICENSE:-true}
export RUN_KUSTOMIZE=${RUN_KUSTOMIZE:-true}
export RUN_TERRAFORM=${RUN_TERRAFORM:-true}
export RUN_TRIGGERS=${RUN_TRIGGERS:-true}

# Optional flags for sub-scripts
export RUN_TF_VALIDATE=${RUN_TF_VALIDATE:-false}
export DRY_RUN_TRIGGERS=${DRY_RUN_TRIGGERS:-false}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_CI_DIR="${SCRIPT_DIR}/local_ci"
FAILURES=0

if [ "${RUN_PRETTIER}" == "true" ]; then
  "${LOCAL_CI_DIR}/check_prettier.sh" || FAILURES=$((FAILURES + 1))
fi

if [ "${RUN_LICENSE}" == "true" ]; then
  "${LOCAL_CI_DIR}/check_license.sh" || FAILURES=$((FAILURES + 1))
fi

if [ "${RUN_KUSTOMIZE}" == "true" ]; then
  "${LOCAL_CI_DIR}/check_kustomize.sh" || FAILURES=$((FAILURES + 1))
fi

if [ "${RUN_TERRAFORM}" == "true" ]; then
  "${LOCAL_CI_DIR}/check_terraform.sh" || FAILURES=$((FAILURES + 1))
fi

"${LOCAL_CI_DIR}/check_cspell.sh" || FAILURES=$((FAILURES + 1))

if [ "${RUN_TRIGGERS}" == "true" ]; then
  if [ "${DRY_RUN_TRIGGERS}" == "true" ]; then
    "${LOCAL_CI_DIR}/check_cloudbuild_triggers.sh" --dry-run || FAILURES=$((FAILURES + 1))
  else
    "${LOCAL_CI_DIR}/check_cloudbuild_triggers.sh" || FAILURES=$((FAILURES + 1))
  fi
fi

echo ""
if [ ${FAILURES} -eq 0 ]; then
  echo -e "${SUCCESS} 🎉 All local CI checks passed! You are ready to create or update your PR."
else
  echo -e "${ERROR} ❌ ${FAILURES} check(s) failed. Please review the errors above before pushing."
  exit 1
fi
