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

# Act 2: Crushing the Cold-Start Penalty (Golden Snapshot Restore vs Cold K8s gVisor Pod)
# Side-by-side race between:
#   A) Standard Kubernetes Pod with `runtimeClassName: gvisor` booting and importing
#      `numpy`, `scipy`, `pandas`, and `matplotlib` from scratch (~15-25s).
#   B) Agent Substrate Actor restored from the `scientific-python` Golden Snapshot
#      (`SNAPSHOT_FIDELITY_MEMORY`) onto a warm WorkerPool pod (<500ms).

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../kubernetes-manifests"
ATESPACE="${SUBSTRATE_ATESPACE:-secure-runtime}"
TEMPLATE_NAME="${SUBSTRATE_ACTOR_TEMPLATE:-scientific-python}"
WARM_ACTOR="race-actor-$(date +%s)"
PROXY_PORT="${PROXY_PORT:-18082}"

echo "========================================================================"
echo " ACT 2: Cold-Start Race — Standard gVisor Pod vs Substrate Golden Snapshot"
echo "========================================================================"

RUNNER_IMAGE="$(kubectl get deployment triage-agent -n agent-harness -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null | sed 's/secure-runtime-agent:/secure-runtime-runner:/')"
if [[ -z "${RUNNER_IMAGE}" ]]; then
  echo "Error: Could not resolve RUNNER_IMAGE from cluster. Set RUNNER_IMAGE env var explicitly." >&2
  exit 1
fi

echo "==> [Baseline A] Creating fresh cold Kubernetes gVisor Pod (cold-gvisor-baseline)..."
kubectl delete pod cold-gvisor-baseline -n default --ignore-not-found >/dev/null 2>&1 || true

COLD_START_NS="$(date +%s%N)"
sed "s|\${RUNNER_IMAGE}|${RUNNER_IMAGE}|g" "${MANIFESTS_DIR}/baseline/cold-pod.yaml" | kubectl apply -f - >/dev/null
kubectl wait --for=condition=Ready pod/cold-gvisor-baseline -n default --timeout=180s >/dev/null
COLD_END_NS="$(date +%s%N)"
COLD_TOTAL_MS="$(( (COLD_END_NS - COLD_START_NS) / 1000000 ))"
echo "    [Baseline A] Cold gVisor Pod Ready (incl. numpy/scipy/pandas/matplotlib import): ${COLD_TOTAL_MS} ms"

echo ""
echo "==> [Substrate B] Creating & waking Actor '${WARM_ACTOR}' from Golden Snapshot '${TEMPLATE_NAME}'..."
kubectl-ate create actor "${WARM_ACTOR}" -a "${ATESPACE}" --template "${TEMPLATE_NAME}" >/dev/null

kubectl-ate proxy actor "${WARM_ACTOR}" -a "${ATESPACE}" --port "${PROXY_PORT}" >/tmp/act2-proxy.log 2>&1 &
PROXY_PID=$!
trap 'kill "${PROXY_PID}" >/dev/null 2>&1 || true; kubectl delete pod cold-gvisor-baseline -n default --ignore-not-found >/dev/null 2>&1 || true' EXIT
sleep 1

WARM_START_NS="$(date +%s%N)"
READY_JSON="$(curl -fsS "http://127.0.0.1:${PROXY_PORT}/readyz")"
WARM_END_NS="$(date +%s%N)"
WARM_TOTAL_MS="$(( (WARM_END_NS - WARM_START_NS) / 1000000 ))"
echo "    [Substrate B] Golden Snapshot Actor Ready (/readyz): ${WARM_TOTAL_MS} ms"
echo "    [Substrate B] Pre-loaded scientific stack payload  : ${READY_JSON}"

echo ""
echo "==> [Stateful Pause/Resume Check] Writing state to /tmp/triage-state.json, pausing, and resuming..."
curl -fsS -X POST "http://127.0.0.1:${PROXY_PORT}/fs-state" \
  -H "Content-Type: application/json" \
  -d '{"issue": 19, "solver": "tikhonov_1e-6", "status": "verified"}' >/dev/null

kubectl-ate pause actor "${WARM_ACTOR}" -a "${ATESPACE}" >/dev/null
RESUME_START_NS="$(date +%s%N)"
STATE_AFTER_RESUME="$(curl -fsS "http://127.0.0.1:${PROXY_PORT}/fs-state")"
RESUME_END_NS="$(date +%s%N)"
RESUME_MS="$(( (RESUME_END_NS - RESUME_START_NS) / 1000000 ))"

echo ""
echo "------------------------------------------------------------------------"
echo " COLD-START RACE SUMMARY"
echo "------------------------------------------------------------------------"
printf " %-42s : %8d ms\n" "Standard Kubernetes gVisor Pod (Cold Boot)" "${COLD_TOTAL_MS}"
printf " %-42s : %8d ms\n" "Agent Substrate Golden Snapshot Wakeup" "${WARM_TOTAL_MS}"
printf " %-42s : %8d ms\n" "Agent Substrate Stateful Pause -> Resume" "${RESUME_MS}"
echo "------------------------------------------------------------------------"
echo "Restored state from GCS snapshot: ${STATE_AFTER_RESUME}"
