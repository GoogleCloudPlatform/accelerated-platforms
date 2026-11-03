#!/usr/bin/env bash
#
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

# Provisions independent regional GKE Autopilot inference-ref-arch islands from
# a single checkout without mutating tracked *.auto.tfvars or ~/.kube/config.
#
# Required environment variables:
#   PROJECT_ID : Google Cloud project ID
# Optional environment variables:
#   HF_TOKEN                 : Hugging Face access token stored in Secret Manager
#   TF_VAR_resource_name_prefix : Resource prefix (default: "inf")
#   ENABLE_POD_SNAPSHOTS     : "true" or "false" (default: "false")
#   ACTIVE_MIGRATION_ENABLED : "true" or "false" (default: "false")
#   MIRROR_IMAGES            : Space-separated "<src_image>=<dst_subpath:tag>"
#                              entries to mirror into each regional Artifact Registry
#
# Positional arguments:
#   "<platform_name>:<region>" pairs. Defaults to:
#     "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# shellcheck source=platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
source "${MY_PATH}/helpers.sh"

if [[ -z "${PROJECT_ID:-}" ]]; then
  echo "ERROR: PROJECT_ID must be set." >&2
  exit 1
fi

gcloud projects describe "${PROJECT_ID}" --format="value(projectId)" >/dev/null

ENABLE_POD_SNAPSHOTS="${ENABLE_POD_SNAPSHOTS:-false}"
ACTIVE_MIGRATION_ENABLED="${ACTIVE_MIGRATION_ENABLED:-false}"
PREFIX="${TF_VAR_resource_name_prefix:-inf}"

if (($# > 0)); then
  RING_TARGETS=("$@")
else
  RING_TARGETS=(
    "americas:us-central1"
    "europe:europe-west2"
    "apac:asia-southeast1"
  )
fi

mirror_job_ids=()

for idx in "${!RING_TARGETS[@]}"; do
  entry="${RING_TARGETS[${idx}]}"
  platform_name="${entry%%:*}"
  region="${entry##*:}"
  if [[ -z "${platform_name}" || -z "${region}" || "${platform_name}" == "${entry}" ]]; then
    echo "ERROR: Invalid ring target '${entry}'. Expected '<platform_name>:<region>'." >&2
    exit 1
  fi

  echo "=================================================================="
  echo "[${idx}] Provisioning '${PREFIX}-${platform_name}' in ${region}"
  echo "=================================================================="

  use_region "${platform_name}" "${region}"
  mr_set_cidrs_for_index "${idx}"

  export TF_VAR_network_cluster_subnet_node_ip_cidr_range="${MR_NODE_CIDR}"
  export TF_VAR_network_cluster_subnet_proxy_ip_cidr_range="${MR_PROXY_CIDR}"
  export TF_VAR_network_cluster_subnet_master_ipv4_cidr_block="${MR_MASTER_CIDR}"
  export TF_VAR_network_cluster_pod_ipv4_cidr_block="${MR_POD_CIDR}"
  export TF_VAR_network_cluster_services_ipv4_cidr_block="${MR_SERVICES_CIDR}"
  export TF_VAR_cluster_custom_compute_class_active_migration_enabled="${ACTIVE_MIGRATION_ENABLED}"
  export TF_VAR_ira_online_gpu_pod_snapshots_enabled="${ENABLE_POD_SNAPSHOTS}"

  mkdir -p "$(dirname "${KUBECONFIG}")"

  "${ACP_PLATFORM_USE_CASE_DIR}/terraform/deploy-ap.sh"

  (
    cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/online_gpu"
    rm -rf .terraform/
    terraform init
    terraform plan -input=false -out=tfplan
    terraform apply -input=false tfplan
    rm -f tfplan
  )

  if [[ -n "${HF_TOKEN:-}" ]]; then
    for secret_suffix in "huggingface-hub-access-token-read" "huggingface-hub-access-token-write"; do
      secret_name="${PREFIX}-${platform_name}-${secret_suffix}"
      printf '%s' "${HF_TOKEN}" | gcloud secrets versions add "${secret_name}" \
        --project="${PROJECT_ID}" \
        --data-file=- >/dev/null
    done
  fi

  if [[ "${ENABLE_POD_SNAPSHOTS}" == "true" ]]; then
    cluster_id="${PREFIX}-${platform_name}"
    for _ in $(seq 1 90); do
      cluster_status="$(gcloud container clusters describe "${cluster_id}" --location="${region}" --project="${PROJECT_ID}" --format='value(status)')"
      if [[ "${cluster_status}" == "RUNNING" || "${cluster_status}" == "ERROR" ]]; then
        break
      fi
      echo "Waiting for ${cluster_id} to return to RUNNING (currently ${cluster_status})..."
      sleep 10
    done
    gcloud beta container clusters update "${cluster_id}" \
      --enable-pod-snapshots \
      --location="${region}" \
      --project="${PROJECT_ID}" \
      --quiet
  fi

  if [[ -n "${MIRROR_IMAGES:-}" ]]; then
    read -r -a mirror_specs <<<"${MIRROR_IMAGES}"
    for spec in "${mirror_specs[@]}"; do
      src_img="${spec%%=*}"
      dst_subpath="${spec#*=}"
      if [[ -z "${src_img}" || -z "${dst_subpath}" || "${src_img}" == "${spec}" ]]; then
        echo "ERROR: Invalid MIRROR_IMAGES entry '${spec}'. Expected '<src_image>=<dst_subpath:tag>'." >&2
        exit 1
      fi
      mirror_image_to_ar "${region}" "${platform_name}" "${src_img}" "${dst_subpath}" &
      mirror_job_ids+=("$!")
    done
  fi
done

for job_id in "${mirror_job_ids[@]}"; do
  wait "${job_id}"
done

echo "All ${#RING_TARGETS[@]} regional islands provisioned successfully."
