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

# Deploys a stateless, zero-IAM Cloud Run IAP + Direct VPC Egress proxy in front
# of the in-cluster triage-agent-svc Internal LoadBalancer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../../../.." && pwd)"
PROJECT_ID="${TF_VAR_platform_default_project_id:-$(gcloud config get-value project)}"
REGION="${TF_VAR_platform_default_region:-us-central1}"
RESOURCE_PREFIX="${TF_VAR_resource_name_prefix:-sec}"
VPC_NETWORK="${VPC_NETWORK:-${RESOURCE_PREFIX}-secrt}"
VPC_SUBNET="${VPC_SUBNET:-${RESOURCE_PREFIX}-secrt}"
AR_REPO="${AR_REPO:-${RESOURCE_PREFIX}-secrt}"
SERVICE_NAME="${SERVICE_NAME:-secure-runtime-ui}"
SA_NAME="${SA_NAME:-${RESOURCE_PREFIX}-secrt-ui-sa}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short=12 HEAD)}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${IMAGE_TAG}"
CALLER_ACCOUNT="${IAP_ALLOWED_USER:-$(gcloud config get-value account)}"

echo "==> Resolving Internal LoadBalancer IP for agent-harness/triage-agent-svc..."
UPSTREAM_IP=""
for _ in $(seq 1 40); do
  UPSTREAM_IP="$(kubectl get svc triage-agent-svc -n agent-harness -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)"
  if [[ -n "${UPSTREAM_IP}" ]]; then
    break
  fi
  sleep 3
done
if [[ -z "${UPSTREAM_IP}" ]]; then
  echo "Error: Timed out waiting for agent-harness/triage-agent-svc Internal LoadBalancer IP." >&2
  exit 1
fi
echo "    Upstream Internal LoadBalancer: http://${UPSTREAM_IP}:80"

echo "==> Ensuring zero-privilege Cloud Run ServiceAccount ${SA_EMAIL}..."
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Secure Runtime Stateless IAP Proxy (Zero IAM)" \
    --project="${PROJECT_ID}"
fi

# Enforce least privilege: remove any legacy cluster-developer binding if present.
gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/container.developer" \
  --all \
  --quiet >/dev/null 2>&1 || true

BUILD_CTX="$(mktemp -d)"
trap 'rm -rf "${BUILD_CTX}"' EXIT
cp "${SCRIPT_DIR}/ui_server.py" "${BUILD_CTX}/ui_server.py"

cat >"${BUILD_CTX}/Dockerfile" <<'EOF'
FROM python:3.12-slim-bookworm
WORKDIR /app
COPY ui_server.py /app/ui_server.py
RUN chmod 0555 /app/ui_server.py
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp
USER 65532:65532
EXPOSE 8080
CMD ["python3", "/app/ui_server.py"]
EOF

echo "==> Building stateless proxy image ${IMAGE_URI} via Cloud Build..."
gcloud builds submit "${BUILD_CTX}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --tag="${IMAGE_URI}" \
  --quiet

echo "==> Deploying IAP-protected Cloud Run proxy ${SERVICE_NAME} -> http://${UPSTREAM_IP}:80..."
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
  --memory=512Mi \
  --timeout=300 \
  --min-instances=0 \
  --max-instances=3 \
  --set-env-vars="UPSTREAM_URL=http://${UPSTREAM_IP}:80" \
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
echo " Stateless IAP Cloud Run Proxy Live (Zero GCP IAM on ServiceAccount)"
echo "   Mission Control UI : ${SERVICE_URL}/"
echo "   Google ADK Web UI  : ${SERVICE_URL}/dev-ui/?app=secure_runtime_agent"
echo "========================================================================"
