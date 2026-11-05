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

# Set TRTLLM_VARIANT_SUFFIX=-podsnapshot to select the GKE Pod snapshot overlays.
IRA_GPU_ENGINE_DIR="trtllm"
IRA_GPU_CONFIGURE="configure_trtllm.sh"
IRA_GPU_SERVICE="trtllm"
IRA_GPU_VARIANT_SUFFIX="${TRTLLM_VARIANT_SUFFIX:-}"
# shellcheck source=test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/common.sh
source "${MY_PATH}/../common.sh"
# shellcheck disable=SC2154
if [[ "${IRA_GPU_VARIANT_SUFFIX}" == "-podsnapshot" ]]; then
  IRA_GPU_MODELS=("${hf_gpu_trtllm_podsnapshot_models[@]}")
else
  IRA_GPU_MODELS=("${hf_gpu_trtllm_models[@]}")
fi

test_variant() {
  local variant_dir="${1}" app restore_output
  ira_gpu_wait_ready "${variant_dir}"

  if [[ -n "$(ira_gpu_rendered_names "${variant_dir}" PodSnapshotPolicy)" ]]; then
    app="$(ira_gpu_runtime_value "${variant_dir}" APP_LABEL)"
    ira_gpu_wait_pod_snapshot "${app}"
    echo "Waiting for the cold-start replica to resume after the checkpoint upload..."
    # shellcheck disable=SC2154
    kubectl --namespace="${ira_online_gpu_kubernetes_namespace_name}" rollout status "deployment/${app}" --timeout=300s
    ira_gpu_smoke_test "${variant_dir}"

    echo "Scaling to 2 replicas and measuring the snapshot restore..."
    restore_output="$(APP="${app}" SERVED_MODEL_NAME="$(ira_gpu_runtime_value "${variant_dir}" MODEL_ID)" \
      "${MY_PATH}/../measure_restore.sh" 2 | tee /dev/stderr)"
    if ! awk '
      /^POD \(suffix\)/ { in_table=1; next }
      in_table && NF == 0 { in_table=0 }
      in_table {
        rows++
        if ($NF != "0" || $(NF-1) == "-" || $(NF-2) == "-" || $(NF-3) == "-" || $(NF-4) == "-") {
          bad=1
        }
      }
      END { exit (rows > 0 && !bad) ? 0 : 1 }
    ' <<<"${restore_output}"; then
      echo "Expected the restored replica to report Ready, PodRestored, FIRST_RESPONSE, and LOADING=0!" >&2
      exit 1
    fi
    return
  fi

  ira_gpu_smoke_test "${variant_dir}"
}

ira_gpu_for_each_variant test_variant
