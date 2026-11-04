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

QUARANTINED_ACTOR="${QUARANTINED_ACTOR:-triage-actor-42}"
CLEAN_ACTOR="triage-actor-clean-$(date +%s)"

echo "========================================================================"
echo " ACT 4: Audit Trail, Forensic Quarantine & Clean Golden Snapshot Reset  "
echo "========================================================================"

kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c "import sys; from secure_runtime_agent.agent import audit_and_reset_actor_to_golden; from secure_runtime_agent.substrate_client import SubstrateClient; print(audit_and_reset_actor_to_golden(sys.argv[1], sys.argv[2])); SubstrateClient().suspend_actor(sys.argv[2])" "${QUARANTINED_ACTOR}" "${CLEAN_ACTOR}"
