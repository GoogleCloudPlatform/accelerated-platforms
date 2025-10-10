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

STEP_ID=${1:-"Check project builds"}

exit_handler() {
  exit_code=$?

  if [ ${exit_code} -ne 0 ]; then
    echo "- ${STEP_ID}" >>/workspace/build-failed.lock
  fi

  exit 0
}
trap exit_handler EXIT

eval export BUILD_LOCATION=\"${BUILD_LOCATION}\"
eval export BUILD_PROJECT_ID=\"${BUILD_PROJECT_ID}\"

echo "Checking for running build(s) in project ID '${BUILD_PROJECT_ID}' in region '${BUILD_LOCATION}''..."
while [ $(gcloud builds list --filter="status=WORKING" --format="value(id)" --project="${BUILD_PROJECT_ID}" --region="${BUILD_LOCATION}" | wc -l) -ne 0 ]; do
  echo "Waiting for build(s) to complete..."
  gcloud builds list --filter="status=WORKING" --format="value(id, substitutions.TRIGGER_NAME, status)" --project="${BUILD_PROJECT_ID}" --region="${BUILD_LOCATION}"
  echo
  sleep 30
done

echo "Checking for failed build(s) in project ID '${BUILD_PROJECT_ID}' in region '${BUILD_LOCATION}''..."
failed_builds=$(gcloud builds list --filter="(status=\"CANCELLED\" OR status=\"FAILURE\" OR status=\"TIMEOUT\")" --format="value(id, substitutions.TRIGGER_NAME, status)" --project="${BUILD_PROJECT_ID}" --region="${BUILD_LOCATION}" | wc -l)
if [ ${failed_builds} -ne 0 ]; then
  echo "The following build trigger(s) failed:"
  gcloud builds list --filter="(status=\"CANCELLED\" OR status=\"FAILURE\" OR status=\"TIMEOUT\")" --format="value(id, substitutions.TRIGGER_NAME, status)" --project="${BUILD_PROJECT_ID}" --region="${BUILD_LOCATION}"
  exit 1
fi
