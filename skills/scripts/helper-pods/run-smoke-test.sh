#!/usr/bin/env bash
# Copyright 2026 Google LLC
# Sourced dynamic gateway endpoint smoke test validation helper

set -eo pipefail

NAMESPACE=${1}
GATEWAY_NAME="llm-d-inference-gateway"

# 1. Resolve Gateway IP Address dynamically
echo "Resolving IP address for Gateway '${GATEWAY_NAME}' in namespace '${NAMESPACE}'..."
GATEWAY_IP=$(kubectl get gateway "${GATEWAY_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.addresses[0].value}' 2>/dev/null || true)

if [ -z "${GATEWAY_IP}" ]; then
  echo "Warning: Gateway resource not found or lacks programmed IP. Falling back to default ClusterIP service..."
  # Try EPP router ClusterIP service
  GATEWAY_IP=$(kubectl get svc precise-prefix-cache-routing-epp -n "${NAMESPACE}" -o jsonpath='{.spec.clusterIP}' 2>/dev/null || true)
fi

if [ -z "${GATEWAY_IP}" ]; then
  echo "Error: Could not resolve Gateway IP or fallback service IP."
  exit 1
fi

echo "Resolved Endpoint IP: ${GATEWAY_IP}"

# 2. Deploy temporary smoke-test pod using resolved IP
echo "Launching model-smoke-test pod..."
kubectl apply -f -smoke-test.yaml


# 3. Wait for pod execution to complete
echo "Waiting for pod model-smoke-test to complete..."
kubectl wait --for=condition=Ready pod/model-smoke-test -n "${NAMESPACE}" --timeout=60s >/dev/null

# 4. Fetch logs and status
echo "Fetching endpoint response..."
kubectl logs pod/model-smoke-test -n "${NAMESPACE}"

# 5. Clean up pod
echo "Cleaning up smoke-test pod..."
kubectl delete pod model-smoke-test -n "${NAMESPACE}" >/dev/null
echo "Smoke test helper complete!"
