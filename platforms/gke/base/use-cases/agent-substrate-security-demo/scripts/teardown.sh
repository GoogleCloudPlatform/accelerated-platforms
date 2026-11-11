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
# demo-labeled GCS snapshot bucket, dedicated per-cluster ServiceAccounts,
# demo-labeled Artifact Registry repository (when no clusters remain in the
# region), project-level Workload Identity bindings (when no clusters remain in
# the project), and (when --delete-network is passed and no clusters remain on
# the VPC) shared Subnet, Cloud NAT/Router, and VPC.

set -euo pipefail

DELETE_SHARED_NETWORK="${DELETE_SHARED_NETWORK:-false}"
for arg in "$@"; do
  case "${arg}" in
    --delete-network)
      DELETE_SHARED_NETWORK="true"
      ;;
    --yes)
      # Accepted for non-interactive callers; shared VPC removal requires --delete-network.
      ;;
    -h|--help)
      echo "Usage: $0 [--yes] [--delete-network]"
      exit 0
      ;;
    *)
      echo "Error: unknown argument '${arg}'. Usage: $0 [--yes] [--delete-network]" >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STATE_DIR="${USE_CASE_DIR}/.state"

TMP_KC=""
cleanup_teardown_tmp() {
  if [[ -n "${TMP_KC}" && -f "${TMP_KC}" ]]; then
    rm -f "${TMP_KC}"
  fi
}
trap cleanup_teardown_tmp EXIT

KUBE_CTX="$(kubectl config current-context 2>/dev/null || true)"
CTX_PROJECT=""
CTX_LOCATION=""
CTX_CLUSTER=""
if [[ "${KUBE_CTX}" =~ ^gke_([^_]+)_([^_]+)_(.+)$ ]]; then
  CTX_PROJECT="${BASH_REMATCH[1]}"
  CTX_LOCATION="${BASH_REMATCH[2]}"
  CTX_CLUSTER="${BASH_REMATCH[3]}"
fi

STAGED_PROJECT_ID=""
STAGED_CLUSTER_NAME=""
STAGED_CLUSTER_LOCATION=""
STAGED_AR_REPO=""
STAGED_BUCKET_NAME=""
STAGED_GSA_NAME=""
STAGED_NAMESPACE=""
if [[ -f "${STATE_DIR}/staged.env" ]]; then
  while IFS='=' read -r k v; do
    case "${k}" in
      PROJECT_ID) STAGED_PROJECT_ID="${v}" ;;
      CLUSTER_NAME) STAGED_CLUSTER_NAME="${v}" ;;
      CLUSTER_LOCATION) STAGED_CLUSTER_LOCATION="${v}" ;;
      AR_REPO) STAGED_AR_REPO="${v}" ;;
      BUCKET_NAME) STAGED_BUCKET_NAME="${v}" ;;
      SNAPSHOT_TRANSFER_GSA_NAME) STAGED_GSA_NAME="${v}" ;;
      NAMESPACE) STAGED_NAMESPACE="${v}" ;;
    esac
  done < "${STATE_DIR}/staged.env"
fi

TARGET_CLUSTER_HINT="${CLUSTER_NAME:-${CTX_CLUSTER:-${STAGED_CLUSTER_NAME:-}}}"
if [[ -n "${STAGED_CLUSTER_NAME}" && "${TARGET_CLUSTER_HINT}" != "${STAGED_CLUSTER_NAME}" ]]; then
  STAGED_PROJECT_ID=""
  STAGED_CLUSTER_NAME=""
  STAGED_CLUSTER_LOCATION=""
  STAGED_AR_REPO=""
  STAGED_BUCKET_NAME=""
  STAGED_GSA_NAME=""
  STAGED_NAMESPACE=""
fi

DEFAULT_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
[[ "${DEFAULT_PROJECT}" == "(unset)" ]] && DEFAULT_PROJECT=""

