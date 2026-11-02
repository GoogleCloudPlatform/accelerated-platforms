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

# Act 4: End-to-End Audit Trail, Quarantine & Golden Snapshot Reset
# Demonstrates:
# 1. Inspecting the structured L7 audit log recorded by `intent-extproc` (showing
#    allowed `GET` calls and denied `POST` violations attributed to the actor's
#    cryptographic SPIFFE identity).
# 2. Checkpointing and suspending `triage-actor-42` (`kubectl-ate suspend actor`)
#    to preserve its memory & filesystem state for forensic analysis while
#    releasing worker compute.
# 3. Spawning a clean replacement actor from the immutable `scientific-python`
#    Golden Snapshot in <500ms.

set -o errexit
set -o nounset
set -o pipefail

ATESPACE="${SUBSTRATE_ATESPACE:-secure-runtime}"
QUARANTINED_ACTOR="${QUARANTINED_ACTOR:-triage-actor-42}"
CLEAN_ACTOR="triage-actor-clean-$(date +%s)"
TEMPLATE_NAME="${SUBSTRATE_ACTOR_TEMPLATE:-scientific-python}"

echo "========================================================================"
echo " ACT 4: Audit Trail, Forensic Quarantine & Clean Golden Snapshot Reset  "
echo "========================================================================"

echo "==> 1. Querying structured L7 egress audit events from intent-extproc (/v1/audit):"
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - <<'PYEOF'
import json
import os
import httpx

control_url = os.environ.get("INTENT_EXTPROC_CONTROL_URL", "http://intent-extproc.ate-system.svc:8080")
resp = httpx.get(f"{control_url}/v1/audit", timeout=10.0)
resp.raise_for_status()
print(json.dumps(resp.json(), indent=2))
PYEOF

echo ""
echo "==> 2. Quarantining '${ATESPACE}/${QUARANTINED_ACTOR}': revoking egress and checkpointing state to GCS..."
kubectl-ate delete egress-policy "${QUARANTINED_ACTOR}" -a "${ATESPACE}" >/dev/null 2>&1 || true
kubectl-ate suspend actor "${QUARANTINED_ACTOR}" -a "${ATESPACE}"
echo "    Actor '${QUARANTINED_ACTOR}' is now suspended to GCS with zero egress permissions."

echo ""
echo "==> 3. Spawning clean actor '${CLEAN_ACTOR}' from the immutable '${TEMPLATE_NAME}' Golden Snapshot..."
kubectl-ate create actor "${CLEAN_ACTOR}" -a "${ATESPACE}" --template "${TEMPLATE_NAME}" >/dev/null
READY_JSON="$(kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${CLEAN_ACTOR}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
client = SubstrateClient()
print(json.dumps(client.call_actor(actor_name, "GET", "/readyz")))
PYEOF
)"
SPAWN_MS="$(python3 -c 'import json, sys; print(json.loads(sys.stdin.read())["router_roundtrip_ms"])' <<<"${READY_JSON}")"
echo "    Clean actor '${ATESPACE}/${CLEAN_ACTOR}' restored from Golden Snapshot & ready in ${SPAWN_MS} ms."

# Suspend the clean actor when idle so the warm worker slot is returned to the pool.
kubectl-ate suspend actor "${CLEAN_ACTOR}" -a "${ATESPACE}" >/dev/null 2>&1 || true
