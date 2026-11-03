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

# Shared multi-region shell helpers for inference-ref-arch guides and runbook
# workflows. Source this file in interactive sessions or scripts:
#   source platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh

MR_HELPERS_DIR="$(
  SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
  cd "$(dirname "${SCRIPT_SOURCE}")" >/dev/null 2>&1 || exit 1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MR_HELPERS_DIR}/../../../../../../../")"
ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch"
export ACP_REPO_DIR ACP_PLATFORM_BASE_DIR ACP_PLATFORM_CORE_DIR ACP_PLATFORM_USE_CASE_DIR

# Digest-pinned crane v0.22.1 image used when mirroring upstream images into
# regional Artifact Registry repositories via Cloud Build.
export MR_CRANE_IMAGE="gcr.io/go-containerregistry/crane:v0.22.1@sha256:1f968817b95790bed063f71175aa6b8ff879fa17064020415f3e18bb6e6a36e1"

# Computes deterministic, non-overlapping RFC1918 CIDRs for ring index 0..11,
# staying outside Google Cloud's 10.128.0.0/9 auto-mode subnet space so VPCs
# can be peered safely when testing cross-region patterns.
mr_set_cidrs_for_index() {
  local idx="${1:?Usage: mr_set_cidrs_for_index <0..11>}"
  if [[ ! "${idx}" =~ ^[0-9]+$ ]] || ((idx < 0 || idx >= 12)); then
    echo "ERROR: ring index '${idx}' must be an integer in 0..11." >&2
    return 1
  fi

  MR_NODE_CIDR="10.$((16 + idx * 4)).0.0/20"
  MR_PROXY_CIDR="10.$((16 + idx * 4)).16.0/23"
  MR_MASTER_CIDR="172.16.0.$((16 + idx * 16))/28"
  MR_POD_CIDR="10.$((64 + idx)).0.0/17"
  MR_SERVICES_CIDR="10.96.$((idx * 4)).0/22"
  export MR_NODE_CIDR MR_PROXY_CIDR MR_MASTER_CIDR MR_POD_CIDR MR_SERVICES_CIDR
}

# Points ACP Terraform environment variables and KUBECONFIG at a specific
# regional island without modifying tracked *.auto.tfvars or ~/.kube/config.
use_region() {
  local platform_name="${1:?Usage: use_region <platform_name> <region>}"
  local region="${2:?Usage: use_region <platform_name> <region>}"
  local project_id="${PROJECT_ID:-${TF_VAR_platform_default_project_id:-}}"
  if [[ -z "${project_id}" ]]; then
    echo "ERROR: PROJECT_ID (or TF_VAR_platform_default_project_id) must be set before calling use_region." >&2
    return 1
  fi
  local prefix="${TF_VAR_resource_name_prefix:-inf}"

  export PROJECT_ID="${project_id}"
  export TF_VAR_platform_default_project_id="${project_id}"
  export TF_VAR_platform_default_region="${region}"
  export TF_VAR_cluster_region="${region}"
  export TF_VAR_platform_name="${platform_name}"
  export TF_VAR_resource_name_prefix="${prefix}"
  export TF_VAR_cluster_autopilot_enabled="true"
  export TF_VAR_terraform_write_tfvars="false"
  export KUBECONFIG="${ACP_PLATFORM_BASE_DIR}/kubernetes/kubeconfig/${project_id}-${prefix}-${platform_name}"
}

# Stages a single Hugging Face model into the active region's GCS model bucket
# using the canonical inference-ref-arch model-download scripts.
stage_hf_model() {
  local model_id="${1:?Usage: stage_hf_model <hf_model_id>}"
  (
    set -o errexit
    set -o nounset
    set -o pipefail

    HF_MODEL_ID="$(echo "${model_id}" | tr '[:upper:]' '[:lower:]')"
    export HF_MODEL_ID
    local dl_dir="${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface"
    "${dl_dir}/download_apply.sh"
    "${dl_dir}/download_wait.sh"
    "${dl_dir}/download_delete.sh"
  )
}

# Server-side copies a staged model directory from one regional GCS
# hf-hub-models bucket to another, failing fast if the source directory is
# missing or empty. Note that hf-model-to-gcs writes under lowercase MODEL_ID.
replicate_hf_model() {
  local src_platform="${1:?Usage: replicate_hf_model <src_platform> <dst_platform> <hf_model_id>}"
  local dst_platform="${2:?Usage: replicate_hf_model <src_platform> <dst_platform> <hf_model_id>}"
  local model_id="${3:?Usage: replicate_hf_model <src_platform> <dst_platform> <hf_model_id>}"
  local project_id="${PROJECT_ID:-${TF_VAR_platform_default_project_id:-}}"
  local prefix="${TF_VAR_resource_name_prefix:-inf}"

  (
    set -o errexit
    set -o nounset
    set -o pipefail

    if [[ -z "${project_id}" ]]; then
      echo "ERROR: PROJECT_ID must be set before calling replicate_hf_model." >&2
      exit 1
    fi

    local model_subpath
    model_subpath="$(echo "${model_id}" | tr '[:upper:]' '[:lower:]')"
    local src_uri="gs://${project_id}-${prefix}-${src_platform}-hf-hub-models/${model_subpath}"
    local dst_uri="gs://${project_id}-${prefix}-${dst_platform}-hf-hub-models/${model_subpath}"

    if [[ -z "$(gcloud storage ls "${src_uri}/")" ]]; then
      echo "ERROR: Source model path '${src_uri}/' is empty or missing." >&2
      exit 1
    fi

    echo "Replicating '${model_subpath}' from ${src_uri} to ${dst_uri}..."
    gcloud storage rsync --recursive "${src_uri}" "${dst_uri}"
  )
}

# Mirrors an upstream image (ideally digest-pinned) into a regional Artifact
# Registry repository so GKE image streaming can lazy-load container layers.
mirror_image_to_ar() {
  local region="${1:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local platform_name="${2:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local src_image="${3:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local dst_subpath="${4:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local project_id="${PROJECT_ID:-${TF_VAR_platform_default_project_id:-}}"
  local prefix="${TF_VAR_resource_name_prefix:-inf}"

  (
    set -o errexit
    set -o nounset
    set -o pipefail

    if [[ -z "${project_id}" ]]; then
      echo "ERROR: PROJECT_ID must be set before calling mirror_image_to_ar." >&2
      exit 1
    fi

    local dst_image="${region}-docker.pkg.dev/${project_id}/${prefix}-${platform_name}/${dst_subpath}"
    local cb_config
    cb_config="$(mktemp)"
    trap 'rm -f "${cb_config}"' EXIT

    cat >"${cb_config}" <<EOF
steps:
- name: '${MR_CRANE_IMAGE}'
  args: ['copy', '--platform', 'linux/amd64', '${src_image}', '${dst_image}']
options:
  machineType: 'E2_HIGHCPU_8'
timeout: '3600s'
EOF

    echo "Mirroring ${src_image} -> ${dst_image}..."
    gcloud builds submit \
      --no-source \
      --project="${project_id}" \
      --region="${region}" \
      --config="${cb_config}" \
      --quiet
  )
}
