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
#
# Scales a vllm-fast-restore Deployment out and measures each new replica.
#
# `Ready` is not a restore measurement: a restored vLLM process answers
# `/health` as soon as gVisor resumes it, while GKE is still loading its memory
# from Cloud Storage. This script therefore reports, for every new Pod:
#
#   - PodScheduled -> Ready
#   - PodScheduled -> PodRestored (set by GKE when the restore is complete)
#   - PodScheduled -> first successful /v1/completions response
#
# plus the node's age when the Pod was scheduled and the image pull event, so
# each result states whether it ran on a new node and whether the image was
# already on disk.
#
# Requests are sent from an existing replica of the same Deployment (the vLLM
# image includes curl), directly to the new Pod's IP, starting as soon as the
# Pod has one.
#
# Usage:
#   export VLLM_VARIANT=... SERVED_MODEL_NAME=...
#   measure_restore.sh [REPLICAS]    # default: current replicas + 1
#
# Requires GNU date (Cloud Shell or Linux).
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

source "${MY_PATH}/../../../terraform/_shared_config/scripts/set_environment_variables.sh" >/dev/null

: "${VLLM_VARIANT:?Set VLLM_VARIANT, for example l4-llama-3-1-8b-instruct}"
: "${SERVED_MODEL_NAME:?Set SERVED_MODEL_NAME, for example meta-llama/Llama-3.1-8B-Instruct}"

if ! date --version >/dev/null 2>&1; then
  echo "GNU date is required. Run this script from Cloud Shell or Linux." >&2
  exit 1
fi

NS="${ira_online_gpu_kubernetes_namespace_name}"
APP="vllm-fast-restore-${VLLM_VARIANT}"
KUBECTL=(kubectl --namespace="${NS}")
DEADLINE_SECONDS="${DEADLINE_SECONDS:-3600}"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

epoch() { date --date="$1" +%s.%N; }
rel() { # rel <t> <t0>: seconds from t0 to t, one decimal
  if [[ -z "$1" || -z "$2" ]]; then echo "-"; else awk -v a="$1" -v b="$2" 'BEGIN { printf "%.1f", a - b }'; fi
}
since() { # since <RFC 3339 time or empty> <t0>
  if [[ -z "$1" ]]; then echo "-"; else rel "$(epoch "$1")" "$2"; fi
}
cond() { # cond <pod> <type>: lastTransitionTime of a True condition
  "${KUBECTL[@]}" get pod "$1" \
    --output=jsonpath="{.status.conditions[?(@.type==\"$2\")].lastTransitionTime}"
}

