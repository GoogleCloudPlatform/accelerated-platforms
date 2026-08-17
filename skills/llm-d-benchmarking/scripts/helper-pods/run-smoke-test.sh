#!/usr/bin/env bash
# Copyright 2026 Google LLC
# Sourced dynamic gateway endpoint smoke test validation helper

set -eo pipefail

ENDPOINT_URL=${1}
NAMESPACE=${2:-"default"}

if [ -z "${ENDPOINT_URL}" ]; then
  echo "Usage: $0 <endpoint_url> [namespace]"
  echo "Example: $0 http://vllm-service:8000 default"
  exit 1
fi

echo "Testing Endpoint URL: ${ENDPOINT_URL}"

# 1. Deploy temporary smoke-test pod
echo "Launching model-smoke-test pod..."
SCRIPT_DIR=$(dirname "$0")
sed "s,REPLACE_ENDPOINT_URL,${ENDPOINT_URL},g" "${SCRIPT_DIR}/smoke-test.yaml" | kubectl apply -n "${NAMESPACE}" -f -

# 2. Wait for pod execution to complete
echo "Waiting for pod model-smoke-test to complete..."
kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/model-smoke-test -n "${NAMESPACE}" --timeout=60s >/dev/null || true

# 3. Fetch logs and status
echo "Fetching endpoint response..."
kubectl logs pod/model-smoke-test -n "${NAMESPACE}"

# 4. Clean up pod
echo "Cleaning up smoke-test pod..."
kubectl delete pod model-smoke-test -n "${NAMESPACE}" --ignore-not-found --grace-period=0 --force >/dev/null
echo "Smoke test helper complete!"
