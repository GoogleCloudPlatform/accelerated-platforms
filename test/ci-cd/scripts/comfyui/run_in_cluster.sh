#!/usr/bin/env bash
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
# This script NEVER exits non-zero. All failures are logged to ERROR_FILE.

set -o nounset
set -o pipefail
set -o errtrace

# --- Load env (best-effort) ---
# shellcheck disable=SC1091
source /workspace/build.env 2>/dev/null || true
if [ -n "${ACP_PLATFORM_BASE_DIR:-}" ]; then
  # shellcheck disable=SC1091
  source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh" 2>/dev/null || true
fi

# --- Vars (preserved defaults) ---
export POD_NAME="${POD_NAME:-comfyui-client}"
export ERROR_FILE="${ERROR_FILE:-/workspace/build-failed.lock}"
export TEST_WORKFLOW_DIR="${TEST_WORKFLOW_DIR:-test/ci-cd/scripts/comfyui/}"

COMFYUI_PORT="${COMFYUI_PORT:-8188}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-180}"
STEP_ID=${1}

# --- Helpers ---
step() { echo -e "\n==== [STEP] $* ====\n"; }
info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
log_error() {

  exit_code=$?

  if [ ${exit_code} -ne 0 ]; then
    echo "- ${STEP_ID}" >>/workspace/build-failed.lock
  fi

  exit 0
}

trap 'log_error "shell error (exit=$?) at line ${BASH_LINENO[0]} running: ${BASH_COMMAND}"' ERR

cleanup_on_exit() {
  step "Cleanup"
  info "Deleting pod: ${POD_NAME} (namespace: ${comfyui_kubernetes_namespace})"
  kubectl delete pod "${POD_NAME}" -n "${comfyui_kubernetes_namespace}" --ignore-not-found=true >/dev/null 2>&1 || true

  step "Final status"
  if [ -s "${ERROR_FILE}" ]; then
    warn "Test run had failures. See '${ERROR_FILE}' for details. "
    step "ERROR FILE CONTENTS"
    cat "${ERROR_FILE}" || true
  else
    info "Test run completed successfully."
  fi
  # ALWAYS exit 0 per requirement
  exit 0
}
trap cleanup_on_exit EXIT

