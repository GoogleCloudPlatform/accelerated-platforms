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

: "${PROJECT_ID:?Please set export PROJECT_ID=your-gcp-project-id before running this script}"
export PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
export REGION="${REGION:-us-central1}"
export ZONE="${ZONE:-us-central1-a}"
export CLUSTER_NAME="${CLUSTER_NAME:-ai-agent-cluster}"
export NETWORK_NAME="${NETWORK_NAME:-ai-agent-network}"
export SUBNET_NAME="${SUBNET_NAME:-ai-agent-subnet}"
export PROXY_SUBNET_NAME="${PROXY_SUBNET_NAME:-proxy-only-subnet}"

echo "==> [1/5] Deleting Kubernetes LoadBalancer Service to release external forwarding rule..."
kubectl delete svc code-agent-service -n default --ignore-not-found || true

echo "==> [2/5] Deleting GKE Cluster ($CLUSTER_NAME)..."
gcloud container clusters delete "$CLUSTER_NAME" \
  --zone="$ZONE" \
  --project="$PROJECT_ID" \
  --quiet || true

echo "==> [3/5] Deleting Artifact Registry repository (agent-repo)..."
gcloud artifacts repositories delete agent-repo \
  --location="$REGION" \
  --project="$PROJECT_ID" \
  --quiet || true

echo "==> [4/5] Deleting Custom VPC Subnets and Network ($NETWORK_NAME)..."
gcloud compute networks subnets delete "$SUBNET_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --quiet || true

gcloud compute networks subnets delete "$PROXY_SUBNET_NAME" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --quiet || true

gcloud compute networks delete "$NETWORK_NAME" \
  --project="$PROJECT_ID" \
  --quiet || true

echo "==> [5/5] Removing Workload Identity IAM policy bindings..."
MEMBER="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/default/sa/adk-agent-sa"
for ROLE in roles/logging.logWriter roles/cloudtrace.agent roles/aiplatform.user; do
  gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
    --member="$MEMBER" \
    --role="$ROLE" \
    --condition=None \
    --quiet || true
done

echo "==> Cleanup Complete!"
