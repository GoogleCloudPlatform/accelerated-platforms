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

# create-cluster.sh — Standalone GKE 1.37+ cluster creation (Option A) with private
# worker nodes, Cloud NAT, control-plane DNS endpoint, dedicated least-privilege
# node ServiceAccount, deterministic non-overlapping subnet CIDRs, and stockout timeout.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
CLUSTER_NAME="${CLUSTER_NAME:-agent-substrate-live}"
CLUSTER_LOCATION="${CLUSTER_LOCATION:-us-central1-b}"
GKE_VERSION="${GKE_VERSION:-1.37}"
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
SUBNETWORK="${SUBNETWORK:-ai-agent-subnet-${REGION}}"
ROUTER_NAME="${ROUTER_NAME:-${NETWORK}-router-${REGION}}"
NAT_NAME="${NAT_NAME:-${NETWORK}-nat-${REGION}}"
CLEAN_CLUSTER_SLUG="$(printf '%s' "${CLUSTER_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | cut -c1-18 | sed 's/-\+$//')"
NODE_SA_NAME="${NODE_SA_NAME:-ate-nodes-${CLEAN_CLUSTER_SLUG:-gke}}"
NODE_SA_EMAIL="${NODE_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

[[ -n "${PROJECT_ID}" ]] || { echo "Error: set PROJECT_ID=<gcp-project-id>" >&2; exit 1; }

select_subnet_cidr() {
  if [[ -n "${SUBNET_RANGE:-}" ]]; then
    printf '%s' "${SUBNET_RANGE}"
    return 0
  fi
  local existing
  existing="$(gcloud compute networks subnets list --project "${PROJECT_ID}" --network "${NETWORK}" --format='value(ipCidrRange)' 2>/dev/null || true)"
  python3 - "${REGION}" "${existing}" <<'EOF'
import hashlib, ipaddress, sys
region = sys.argv[1]
used = [ipaddress.ip_network(line.strip(), strict=False) for line in sys.argv[2].splitlines() if line.strip()]
seed = int(hashlib.sha256(region.encode("utf-8")).hexdigest()[:4], 16)
for step in range(256):
    second = 128 + ((seed + step) % 64)
    third = (((seed >> 6) + step) * 16) % 256
    cand = ipaddress.ip_network(f"10.{second}.{third}.0/20")
    if not any(cand.overlaps(u) for u in used):
        print(str(cand))
        sys.exit(0)
sys.exit("Unable to allocate non-overlapping /20 subnet CIDR; set SUBNET_RANGE explicitly.")
EOF
}

echo "==> 1/5: Enabling APIs and ensuring VPC (${NETWORK}), Subnet (${SUBNETWORK}), and Cloud NAT in ${REGION}"
gcloud services enable container.googleapis.com compute.googleapis.com iam.googleapis.com --project "${PROJECT_ID}"
if ! gcloud compute networks describe "${NETWORK}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute networks create "${NETWORK}" --project "${PROJECT_ID}" --subnet-mode=custom
fi
if ! gcloud compute networks subnets describe "${SUBNETWORK}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  CHOSEN_CIDR="$(select_subnet_cidr)"
  gcloud compute networks subnets create "${SUBNETWORK}" \
    --project "${PROJECT_ID}" \
    --network "${NETWORK}" \
    --region "${REGION}" \
    --range "${CHOSEN_CIDR}" \
    --enable-private-ip-google-access
fi
if ! gcloud compute routers describe "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute routers create "${ROUTER_NAME}" \
    --project "${PROJECT_ID}" \
    --network "${NETWORK}" \
    --region "${REGION}"
fi
if ! gcloud compute routers nats describe "${NAT_NAME}" --router "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud compute routers nats create "${NAT_NAME}" \
    --project "${PROJECT_ID}" \
    --router "${ROUTER_NAME}" \
    --region "${REGION}" \
    --auto-allocate-nat-external-ips \
    --nat-all-subnet-ip-ranges
fi

retry_iam() {
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if "$@" >/dev/null 2>&1; then
      return 0
    fi
    sleep $((attempt * 2))
  done
  "$@" >/dev/null
}

echo "==> 2/5: Ensuring least-privilege GKE node ServiceAccount (${NODE_SA_EMAIL})"
if ! gcloud iam service-accounts describe "${NODE_SA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${NODE_SA_NAME}" \
    --project "${PROJECT_ID}" \
    --display-name "Agent Substrate GKE Worker Nodes (${CLUSTER_NAME})"
fi
for role in \
  roles/container.defaultNodeServiceAccount \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/stackdriver.resourceMetadata.writer \
  roles/artifactregistry.reader; do
  retry_iam gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${NODE_SA_EMAIL}" \
    --role="${role}" \
    --condition=None \
    --quiet
done

