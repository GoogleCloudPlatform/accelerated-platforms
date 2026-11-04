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

# Act 1: The Untrusted Boundary (gVisor Sentry User-Space Kernel Isolation)
# Demonstrates how untrusted model-generated code executes inside an Agent
# Substrate actor isolated by gVisor (`runsc`), intercepting system calls in
# user space and masking host kernel interfaces.

set -o errexit
set -o nounset
set -o pipefail

ATESPACE="${SUBSTRATE_ATESPACE:-secure-runtime}"
ACTOR_NAME="${ACTOR_NAME:-triage-actor-19}"

echo "========================================================================"
echo " ACT 1: The Untrusted Boundary — gVisor User-Space Syscall Interception "
echo "========================================================================"

kubectl exec -i -n agent-harness deploy/triage-agent -- \
  python3 -c "import sys; from secure_runtime_agent.agent import inspect_sandbox_boundary; print(inspect_sandbox_boundary(sys.argv[1]))" "${ACTOR_NAME}"

echo ""
echo "==> Act 1 complete: Application syscalls are intercepted by the gVisor Sentry in user space."