# The snapshot must exist before scaling out, or the new Pods start cold.
snapshots="$("${KUBECTL[@]}" get podsnapshots \
  --output=jsonpath="{range .items[?(@.spec.policyName==\"vllm-fast-restore-snapshot-policy-${VLLM_VARIANT}\")]}{.metadata.name}{\" \"}{.status.conditions[?(@.type==\"Ready\")].reason}{\"\n\"}{end}")"
if ! grep -q "AllSnapshotsAvailable" <<<"${snapshots}"; then
  echo "No PodSnapshot for ${APP} is AllSnapshotsAvailable yet:" >&2
  echo "${snapshots:-<none>}" >&2
  exit 1
fi

read -r -a before <<<"$("${KUBECTL[@]}" get pods --selector="app=${APP}" \
  --output=jsonpath='{.items[*].metadata.name}')"
if [[ ${#before[@]} -eq 0 ]]; then
  echo "No existing ${APP} Pod to send requests from." >&2
  exit 1
fi
client="$("${KUBECTL[@]}" get pods --selector="app=${APP}" \
  --sort-by=.metadata.creationTimestamp \
  --output=jsonpath='{.items[0].metadata.name}')"

current="$("${KUBECTL[@]}" get deployment "${APP}" --output=jsonpath='{.spec.replicas}')"
target="${1:-$((current + 1))}"
want=$((target - ${#before[@]}))
if [[ ${want} -le 0 ]]; then
  echo "REPLICAS (${target}) must be larger than the number of existing Pods (${#before[@]})." >&2
  exit 1
fi

"${KUBECTL[@]}" scale deployment "${APP}" --replicas="${target}" >/dev/null
echo "Scaled ${APP} from ${current} to ${target} at $(date --utc +%H:%M:%S). Sending requests from ${client}."

probe() { # probe <pod> <ip>: one line per request: start end http_code
  "${KUBECTL[@]}" exec "${client}" -- sh -c '
    body="{\"model\": \"'"${SERVED_MODEL_NAME}"'\", \"prompt\": \"The capital of France is\", \"max_tokens\": 8, \"temperature\": 0}"
    ok=0
    end=$(( $(date +%s) + '"${DEADLINE_SECONDS}"' ))
    while [ "$(date +%s)" -lt "${end}" ]; do
      s=$(date +%s.%N)
      code=$(curl --silent --output /dev/null --write-out "%{http_code}" --max-time 120 \
        --header "Content-Type: application/json" --data "${body}" \
        "http://'"$2"':8000/v1/completions" || true)
      echo "${s} $(date +%s.%N) ${code:-000}"
      if [ "${code}" = "200" ]; then
        ok=$((ok + 1)); [ "${ok}" -ge 3 ] && break
      else
        sleep 0.5
      fi
    done' >"${WORK_DIR}/$1.probe" 2>/dev/null
}

declare -A probed=()
stop=$(($(date +%s) + DEADLINE_SECONDS))
while [[ ${#probed[@]} -lt ${want} && $(date +%s) -lt ${stop} ]]; do
  while read -r pod ip; do
    [[ -z "${ip}" || " ${before[*]} " == *" ${pod} "* || -n "${probed[${pod}]:-}" ]] && continue
    echo "$(date --utc +%H:%M:%S) ${pod} has IP ${ip}; sending requests."
    probe "${pod}" "${ip}" &
    probed[${pod}]=$!
  done < <("${KUBECTL[@]}" get pods --selector="app=${APP}" \
    --output=jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.podIP}{"\n"}{end}')
  sleep 1
done
wait

printf '\n%-24s %8s %-18s %7s %12s %15s %9s %8s\n' \
  "POD (suffix)" "NODE_AGE" "IMAGE" "READY" "POD_RESTORED" "FIRST_RESPONSE" "LATENCY" "LOADING"
for pod in "${!probed[@]}"; do
  scheduled="$(epoch "$(cond "${pod}" PodScheduled)")"
  ready="$(cond "${pod}" Ready)"
  restored="$(cond "${pod}" PodRestored)"
  node="$("${KUBECTL[@]}" get pod "${pod}" --output=jsonpath='{.spec.nodeName}')"
  node_created="$(kubectl get node "${node}" --output=jsonpath='{.metadata.creationTimestamp}')"
  image="$("${KUBECTL[@]}" get events --field-selector="involvedObject.name=${pod},reason=Pulled" \
    --output=jsonpath='{.items[0].message}' | grep -o -e 'already present' -e 'in [0-9.]*m*s ' | head -1 || true)"
  first="$(awk '$3 == 200 { print $1, $2; exit }' "${WORK_DIR}/${pod}.probe")"
  loading="$("${KUBECTL[@]}" logs "${pod}" | grep -c -e "Model loading took" -e "Starting to load model" || true)"
  printf '%-24s %7ss %-18s %6ss %11ss %14ss %8ss %8s\n' \
    "${pod: -24}" \
    "$(since "${node_created}" "${scheduled}" | sed 's/^-//')" \
    "${image:-?}" \
    "$(since "${ready}" "${scheduled}")" \
    "$(since "${restored}" "${scheduled}")" \
    "$(rel "${first#* }" "${scheduled}")" \
    "$(rel "${first#* }" "${first%% *}")" \
    "${loading}"
done
cat <<'EOF'

Times are seconds from the Pod's PodScheduled condition (1 s resolution).
NODE_AGE is the node's age when the Pod was scheduled; a small value means a
new node. LOADING counts model-loading log lines and must be 0 for a restore.
FIRST_RESPONSE is when the first successful /v1/completions response arrived;
LATENCY is how long that request took.
EOF
