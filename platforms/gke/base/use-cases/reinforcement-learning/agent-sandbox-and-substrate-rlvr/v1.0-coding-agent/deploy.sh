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

echo "==> [1/7] Setting project and enabling required Google Cloud APIs..."
gcloud config set project "$PROJECT_ID"
gcloud services enable \
  container.googleapis.com \
  compute.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com \
  cloudtrace.googleapis.com \
  telemetry.googleapis.com

echo "==> [2/7] Creating custom VPC, Subnets, and Artifact Registry..."
gcloud compute networks create "$NETWORK_NAME" --subnet-mode=custom || true
gcloud compute networks subnets create "$SUBNET_NAME" \
  --network="$NETWORK_NAME" --region="$REGION" --range=10.0.0.0/20 || true
gcloud compute networks subnets create "$PROXY_SUBNET_NAME" \
  --network="$NETWORK_NAME" --region="$REGION" \
  --purpose=REGIONAL_MANAGED_PROXY --role=ACTIVE --range=192.168.10.0/24 || true
gcloud artifacts repositories create agent-repo \
  --repository-format=docker --location="$REGION" \
  --description="Docker repository for ADK Coding Agent" || true

echo "==> [3/7] Creating GKE Cluster ($CLUSTER_NAME) and gVisor Sandbox Node Pool..."
gcloud beta container clusters create "$CLUSTER_NAME" \
  --zone="$ZONE" \
  --network="$NETWORK_NAME" \
  --subnetwork="$SUBNET_NAME" \
  --release-channel=rapid \
  --machine-type=e2-standard-4 \
  --num-nodes=3 \
  --workload-pool="${PROJECT_ID}.svc.id.goog" \
  --managed-opentelemetry-scope=COLLECTION_AND_INSTRUMENTATION_COMPONENTS \
  --monitoring=SYSTEM,WORKLOAD \
  --logging=SYSTEM,WORKLOAD || true

gcloud container node-pools create sandbox-pool \
  --cluster="$CLUSTER_NAME" \
  --zone="$ZONE" \
  --machine-type=e2-standard-4 \
  --num-nodes=2 \
  --sandbox type=gvisor || true

gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE"

echo "==> [4/7] Installing GKE Agent Sandbox Controller (v0.1.0), cert-manager & OpenTelemetry Operator..."
export VERSION="v0.1.0"
kubectl apply -f "https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${VERSION}/manifest.yaml"
kubectl apply -f "https://github.com/kubernetes-sigs/agent-sandbox/releases/download/${VERSION}/extensions.yaml"

kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.16.2/cert-manager.yaml
kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=180s

kubectl apply -f https://github.com/open-telemetry/opentelemetry-operator/releases/latest/download/opentelemetry-operator.yaml
kubectl wait --for=condition=Available deployment/opentelemetry-operator-controller-manager -n opentelemetry-operator-system --timeout=180s

echo "==> [5/7] Building ADK Coding Agent Image via Cloud Build..."
gcloud builds submit --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-repo/code-agent:v1" .

echo "==> [6/7] Configuring ROUTER_AUTH_TOKEN Secret, gVisor WarmPool, Router, and Zero-Trust NetworkPolicy..."
kubectl create namespace agent-sandbox --dry-run=client -o yaml | kubectl apply -f -
TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
kubectl create secret generic sandbox-router-secret -n agent-sandbox \
  --from-literal=ROUTER_AUTH_TOKEN="$TOKEN" --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic sandbox-router-secret -n default \
  --from-literal=ROUTER_AUTH_TOKEN="$TOKEN" --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f sandbox-template-and-pool.yaml
kubectl apply -f sandbox-policy.yaml
kubectl apply -f sandbox-router.yaml

echo "==> [7/7] Binding Workload Identity IAM & Deploying ADK Coding Agent..."
MEMBER="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/default/sa/adk-agent-sa"
for ROLE in roles/logging.logWriter roles/cloudtrace.agent roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="$MEMBER" --role="$ROLE" --condition=None --quiet
done

kubectl apply -f otel-instrumentation.yaml
kubectl create configmap code-agent-source -n default --from-file=agent.py=root_agent/agent.py --dry-run=client -o yaml | kubectl apply -f -

envsubst '${PROJECT_ID} ${REGION}' < agent-deployment.yaml | kubectl apply -f -
kubectl rollout status deployment/code-agent -n default --timeout=120s

echo "==> Deployment Complete! Waiting for External IP..."
kubectl get svc code-agent-service -n default
