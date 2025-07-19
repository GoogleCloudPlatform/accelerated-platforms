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

JSON_INPUT=$(</dev/stdin)
eval "$(jq -n "${JSON_INPUT}" | jq -r 'to_entries[] | "\(.key | ascii_upcase)=\(.value | @sh)"')"

retries="${RETRIES}"
wait_time="${WAIT_DELAY}"
while true; do
  if ((retries < 0)); then
    exit 1
  fi

  backend_service=$(gcloud compute backend-services list --project="${PROJECT_ID}" --filter="iap.oauth2ClientId=${OAUTH2_CLIENT_ID}" --format="json(name)")
  if [ "${backend_service}" != "[]" ]; then
    break
  fi

  echo "Waiting for backend service to be created..." >&2
  retries=$((retries - 1))
  sleep "${wait_time}"
done

echo "${backend_service}" | jq .[0]