echo "==> 3/5: Creating private GKE ${GKE_VERSION} cluster '${CLUSTER_NAME}' (${MACHINE_TYPE}, ${DISK_TYPE}, ${NUM_NODES} nodes) in ${CLUSTER_LOCATION}"
if ! gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud beta container clusters create "${CLUSTER_NAME}" \
    --async \
    --project "${PROJECT_ID}" \
    --location "${CLUSTER_LOCATION}" \
    --network "${NETWORK}" \
    --subnetwork "${SUBNETWORK}" \
    --enable-private-nodes \
    --enable-dns-access \
    --enable-ip-alias \
    --enable-dataplane-v2 \
    --release-channel rapid \
    --cluster-version "${GKE_VERSION}" \
    --machine-type "${MACHINE_TYPE}" \
    --disk-type "${DISK_TYPE}" \
    --disk-size 100 \
    --num-nodes "${NUM_NODES}" \
    --service-account "${NODE_SA_EMAIL}" \
    --shielded-secure-boot \
    --shielded-integrity-monitoring \
    --node-labels "workload=agent-substrate" \
    --workload-pool "${PROJECT_ID}.svc.id.goog" \
    --enable-managed-prometheus \
    --managed-otel-scope=COLLECTION_AND_INSTRUMENTATION_COMPONENTS \
    --quiet

  DEADLINE=$((SECONDS + 1200))
  while (( SECONDS < DEADLINE )); do
    C_STATUS="$(gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --format='value(status)' 2>/dev/null || echo 'UNKNOWN')"
    if [[ "${C_STATUS}" == "RUNNING" ]]; then
      break
    fi
    if [[ "${C_STATUS}" == "ERROR" || "${C_STATUS}" == "DEGRADED" ]]; then
      echo "Error: GKE cluster '${CLUSTER_NAME}' entered status ${C_STATUS} during creation." >&2
      exit 1
    fi
    if [[ "${CLUSTER_LOCATION}" =~ -[a-z]$ ]]; then
      MIG="$(gcloud compute instance-groups managed list --project "${PROJECT_ID}" --zones "${CLUSTER_LOCATION}" --filter="name~gke-${CLUSTER_NAME:0:18}" --format='value(name)' 2>/dev/null | head -n1 || true)"
      if [[ -n "${MIG}" ]]; then
        MIG_ERR="$(gcloud compute instance-groups managed list-instances "${MIG}" --zone "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --format='value(lastAttempt.errors.errors.code)' 2>/dev/null || true)"
        if grep -qE 'ZONE_RESOURCE_POOL_EXHAUSTED|QUOTA_EXCEEDED' <<<"${MIG_ERR}"; then
          echo "Error: Zone '${CLUSTER_LOCATION}' exhausted '${MACHINE_TYPE}' capacity (${MIG_ERR//$'\n'/ })." >&2
          echo "Hint: tear down '${CLUSTER_NAME}' once GKE finishes provisioning rollback and retry with CLUSTER_LOCATION=europe-west4-b or MACHINE_TYPE=c3-standard-4." >&2
          exit 1
        fi
      fi
    fi
    sleep 15
  done
  if [[ "$(gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --format='value(status)' 2>/dev/null || true)" != "RUNNING" ]]; then
    echo "Error: Timed out after 20m waiting for GKE cluster '${CLUSTER_NAME}' to reach RUNNING." >&2
    exit 1
  fi
fi

echo "==> 4/5: Adding 7-day maintenance exclusion window (substrate-demo-freeze)"
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
  --add-maintenance-exclusion-name substrate-demo-freeze \
  --add-maintenance-exclusion-start "${START_TIME}" \
  --add-maintenance-exclusion-end "${END_TIME}" \
  --add-maintenance-exclusion-scope no_minor_or_node_upgrades \
  --quiet >/dev/null 2>&1 || echo "Note: maintenance exclusion window already exists on '${CLUSTER_NAME}'."

UPDATE_KUBECONFIG="${UPDATE_KUBECONFIG:-true}"
if [[ "${UPDATE_KUBECONFIG}" == "true" ]]; then
  echo "==> 5/5: Updating kubeconfig (${KUBECONFIG:-~/.kube/config}) with DNS endpoint for '${CLUSTER_NAME}'"
  gcloud container clusters get-credentials "${CLUSTER_NAME}" \
    --project "${PROJECT_ID}" \
    --location "${CLUSTER_LOCATION}" \
    --dns-endpoint
else
  echo "==> 5/5: Skipping kubeconfig context switch (UPDATE_KUBECONFIG=${UPDATE_KUBECONFIG})."
  echo "  Fetch credentials manually with: gcloud container clusters get-credentials '${CLUSTER_NAME}' --location '${CLUSTER_LOCATION}' --project '${PROJECT_ID}' --dns-endpoint"
fi
echo "Cluster '${CLUSTER_NAME}' (${GKE_VERSION}) is ready."
