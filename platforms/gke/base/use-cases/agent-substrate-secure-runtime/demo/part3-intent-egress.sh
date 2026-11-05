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

ISSUE_NUMBER="${ISSUE_NUMBER:-42}"
ACTOR_NAME="${ACTOR_NAME:-triage-actor-42}"
echo "========================================================================"
echo " #3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection     "
echo "========================================================================"
kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c 'import json, sys, urllib.request; req = urllib.request.Request("http://127.0.0.1:8080/api/part3", data=json.dumps({"issue_number": int(sys.argv[1]), "follow_instructions": True, "actor_name": sys.argv[2]}).encode(), headers={"Content-Type": "application/json"}, method="POST"); print(json.dumps(json.loads(urllib.request.urlopen(req, timeout=90).read().decode()), indent=2))' "${ISSUE_NUMBER}" "${ACTOR_NAME}"
