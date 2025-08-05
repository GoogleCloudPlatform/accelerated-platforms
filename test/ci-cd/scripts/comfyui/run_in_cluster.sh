# !/bin/sh
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
#   cluster_name, cluster_region, cluster_project_id, comfyui_kubernetes_namespace, comfyui_endpoints_hostname,
#
# ==============================================================================

# --- Script Configuration ---
set -o errexit
set -o nounset
set -o pipefail


# Check for all required environment variables
if [ -z "$cluster_name" ] || [ -z "$cluster_region" ] || [ -z "$cluster_project_id" ] || \
   [ -z "$comfyui_kubernetes_namespace" ] || [ -z "$comfyui_endpoints_hostname" ] || [ -z "$WORKFLOWS_DIR" ] || \
   [ -z "$TEST_DIR" ]; then
    echo "Error: One or more required environment variables are not set." >&2
    echo "Required: cluster_name, cluster_region, cluster_project_id, comfyui_kubernetes_namespace, HEADLESS_COMFYUI_SERVICE, WORKFLOWS_DIR, TEST_DIR" >&2
    exit 1
fi

# --- Variables ---
# Use a unique name for the pod for concurrent runs.
POD_NAME="comfyui-client"
printenv
# --- verify each file has a test file ---
check_files() {
  for file in "$WORKFLOWS_DIR"/*; do
    if [[ ! -f "$TEST_DIR/workflows/$(basename "$file")" ]]; then
      echo "Error: $(basename "$file") not found in $TEST_DIR." >&2
      exit 1
    fi
  done
}
# --- Cleanup Function ---
cleanup() {
  echo "--- Cleaning up pod: $POD_NAME ---"
  kubectl delete pod "$POD_NAME" --namespace="$comfyui_kubernetes_namespace" --ignore-not-found=true || true
}
trap cleanup EXIT

# 1. Get GKE cluster credentials
echo "--- Getting GKE credentials for project '$cluster_project_id' ---"
gcloud container clusters get-credentials "$cluster_name" --region "$cluster_region" --project "$cluster_project_id" --dns-endpoint

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
kubectl cp "$TEST_DIR/comfyui_prompt_test.sh" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/comfyui_prompt_test.sh"
kubectl cp "$TEST_DIR/workflows" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/workflows"

# 5. Make the runner script executable inside the pod
echo "--- Setting script permissions in pod ---"
kubectl exec --namespace="$comfyui_kubernetes_namespace" "$POD_NAME" -- chmod +x /tmp/comfyui_prompt_test.sh 

# 6. Execute the test script inside the pod, passing environment variables
echo "--- Executing test script in pod ---"
kubectl exec --namespace="$comfyui_kubernetes_namespace" "$POD_NAME" -- \
  sh -c "export COMFYUI_URL='${HEADLESS_COMFYUI_SERVICE}' && \
         export WORKFLOWS_DIR='${WORKFLOWS_DIR}' && \
         export TEST_DIR='${TEST_DIR}' && \
         export POLL_TIMEOUT=300 && \
         export POLL_INTERVAL=5 && \
         export MINIMUM_FILE_SIZE_BYTES=1 && \
         /tmp/comfyui_prompt_test.sh"

echo "--- Script executed successfully ---"
