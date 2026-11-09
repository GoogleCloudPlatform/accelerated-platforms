#!/usr/bin/env bash
# Copyright 2026 Google LLC
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

# create-cluster.sh — Rapid (~4 min) GKE 1.37 cluster creation for the Agent Substrate
# 4-Act Security & Detonation Demo. Supports C4 (c4-standard-4), N4 (n4-standard-4),
# or C3 (c3-standard-4) with automatic Hyperdisk / PD boot disk selection.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
CLUSTER_NAME="${CLUSTER_NAME:-agent-substrate-live}"
CLUSTER_LOCATION="${CLUSTER_LOCATION:-us-central1-b}"
if [[ -z "${REGION:-}" ]]; then
  if [[ "${CLUSTER_LOCATION}" =~ -[a-z]$ ]]; then
    REGION="${CLUSTER_LOCATION%-*}"
  else
    REGION="${CLUSTER_LOCATION}"
  fi
fi
MACHINE_TYPE="${MACHINE_TYPE:-n4-standard-4}"
if [[ -z "${DISK_TYPE:-}" ]]; then
  if [[ "${MACHINE_TYPE}" =~ ^(c4|n4)- ]]; then
    DISK_TYPE="hyperdisk-balanced"
  else
    DISK_TYPE="pd-balanced"
  fi
fi
NUM_NODES="${NUM_NODES:-2}"
NETWORK="${NETWORK:-ai-agent-network}"
SUBNETWORK="${SUBNETWORK:-ai-agent-subnet}"

[[ -n "${PROJECT_ID}" ]] || { echo "Error: set PROJECT_ID=<gcp-project-id>" >&2; exit 1; }

echo "==> 1/4: Ensuring VPC network (${NETWORK}) and subnetwork (${SUBNETWORK}) in ${PROJECT_ID}"
gcloud services enable container.googleapis.com compute.googleapis.com --project "${PROJECT_ID}"
if ! gcloud compute networks describe "${NETWORK}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks create "${NETWORK}" --project "${PROJECT_ID}" --subnet-mode=custom
fi
if ! gcloud compute networks subnets describe "${SUBNETWORK}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks subnets create "${SUBNETWORK}" \
    --project "${PROJECT_ID}" \
    --network "${NETWORK}" \
    --region "${REGION}" \
    --range "10.0.0.0/20"
fi

echo "==> 2/4: Creating GKE 1.37 cluster '${CLUSTER_NAME}' (${MACHINE_TYPE}, ${DISK_TYPE}, ${NUM_NODES} nodes) in ${CLUSTER_LOCATION}"
gcloud beta container clusters create "${CLUSTER_NAME}" \
  --project "${PROJECT_ID}" \
  --location "${CLUSTER_LOCATION}" \
  --network "${NETWORK}" \
  --subnetwork "${SUBNETWORK}" \
  --enable-dataplane-v2 \
  --release-channel rapid \
  --cluster-version 1.37 \
  --machine-type "${MACHINE_TYPE}" \
  --disk-type "${DISK_TYPE}" \
  --disk-size 100 \
  --num-nodes "${NUM_NODES}" \
  --node-labels "workload=agent-substrate" \
  --workload-pool "${PROJECT_ID}.svc.id.goog" \
  --enable-managed-prometheus \
  --managed-otel-scope=COLLECTION_AND_INSTRUMENTATION_COMPONENTS

echo "==> 3/4: Adding 7-day maintenance exclusion window (workshop-freeze)"
read -r START_TIME END_TIME < <(
  python3 - <<'EOF'
import datetime
now = datetime.datetime.now(datetime.timezone.utc)
start = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
end = (now + datetime.timedelta(days=7)).strftime("%Y-%m-%dT00:00:00Z")
print(f"{start} {end}")
EOF
)
gcloud container clusters update "${CLUSTER_NAME}" \
  --project "${PROJECT_ID}" \
  --location "${CLUSTER_LOCATION}" \
  --add-maintenance-exclusion-name workshop-freeze \
  --add-maintenance-exclusion-start "${START_TIME}" \
  --add-maintenance-exclusion-end "${END_TIME}" \
  --add-maintenance-exclusion-scope no_minor_or_node_upgrades

echo "==> 4/4: Configuring kubeconfig and dynamic-rwo (hyperdisk-balanced) default StorageClass"
gcloud container clusters get-credentials "${CLUSTER_NAME}" \
  --project "${PROJECT_ID}" \
  --location "${CLUSTER_LOCATION}"
if kubectl get sc dynamic-rwo >/dev/null 2>&1; then
  kubectl annotate sc standard-rwo storageclass.kubernetes.io/is-default-class=false --overwrite >/dev/null 2>&1 || true
  kubectl annotate sc dynamic-rwo storageclass.kubernetes.io/is-default-class=true --overwrite >/dev/null 2>&1 || true
fi
echo "✅ Cluster '${CLUSTER_NAME}' is ready!"
