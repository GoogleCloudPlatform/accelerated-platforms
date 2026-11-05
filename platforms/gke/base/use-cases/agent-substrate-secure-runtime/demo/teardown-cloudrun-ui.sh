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

# Tears down the optional Cloud Run IAP proxy before VPC destruction.

set -euo pipefail

PROJECT_ID="${TF_VAR_platform_default_project_id:-$(gcloud config get-value project)}"
REGION="${TF_VAR_platform_default_region:-us-central1}"
RESOURCE_PREFIX="${TF_VAR_resource_name_prefix:-sec}"
SERVICE_NAME="${SERVICE_NAME:-secure-runtime-ui}"
SA_NAME="${SA_NAME:-${RESOURCE_PREFIX}-secrt-ui-sa}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" >/dev/null 2>&1; then
  echo "==> Deleting Cloud Run service ${SERVICE_NAME} in ${REGION}..."
  gcloud run services delete "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --quiet
fi

if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "==> Deleting Cloud Run ServiceAccount ${SA_EMAIL}..."
  gcloud iam service-accounts delete "${SA_EMAIL}" --project="${PROJECT_ID}" --quiet
fi
