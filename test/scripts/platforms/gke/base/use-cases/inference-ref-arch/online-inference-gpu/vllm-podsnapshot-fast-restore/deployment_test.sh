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
    echo "Testing '${HF_MODEL_ID}' Pod snapshot fast-restore deployment on '${ACCELERATOR_TYPE}'"
    echo "--------------------------------------------------------------------------------------------"

    echo "Verifying GKE Pod Snapshots CRDs are established on the cluster..."
    kubectl wait --for=condition=established --timeout=60s \
      crd/podsnapshots.podsnapshot.gke.io \
      crd/podsnapshotpolicies.podsnapshot.gke.io \
      crd/podsnapshotstorageconfigs.podsnapshot.gke.io

    SERVED_MODEL_NAME="$(awk -F= '$1 == "MODEL_ID" { print $2 }' "${variant_dir}/runtime.env")"
    export VLLM_VARIANT
    export SERVED_MODEL_NAME

    echo "Waiting for cold-start deployment 'vllm-fast-restore-${VLLM_VARIANT}' to become ready..."
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/vllm-fast-restore-${VLLM_VARIANT}" --timeout=1200s

    echo "Waiting for PodSnapshot for policy 'vllm-fast-restore-snapshot-policy-${VLLM_VARIANT}' to reach AllSnapshotsAvailable..."
    snapshot_ready=0
    for _ in $(seq 1 80); do
      snapshots="$(kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" get podsnapshots \
        --output=jsonpath="{range .items[?(@.spec.policyName==\"vllm-fast-restore-snapshot-policy-${VLLM_VARIANT}\")]}{.metadata.name}{\" \"}{.status.conditions[?(@.type==\"Ready\")].reason}{\"\n\"}{end}")"
      if grep -q "AllSnapshotsAvailable" <<<"${snapshots}"; then
        snapshot_ready=1
        echo "PodSnapshot ready: ${snapshots}"
        break
      fi
      sleep 15
    done
    if [[ ${snapshot_ready} -ne 1 ]]; then
      echo "Timed out waiting for PodSnapshot to reach AllSnapshotsAvailable!"
      exit 1
    fi

    echo "Waiting for cold-start replica to resume after checkpoint upload..."
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/vllm-fast-restore-${VLLM_VARIANT}" --timeout=300s

    echo "Scaling to 2 replicas and measuring snapshot restore..."
    restore_output="$("${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/measure_restore.sh" 2 | tee /dev/stderr)"
    if ! awk '/^-/ { found=1; if ($NF != "0") exit 1 } END { if (!found) exit 1 }' <<<"${restore_output}"; then
      echo "Expected restored replica to report LOADING=0!"
      exit 1
    fi

    echo "Setting up port forwarding..."
    port_forwarding_failed=0
    forwarding_port=$(shuf -i 49152-65535 -n 1)
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" port-forward "service/vllm-fast-restore-${VLLM_VARIANT}" "${forwarding_port}:8000" >/dev/null &
    PF_PID=$!

    echo "Waiting for port forwarding..."
    attempts=0
    while ! echo -e '\x1dclose\x0d' | telnet localhost "${forwarding_port}" >/dev/null 2>&1; do
      if ! kill -0 "${PF_PID}" 2>/dev/null; then
        port_forwarding_failed=1
        echo "Port forwarding process exited!"
        echo
        break
      fi
      attempts=$((attempts + 1))
      if [[ ${attempts} -ge 300 ]]; then
        port_forwarding_failed=1
        echo "Timed out waiting for port forwarding!"
        kill -9 "${PF_PID}" 2>/dev/null || true
        break
      fi

      sleep 0.1
    done

    if [[ ${port_forwarding_failed} == 1 ]]; then
      exit 1
    fi

    echo "Sending GET request to '/v1/models'"
    echo "----------------------------------------------------------------------------------"
    curl --fail --request GET --show-error --silent "http://127.0.0.1:${forwarding_port}/v1/models" | jq -e '.data | length > 0'
    sleep 1
    echo "----------------------------------------------------------------------------------"
    echo

    echo "Sending POST request to '/v1/chat/completions'"
    echo "----------------------------------------------------------------------------------"
    curl "http://127.0.0.1:${forwarding_port}/v1/chat/completions" \
      --data '{
        "model": "'"${SERVED_MODEL_NAME}"'",
        "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
      }' \
      --fail \
      --header "Content-Type: application/json" \
      --request POST \
      --show-error \
      --silent | jq -e '.choices[0].message.content | length > 0'
    echo "----------------------------------------------------------------------------------"

    kill -9 "${PF_PID}" 2>/dev/null || true
    wait "${PF_PID}" 2>/dev/null || true
    echo
  else
    echo "'${HF_MODEL_ID}' model does not have a configuration for '${ACCELERATOR_TYPE}', skipping."
    echo
  fi
done
