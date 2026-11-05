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
echo "========================================================================"
echo " #4: SPIFFE Audit Trail, Quarantine & Clean Golden Snapshot Reset       "
echo "========================================================================"
kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c 'import json, sys, urllib.request; req = urllib.request.Request("http://127.0.0.1:8080/api/part4", data=json.dumps({"tainted_actor": sys.argv[1]}).encode(), headers={"Content-Type": "application/json"}, method="POST"); print(json.dumps(json.loads(urllib.request.urlopen(req, timeout=90).read().decode()), indent=2))' "${QUARANTINED_ACTOR}"
