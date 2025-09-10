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

# --- Load env (best-effort) ---
# shellcheck disable=SC1091
source /workspace/build.env 2>/dev/null || true
if [ -n "${ACP_PLATFORM_BASE_DIR:-}" ]; then
  # shellcheck disable=SC1091
  source "${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh" 2>/dev/null || true
fi

# --- Vars (preserved defaults) ---
export POD_NAME="${POD_NAME:-comfyui-client}"
export ERROR_FILE="/workspace/build-failed.lock"
export TEST_WORKFLOW_DIR="${TEST_WORKFLOW_DIR:-test/ci-cd/scripts/comfyui}"
export COMFYUI_BUCKET="${cluster_project_id}-${unique_identifier_prefix}-${comfyui_app_name}"
export COMFYUI_SERVICE="${comfyui_app_name}-${comfyui_accelerator_type}:8188"
export COMFYUI_DEPLOYMENT=${comfyui_app_name}-${comfyui_accelerator_type}

MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-1200}"
STEP_ID=${1:-build-ci}

# --- Helpers ---
step() { echo -e "\n==== [STEP] $* ====\n"; }
info() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }

log_error() {
  local exit_code=${1:-$?}
  local message=${2:-"Script error on line ${BASH_LINENO[0]} (exit code: ${exit_code}) executing: ${BASH_COMMAND}"}

  if [ ${exit_code} -ne 0 ]; then
    # Corrected line with double quotes
    echo "- [${STEP_ID}] ${message}" >> "${ERROR_FILE}"
  fi

  exit 0
}
trap 'log_error' ERR

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
#  Copy checkpoint file
# ------------------------------------------------------------
step "Copy checkpoint files"
gcloud builds submit \
--config="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/copy-checkpoints/cloudbuild.yaml" \
--gcs-source-staging-dir="gs://${comfyui_cloudbuild_source_bucket_name}/source" \
--no-source \
--project="${cluster_project_id}" \
--service-account="${comfyui_cloudbuild_service_account_id}" \
--substitutions="_BUCKET_NAME=${comfyui_cloud_storage_model_bucket_name}"

# ------------------------------------------------------------
# Get GKE credentials
# ------------------------------------------------------------
step "Get GKE credentials"
info "Fetching credentials for project '${cluster_project_id}'"
${cluster_credentials_command}
kubectl get deployment -n ${comfyui_kubernetes_namespace}

step "Wait for ComfyUI deployment to be Available"
kubectl wait --for=condition=Available deployment/${comfyui_app_name}-${comfyui_accelerator_type} -n ${comfyui_kubernetes_namespace} --timeout=${MAX_WAIT_SECONDS}s

# ------------------------------------------------------------
# Start client pod
# ------------------------------------------------------------
step "Create client pod '${POD_NAME}' in '${comfyui_kubernetes_namespace}'"
# Correctly gets only ONE service account name
export SA_NAME=$(kubectl get serviceaccount -n ${comfyui_kubernetes_namespace} -o custom-columns=NAME:.metadata.name --no-headers | grep -v "^default$" | head -n 1)

kubectl run "${POD_NAME}" \
  --image=alpine:latest \
  --restart=Never \
  -n "${comfyui_kubernetes_namespace}" \
  --overrides="{ \"spec\": { \"serviceAccountName\": \"${SA_NAME}\" } }" \
  --command -- sh -c "apk add --no-cache bash curl jq && echo 'Pod is ready. Waiting...' && sleep 3600"

step "Wait for pod to be Ready"
kubectl wait --for=condition=Ready "pod/${POD_NAME}" -n "${comfyui_kubernetes_namespace}" --timeout=${MAX_WAIT_SECONDS}s

# ------------------------------------------------------------
# Copy test assets
# ------------------------------------------------------------
step "Copy test assets into pod"
info "Copying comfyui-workflow-tester.sh and workflows directory"
TEMP_DIR="${TEST_WORKFLOW_DIR}/tmp"
mkdir -p "${TEMP_DIR}"
cp -r "${TEST_WORKFLOW_DIR}/workflows"/* "${TEMP_DIR}"
for file in "${TEMP_DIR}"/*; do
    if [[ -f "$file" ]]; then
        envsubst < "$file" | sponge "$file"
    fi
done

kubectl cp "${TEST_WORKFLOW_DIR}/comfyui-workflow-tester.sh" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/comfyui-workflow-tester.sh"
kubectl cp "${TEMP_DIR}" "${comfyui_kubernetes_namespace}/${POD_NAME}:/tmp/workflows"
kubectl exec -n "${comfyui_kubernetes_namespace}" "${POD_NAME}" -- chmod +x /tmp/comfyui-workflow-tester.sh
rm -rf "${TEMP_DIR}"

# ------------------------------------------------------------
# Execute tests inside pod
# ------------------------------------------------------------
step "Execute test script in pod"
info "Setting env & running all workflow tests"

POD_RUN_LOG="$(mktemp)"

kubectl exec -n "${comfyui_kubernetes_namespace}" "${POD_NAME}" -- env \
  COMFYUI_URL="http://${COMFYUI_SERVICE}" \
  TEST_WORKFLOW_DIR="/tmp/workflows" \
  POLL_TIMEOUT="300" \
  POLL_INTERVAL="5" \
  MINIMUM_FILE_SIZE_BYTES="1" \
  /bin/bash -lc '
    echo ">> Sourcing test functions..."
    . /tmp/comfyui-workflow-tester.sh

    echo ">> Begin workflow tests..."
    FAILURES_FILE=$(mktemp)

    test_files=("${TEST_WORKFLOW_DIR}"/*)
    total_tests=${#test_files[@]}
    echo ">> Found ${total_tests} workflow files to test."

    for f in "${test_files[@]}"; do
      (
        TEST_LOG=$(mktemp)
        
        if main "${f}"; then
          echo "[PASS] filename: $(basename "$f")"
        else
          echo "[FAIL] filename: $(basename "$f") - See full log below:" >&2
          cat "${TEST_LOG}" >&2
          basename "${f}" >> "${FAILURES_FILE}"
        fi
        rm -f "${TEST_LOG}"
      ) 
    done

    wait

    num_failures=0
    # Check if the failure file has content before counting
    if [ -s "${FAILURES_FILE}" ]; then
      num_failures=$(wc -l < "${FAILURES_FILE}")
    fi
    num_successes=$((total_tests - num_failures))
    echo ">> Summary: ${num_successes} out of ${total_tests} files completed successfully."

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
  sed -n 's/.*\[FAIL\].*filename: \(.*\) - See full log below:$/\1/p' "${POD_RUN_LOG}" >>"${ERROR_FILE}"
  warn "One or more in-pod tests failed. See details in ${ERROR_FILE}."
else
  info "All in-pod tests completed successfully."
fi
