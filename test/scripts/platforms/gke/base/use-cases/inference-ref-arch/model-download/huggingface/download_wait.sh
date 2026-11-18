#!/usr/bin/env bash

# Copyright 2025 Google LLC
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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../../../../")"

# shellcheck source=test/scripts/platforms/gke/base/use-cases/inference-ref-arch/config/huggingface.sh
source "${MY_PATH}/../../config/huggingface.sh"

ts_or_cat() {
  if command -v ts >/dev/null 2>&1; then
    ts "${1}"
  else
    cat
  fi
}

kubectl_wait() {
  export HF_MODEL_ID="${1}"

  # shellcheck source=platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  # shellcheck disable=SC2154
  local ns="${huggingface_hub_downloader_kubernetes_namespace_name}"
  local job_name="${HF_MODEL_ID_HASH}-hf-model-to-gcs"
  local deadline=$(($(date +%s) + 14400))
  local status

  echo "Waiting for '${HF_MODEL_ID}'(${HF_MODEL_ID_HASH}) download" | ts_or_cat "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]"
  while true; do
    status="$(kubectl --namespace="${ns}" get "job/${job_name}" \
      -o jsonpath='{.status.succeeded}:{.status.conditions[?(@.type=="Failed")].status}' 2>/dev/null || true)"
    if [[ "${status%%:*}" == "1" ]]; then
      echo "job.batch/${job_name} condition met" | ts_or_cat "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]"
      break
    fi
    if [[ ":${status#*:}:" == *":True:"* ]]; then
      echo "ERROR: job.batch/${job_name} failed" >&2
      return 1
    fi
    if (($(date +%s) >= deadline)); then
      echo "ERROR: timed out waiting for job.batch/${job_name}" >&2
      return 1
    fi
    sleep 10
  done

  # shellcheck disable=SC2154
  model_size="$(gcloud storage du --readable-sizes --summarize "gs://${huggingface_hub_models_bucket_name}/${HF_MODEL_ID}")"
  echo "Model size in storage: ${model_size}" | ts_or_cat "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]"
}

if [[ -v HF_MODEL_ID && -n "${HF_MODEL_ID}" ]]; then
  models=("$(echo "${HF_MODEL_ID}" | tr '[:upper:]' '[:lower:]')")
else
  # shellcheck disable=SC2154
  models=("${hf_models[@]}")
fi

pids=()
for model in "${models[@]}"; do
  kubectl_wait "${model}" &
  pids+=("$!")
done
failed=0
for pid in "${pids[@]}"; do
  wait "${pid}" || failed=1
done
exit "${failed}"
