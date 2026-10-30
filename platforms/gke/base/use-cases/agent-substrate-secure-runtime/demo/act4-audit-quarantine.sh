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
# 2. Checkpointing and suspending `triage-actor-42` (`kubectl-ate pause actor`)
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
EXTPROC_PORT="${EXTPROC_PORT:-18080}"

echo "========================================================================"
echo " ACT 4: Audit Trail, Forensic Quarantine & Clean Golden Snapshot Reset  "
echo "========================================================================"

kubectl port-forward -n ate-system svc/intent-extproc "${EXTPROC_PORT}:8080" >/tmp/act4-extproc-pf.log 2>&1 &
EXTPROC_PF_PID=$!
trap 'kill "${EXTPROC_PF_PID}" >/dev/null 2>&1 || true' EXIT
sleep 2

echo "==> 1. Querying structured L7 egress audit events from intent-extproc (/v1/audit):"
curl -fsS "http://127.0.0.1:${EXTPROC_PORT}/v1/audit" | python3 -m json.tool

echo ""
echo "==> 2. Quarantining '${ATESPACE}/${QUARANTINED_ACTOR}': revoking egress and checkpointing state to GCS..."
kubectl-ate set egress-policy "${QUARANTINED_ACTOR}" -a "${ATESPACE}" -f - <<'EOF'
rules: []
EOF
kubectl-ate pause actor "${QUARANTINED_ACTOR}" -a "${ATESPACE}"
echo "    Actor '${QUARANTINED_ACTOR}' is now suspended to GCS with zero egress permissions."

echo ""
echo "==> 3. Spawning clean actor '${CLEAN_ACTOR}' from the immutable '${TEMPLATE_NAME}' Golden Snapshot..."
START_NS="$(date +%s%N)"
kubectl-ate create actor "${CLEAN_ACTOR}" -a "${ATESPACE}" --template "${TEMPLATE_NAME}"
END_NS="$(date +%s%N)"
SPAWN_MS="$(( (END_NS - START_NS) / 1000000 ))"
echo "    Clean actor '${ATESPACE}/${CLEAN_ACTOR}' created from Golden Snapshot in ${SPAWN_MS} ms."
