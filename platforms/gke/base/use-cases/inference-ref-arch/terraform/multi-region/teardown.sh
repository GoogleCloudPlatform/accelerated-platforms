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

# Tears down regional inference-ref-arch islands created by provision.sh,
# reusing ACP's core/initialize backend generation and failing fast on IAM,
# authentication, or Terraform errors.
#
# Required environment variables:
#   PROJECT_ID : Google Cloud project ID
# Optional environment variables:
#   TF_VAR_resource_name_prefix : Resource prefix (default: "inf")
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

bucket_exists() {
  local bucket_name="${1}"
  local describe_out
  if describe_out="$(gcloud storage buckets describe "gs://${bucket_name}" --project="${PROJECT_ID}" --format="value(name)" 2>&1)"; then
    return 0
  fi
  local lower_out="${describe_out,,}"
  if [[ "${lower_out}" == *"404"* || "${lower_out}" == *"not found"* ]]; then
    return 1
  fi
  echo "ERROR: Failed to inspect bucket 'gs://${bucket_name}': ${describe_out}" >&2
  exit 1
}

empty_bucket_if_exists() {
  local bucket_name="${1}"
  if ! bucket_exists "${bucket_name}"; then
    echo "Bucket gs://${bucket_name} does not exist; skipping."
    return 0
  fi

  local existing_entries
  existing_entries="$(gcloud storage ls "gs://${bucket_name}/")"
  if [[ -n "${existing_entries}" ]]; then
    echo "Emptying gs://${bucket_name}..."
    gcloud storage rm --recursive "gs://${bucket_name}/**"
  fi
}

for idx in "${!RING_TARGETS[@]}"; do
  entry="${RING_TARGETS[${idx}]}"
  platform_name="${entry%%:*}"
  region="${entry##*:}"
  if [[ -z "${platform_name}" || -z "${region}" || "${platform_name}" == "${entry}" ]]; then
    echo "ERROR: Invalid ring target '${entry}'. Expected '<platform_name>:<region>'." >&2
    exit 1
  fi

  echo "=================================================================="
  echo "[${idx}] Tearing down '${PREFIX}-${platform_name}' in ${region}"
  echo "=================================================================="

  use_region "${platform_name}" "${region}"
  mr_set_cidrs_for_index "${idx}"

  export TF_VAR_network_cluster_subnet_node_ip_cidr_range="${MR_NODE_CIDR}"
  export TF_VAR_network_cluster_subnet_proxy_ip_cidr_range="${MR_PROXY_CIDR}"
  export TF_VAR_network_cluster_subnet_master_ipv4_cidr_block="${MR_MASTER_CIDR}"
  export TF_VAR_network_cluster_pod_ipv4_cidr_block="${MR_POD_CIDR}"
  export TF_VAR_network_cluster_services_ipv4_cidr_block="${MR_SERVICES_CIDR}"
  export TF_VAR_initialize_backend_use_case_name="inference-ref-arch/terraform"
  export ACP_TEARDOWN_RESET_CHECKOUT="false"

  if [[ -f "${KUBECONFIG}" ]]; then
    kubectl --kubeconfig="${KUBECONFIG}" delete podsnapshot --all \
      --namespace="${PREFIX}-${platform_name}-online-gpu" \
      --ignore-not-found >/dev/null 2>&1 || true
  fi

  pod_snapshots_bucket="${PROJECT_ID}-${PREFIX}-${platform_name}-pod-snapshots"
  if bucket_exists "${pod_snapshots_bucket}"; then
    export TF_VAR_ira_online_gpu_pod_snapshots_enabled="true"
  else
    export TF_VAR_ira_online_gpu_pod_snapshots_enabled="false"
  fi

  empty_bucket_if_exists "${PROJECT_ID}-${PREFIX}-${platform_name}-hf-hub-models"
  empty_bucket_if_exists "${pod_snapshots_bucket}"

  state_bucket="${PROJECT_ID}-${PREFIX}-${platform_name}-terraform"
  if ! bucket_exists "${state_bucket}"; then
    echo "State bucket gs://${state_bucket} does not exist; '${PREFIX}-${platform_name}' already torn down."
    rm -f "${KUBECONFIG}"
    continue
  fi

  # Run core/initialize first so ACP generates online_gpu/backend.tf pointing at
  # this region's Terraform state bucket.
  (
    cd "${ACP_PLATFORM_CORE_DIR}/initialize"
    sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${state_bucket}\"/" "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket"
    cp backend.tf.bucket backend.tf
    rm -rf .terraform/
    terraform init
    terraform plan -input=false -out=tfplan
    terraform apply -input=false tfplan
    rm -f tfplan
  )

  (
    cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/online_gpu"
    rm -rf .terraform/
    terraform init
    terraform destroy -auto-approve
    rm -rf .terraform/ backend.tf
  )

  "${ACP_PLATFORM_USE_CASE_DIR}/terraform/teardown-ap.sh"
  rm -f "${KUBECONFIG}"
done

git -C "${ACP_REPO_DIR}" checkout -- "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket"
echo "All ${#RING_TARGETS[@]} regional islands torn down cleanly."
