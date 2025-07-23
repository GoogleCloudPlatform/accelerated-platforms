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

restart_build="false"
for trigger_id in "$@"; do
  echo "Checking trigger '${trigger_id}'..."
  while [ $(gcloud builds list --filter="status=WORKING AND triggerId=${trigger_id}" --format="value(substitutions.BUILD_ID)" --project="${PROJECT_ID}" --region="${LOCATION}" | wc -l) -ne 0 ]; do
    echo "Waiting for trigger build to complete"
    restart_build="true"
    sleep 5
  done
done

if [[ "${restart_build}" == "true" ]]; then
  # TODO: restart/retry build or pull new image
  return
fi
