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
  --project=${DELETE_PROJECT_ID} 2>/dev/null
)
for endpoint in ${endpoints}; do
  echo "    Deleting endpoint '${endpoint}'"
  gcloud endpoints services delete ${endpoint} \
  --project=${DELETE_PROJECT_ID} \
  --quiet
done

echo "Deleting project '${DELETE_PROJECT_ID}'..."
gcloud projects delete "${DELETE_PROJECT_ID}" \
  --quiet
