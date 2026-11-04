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

set -euo pipefail

QUARANTINED_ACTOR="${QUARANTINED_ACTOR:-triage-actor-42}"
CLEAN_ACTOR="triage-actor-clean-$(date +%s)"
echo "========================================================================"
echo " ACT 4: Audit Trail, Forensic Quarantine & Clean Golden Snapshot Reset  "
echo "========================================================================"
kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c "import sys; from secure_runtime_agent.agent import audit_and_reset_actor_to_golden; from secure_runtime_agent.substrate_client import SubstrateClient; print(audit_and_reset_actor_to_golden(sys.argv[1], sys.argv[2])); SubstrateClient().suspend_actor(sys.argv[2])" "${QUARANTINED_ACTOR}" "${CLEAN_ACTOR}"