PROJECT_ID="${PROJECT_ID:-${CTX_PROJECT:-${STAGED_PROJECT_ID:-${DEFAULT_PROJECT}}}}"
CLUSTER_NAME="${CLUSTER_NAME:-${CTX_CLUSTER:-${STAGED_CLUSTER_NAME:-agent-substrate-live}}}"
CLUSTER_LOCATION="${CLUSTER_LOCATION:-${CTX_LOCATION:-${STAGED_CLUSTER_LOCATION:-us-central1-b}}}"
if [[ -z "${REGION:-}" ]]; then
  if [[ "${CLUSTER_LOCATION}" =~ -[a-z]$ ]]; then
    REGION="${CLUSTER_LOCATION%-*}"
  else
    REGION="${CLUSTER_LOCATION}"
  fi
fi
NAMESPACE="${NAMESPACE:-${STAGED_NAMESPACE:-agent-sandbox}}"
AR_REPO="${AR_REPO:-${STAGED_AR_REPO:-agent-substrate}}"
NETWORK="${NETWORK:-ai-agent-network}"
SUBNETWORK="${SUBNETWORK:-${NETWORK%-network}-subnet-${REGION}}"
ROUTER_NAME="${ROUTER_NAME:-${NETWORK}-router-${REGION}}"
NAT_NAME="${NAT_NAME:-${NETWORK}-nat-${REGION}}"
CLEAN_CLUSTER_SLUG="$(printf '%s' "${CLUSTER_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | cut -c1-18 | sed 's/-\+$//')"
RAW_BUCKET="$(printf '%s-%s-ate-snaps' "${PROJECT_ID:0:28}" "${CLUSTER_NAME:0:20}" | tr '[:upper:]' '[:lower:]' | sed 's/google/ggl/g' | tr -cd 'a-z0-9-' | sed 's/-\+$//; s/^-\+//')"
DEFAULT_BUCKET_NAME="${RAW_BUCKET:0:63}"
BUCKET_NAME="${BUCKET_NAME:-${STAGED_BUCKET_NAME:-${DEFAULT_BUCKET_NAME}}}"
SNAPSHOT_TRANSFER_GSA_NAME="${SNAPSHOT_TRANSFER_GSA_NAME:-${STAGED_GSA_NAME:-ate-snap-${CLEAN_CLUSTER_SLUG:-gke}}}"
NODE_SA_NAME="${NODE_SA_NAME:-ate-nodes-${CLEAN_CLUSTER_SLUG:-gke}}"

[[ -n "${PROJECT_ID}" ]] || { echo "Error: set PROJECT_ID=<gcp-project-id>" >&2; exit 1; }

FAILURES=0
cleanup_ignore_not_found() {
  local desc="$1"; shift
  local err_out lower rc=0
  err_out="$("$@" 2>&1)" || rc=$?
  if [[ "${rc}" -eq 0 ]]; then
    return 0
  fi
  lower="$(printf '%s' "${err_out}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${lower}" == *"not found"* \
     || "${lower}" == *"not_found"* \
     || "${lower}" == *"404"* \
     || "${lower}" == *"does not exist"* \
     || "${lower}" == *"matched no objects"* ]]; then
    return 0
  fi
  echo "Warning: failed to ${desc} (exit ${rc}): ${err_out}" >&2
  FAILURES=$((FAILURES + 1))
  return 0
}

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/port-forward.sh"
echo "==> 1/6: Stopping managed local port-forwards"
stop_managed_port_forwards "${STATE_DIR}"

echo "==> 2/6: Deleting Cloud Monitoring dashboards scoped to '${CLUSTER_NAME}'"
if ! PROJECT_ID="${PROJECT_ID}" CLUSTER_NAME="${CLUSTER_NAME}" "${SCRIPT_DIR}/dashboards.sh" delete; then
  echo "Warning: failed to delete one or more Cloud Monitoring dashboards for '${CLUSTER_NAME}'." >&2
  FAILURES=$((FAILURES + 1))