# (defined but NOT called; kept for parity)
check_files() {
  for file in "$WORKFLOWS_DIR"/*; do
    if [[ ! -f "$TEST_WORKFLOW_DIR/workflows/$(basename "$file")" ]]; then
      echo "Error: $(basename "$file") not found in $TEST_WORKFLOW_DIR." >&2
      log_error "Missing test file: $(basename "$file") expected in $TEST_WORKFLOW_DIR/workflows"
    fi
  done
}

# ------------------------------------------------------------
# Credentials — ORIGINAL explicit command
# ------------------------------------------------------------
step "Get GKE credentials (original explicit command)"
echo "[INFO] ${cluster_credentials_command}"
${cluster_credentials_command} \
  || log_error "gcloud get-credentials failed ${cluster_credentials_command}"

# ------------------------------------------------------------
# Wait for API & namespace
# ------------------------------------------------------------
step "Wait for cluster & namespace '${comfyui_kubernetes_namespace}'"
attempt=0
while true; do
  attempt=$((attempt + 1))
  if kubectl get namespace "${comfyui_kubernetes_namespace}" >/dev/null 2>&1; then
    info "Namespace '${comfyui_kubernetes_namespace}' is accessible."
    break
  fi
  if [ "${attempt}" -ge "${MAX_WAIT_SECONDS}" ]; then
    log_error "Timeout waiting for namespace '${comfyui_kubernetes_namespace}' after ${MAX_WAIT_SECONDS}s"
    break
  fi
  sleep 1
done

info "Listing namespaces:"
kubectl get namespaces || log_error "kubectl get namespaces failed"

# ------------------------------------------------------------
# Copy the checkpoint files
# ------------------------------------------------------------
gcloud builds submit \
--config="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/copy-checkpoints/cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${comfyui_cloudbuild_source_bucket_name}/source" \
--no-source \
--project="${cluster_project_id}" \
--service-account="${comfyui_cloudbuild_service_account_id}" \
--substitutions="_BUCKET_NAME=${comfyui_cloud_storage_model_bucket_name}"

# ------------------------------------------------------------
# Start client pod (install bash + curl + jq)
# ------------------------------------------------------------
step "Create client pod '${POD_NAME}' in '${comfyui_kubernetes_namespace}'"
kubectl run "${POD_NAME}" \
  --image=alpine:latest \
  --restart=Never \
  -n "${comfyui_kubernetes_namespace}" \
  --command -- sh -c "apk add --no-cache bash curl jq >/dev/null && echo 'Pod is ready. Waiting...' && sleep 3600" \
  || log_error "Failed to create pod ${POD_NAME}"

step "Wait for pod Ready"
kubectl wait --for=condition=Ready "pod/${POD_NAME}" -n "${comfyui_kubernetes_namespace}" --timeout=120s \
  || log_error "Pod ${POD_NAME} not Ready within timeout"

# ------------------------------------------------------------
# Copy test assets
# ------------------------------------------------------------
step "Copy test assets into pod"
info "Copy comfyui_prompt_test.sh"
kubectl cp "${TEST_WORKFLOW_DIR}/comfyui_prompt_test.sh" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/comfyui_prompt_test.sh" \
  || log_error "Failed to copy comfyui_prompt_test.sh"
info "Copy workflows directory"
kubectl cp "${TEST_WORKFLOW_DIR}/workflows" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/workflows" \
  || log_error "Failed to copy workflows directory"

step "chmod +x in pod"
kubectl exec -n "${comfyui_kubernetes_namespace}" "${POD_NAME}" -- chmod +x /tmp/comfyui_prompt_test.sh \
  || log_error "chmod +x /tmp/comfyui_prompt_test.sh failed"

# ------------------------------------------------------------
# Discover service IP (YOUR ORIGINAL LOGIC)
# ------------------------------------------------------------
step "Discover ComfyUI service IP (port ${COMFYUI_PORT})"
info "Services in namespace '${comfyui_kubernetes_namespace}':"
kubectl get service -n "${comfyui_kubernetes_namespace}" || log_error "kubectl get service failed"

SERVICE_IP_AND_PORT="$(kubectl get service -n "${comfyui_kubernetes_namespace}" | grep "${COMFYUI_PORT}" | awk '{print $3}'):${COMFYUI_PORT}"
info "Using service endpoint: ${SERVICE_IP_AND_PORT}"

# ------------------------------------------------------------
# Execute tests inside pod — stream logs; stop on first error
# ------------------------------------------------------------
step "Execute test script in pod"
echo "[INFO] Setting env & running tests inside pod..."

POD_RUN_LOG="$(mktemp)"

kubectl exec -n "${comfyui_kubernetes_namespace}" "${POD_NAME}" -- env \
  COMFYUI_URL="http://${SERVICE_IP_AND_PORT}" \
  TEST_WORKFLOW_DIR="/tmp/workflows" \
  POLL_TIMEOUT="300" \
  POLL_INTERVAL="5" \
  MINIMUM_FILE_SIZE_BYTES="1" \
  /bin/bash -lc '
    echo ">> Inside pod"
    echo ">> COMFYUI_URL=${COMFYUI_URL}"
    echo ">> TEST_WORKFLOW_DIR=${TEST_WORKFLOW_DIR}"
    echo ">> Listing workflows:"
    ls -la "${TEST_WORKFLOW_DIR}" || true

    . /tmp/comfyui_prompt_test.sh

    echo ">> Begin workflow tests (stop on first error)"
    for f in "${TEST_WORKFLOW_DIR}"/*; do
      echo "---- Working on file: ${f} ----"
      if ! main "${f}"; then
        echo "!! FAILED: ${f}" >&2
        exit 1     # stop on FIRST failure
      else
        echo " OK: ${f}"
      fi
    done

    echo ">> All workflows completed successfully."
    exit 0
  ' 2>&1 | tee "${POD_RUN_LOG}"

exec_ec=${PIPESTATUS[0]}   # exit code of kubectl exec (not tee)

if [ "${exec_ec}" -ne 0 ]; then
  log_error "In-pod test script reported a failure (stopped on first error; exit=${exec_ec})"
  cat "${POD_RUN_LOG}" >> "${ERROR_FILE}" || true
  echo "[INFO] Stopping after first failure. See ${ERROR_FILE}."
else
  info "In-pod tests completed successfully."
fi

