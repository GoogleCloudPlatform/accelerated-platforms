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

# Act 3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection
# Demonstrates:
# 1. Setting a per-actor `EgressPolicy` on `triage-actor-42` that permits HTTPS
#    solely to `api.github.com:443` and injects the `Authorization` header out
#    of sandbox from `agent-credentials/github-readonly-token`.
# 2. Pushing a dynamic L7 HTTP method/path rule (`GET`, `HEAD` only) to
#    `ate-system/intent-extproc`.
# 3. Verifying from inside the actor sandbox:
#    - `GET https://api.github.com/repos/${GITHUB_REPO}/issues` succeeds (`200 OK`)
#      without any token inside the sandbox environment or filesystem.
#    - `POST https://api.github.com/repos/${GITHUB_REPO}/issues/1/comments` is
#      rejected with `403 Forbidden` by `intent-extproc`.
#    - `GET https://unapproved-collector.example.com/telemetry` is blocked by
#      `atenet-egress` default-deny egress (`NXDOMAIN` / connection rejected).

set -o errexit
set -o nounset
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../kubernetes-manifests"
ATESPACE="${SUBSTRATE_ATESPACE:-secure-runtime}"
ACTOR_NAME="${ACTOR_NAME:-triage-actor-42}"
TEMPLATE_NAME="${SUBSTRATE_ACTOR_TEMPLATE:-scientific-python}"
GITHUB_REPO="${GITHUB_REPO:-GoogleCloudPlatform/accelerated-platforms}"

echo "========================================================================"
echo " ACT 3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection  "
echo "========================================================================"

if ! kubectl-ate get actor "${ACTOR_NAME}" -a "${ATESPACE}" >/dev/null 2>&1; then
  kubectl-ate create actor "${ACTOR_NAME}" -a "${ATESPACE}" --template "${TEMPLATE_NAME}"
fi

echo "==> 1. Applying per-actor EgressPolicy (api.github.com:443 + out-of-sandbox replaceHeaders)..."
kubectl-ate delete egress-policy "${ACTOR_NAME}" -a "${ATESPACE}" >/dev/null 2>&1 || true
kubectl-ate create egress-policy "${ACTOR_NAME}" -a "${ATESPACE}" \
  -f "${MANIFESTS_DIR}/substrate/github-read-egress-policy.yaml"

echo "==> 2. Pushing dynamic READ_ONLY L7 rule (GET/HEAD only) to intent-extproc..."
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ATESPACE}/${ACTOR_NAME}" "${GITHUB_REPO}" <<'PYEOF'
import json
import os
import sys
import httpx

actor_ref = sys.argv[1]
github_repo = sys.argv[2]
control_url = os.environ.get("INTENT_EXTPROC_CONTROL_URL", "http://intent-extproc.ate-system.svc:8080")
resp = httpx.put(
    f"{control_url}/v1/policies",
    json={
        "actor": actor_ref,
        "intent": "github_issue_read_only",
        "allowed_hosts": ["api.github.com"],
        "allowed_methods": ["GET", "HEAD"],
        "allowed_path_prefixes": [f"/repos/{github_repo}/"],
    },
    timeout=10.0,
)
resp.raise_for_status()
print(json.dumps(resp.json(), indent=2))
PYEOF

echo ""
echo "==> 3. Verifying zero credentials exist inside the actor sandbox environment or filesystem..."
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ACTOR_NAME}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
cred_check_code = """
import os
suspect_vars = {k: v for k, v in os.environ.items() if any(tok in k.upper() for tok in ("TOKEN", "SECRET", "KEY", "PAT", "AUTH"))}
print("Credential-like environment variables inside sandbox:", suspect_vars)
print("Kubernetes serviceaccount secret mount exists:", os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"))
"""
client = SubstrateClient()
print(json.dumps(client.call_actor(actor_name, "POST", "/exec", {"code": cred_check_code}), indent=2))
PYEOF

echo ""
echo "==> 4. [ALLOWED INTENT] Testing GET https://api.github.com/repos/${GITHUB_REPO}/issues (credential injected at egress gateway):"
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ACTOR_NAME}" "${GITHUB_REPO}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
github_repo = sys.argv[2]
client = SubstrateClient()
res = client.call_actor(
    actor_name,
    "POST",
    "/egress-test",
    {
        "method": "GET",
        "url": f"https://api.github.com/repos/{github_repo}/issues?per_page=1",
        "headers": {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer ate-injected-at-egress",
        },
    },
)
print(json.dumps(res, indent=2))
PYEOF

echo ""
echo "==> 5. [BLOCKED WRITE INTENT] Testing POST https://api.github.com/repos/${GITHUB_REPO}/issues/1/comments (blocked at L7 by intent-extproc):"
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ACTOR_NAME}" "${GITHUB_REPO}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
github_repo = sys.argv[2]
client = SubstrateClient()
res = client.call_actor(
    actor_name,
    "POST",
    "/egress-test",
    {
        "method": "POST",
        "url": f"https://api.github.com/repos/{github_repo}/issues/1/comments",
        "headers": {
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer ate-injected-at-egress",
        },
        "body": '{"body": "Unauthorized comment attempt"}',
    },
)
print(json.dumps(res, indent=2))
PYEOF

echo ""
echo "==> 6. [BLOCKED DESTINATION] Testing GET https://unapproved-collector.example.com/telemetry (blocked by default-deny DNS/egress):"
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ACTOR_NAME}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
client = SubstrateClient()
res = client.call_actor(
    actor_name,
    "POST",
    "/egress-test",
    {
        "method": "GET",
        "url": "https://unapproved-collector.example.com/telemetry",
    },
)
print(json.dumps(res, indent=2))
PYEOF
