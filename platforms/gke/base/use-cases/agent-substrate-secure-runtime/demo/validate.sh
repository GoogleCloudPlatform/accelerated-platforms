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

# End-to-end validation script for the Agent Substrate Secure Runtime deployment.

set -o errexit
set -o nounset
set -o pipefail

ATESPACE="${SUBSTRATE_ATESPACE:-secure-runtime}"

echo "==> 1. Checking ate-system control plane & data plane pods..."
kubectl get pods -n ate-system
kubectl wait --for=condition=Available deployment/ate-api-server -n ate-system --timeout=120s
kubectl wait --for=condition=Available deployment/atenet-router -n ate-system --timeout=120s
kubectl wait --for=condition=Available deployment/atenet-egress -n ate-system --timeout=120s
kubectl wait --for=condition=Available deployment/intent-extproc -n ate-system --timeout=120s

echo "==> 2. Checking WorkerPool in ate-workers..."
kubectl get workerpool -n ate-workers
kubectl get pods -n ate-workers -l workload=scientific-python
READY_WORKERS="$(kubectl get deployment scientific-gvisor -n ate-workers -o jsonpath='{.status.readyReplicas}')"
if [[ "${READY_WORKERS:-0}" -lt 1 ]]; then
  echo "Error: Expected at least 1 Ready replica in WorkerPool scientific-gvisor, got ${READY_WORKERS:-0}" >&2
  exit 1
fi

echo "==> 3. Checking ActorTemplate in atespace '${ATESPACE}'..."
kubectl-ate get actor-template scientific-python -a "${ATESPACE}"

echo "==> 4. Checking out-of-sandbox credential Secret in agent-credentials..."
kubectl get secret github-readonly-token -n agent-credentials

echo "==> 5. Checking ADK GitHub Triage Agent in agent-harness..."
kubectl wait --for=condition=Available deployment/triage-agent -n agent-harness --timeout=120s
kubectl get pods -n agent-harness

echo "==> All Secure Runtime components are healthy and ready for the live demo!"
