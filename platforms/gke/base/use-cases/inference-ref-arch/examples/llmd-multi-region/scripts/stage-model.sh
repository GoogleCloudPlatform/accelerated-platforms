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

# Stages the model weights in a region's Cloud Storage bucket.
#
# Usage: stage-model.sh <region_key>
#
# By default the model is downloaded from Hugging Face with the
# inference-ref-arch model download Job (kubernetes-manifests/model-download).
# Set MR_MODEL_SOURCE_BUCKET to copy it from an existing bucket instead (for
# example, the bucket of another region that already has the model; see also
# replicate_hf_model in terraform/multi-region/helpers.sh).

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

key="${1:?usage: stage-model.sh <region_key>}"
mr_validate_region_key "${key}"
scope="region/${key}"
bucket="$(mr_models_bucket "${key}")"
wt="$(mr_worktree_dir "${key}")"

model_present() {
  gcloud storage ls "gs://${bucket}/${MR_MODEL_PATH}/config.json" >/dev/null 2>&1 &&
    gcloud storage ls "gs://${bucket}/${MR_MODEL_PATH}/*.safetensors" >/dev/null 2>&1
}

copy_from_bucket() {
  gcloud storage rsync --recursive \
    "gs://${MR_MODEL_SOURCE_BUCKET}/${MR_MODEL_PATH}" \
    "gs://${bucket}/${MR_MODEL_PATH}"
}

download_from_hugging_face() {
  (
    use_region "${key}" "$(mr_region "${key}")" "$(mr_cidr_index "${key}")"
    export HF_MODEL_ID="${MR_MODEL_PATH}"

    # configure_huggingface.sh writes rendered manifests into the checkout's
    # kubernetes-manifests/model-download/huggingface/ directory. Use the
    # region's Git worktree when available so parallel regional staging never
    # races; otherwise serialize manifest rendering on a local lock.
    local checkout="${ACP_REPO_DIR}"
    if [[ -e "${wt}/.git" ]]; then
      checkout="${wt}"
    fi
    local km="${checkout}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download"
    # shellcheck source=/dev/null
    source "${checkout}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
    # shellcheck disable=SC2154
    local ns="${huggingface_hub_downloader_kubernetes_namespace_name}"
    local job="${HF_MODEL_ID_HASH}-hf-model-to-gcs"

    kubectl delete job "${job}" -n "${ns}" --ignore-not-found --wait=true
    if [[ "${checkout}" == "${ACP_REPO_DIR}" ]]; then
      mkdir -p "${MR_WORK_DIR}/locks"
      (
        flock -x 9
        "${km}/configure_huggingface.sh"
        kubectl apply --kustomize "${km}/huggingface"
      ) 9>"${MR_WORK_DIR}/locks/stage-model.lock"
    else
      "${km}/configure_huggingface.sh"
      kubectl apply --kustomize "${km}/huggingface"
    fi

    # Poll per-cluster Job status directly (download_wait.sh uses pkill across
    # matching kubectl wait commands, which would collide across parallel
    # regions). Large models take a while: allow up to 90 minutes.
    local deadline=$(($(date +%s) + 5400))
    while true; do
      local succeeded failed_cond
      succeeded="$(kubectl get job "${job}" -n "${ns}" -o jsonpath='{.status.succeeded}' 2>/dev/null || true)"
      failed_cond="$(kubectl get job "${job}" -n "${ns}" -o jsonpath='{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)"
      if [[ "${succeeded}" == "1" ]]; then
        kubectl logs "job/${job}" -n "${ns}" --tail=20 || true
        kubectl delete job "${job}" -n "${ns}" --ignore-not-found
        break
      fi
      if [[ "${failed_cond}" == "True" ]]; then
        kubectl logs "job/${job}" -n "${ns}" --tail=100 || true
        mr_die "model download job ${job} failed"
      fi
      [[ $(date +%s) -lt ${deadline} ]] || mr_die "model download job ${job} timed out"
      sleep 15
    done
  )
}

if model_present; then
  mr_log "gs://${bucket}/${MR_MODEL_PATH} already contains the model, skipping"
  exit 0
fi

if [[ -n "${MR_MODEL_SOURCE_BUCKET}" ]]; then
  mr_stage "model_copy_from_bucket" "${scope}" copy_from_bucket
else
  mr_stage "model_download_from_hugging_face" "${scope}" download_from_hugging_face
fi

model_present || mr_die "model files not found in gs://${bucket}/${MR_MODEL_PATH} after staging"
mr_log "Model staged in gs://${bucket}/${MR_MODEL_PATH}"
