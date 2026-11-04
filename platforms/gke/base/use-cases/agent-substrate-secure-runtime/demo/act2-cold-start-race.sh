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

echo "========================================================================"
echo " ACT 2: Cold-Start Race — Standard gVisor Pod vs Substrate Golden Snapshot"
echo "========================================================================"

RUNNER_IMAGE="$(kubectl get deployment triage-agent -n agent-harness -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null | sed 's/secure-runtime-agent:/secure-runtime-runner:/')"
if [[ -z "${RUNNER_IMAGE}" ]]; then
  echo "Error: Could not resolve RUNNER_IMAGE from cluster. Set RUNNER_IMAGE env var explicitly." >&2
  exit 1
fi

trap 'kubectl delete pod cold-gvisor-baseline -n default --ignore-not-found >/dev/null 2>&1 || true' EXIT

echo "==> [Baseline A] Creating fresh cold Kubernetes gVisor Pod (cold-gvisor-baseline)..."
kubectl delete pod cold-gvisor-baseline -n default --ignore-not-found >/dev/null 2>&1 || true

COLD_START_NS="$(date +%s%N)"
sed "s|\${RUNNER_IMAGE}|${RUNNER_IMAGE}|g" "${MANIFESTS_DIR}/baseline/cold-pod.yaml" | kubectl apply -f - >/dev/null
kubectl wait --for=condition=Ready pod/cold-gvisor-baseline -n default --timeout=180s >/dev/null
COLD_END_NS="$(date +%s%N)"
COLD_TOTAL_MS="$(( (COLD_END_NS - COLD_START_NS) / 1000000 ))"
echo "    [Baseline A] Cold gVisor Pod Ready (incl. numpy/scipy/pandas/matplotlib import): ${COLD_TOTAL_MS} ms"

echo ""
echo "==> [Substrate B] Creating, waking, suspending, and resuming Actor '${WARM_ACTOR}' from Golden Snapshot '${TEMPLATE_NAME}'..."
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${WARM_ACTOR}" "${COLD_TOTAL_MS}" <<'PYEOF'
import json, sys
from secure_runtime_agent.agent import run_python_in_actor
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name, cold_ms = sys.argv[1], sys.argv[2]
client = SubstrateClient()
client.ensure_actor(actor_name)
ready = client.call_actor(actor_name, "GET", "/readyz")
warm_ms = ready["router_roundtrip_ms"]

run_python_in_actor(
    code='STATE = {"issue": 19, "solver": "tikhonov_1e-6", "status": "verified"}',
    actor_name=actor_name,
    suspend_after=True,
)
resumed = json.loads(
    run_python_in_actor(
        code="import json; print(json.dumps(STATE))",
        actor_name=actor_name,
        suspend_after=True,
    )
)["execution"]

print(f"    [Substrate B] Golden Snapshot Actor Ready (/readyz): {warm_ms} ms")
print(f"    [Substrate B] Pre-loaded scientific stack payload  : {json.dumps(ready)}")
print("\n------------------------------------------------------------------------")
print(" COLD-START RACE SUMMARY")
print("------------------------------------------------------------------------")
print(f" {'Standard Kubernetes gVisor Pod (Cold Boot)':<42} : {cold_ms:>8} ms")
print(f" {'Agent Substrate Golden Snapshot Wakeup':<42} : {warm_ms:>8} ms")
print(f" {'Agent Substrate Stateful Pause -> Resume':<42} : {resumed['router_roundtrip_ms']:>8} ms")
print("------------------------------------------------------------------------")
print(f"Restored in-memory state from GCS snapshot: {resumed['stdout'].strip()}")
PYEOF
