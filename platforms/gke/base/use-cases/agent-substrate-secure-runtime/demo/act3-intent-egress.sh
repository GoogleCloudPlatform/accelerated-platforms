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

ACTOR_NAME="${ACTOR_NAME:-triage-actor-42}"

echo "========================================================================"
echo " ACT 3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection  "
echo "========================================================================"

kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c "import sys; from secure_runtime_agent.agent import triage_github_issue_in_sandbox; print(triage_github_issue_in_sandbox(42, True, sys.argv[1]))" "${ACTOR_NAME}"
