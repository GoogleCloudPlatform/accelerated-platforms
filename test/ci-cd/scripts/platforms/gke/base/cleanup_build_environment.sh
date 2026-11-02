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

STEP_ID=${1}

exit_handler() {
  exit_code=$?

  if [ ${exit_code} -ne 0 ]; then
    echo "- ${STEP_ID}" >>/workspace/build-failed.lock
  fi

  exit 0
}
trap exit_handler EXIT

set --
source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh"

DIAGNOSTICS_SCRIPT="${ACP_REPO_DIR}/test/ci-cd/scripts/platforms/gke/base/print_build_diagnostics.sh"

# Capture diagnostics before the project is deleted. These are informational
# only and never fail the step.
if [ -e /workspace/build-failed.lock ]; then
  # Operations (including failed ones) for clusters that the teardown already
  # deleted, and any clusters that the teardown left behind.
  "${DIAGNOSTICS_SCRIPT}" cluster || true
fi
"${DIAGNOSTICS_SCRIPT}" project || true

# Delete the dedicated project
#
# Cloud Endpoints services keep a project from being deleted for about 60
# minutes after they're created (see #590), which can be longer than the time
# left in the build. If the deletion is still blocked by child resources after
# DELETE_PROJECT_TIMEOUT, log a warning and leave the project to the hourly
# project cleaner (test/ci-cd/cloudbuild/ci-cd/project-cleaner.yaml), which
# deletes CI projects whose build is no longer running.
DELETE_PROJECT_TIMEOUT="${DELETE_PROJECT_TIMEOUT:-10m}"

export DELETE_PROJECT_ID="${platform_default_project_id}"
delete_project_log=$(mktemp)
delete_project_exit_code=0
timeout "${DELETE_PROJECT_TIMEOUT}" "${ACP_REPO_DIR}/test/ci-cd/scripts/delete_project.sh" 2>&1 |
  tee "${delete_project_log}" || delete_project_exit_code=$?

if [ "${delete_project_exit_code}" -ne 0 ]; then
  echo "Deleting project '${DELETE_PROJECT_ID}' didn't finish (exit code ${delete_project_exit_code})"
  "${DIAGNOSTICS_SCRIPT}" project-delete-failure "${delete_project_log}" || true

  # Check why the project still exists
  final_delete_output=""
  if final_delete_output=$(gcloud projects delete "${DELETE_PROJECT_ID}" --quiet 2>&1); then
    echo "Successfully deleted project '${DELETE_PROJECT_ID}'."
    exit 0
  fi
  echo "${final_delete_output}"

  if [[ "${final_delete_output}" == *"DELETE_REQUESTED"* ]]; then
    echo "Project '${DELETE_PROJECT_ID}' is already in DELETE_REQUESTED state."
    exit 0
  fi

  if [[ "${final_delete_output}" == *"PROJECT_DELETE_CHILD_RESOURCE"* ]] ||
    [[ "${final_delete_output}" == *"has active or recent created child resources"* ]]; then
    echo "WARNING: Deleting project '${DELETE_PROJECT_ID}' is blocked by child resources that are still being purged."
    echo "WARNING: Leaving the project to the project cleaner, which deletes it after its build is no longer running."
    exit 0
  fi

  exit 1
fi
