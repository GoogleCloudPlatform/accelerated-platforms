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
ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../../../../../../)"

source "${MY_PATH}/../../config/huggingface.sh"

kubectl_wait(){
  export HF_MODEL_ID=${1}

  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  echo "Waiting for '${HF_MODEL_ID}'(${HF_MODEL_ID_HASH}) download" | ts "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]"
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} wait job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --for=condition=complete --timeout=14400s | ts "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]" &
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} wait job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --for=condition=failed --timeout=14400s | ts "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]" && exit 1 &
  wait -n && \
  pkill -f "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} wait job/${HF_MODEL_ID_HASH}-hf-model-to-gcs" || true

  model_size=$(gcloud storage du --readable-sizes --summarize "gs://${huggingface_hub_models_bucket_name}/${HF_MODEL_ID}")
  echo "Model size in storage: ${model_size}" | ts "$(date +'%Y-%m-%d %H:%M:%S.%N %Z') [${HF_MODEL_ID}]"
}

for model in "${hf_models[@]}"; do
  kubectl_wait "${model}" &
done
wait
