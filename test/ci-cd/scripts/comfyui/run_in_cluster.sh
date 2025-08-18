#!/usr/bin/env bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
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
#   cluster_name, cluster_region, cluster_project_id, comfyui_kubernetes_namespace, comfyui_endpoints_hostname,
#
# ==============================================================================

# --- Script Configuration ---
set -o nounset
set -o pipefail

source /workspace/build.env
source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

ls
# --- Variables ---
# Use a unique name for the pod for concurrent runs.
export POD_NAME="comfyui-client"
# Use a lock file to track errors
export ERROR_FILE="/workspace/build-failed.lock"

export WORKFLOWS_DIR="test/ci-cd/scripts/comfyui/workflows"
# --- Cleanup and Error Handling Functions ---
cleanup_on_exit() {
  echo "--- Cleaning up pod: $POD_NAME ---"
  kubectl delete pod "$POD_NAME" --namespace="$comfyui_kubernetes_namespace" --ignore-not-found=true || true
  exit 0
}

# The main error handler function
# This function will be called on every command failure
error_handler() {
  local exit_code=$?
  if [ $exit_code -ne 0 ]; then
    echo "Error $exit_code"
  fi
}

# Trap ERR and call the error handler
trap error_handler ERR
# Always clean up on exit, regardless of success or failure
trap cleanup_on_exit EXIT

# Check for all required environment variables
if [ -z "${cluster_name:-}" ] || [ -z "${cluster_region:-}" ] || [ -z "${cluster_project_id:-}" ] || \
   [ -z "${comfyui_kubernetes_namespace:-}" ]; then
    echo "Error: One or more required environment variables are not set." >&2
    echo "Required: cluster_name, cluster_region, cluster_project_id, comfyui_kubernetes_namespace, HEADLESS_COMFYUI_SERVICE, WORKFLOWS_DIR, TEST_DIR" >&2
    echo "Error: Required environment variables are not set." >> "${ERROR_FILE}"
    exit 0
fi

# --- verify each file has a test file ---
check_files() {
  for file in "$WORKFLOWS_DIR"/*; do
    if [[ ! -f "$TEST_DIR/workflows/$(basename "$file")" ]]; then
      echo "Error: $(basename "$file") not found in $TEST_DIR." >&2
      echo "Error: $(basename "$file") not found in $TEST_DIR." >> "${ERROR_FILE}"
      exit 0
    fi
  done
}

# 1. Get GKE cluster credentials
echo "--- Getting GKE credentials for project '$cluster_project_id' ---"
# Note: The `cluster_credentials_command` variable is assumed to be sourced from the `set_environment_variables.sh` script
$cluster_credentials_command

# --- Wait for cluster to be available...
echo "--- Waiting for cluster to become available... ---"
MAX_WAIT_SECONDS=180
ATTEMPT=0
while true; do
  ATTEMPT=$((ATTEMPT + 1))
  echo "Attempting to connect to cluster (Attempt $ATTEMPT)..."
  if kubectl get namespaces >/dev/null 2>&1; then
    echo "Cluster is available. Proceeding."
    break
  fi
  if [ $ATTEMPT -ge $MAX_WAIT_SECONDS ]; then
    echo "Timeout waiting for cluster to become available. Exiting." >&2
    exit 0
  fi
  sleep 5
done

# --- Verify namespace exists ---
echo "--- Verifying that namespace '$comfyui_kubernetes_namespace' exists... ---"
if ! kubectl get namespace "$comfyui_kubernetes_namespace" >/dev/null 2>&1; then
    echo "Error: The required namespace '$comfyui_kubernetes_namespace' does not exist." >&2
    exit 0
fi
echo "Namespace '$comfyui_kubernetes_namespace' found."

# --- Remaining script steps ---
echo "-----KUBECTL NAMESPACES-----"
kubectl get namespaces
# 2. Run a temporary client pod
echo "--- Creating pod: $POD_NAME in namespace '$comfyui_kubernetes_namespace' ---"
kubectl run "$POD_NAME" \
  --image=alpine:latest \
  --restart=Never \
  --namespace="$comfyui_kubernetes_namespace" \
  --command -- sh -c "apk add --no-cache curl jq && echo 'Pod is ready. Waiting...' && sleep 3600"

# 3. Wait for the pod to be ready
echo "--- Waiting for pod to be ready ---"
kubectl wait --for=condition=Ready pod/"$POD_NAME" --namespace="$comfyui_kubernetes_namespace" --timeout=60s

# 4. Copy files to the pod
echo "--- Copying files to pod ---"
kubectl cp "$WORKFLOWS_DIR/comfyui_prompt_test.sh" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/comfyui_prompt_test.sh"
kubectl cp "$WORKFLOWS_DIR/workflows" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/workflows"

# 5. Make the runner script executable inside the pod
echo "--- Setting script permissions in pod ---"
kubectl exec --namespace="$comfyui_kubernetes_namespace" "$POD_NAME" -- chmod +x /tmp/comfyui_prompt_test.sh

# 6. Get ComfyUI IP address
echo "--- Getting Comfy IP ---"
SERVICE_IP_AND_PORT=$(kubectl get service -n "$comfyui_kubernetes_namespace" | grep "8188" | awk '{print $3}'):8188
echo "Service IP and Port: $SERVICE_IP_AND_PORT"

# 7. Execute the test script inside the pod, passing environment variables
echo "--- Executing test script in pod ---"
kubectl exec --namespace="$comfyui_kubernetes_namespace" "$POD_NAME" -- \
  sh -c "export COMFYUI_URL='${SERVICE_IP_AND_PORT}' && \
          export WORKFLOWS_DIR='${WORKFLOWS_DIR}' && \
          export POLL_TIMEOUT=300 && \
          export POLL_INTERVAL=5 && \
          export MINIMUM_FILE_SIZE_BYTES=1 && \
          /tmp/comfyui_prompt_test.sh"

echo "--- Script execution completed ---"
