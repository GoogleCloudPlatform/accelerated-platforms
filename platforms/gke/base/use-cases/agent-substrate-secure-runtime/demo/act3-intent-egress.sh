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

ACTOR_NAME="${ACTOR_NAME:-triage-actor-42}"
echo "========================================================================"
echo " ACT 3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection  "
echo "========================================================================"
kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c "import sys; from secure_runtime_agent.agent import triage_github_issue_in_sandbox; print(triage_github_issue_in_sandbox(42, True, sys.argv[1]))" "${ACTOR_NAME}"
