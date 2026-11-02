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
TEMPLATE_NAME="${SUBSTRATE_ACTOR_TEMPLATE:-scientific-python}"

echo "========================================================================"
echo " ACT 1: The Untrusted Boundary — gVisor User-Space Syscall Interception "
echo "========================================================================"

if ! kubectl-ate get actor "${ACTOR_NAME}" -a "${ATESPACE}" >/dev/null 2>&1; then
  echo "==> Creating actor '${ACTOR_NAME}' in atespace '${ATESPACE}' from template '${TEMPLATE_NAME}'..."
  kubectl-ate create actor "${ACTOR_NAME}" -a "${ATESPACE}" --template "${TEMPLATE_NAME}"
fi

echo "==> 1. Inspecting container security boundary inside the actor (/boundary via mTLS atenet-router):"
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ACTOR_NAME}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
client = SubstrateClient()
print(json.dumps(client.call_actor(actor_name, "GET", "/boundary"), indent=2))
PYEOF

echo ""
echo "==> 2. Probing restricted kernel operations inside the gVisor Sentry (/exec):"
kubectl exec -i -n agent-harness deploy/triage-agent -- python3 - "${ACTOR_NAME}" <<'PYEOF'
import json
import sys
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = sys.argv[1]
boundary_code = """
import os
import platform
import subprocess

print(f"Kernel release reported by Sentry : {platform.release()}")
for path in ["/proc/kcore", "/proc/kallsyms", "/proc/sysrq-trigger", "/sys/firmware"]:
    try:
        with open(path, "rb") as f:
            data = f.read(16)
        print(f"  [UNEXPECTED] Read {path}: {len(data)} bytes")
    except Exception as exc:
        print(f"  [BLOCKED BY SENTRY] {path} -> {type(exc).__name__}: {exc}")

kmsg = subprocess.run(["dmesg"], capture_output=True, text=True)
print(f"dmesg exit_code={kmsg.returncode} stderr={kmsg.stderr.strip() or 'restricted by user-space kernel'}")
"""
client = SubstrateClient()
res = client.call_actor(actor_name, "POST", "/exec", {"code": boundary_code})
print(json.dumps(res, indent=2))
PYEOF

echo ""
echo "==> Act 1 complete: Application syscalls are intercepted by the gVisor Sentry in user space."
