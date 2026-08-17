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

if [[ -v RESERVATIONS ]]; then
  DELETE_PROJECT_NUMBER=$(gcloud projects describe "${DELETE_PROJECT_ID}" --format="value(projectNumber)")
  for reservation in ${RESERVATIONS}; do
    zone=$(echo "${reservation}" | awk -F'-' '{print $(NF-2) "-" $(NF-1) "-" $NF}')

    echo "Deleting project '${DELETE_PROJECT_ID}(${DELETE_PROJECT_NUMBER})' from shared reservation '${reservation}' in '${zone}'"
    gcloud compute reservations update "${reservation}" \
      --remove-share-with="${DELETE_PROJECT_NUMBER}" \
      --zone="${zone}"
  done
fi

endpoints=$(
  gcloud endpoints services list \
  --format="value(serviceName)" \
  --project="${DELETE_PROJECT_ID}" 2>/dev/null
)
for endpoint in ${endpoints}; do
  echo "    Deleting endpoint '${endpoint}'"
  gcloud endpoints services delete "${endpoint}" \
    --project="${DELETE_PROJECT_ID}" \
    --quiet
done

echo "Deleting project '${DELETE_PROJECT_ID}'..."

MAX_RETRIES=15
ATTEMPT=0
BASE_SLEEP=15
MAX_SLEEP=45

while true; do
  ATTEMPT=$((ATTEMPT + 1))
  delete_output=""
  if delete_output=$(gcloud projects delete "${DELETE_PROJECT_ID}" --quiet 2>&1); then
    echo "Successfully deleted project '${DELETE_PROJECT_ID}'."
    break
  fi

  # Idempotency check in case the deletion transitioned state on retry
  if [[ "${delete_output}" == *"DELETE_REQUESTED"* ]]; then
    echo "Project '${DELETE_PROJECT_ID}' is already in DELETE_REQUESTED state."
    break
  fi

  if [ "${ATTEMPT}" -ge "${MAX_RETRIES}" ]; then
    echo "ERROR: Failed to delete project '${DELETE_PROJECT_ID}' after ${MAX_RETRIES} attempts." >&2
    echo "${delete_output}" >&2
    exit 1
  fi

  # Calculate exponential cap: min(MAX_SLEEP, BASE_SLEEP * 1.5^(ATTEMPT - 1))
  factor=$(( 10 + (ATTEMPT - 1) * 3 ))
  current_cap=$(( (BASE_SLEEP * factor) / 10 ))
  if [ "${current_cap}" -gt "${MAX_SLEEP}" ]; then
    current_cap="${MAX_SLEEP}"
  fi

  # Full jitter: random sleep between 10s and current_cap
  jitter_range=$(( current_cap - 10 + 1 ))
  sleep_seconds=$(( 10 + RANDOM % jitter_range ))

  echo "Project deletion blocked by pending child resource purge (Attempt ${ATTEMPT}/${MAX_RETRIES}). Retrying in ${sleep_seconds}s (with jitter)..."
  sleep "${sleep_seconds}"
done

