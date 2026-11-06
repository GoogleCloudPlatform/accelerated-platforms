#!/usr/bin/env bash
#
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

# Deploys the multi-region environment from scratch on top of the shared
# multi-region foundation (terraform/multi-region/provision.sh) and records the
# wall-clock time of every stage:
#   1. shared VPC network, GLOBAL_MANAGED_PROXY subnets, and every regional
#      platform in parallel (terraform/multi-region/provision.sh --parallel),
#   2. per-region model-bucket metadata IAM (for vLLM runai_streamer) and
#      cluster attribution labels,
#   3. fleet features (only with MR_GLOBAL_LB=mc-gateway),
#   4. benchmark infrastructure (results bucket and IAM),
#   5. model staging in every region, in parallel.
#
# Usage: deploy-all.sh [--dry-run] [--regions-only]
#
#   --dry-run       Print the multi-region provisioning plan without calling
#                   Google Cloud.
#   --regions-only  Run steps 1-2 only (for example, with
#                   MR_POD_SNAPSHOTS_ENABLED=true ACP_DEPLOY_CORE_PLATFORM=false
#                   to enable Pod snapshots on already-provisioned clusters).
#
# Experiment arms are deployed separately (deploy-arm.sh / run-experiment.sh),
# so that GPUs are only consumed while an arm is being measured.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

dry_run="false"
regions_only="false"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --dry-run) dry_run="true" && shift ;;
  --regions-only) regions_only="true" && shift ;;
  -h | --help)
    echo "Usage: $(basename "$0") [--dry-run] [--regions-only]"
    exit 0
    ;;
  *) mr_die "unknown argument: ${1} (usage: $(basename "$0") [--dry-run] [--regions-only])" ;;
  esac
done

targets=()
for key in ${MR_REGION_KEYS}; do
  mr_validate_region_key "${key}"
  targets+=("$(mr_target_spec "${key}")")