fi

echo "==> 3/6: Releasing PVCs and deleting GKE cluster '${CLUSTER_NAME}' (${CLUSTER_LOCATION})"
if gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  TMP_KC="$(mktemp)"
  chmod 0600 "${TMP_KC}"
  if KUBECONFIG="${TMP_KC}" gcloud container clusters get-credentials "${CLUSTER_NAME}" \
      --location "${CLUSTER_LOCATION}" \
      --project "${PROJECT_ID}" \
      --dns-endpoint >/dev/null 2>&1; then
    cleanup_ignore_not_found "delete postgres StatefulSet" \
      env KUBECONFIG="${TMP_KC}" kubectl -n ate-system delete statefulset postgres --ignore-not-found
    cleanup_ignore_not_found "delete ate-system PVCs" \
      env KUBECONFIG="${TMP_KC}" kubectl -n ate-system delete pvc --all --ignore-not-found --timeout=60s
  fi
  rm -f "${TMP_KC}"
  TMP_KC=""
  gcloud container clusters delete "${CLUSTER_NAME}" \
    --location "${CLUSTER_LOCATION}" \
    --project "${PROJECT_ID}" \
    --quiet
fi

echo "==> 4/6: Deleting demo-labeled GCS snapshot bucket (gs://${BUCKET_NAME}) and dedicated ServiceAccounts"
if gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  BUCKET_LABELS="$(gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --format='value(labels.created-by,labels.managed-by)' 2>/dev/null || true)"
  if [[ "${BUCKET_LABELS}" == *"agent-substrate-demo"* || "${BUCKET_NAME}" == "${DEFAULT_BUCKET_NAME}" ]]; then
    cleanup_ignore_not_found "empty snapshot bucket gs://${BUCKET_NAME}" \
      gcloud storage rm --recursive "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --quiet
    cleanup_ignore_not_found "delete snapshot bucket gs://${BUCKET_NAME}" \
      gcloud storage buckets delete "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --quiet
  else
    echo "  Note: preserving bucket 'gs://${BUCKET_NAME}' (missing created-by=agent-substrate-demo label)."
  fi
fi

NODE_SA_EMAIL="${NODE_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
for role in \
  roles/container.defaultNodeServiceAccount \
  roles/logging.logWriter \
  roles/monitoring.metricWriter \
  roles/stackdriver.resourceMetadata.writer \
  roles/artifactregistry.reader; do
  cleanup_ignore_not_found "remove ${role} from ${NODE_SA_EMAIL}" \
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${NODE_SA_EMAIL}" \
      --role="${role}" \
      --condition=None --quiet
done
if gcloud iam service-accounts describe "${NODE_SA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  cleanup_ignore_not_found "delete node ServiceAccount ${NODE_SA_EMAIL}" \
    gcloud iam service-accounts delete "${NODE_SA_EMAIL}" --project "${PROJECT_ID}" --quiet
fi

TRANSFER_GSA_EMAIL="${SNAPSHOT_TRANSFER_GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  cleanup_ignore_not_found "delete snapshot transfer ServiceAccount ${TRANSFER_GSA_EMAIL}" \
    gcloud iam service-accounts delete "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" --quiet
fi

# Abort immediately (no `|| true`) if listing clusters fails so shared resources are never removed blindly.
REMAINING_REGION_CLUSTERS="$(gcloud container clusters list --project "${PROJECT_ID}" --filter="network~(^|/)${NETWORK}$ AND location~^${REGION}(-|$)" --format='value(name)')"
REMAINING_NETWORK_CLUSTERS="$(gcloud container clusters list --project "${PROJECT_ID}" --filter="network~(^|/)${NETWORK}$" --format='value(name)')"
REMAINING_PROJECT_CLUSTERS="$(gcloud container clusters list --project "${PROJECT_ID}" --format='value(name)')"

