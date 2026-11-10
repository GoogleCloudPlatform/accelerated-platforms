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

# teardown.sh — Complete cleanup for standalone Option A deployments.
# Removes managed port-forwards, Cloud Monitoring dashboards, GKE cluster,
# GCS snapshot bucket, dedicated per-cluster ServiceAccounts, and (when no other
# clusters remain on the shared VPC/region) Artifact Registry, Cloud NAT/Router,
# Subnet/VPC, and project Workload Identity bindings.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${USE_CASE_DIR}/.state"

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
NAMESPACE="${NAMESPACE:-agent-sandbox}"
AR_REPO="${AR_REPO:-agent-substrate}"
NETWORK="${NETWORK:-ai-agent-network}"
SUBNETWORK="${SUBNETWORK:-ai-agent-subnet-${REGION}}"
ROUTER_NAME="${ROUTER_NAME:-${NETWORK}-router-${REGION}}"
NAT_NAME="${NAT_NAME:-${NETWORK}-nat-${REGION}}"
CLEAN_CLUSTER_SLUG="$(printf '%s' "${CLUSTER_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | cut -c1-18 | sed 's/-\+$//')"
RAW_BUCKET="$(printf '%s-%s-ate-snaps' "${PROJECT_ID:0:28}" "${CLUSTER_NAME:0:20}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | sed 's/-\+$//; s/^-\+//')"
BUCKET_NAME="${BUCKET_NAME:-${RAW_BUCKET:0:63}}"
SNAPSHOT_TRANSFER_GSA_NAME="${SNAPSHOT_TRANSFER_GSA_NAME:-ate-snap-${CLEAN_CLUSTER_SLUG:-gke}}"
NODE_SA_NAME="${NODE_SA_NAME:-ate-nodes-${CLEAN_CLUSTER_SLUG:-gke}}"

[[ -n "${PROJECT_ID}" ]] || { echo "Error: set PROJECT_ID=<gcp-project-id>" >&2; exit 1; }

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/port-forward.sh"
echo "==> 1/6: Stopping managed local port-forwards"
stop_managed_port_forwards "${STATE_DIR}"

echo "==> 2/6: Deleting Cloud Monitoring dashboards scoped to '${CLUSTER_NAME}'"
PROJECT_ID="${PROJECT_ID}" CLUSTER_NAME="${CLUSTER_NAME}" "${SCRIPT_DIR}/dashboards.sh" delete || true

echo "==> 3/6: Releasing PVCs and deleting GKE cluster '${CLUSTER_NAME}' (${CLUSTER_LOCATION})"
if gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  TMP_KC="$(mktemp)"
  KUBECONFIG="${TMP_KC}" gcloud container clusters get-credentials "${CLUSTER_NAME}" \
    --location "${CLUSTER_LOCATION}" \
    --project "${PROJECT_ID}" \
    --dns-endpoint >/dev/null 2>&1 || true
  KUBECONFIG="${TMP_KC}" kubectl -n ate-system delete statefulset postgres --ignore-not-found >/dev/null 2>&1 || true
  KUBECONFIG="${TMP_KC}" kubectl -n ate-system delete pvc --all --ignore-not-found --timeout=60s >/dev/null 2>&1 || true
  rm -f "${TMP_KC}"
  gcloud container clusters delete "${CLUSTER_NAME}" \
    --location "${CLUSTER_LOCATION}" \
    --project "${PROJECT_ID}" \
    --quiet
fi

echo "==> 4/6: Deleting cluster GCS snapshot bucket (gs://${BUCKET_NAME}) and dedicated ServiceAccounts"
if gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage rm --recursive "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
  gcloud storage buckets delete "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --quiet >/dev/null 2>&1 || true
fi

NODE_SA_EMAIL="${NODE_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
for role in \
  roles/container.defaultNodeServiceAccount \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/stackdriver.resourceMetadata.writer \
  roles/artifactregistry.reader; do
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${NODE_SA_EMAIL}" \
    --role="${role}" \
    --condition=None --quiet >/dev/null 2>&1 || true
done
if gcloud iam service-accounts describe "${NODE_SA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts delete "${NODE_SA_EMAIL}" --project "${PROJECT_ID}" --quiet
fi

TRANSFER_GSA_EMAIL="${SNAPSHOT_TRANSFER_GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts delete "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" --quiet
fi

REMAINING_REGION_CLUSTERS="$(gcloud container clusters list --project "${PROJECT_ID}" --filter="network=${NETWORK} AND location~^${REGION}" --format='value(name)' 2>/dev/null || true)"
REMAINING_NETWORK_CLUSTERS="$(gcloud container clusters list --project "${PROJECT_ID}" --filter="network=${NETWORK}" --format='value(name)' 2>/dev/null || true)"

echo "==> 5/6: Cleaning up regional Artifact Registry (${AR_REPO}) and Cloud NAT/Router/Subnet in ${REGION}"
if [[ -z "${REMAINING_REGION_CLUSTERS}" ]]; then
  if gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud artifacts repositories delete "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" --quiet
  fi
  if gcloud compute routers nats describe "${NAT_NAME}" --router "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute routers nats delete "${NAT_NAME}" --router "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --quiet
  fi
  if gcloud compute routers describe "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute routers delete "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --quiet
  fi
  if gcloud compute networks subnets describe "${SUBNETWORK}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute networks subnets delete "${SUBNETWORK}" --region "${REGION}" --project "${PROJECT_ID}" --quiet || true
  fi
else
  echo "  Note: keeping shared regional resources in ${REGION} while clusters remain on ${NETWORK}: $(tr '\n' ' ' <<<"${REMAINING_REGION_CLUSTERS}")"
fi

echo "==> 6/6: Cleaning up project Workload Identity bindings and VPC (${NETWORK})"
if [[ -z "${REMAINING_NETWORK_CLUSTERS}" ]]; then
  PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
  WI="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject"
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="${WI}/ns/${NAMESPACE}/sa/gateway" \
    --role="roles/aiplatform.user" \
    --condition=None --quiet >/dev/null 2>&1 || true
  gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="${WI}/ns/${NAMESPACE}/sa/prometheus-ui" \
    --role="roles/monitoring.viewer" \
    --condition=None --quiet >/dev/null 2>&1 || true

  REMAINING_SUBNETS="$(gcloud compute networks subnets list --network "${NETWORK}" --project "${PROJECT_ID}" --format='value(name)' 2>/dev/null || true)"
  if [[ -z "${REMAINING_SUBNETS}" ]] && gcloud compute networks describe "${NETWORK}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud compute networks delete "${NETWORK}" --project "${PROJECT_ID}" --quiet || true
  fi
else
  echo "  Note: keeping shared VPC '${NETWORK}' and project Workload Identity bindings while clusters remain active."
fi

echo "Option A teardown complete for '${CLUSTER_NAME}' in '${PROJECT_ID}'."