done
((${#targets[@]} > 0)) || mr_die "MR_REGION_KEYS is empty"

if [[ "${dry_run}" == "true" ]]; then
  exec "${MR_MULTI_REGION_DIR}/provision.sh" --parallel --dry-run "${targets[@]}"
fi

export MR_RUN_ID
mr_require_example_tools

if [[ -z "${HF_TOKEN:-}" ]]; then
  if [[ -s "${MR_HF_TOKEN_FILE}" ]]; then
    HF_TOKEN="$(tr -d '\r\n' <"${MR_HF_TOKEN_FILE}")"
    export HF_TOKEN
  elif [[ -z "${MR_MODEL_SOURCE_BUCKET}" && "${regions_only}" != "true" ]]; then
    mr_die "Hugging Face token file '${MR_HF_TOKEN_FILE}' is missing or empty (or export HF_TOKEN / MR_MODEL_SOURCE_BUCKET)"
  fi
fi

logs="${MR_WORK_DIR}/logs/${MR_RUN_ID}"
mkdir -p "${logs}"
mr_log "Run ${MR_RUN_ID}: logs in ${logs}, timings in ${MR_TIMINGS_FILE}"

# The vLLM Run:ai Model Streamer loads gs:// models with the Cloud Storage
# client, which reads bucket metadata (storage.buckets.get). online_gpu grants
# the Cloud Storage FUSE object role, so also grant legacyBucketReader to the
# namespace Kubernetes service account (Workload Identity principal).
grant_model_bucket_reader() {
  local key="${1}" project_number="${2}"
  gcloud storage buckets add-iam-policy-binding "gs://$(mr_models_bucket "${key}")" \
    --member="principal://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${MR_PROJECT_ID}.svc.id.goog/subject/ns/${MR_NAMESPACE}/sa/${MR_NAMESPACE}" \
    --role="roles/storage.legacyBucketReader" >/dev/null
}

cluster_is_running() {
  [[ "$(gcloud container clusters describe "${1}" --location "${2}" --project "${MR_PROJECT_ID}" --format='value(status)')" == "RUNNING" ]]
}

label_cluster() {
  local key="${1}" cluster region
  cluster="$(mr_cluster_name "${key}")"
  region="$(mr_region "${key}")"
  mr_wait_for 1800 20 "cluster ${cluster} RUNNING" cluster_is_running "${cluster}" "${region}" || return 1
  gcloud container clusters update "${cluster}" \
    --location "${region}" \
    --project "${MR_PROJECT_ID}" \
    --update-labels "created_by=${MR_OWNER_LABEL},acp_environment=${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME},acp_example=llmd-multi-region" \
    --quiet >/dev/null
}

post_provision_region() {
  local key="${1}" project_number="${2}"
  local scope="region/${key}"
  mr_stage "kubeconfig" "${scope}" mr_get_credentials "${key}"
  mr_stage "model_bucket_reader_iam" "${scope}" grant_model_bucket_reader "${key}" "${project_number}"
  mr_stage "label_cluster" "${scope}" label_cluster "${key}"
}

run_stage_hf_model() {
  local key="${1}"
  (
    use_region "${key}" "$(mr_region "${key}")" "$(mr_cidr_index "${key}")"
    stage_hf_model --skip-existing "${MR_HF_MODEL_ID}"
  )
}

stage_region_model() {
  local key="${1}" scope="region/${1}" bucket
  bucket="$(mr_models_bucket "${key}")"
  if [[ -n "${MR_MODEL_SOURCE_BUCKET}" ]]; then
    if gcloud storage ls "gs://${bucket}/${MR_MODEL_PATH}/config.json" >/dev/null 2>&1 &&
      gcloud storage ls "gs://${bucket}/${MR_MODEL_PATH}/*.safetensors" >/dev/null 2>&1; then
      mr_log "gs://${bucket}/${MR_MODEL_PATH} already contains the model, skipping"
      return 0
    fi
    mr_stage "model_copy_from_bucket" "${scope}" gcloud storage rsync --recursive \
      "gs://${MR_MODEL_SOURCE_BUCKET}/${MR_MODEL_PATH}" \
      "gs://${bucket}/${MR_MODEL_PATH}"
  else
    mr_stage "model_download_from_hugging_face" "${scope}" run_stage_hf_model "${key}"
  fi
}

stage_models_parallel() {
  local key pids=() rc=0
  for key in ${MR_REGION_KEYS}; do
    (stage_region_model "${key}") >"${logs}/models-${key}.log" 2>&1 &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "${pid}" || rc=1; done
  [[ ${rc} -eq 0 ]] || mr_die "models staging failed in at least one region; see ${logs}/models-*.log"
}

setup_start="$(date +%s.%N)"
mr_stage "provision_foundation" "global" "${MR_MULTI_REGION_DIR}/provision.sh" --parallel "${targets[@]}"

project_number="$(gcloud projects describe "${MR_PROJECT_ID}" --format='value(projectNumber)')"
pids=()
post_rc=0
for key in ${MR_REGION_KEYS}; do
  (post_provision_region "${key}" "${project_number}") >"${logs}/post-provision-${key}.log" 2>&1 &
  pids+=($!)
done
for pid in "${pids[@]}"; do wait "${pid}" || post_rc=1; done
[[ ${post_rc} -eq 0 ]] || mr_die "post-provision step failed in at least one region; see ${logs}/post-provision-*.log"

if [[ "${regions_only}" != "true" ]]; then
  if [[ "${MR_GLOBAL_LB}" == "mc-gateway" ]]; then
    "${MY_PATH}/deploy-fleet.sh"
  fi
  if [[ -x "${MY_PATH}/deploy-bench-infra.sh" ]]; then
    "${MY_PATH}/deploy-bench-infra.sh"
  fi
  stage_models_parallel
fi
mr_record_timing "setup_total" "global" "${setup_start}" "$(date +%s.%N)" "ok"

"${MR_PYTHON}" "${MR_EXAMPLE_DIR}/bench/setup_report.py" "${MR_TIMINGS_FILE}" | tee "${MR_RESULTS_DIR}/setup-${MR_RUN_ID}.md"
