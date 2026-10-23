#!/usr/bin/env bash

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
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../../../../../../../")"

source "${MY_PATH}/../../config/huggingface.sh"

if [[ ! -v ACCELERATOR_TYPE ]]; then
  echo "ACCELERATOR_TYPE is not set, exiting!"
  exit 1
fi

if [[ -v HF_MODEL_ID && -n "${HF_MODEL_ID}" ]]; then
  models=("${HF_MODEL_ID}")
else
  models=("${hf_gpu_vllm_podsnapshot_models[@]}")
fi

for model in "${models[@]}"; do
  export HF_MODEL_ID=${model}
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  VLLM_VARIANT="${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  variant_dir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/${VLLM_VARIANT}"
  if [[ -d "${variant_dir}" ]]; then
    echo "Deleting '${HF_MODEL_ID}' Pod snapshot fast-restore resources on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"
    "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" delete "deployment/vllm-fast-restore-${VLLM_VARIANT}" --ignore-not-found
    snapshots="$(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" get podsnapshots \
      --output=jsonpath="{range .items[?(@.spec.policyName=='vllm-fast-restore-snapshot-policy-${VLLM_VARIANT}')]}{.metadata.name}{' '}{end}" || true)"
    if [[ -n "${snapshots}" ]]; then
      # shellcheck disable=SC2086
      kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" delete podsnapshots ${snapshots} --ignore-not-found
    fi
    kubectl delete --ignore-not-found --kustomize "${variant_dir}"
    echo
  else
    echo "'${HF_MODEL_ID}' model does not have a configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
