#!/bin/sh
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
#
# GKE In-Pod Runner
#
# Description:
#   This script automates running a test inside a temporary GKE pod.
#   It is configured entirely via environment variables.
#
# Required Environment Variables:
#   GKE_CLUSTER, GKE_REGION, GKE_PROJECT, NAMESPACE, COMFYUI_URL,
#   WORKFLOWS_DIR, TEST_DIR
#
# ==============================================================================

# --- Script Configuration ---
set -e # Exit immediately if any command fails.

# Check for all required environment variables
if [ -z "$GKE_CLUSTER" ] || [ -z "$GKE_REGION" ] || [ -z "$GKE_PROJECT" ] || \
   [ -z "$NAMESPACE" ] || [ -z "$COMFYUI_URL" ] || [ -z "$WORKFLOWS_DIR" ] || \
   [ -z "$TEST_DIR" ]; then
    echo "Error: One or more required environment variables are not set." >&2
    echo "Required: GKE_CLUSTER, GKE_REGION, GKE_PROJECT, NAMESPACE, COMFYUI_URL, WORKFLOWS_DIR, TEST_DIR" >&2
    exit 1
fi

# --- Variables ---
WORKFLOW_DIR=./workflows
WORKFLOW_BASENAME=$(basename "$WORKFLOW_FILE")
# Use a unique name for the pod for concurrent runs.
POD_NAME="comfyui-client"

# --- Cleanup Function ---
cleanup() {
  echo "--- Cleaning up pod: $POD_NAME ---"
  kubectl delete pod "$POD_NAME" --namespace="$NAMESPACE" --ignore-not-found=true || true
}
trap cleanup EXIT

# 1. Get GKE cluster credentials
echo "--- Getting GKE credentials for project '$GKE_PROJECT' ---"
gcloud container clusters get-credentials "$GKE_CLUSTER" --region "$GKE_REGION" --project "$GKE_PROJECT" --dns-endpoint

# 2. Run a temporary client pod
echo "--- Creating pod: $POD_NAME in namespace '$NAMESPACE' ---"
kubectl run "$POD_NAME" \
  --image=alpine:latest \
  --restart=Never \
  --namespace="$NAMESPACE" \
  --command -- sh -c "apk add --no-cache curl jq && echo 'Pod is ready. Waiting...' && sleep 3600"

# 3. Wait for the pod to be ready
echo "--- Waiting for pod to be ready ---"
kubectl wait --for=condition=Ready pod/"$POD_NAME" --namespace="$NAMESPACE" --timeout=60s

# 4. Copy files to the pod
echo "--- Copying files to pod ---"
kubectl cp ./comfyui_runner.sh "${NAMESPACE}/${POD_NAME}:/tmp/comfyui_runner.sh"
kubectl cp ./$WORKFLOW_DIR "${NAMESPACE}/${POD_NAME}:/tmp/$WORKFLOW_DIR"

# 5. Make the runner script executable inside the pod
echo "--- Setting script permissions in pod ---"
kubectl exec --namespace="$NAMESPACE" "$POD_NAME" -- chmod +x /tmp/comfyui_runner.sh

# 6. Execute the test script inside the pod, passing environment variables
echo "--- Executing test script in pod ---"
kubectl exec --namespace="$NAMESPACE" "$POD_NAME" -- \
  sh -c "export COMFYUI_URL='${COMFYUI_URL}' && \
         export WORKFLOWS_DIR='${WORKFLOWS_DIR}' && \
         export TEST_DIR='${TEST_DIR}' && \
         export POLL_TIMEOUT=300 && \
         export POLL_INTERVAL=5 && \
         export MINIMUM_FILE_SIZE_BYTES=1 && \
         /tmp/comfyui_runner.sh /tmp/workflows"

echo "--- Script executed successfully ---"
