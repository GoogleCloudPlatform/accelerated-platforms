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

echo "Accessing 'project-creator-service-account' secret..."
PROJECT_CREATOR_SA=$(gcloud secrets versions access latest \
  --project="accelerated-platforms" \
  --secret="project-creator-service-account")

echo "Accessing 'project-creator-billing-account-id' secret..."
PROJECT_CREATOR_BILLING_ACCOUNT=$(gcloud secrets versions access latest \
  --impersonate-service-account="${PROJECT_CREATOR_SA}" \
  --project="accelerated-platforms" \
  --secret="project-creator-billing-account-id" 2>&1 | grep -v 'impersonation')

echo "Accessing 'project-creator-folder-id' secret..."
PROJECT_CREATOR_FOLDER_ID=$(gcloud secrets versions access latest \
  --impersonate-service-account="${PROJECT_CREATOR_SA}" \
  --project="accelerated-platforms" \
  --secret="project-creator-folder-id" 2>&1 | grep -v 'impersonation')

echo "Creating project '${NEW_PROJECT_ID}'..."
gcloud projects create "${NEW_PROJECT_ID}" \
  --folder="${PROJECT_CREATOR_FOLDER_ID}" \
  --impersonate-service-account="${PROJECT_CREATOR_SA}" 2>&1 | grep -v 'impersonation'

echo "Linking billing account to project '${NEW_PROJECT_ID}'..."
gcloud billing projects link "${NEW_PROJECT_ID}" \
  --billing-account="${PROJECT_CREATOR_BILLING_ACCOUNT}" \
  --impersonate-service-account="${PROJECT_CREATOR_SA}" 2>&1 | grep -v -E 'billingAccountName|impersonation'

if [[ -v RESERVATIONS ]]; then
  for reservation in ${RESERVATIONS}; do
    zone=$(echo "${reservation}" | awk -F'-' '{print $(NF-2) "-" $(NF-1) "-" $NF}')

    echo "Adding project '${NEW_PROJECT_ID}' to shared reservation '${reservation}' in '${zone}'"
    gcloud compute reservations update "${reservation}" \
      --add-share-with="${NEW_PROJECT_ID}" \
      --zone="${zone}"
  done
fi
