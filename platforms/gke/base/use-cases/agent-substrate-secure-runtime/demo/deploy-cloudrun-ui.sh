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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ID="${TF_VAR_platform_default_project_id:-$(gcloud config get-value project)}"
REGION="${TF_VAR_platform_default_region:-us-central1}"
CLUSTER_NAME="${GKE_CLUSTER_NAME:-sec-secrt}"
VPC_NETWORK="${VPC_NETWORK:-sec-secrt}"
VPC_SUBNET="${VPC_SUBNET:-sec-secrt}"
AR_REPO="${AR_REPO:-sec-secrt}"
SERVICE_NAME="${SERVICE_NAME:-secure-runtime-ui}"
SA_NAME="${SA_NAME:-sec-secrt-ui-sa}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:latest"
CALLER_ACCOUNT="${IAP_ALLOWED_USER:-$(gcloud config get-value account)}"

echo "==> Ensuring Cloud Run ServiceAccount ${SA_EMAIL}..."
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Secure Runtime Mission Control Cloud Run UI" \
    --project="${PROJECT_ID}"
fi

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/container.developer" \
  --condition=None \
  --quiet >/dev/null

BUILD_CTX="$(mktemp -d)"
trap 'rm -rf "${BUILD_CTX}"' EXIT
cp "${SCRIPT_DIR}/ui_server.py" "${BUILD_CTX}/ui_server.py"

cat >"${BUILD_CTX}/Dockerfile" <<'EOF'
FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    kubectl \
    google-cloud-cli-gke-gcloud-auth-plugin \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY ui_server.py /app/ui_server.py
ENV HOME=/tmp \
    USE_GKE_GCLOUD_AUTH_PLUGIN=True \
    PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3", "/app/ui_server.py"]
EOF

echo "==> Building ${IMAGE_URI} via Cloud Build..."
gcloud builds submit "${BUILD_CTX}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${IMAGE_URI}" \
  --quiet

echo "==> Deploying IAP-protected Cloud Run service ${SERVICE_NAME} with Direct VPC Egress (${VPC_NETWORK}/${VPC_SUBNET})..."
gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE_URI}" \
  --service-account="${SA_EMAIL}" \
  --network="${VPC_NETWORK}" \
  --subnet="${VPC_SUBNET}" \
  --vpc-egress=private-ranges-only \
  --iap \
  --no-allow-unauthenticated \
  --cpu=1 \
  --memory=1Gi \
  --timeout=300 \
  --min-instances=0 \
  --max-instances=3 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GKE_CLUSTER_NAME=${CLUSTER_NAME},GKE_CLUSTER_LOCATION=${REGION}" \
  --quiet

echo "==> Granting IAP access (roles/iap.httpsResourceAccessor) to user:${CALLER_ACCOUNT}..."
gcloud iap web add-iam-policy-binding \
  --project="${PROJECT_ID}" \
  --resource-type=cloud-run \
  --region="${REGION}" \
  --service="${SERVICE_NAME}" \
  --member="user:${CALLER_ACCOUNT}" \
  --role="roles/iap.httpsResourceAccessor" \
  --quiet >/dev/null

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo ""
echo "========================================================================"
echo " Cloud Run Frontend Live (IAP-Protected — No Cloudtop Needed!)"
echo "   Mission Control UI : ${SERVICE_URL}/"
echo "   Google ADK Web UI  : ${SERVICE_URL}/dev-ui/?app=secure_runtime_agent"
echo "========================================================================"
