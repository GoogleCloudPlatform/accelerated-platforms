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
source /workspace/build.env 2>/dev/null || true
if [ -n "${ACP_PLATFORM_BASE_DIR:-}" ]; then
  source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh" 2>/dev/null || true
fi

# --- Vars ---
export ERROR_FILE="${ERROR_FILE:-/workspace/build-failed.lock}"
export SOURCE_TEST_DIR="${SOURCE_TEST_DIR:-test/ci-cd/scripts/comfyui/}"
STEP_ID=${1:-build-ci}

# --- Test Configuration ---
COMFYUI_NAMESPACE="${comfyui_kubernetes_namespace:-comfyui}"
COMFYUI_SERVICE_NAME="${COMFYUI_SERVICE_NAME:-comfyui-nvidia-l4}"
COMFYUI_LOCAL_PORT="${COMFYUI_LOCAL_PORT:-8188}"
COMFYUI_REMOTE_PORT="${COMFYUI_REMOTE_PORT:-8188}"
PORT_FORWARD_PID=""

# --- Helpers ---
step() { echo -e "\n==== [STEP] $* ====\n"; }
info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }

log_error() {
  local exit_code=${1:-$?}
  local message=${2:-"Script error on line ${BASH_LINENO[0]} (exit code: ${exit_code}) executing: ${BASH_COMMAND}"}

  if [ "${exit_code}" -eq 0 ] && [ "$#" -eq 0 ]; then
    return
  fi

  >"${ERROR_FILE}"
  echo "- [${STEP_ID}] ${message}" >>"${ERROR_FILE}"
  exit 0
}
trap 'log_error' ERR

cleanup_on_exit() {
  step "Cleanup"
  if [ -n "${PORT_FORWARD_PID}" ]; then
    info "Stopping port-forward process (PID: ${PORT_FORWARD_PID})..."
    kill "${PORT_FORWARD_PID}" >/dev/null 2>&1 || true
  fi

  step "Final status"
  if [ -s "${ERROR_FILE}" ]; then
    warn "Test run had failures. See '${ERROR_FILE}' for details."
    step "ERROR FILE CONTENTS"
    cat "${ERROR_FILE}" || true
  else
    info "Test run completed successfully."
  fi

  info "Exiting with status 0 to ensure build step passes."
  exit 0
}
trap cleanup_on_exit EXIT

# ------------------------------------------------------------
# Prepare local test assets
# ------------------------------------------------------------
step "Prepare local test assets"
PREPARED_ASSETS_DIR=$(mktemp -d)
info "Preparing workflows in temporary directory: ${PREPARED_ASSETS_DIR}"

cp -r "${SOURCE_TEST_DIR}/workflows/"* "${PREPARED_ASSETS_DIR}/"
for file in "${PREPARED_ASSETS_DIR}"/*; do
    if [[ -f "$file" ]]; then
        # Substitute environment variables into workflow JSON files
        envsubst < "$file" | sponge "$file"
    fi
done

# ------------------------------------------------------------
# Start Port Forwarding
# ------------------------------------------------------------
step "Start port-forward to ComfyUI service"
info "Forwarding localhost:${COMFYUI_LOCAL_PORT} to service/${COMFYUI_SERVICE_NAME}:${COMFYUI_REMOTE_PORT} in namespace ${COMFYUI_NAMESPACE}"

kubectl port-forward \
  "service/${COMFYUI_SERVICE_NAME}" \
  -n "${COMFYUI_NAMESPACE}" \
  "${COMFYUI_LOCAL_PORT}:${COMFYUI_REMOTE_PORT}" >/dev/null 2>&1 &
PORT_FORWARD_PID=$!

info "Waiting for port-forward to be ready (PID: ${PORT_FORWARD_PID})..."
start_time=$(date +%s)
while ! curl -s --head "http://localhost:${COMFYUI_LOCAL_PORT}/" > /dev/null; do
    if ! kill -0 $PORT_FORWARD_PID 2>/dev/null; then
        log_error 1 "Port-forward process failed to start."
    fi
    current_time=$(date +%s)
    if (( current_time - start_time > 30 )); then
        log_error 1 "Timeout waiting for port-forward to establish."
    fi
    sleep 1
done
info "Port-forward is active."

# ------------------------------------------------------------
# Execute tests locally
# ------------------------------------------------------------
step "Execute test script locally"
info "Setting env & running all workflow tests"

POD_RUN_LOG="$(mktemp)"

source "${SOURCE_TEST_DIR}/comfyui_prompt_test.sh"

# Set environment variables for the sourced test functions
export COMFYUI_URL="http://localhost:${COMFYUI_LOCAL_PORT}"
export POLL_TIMEOUT="300"
export MINIMUM_FILE_SIZE_BYTES="1"

# --- Run tests ---
(
    echo ">> Begin workflow tests..."
    FAILURES_FILE=$(mktemp)

    for f in "${PREPARED_ASSETS_DIR}"/*; do
      (
        TEST_LOG=$(mktemp)
        
        # Run the main test function and capture all its output.
        if main "${f}" >"${TEST_LOG}" 2>&1; then
          echo "---- [PASS]  OK: $(basename "$f")"
        else
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
) 2>&1 | tee "${POD_RUN_LOG}"


if grep -q "__WORKFLOW_TESTS_FAILED__" "${POD_RUN_LOG}"; then
  echo "Failed Workflows:" >"${ERROR_FILE}"
  sed -n 's/.*\[FAIL\].*FAILED: \(.*\) - See full log below:$/\1/p' "${POD_RUN_LOG}" >>"${ERROR_FILE}"
  warn "One or more tests failed. See details in ${ERROR_FILE}."
else
  info "All tests completed successfully."
fi
