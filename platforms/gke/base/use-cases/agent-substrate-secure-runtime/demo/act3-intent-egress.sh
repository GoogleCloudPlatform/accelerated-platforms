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
GITHUB_REPO="${GITHUB_REPO:-demo-org/secure-runtime-sandbox-demo}"
ACTOR_PORT="${ACTOR_PORT:-18083}"
EXTPROC_PORT="${EXTPROC_PORT:-18080}"

echo "========================================================================"
echo " ACT 3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection  "
echo "========================================================================"

if ! kubectl-ate get actor "${ACTOR_NAME}" -a "${ATESPACE}" >/dev/null 2>&1; then
  kubectl-ate create actor "${ACTOR_NAME}" -a "${ATESPACE}" --template "${TEMPLATE_NAME}"
fi

echo "==> 1. Applying per-actor EgressPolicy (api.github.com:443 + out-of-sandbox replaceHeaders)..."
kubectl-ate set egress-policy "${ACTOR_NAME}" -a "${ATESPACE}" \
  -f "${MANIFESTS_DIR}/substrate/github-read-egress-policy.yaml"

echo "==> 2. Pushing dynamic READ_ONLY L7 rule (GET/HEAD only) to intent-extproc..."
kubectl port-forward -n ate-system svc/intent-extproc "${EXTPROC_PORT}:8080" >/tmp/act3-extproc-pf.log 2>&1 &
EXTPROC_PF_PID=$!
kubectl-ate proxy actor "${ACTOR_NAME}" -a "${ATESPACE}" --port "${ACTOR_PORT}" >/tmp/act3-actor-proxy.log 2>&1 &
ACTOR_PROXY_PID=$!
trap 'kill "${EXTPROC_PF_PID}" "${ACTOR_PROXY_PID}" >/dev/null 2>&1 || true' EXIT
sleep 2

curl -fsS -X PUT "http://127.0.0.1:${EXTPROC_PORT}/v1/policies" \
  -H "Content-Type: application/json" \
  -d "{
    \"actor\": \"${ATESPACE}/${ACTOR_NAME}\",
    \"intent\": \"github_issue_read_only\",
    \"allowed_hosts\": [\"api.github.com\"],
    \"allowed_methods\": [\"GET\", \"HEAD\"],
    \"allowed_path_prefixes\": [\"/repos/${GITHUB_REPO}/\"]
  }" | python3 -m json.tool

echo ""
echo "==> 3. Verifying zero credentials exist inside the actor sandbox environment or filesystem..."
read -r -d '' CRED_CHECK_CODE <<'PYEOF' || true
import os
suspect_vars = {k: v for k, v in os.environ.items() if any(tok in k.upper() for tok in ("TOKEN", "SECRET", "KEY", "PAT", "AUTH"))}
print("Credential-like environment variables inside sandbox:", suspect_vars)
print("Kubernetes serviceaccount secret mount exists:", os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount/token"))
PYEOF
PAYLOAD="$(python3 -c 'import json, sys; print(json.dumps({"code": sys.stdin.read()}))' <<<"${CRED_CHECK_CODE}")"
curl -fsS -X POST "http://127.0.0.1:${ACTOR_PORT}/exec" \
  -H "Content-Type: application/json" \
  -d "${PAYLOAD}" | python3 -m json.tool

echo ""
echo "==> 4. [ALLOWED INTENT] Testing GET https://api.github.com/repos/${GITHUB_REPO}/issues (credential injected at egress gateway):"
curl -fsS -X POST "http://127.0.0.1:${ACTOR_PORT}/egress-test" \
  -H "Content-Type: application/json" \
  -d "{
    \"method\": \"GET\",
    \"url\": \"https://api.github.com/repos/${GITHUB_REPO}/issues\",
    \"headers\": {\"Accept\": \"application/vnd.github+json\"}
  }" | python3 -m json.tool

echo ""
echo "==> 5. [BLOCKED WRITE INTENT] Testing POST https://api.github.com/repos/${GITHUB_REPO}/issues/1/comments (blocked at L7 by intent-extproc):"
curl -fsS -X POST "http://127.0.0.1:${ACTOR_PORT}/egress-test" \
  -H "Content-Type: application/json" \
  -d "{
    \"method\": \"POST\",
    \"url\": \"https://api.github.com/repos/${GITHUB_REPO}/issues/1/comments\",
    \"headers\": {\"Accept\": \"application/vnd.github+json\"},
    \"body\": \"{\\\"body\\\": \\\"Unauthorized comment attempt\\\"}\"
  }" | python3 -m json.tool

echo ""
echo "==> 6. [BLOCKED DESTINATION] Testing GET https://unapproved-collector.example.com/telemetry (blocked by default-deny DNS/egress):"
curl -fsS -X POST "http://127.0.0.1:${ACTOR_PORT}/egress-test" \
  -H "Content-Type: application/json" \
  -d "{
    \"method\": \"GET\",
    \"url\": \"https://unapproved-collector.example.com/telemetry\"
  }" | python3 -m json.tool