echo "==> 5/6: Cleaning up demo-created regional Artifact Registry (${AR_REPO}) and regional networking in ${REGION}"
if [[ -z "${REMAINING_REGION_CLUSTERS}" ]]; then
  if gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    AR_LABELS="$(gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" --format='value(labels.created-by,labels.managed-by)')"
    if [[ "${AR_LABELS}" == *"agent-substrate-demo"* ]]; then
      cleanup_ignore_not_found "delete Artifact Registry ${AR_REPO}" \
        gcloud artifacts repositories delete "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" --quiet
    else
      echo "  Note: preserving Artifact Registry '${AR_REPO}' (missing created-by=agent-substrate-demo label)."
    fi
  fi
  if [[ "${DELETE_SHARED_NETWORK}" == "true" ]]; then
    cleanup_ignore_not_found "delete subnet ${SUBNETWORK}" \
      gcloud compute networks subnets delete "${SUBNETWORK}" --region "${REGION}" --project "${PROJECT_ID}" --quiet
    if ! gcloud compute networks subnets describe "${SUBNETWORK}" --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
      cleanup_ignore_not_found "delete Cloud NAT ${NAT_NAME}" \
        gcloud compute routers nats delete "${NAT_NAME}" --router "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --quiet
      cleanup_ignore_not_found "delete Cloud Router ${ROUTER_NAME}" \
        gcloud compute routers delete "${ROUTER_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --quiet
    fi
  else
    echo "  Note: preserving shared subnet '${SUBNETWORK}' and Cloud NAT/Router (pass --delete-network to remove)."
  fi
else
  echo "  Note: keeping shared regional resources in ${REGION} while clusters remain on ${NETWORK}: $(tr '\n' ' ' <<<"${REMAINING_REGION_CLUSTERS}")"
fi

echo "==> 6/6: Cleaning up project Workload Identity bindings and VPC (${NETWORK})"
if [[ -z "${REMAINING_PROJECT_CLUSTERS}" ]]; then
  PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
  WI="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject"
  cleanup_ignore_not_found "remove gateway aiplatform.user binding" \
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
      --member="${WI}/ns/${NAMESPACE}/sa/gateway" \
      --role="roles/aiplatform.user" \
      --condition=None --quiet
  cleanup_ignore_not_found "remove prometheus-ui monitoring.viewer binding" \
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
      --member="${WI}/ns/${NAMESPACE}/sa/prometheus-ui" \
      --role="roles/monitoring.viewer" \
      --condition=None --quiet
else
  echo "  Note: keeping project-scoped Workload Identity bindings while clusters remain in project '${PROJECT_ID}'."
fi

if [[ "${DELETE_SHARED_NETWORK}" == "true" ]]; then
  if [[ -z "${REMAINING_NETWORK_CLUSTERS}" ]]; then
    REMAINING_SUBNETS="$(gcloud compute networks subnets list --network "${NETWORK}" --project "${PROJECT_ID}" --format='value(name)')"
    if [[ -z "${REMAINING_SUBNETS}" ]] && gcloud compute networks describe "${NETWORK}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
      cleanup_ignore_not_found "delete VPC ${NETWORK}" \
        gcloud compute networks delete "${NETWORK}" --project "${PROJECT_ID}" --quiet
    fi
  else
    echo "  Note: keeping shared VPC '${NETWORK}' while clusters remain on it."
  fi
else
  echo "  Note: preserving shared VPC '${NETWORK}' (pass --delete-network to remove)."
fi

rm -rf "${STATE_DIR}"

if (( FAILURES > 0 )); then
  echo "Error: Option A teardown finished with ${FAILURES} error(s) for '${CLUSTER_NAME}' in '${PROJECT_ID}'." >&2
  exit 1
fi
echo "Option A teardown complete for '${CLUSTER_NAME}' in '${PROJECT_ID}'."
