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
retry_count=0
max_retries=5
until gcloud projects describe "${NEW_PROJECT_ID}" >/dev/null 2>&1 || \
  gcloud projects create "${NEW_PROJECT_ID}" \
    --folder="${PROJECT_CREATOR_FOLDER_ID}" \
    --impersonate-service-account="${PROJECT_CREATOR_SA}" 2>&1 | grep -v 'impersonation' || \
  [ ${retry_count} -ge ${max_retries} ]; do
  retry_count=$((retry_count + 1))
  sleep_time=$((retry_count * 5 + RANDOM % 5))
  echo "  Project creation failed with transient error, retrying (${retry_count}/${max_retries}) in ${sleep_time}s..."
  sleep ${sleep_time}
done

if ! gcloud projects describe "${NEW_PROJECT_ID}" >/dev/null 2>&1; then
  echo "Error: Failed to create project '${NEW_PROJECT_ID}' after ${max_retries} attempts." >&2
  exit 1
fi

echo "Linking billing account to project '${NEW_PROJECT_ID}'..."
retry_count=0
max_retries=5
until gcloud billing projects link "${NEW_PROJECT_ID}" \
  --billing-account="${PROJECT_CREATOR_BILLING_ACCOUNT}" \
  --impersonate-service-account="${PROJECT_CREATOR_SA}" 2>&1 | grep -v -E 'billingAccountName|impersonation' || \
  [ ${retry_count} -ge ${max_retries} ]; do
  retry_count=$((retry_count + 1))
  sleep_time=$((retry_count * 5))
  echo "  Billing account link failed with transient error, retrying (${retry_count}/${max_retries}) in ${sleep_time}s..."
  sleep ${sleep_time}
done

echo "Enabling Compute Engine API for project '${NEW_PROJECT_ID}'..."
gcloud services enable compute.googleapis.com --project="${NEW_PROJECT_ID}" 2>&1 | grep -v 'impersonation' || true

if [[ -v RESERVATIONS ]]; then
  for reservation in ${RESERVATIONS}; do
    zone=$(echo "${reservation}" | awk -F'-' '{print $(NF-2) "-" $(NF-1) "-" $NF}')

    echo "Adding project '${NEW_PROJECT_ID}' to shared reservation '${reservation}' in '${zone}'"
    retry_count=0
    max_retries=3
    until gcloud compute reservations update "${reservation}" \
      --add-share-with="${NEW_PROJECT_ID}" \
      --zone="${zone}" || [ ${retry_count} -eq ${max_retries} ]; do
      retry_count=$((retry_count + 1))
      echo "  Reservation update failed with transient error, retrying (${retry_count}/${max_retries}) in 5s..."
      sleep 5
    done
  done
fi
