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
  --project=${DELETE_PROJECT_ID} 2>/dev/null || true
)
echo "Found these endpoints - ${endpoints}"
for endpoint in ${endpoints}; do
  echo "    Deleting endpoint '${endpoint}'"
  gcloud endpoints services delete ${endpoint} \
  --project=${DELETE_PROJECT_ID} \
  --quiet || true
done

sleep 120 # sometimes the endpoints api takes a while to delete the endpoints

echo "Deleting project '${DELETE_PROJECT_ID}'..."

MAX_RETRIES=15
ATTEMPT=0

while true; do
  # Capture both stdout and stderr from the deletion attempt safely under errexit
  delete_output=""
  if delete_output=$(gcloud projects delete "${DELETE_PROJECT_ID}" --quiet 2>&1); then
    echo "Project '${DELETE_PROJECT_ID}' deleted successfully."
    break
  fi

  # Print the error output
  echo "${delete_output}"

  # Extract unique service IDs from error patterns like "subject: services/173305059169"
  blocking_services=$(echo "${delete_output}" | grep -o 'services/[0-9a-zA-Z._-]*' | sed 's|services/||' | sort -u || true)

  if [[ -n "${blocking_services}" ]]; then
    for svc in ${blocking_services}; do
      echo "------------------------------------------------------------"
      echo "--> Describing blocking child service: ${svc}"
      echo "------------------------------------------------------------"
      gcloud endpoints services describe "${svc}" \
        --project="${DELETE_PROJECT_ID}" \
        --format="yaml" 2>&1 || true
    done
  fi

  ATTEMPT=$((ATTEMPT + 1))
  if [ "${ATTEMPT}" -ge "${MAX_RETRIES}" ]; then
    echo "WARNING: Project deletion deferred due to pending soft-deleted child resources (e.g. Endpoints). Project will be cleaned up by background sweeper." >&2
    exit 0
  fi

  echo "Project deletion blocked by pending child resource purge. Retrying in 20s (Attempt ${ATTEMPT}/${MAX_RETRIES})..."
  sleep 20
done

