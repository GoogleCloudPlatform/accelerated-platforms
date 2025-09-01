#!/usr/bin/env bash
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# This script ALWAYS exits 0. All failures are logged to ERROR_FILE.

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
STEP_ID=${1:-build-ci} # Default STEP_ID to 'build-ci' if not provided

# --- Helpers ---
step() { echo -e "\n==== [STEP] $* ====\n"; }
info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }

# This function is triggered by the ERR trap or called directly.
# It logs an error message and always exits 0.
log_error() {
  local exit_code=${1:-$?} # Use provided exit code or last command's
  local message=${2:-"Script error on line ${BASH_LINENO[0]} (exit code: ${exit_code}) executing: ${BASH_COMMAND}"}

  # Ensure we don't log successful exits when called from the ERR trap
  if [ "${exit_code}" -eq 0 ] && [ "$#" -eq 0 ]; then
    return
  fi

  >"${ERROR_FILE}" # Clear the error file
  echo "- [${STEP_ID}] ${message}" >>"${ERROR_FILE}"
  exit 0 # Always exit 0
}
trap 'log_error' ERR

# This function runs on any script exit.
# It cleans up the pod and ALWAYS exits 0.
cleanup_on_exit() {
  step "Cleanup"
  info "Deleting pod: ${POD_NAME} (namespace: ${comfyui_kubernetes_namespace})"
  kubectl delete pod "${POD_NAME}" -n "${comfyui_kubernetes_namespace}" --ignore-not-found=true >/dev/null 2>&1 || true

  step "Final status"
  if [ -s "${ERROR_FILE}" ]; then
    warn "Test run had failures. See '${ERROR_FILE}' for details."
    step "ERROR FILE CONTENTS"
    cat "${ERROR_FILE}" || true
  else
    info "Test run completed successfully."
  fi

  # ALWAYS exit 0 per requirement
  info "Exiting with status 0 to ensure build step passes."
  exit 0
}
trap cleanup_on_exit EXIT

# ------------------------------------------------------------
# Start client pod
# ------------------------------------------------------------
step "Create client pod '${POD_NAME}' in '${comfyui_kubernetes_namespace}'"
export SA_NAME=$(kubectl get serviceaccount -n ${comfyui_kubernetes_namespace} -o custom-columns=NAME:.metadata.name --no-headers | grep -v "^default$")
kubectl run "${POD_NAME}" \
  --image=debian:12-slim \
  --restart=Never \
  -n "${comfyui_kubernetes_namespace}" \
  --overrides="{ \"spec\": { \"serviceAccountName\": \"${SA_NAME}\" } }" \
  --command -- sh -c "echo 'Pod is ready with tools pre-installed. Waiting...' && sleep 3600"

step "Wait for pod to be Ready"
kubectl wait --for=condition=Ready "pod/${POD_NAME}" -n "${comfyui_kubernetes_namespace}" --timeout=3600s

# ------------------------------------------------------------
# Copy test assets
# ------------------------------------------------------------
step "Copy test assets into pod"
info "Copying comfyui_prompt_test.sh and workflows directory"
TEMP_DIR="${TEST_WORKFLOW_DIR}/tmp"
mkdir -p "${TEMP_DIR}"
cp -r "${TEST_WORKFLOW_DIR}/workflows/"* "${TEMP_DIR}"
for file in "${TEMP_DIR}"/*; do
    if [[ -f "$file" ]]; then
        envsubst < "$file" | sponge "$file"
    fi
done

kubectl cp "${TEST_WORKFLOW_DIR}/comfyui-workflow-tester.sh" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/comfyui-workflow-tester.sh"
kubectl cp "${TEMP_DIR}" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/workflows"
kubectl exec -n "${comfyui_kubernetes_namespace}" "${POD_NAME}" -- chmod +x /tmp/comfyui-workflow-tester.sh

# ------------------------------------------------------------
# Discover service IP
# ------------------------------------------------------------
step "Discover ComfyUI service IP (port ${COMFYUI_PORT})"
SERVICE_IP_AND_PORT="$(kubectl get service -n "${comfyui_kubernetes_namespace}" | grep "${COMFYUI_PORT}" | awk '{print $3}'):${COMFYUI_PORT}"
info "Using service endpoint: ${SERVICE_IP_AND_PORT}"

# ------------------------------------------------------------
# Execute tests inside pod
# ------------------------------------------------------------
step "Execute test script in pod"
info "Setting env & running all workflow tests"

POD_RUN_LOG="$(mktemp)"

kubectl exec -n "${comfyui_kubernetes_namespace}" "${POD_NAME}" -- env \
  COMFYUI_URL="http://${SERVICE_IP_AND_PORT}" \
  TEST_WORKFLOW_DIR="/tmp/workflows" \
  POLL_TIMEOUT="300" \
  POLL_INTERVAL="5" \
  MINIMUM_FILE_SIZE_BYTES="1" \
  /bin/bash -lc '
    echo ">> Sourcing test functions..."
    . /tmp/comfyui_prompt_test.sh

    echo ">> Begin workflow tests..."
    FAILURES_FILE=$(mktemp)

    for f in "${TEST_WORKFLOW_DIR}"/*; do
      (
        TEST_LOG=$(mktemp)
        
        # Run test and capture all its output.
        if main "${f}" >"${TEST_LOG}" 2>&1; then
          # On success, just print a clean OK message.
          echo "---- [PASS]  OK: $(basename "$f")"
        else
          # On failure, print the failure message AND the detailed log.
          echo "---- [FAIL]  FAILED: $(basename "$f") - See full log below:" >&2
          cat "${TEST_LOG}" >&2
          basename "${f}" >> "${FAILURES_FILE}"
        fi
        rm -f "${TEST_LOG}"
      ) 
    done

    wait

    if [ -s "${FAILURES_FILE}" ]; then
      echo ">> The following workflow tests failed:" >&2
      cat "${FAILURES_FILE}" >&2
      echo "__WORKFLOW_TESTS_FAILED__"
    else
      echo ">> All workflows completed successfully."
    fi

    # ALWAYS exit 0 from the pod
    exit 0
  ' 2>&1 | tee "${POD_RUN_LOG}"

if grep -q "__WORKFLOW_TESTS_FAILED__" "${POD_RUN_LOG}"; then
  echo "Failed Workflows:" >"${ERROR_FILE}"
  sed -n 's/.*\[FAIL\].*FAILED: \(.*\) - See full log below:$/\1/p' "${POD_RUN_LOG}" >>"${ERROR_FILE}"
  warn "One or more in-pod tests failed. See details in ${ERROR_FILE}."
else
  info "All in-pod tests completed successfully."
fi
