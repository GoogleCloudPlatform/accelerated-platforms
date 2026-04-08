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

set -e

# --- Configuration & Discovery ---
SCRIPT_DIR="$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd -P)"
if [[ -z "${ACP_REPO_DIR:-}" ]]; then
  ACP_REPO_DIR="$(cd "${SCRIPT_DIR}/../../../../../../" >/dev/null 2>&1 && pwd -P)"
  export ACP_REPO_DIR
fi

ENV_SCRIPT="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
if [[ -f "${ENV_SCRIPT}" ]]; then
  echo "[INFO] Sourcing environment variables..."
  source "${ENV_SCRIPT}"
else
  echo "[ERROR] Could not find environment script at ${ENV_SCRIPT}"
  exit 1
fi

# --- Default Price Mapping (On-Demand) ---
# Prices as of April 2026. Users should seek updated prices on:
# https://cloud.google.com/products/compute/pricing
function get_hourly_cost() {
  case "$1" in
  "l4") echo "1.147208384" ;;      # g2-standard-16 + 1x L4
  "l4-x2") echo "2.000832696" ;;   # g2-standard-24 + 2x L4
  "l4-x4") echo "4.001665392" ;;   # g2-standard-48 + 4x L4
  "rtx-pro-6000") echo "4.4999" ;; # g4-standard-48 + 1x RTX 6000 (96GB)
  "rtx-pro-6000-1-2") echo "2.5874425" ;; # g4-standard-24 + 1/2x RTX 6000
  "rtx-pro-6000-1-4") echo "1.29372125" ;; # g4-standard-12 + 1/4x RTX 6000
  "rtx-pro-6000-1-8") echo "0.646860625" ;; # g4-standard-6 + 1/8x RTX 6000
  *) echo "0.0" ;;
  esac
}

# --- CLI Arguments ---
BUILD_IMAGE=false
SYNC_ONLY=false
SCENARIOS_JSON=""
MANUAL_COST=""
ACCELERATORS_INPUT=""

while [[ "$#" -gt 0 ]]; do
  case $1 in
  --build) BUILD_IMAGE=true ;;
  --sync-only) SYNC_ONLY=true ;;
  --scenarios)
    SCENARIOS_JSON="$2"
    shift
    ;;
  --accelerator)
    ACCELERATORS_INPUT="$2"
    shift
    ;;
  --model)
    export HF_MODEL_ID="$2"
    shift
    ;;
  --manual-cost)
    MANUAL_COST="$2"
    shift
    ;;
  *)
    echo "Unknown parameter: $1"
    exit 1
    ;;
  esac
  shift
done

if [[ -z "${ACCELERATORS_INPUT}" ]]; then
  echo "[ERROR] --accelerator is required (can be comma-separated list)"
  exit 1
fi
if [[ -z "${HF_MODEL_ID}" ]]; then
  echo "[ERROR] --model is required"
  exit 1
fi

# Minify scenarios JSON and inject model_id to prevent Kustomize parsing errors
if [[ "${SYNC_ONLY}" != "true" ]]; then
  if [[ -z "${SCENARIOS_JSON}" ]]; then
    SCENARIOS_JSON='[{"batch": 1, "vus": 1}]'
  fi
  export K6_SCENARIOS_JSON
  K6_SCENARIOS_JSON=$(echo "${SCENARIOS_JSON}" | jq -c --arg m "${HF_MODEL_ID}" 'map(. + {model_id: $m})')
fi

# --- Phase 1: Build (Once) ---
if [[ "${BUILD_IMAGE}" == "true" ]]; then
  echo "[INFO] Building benchmark container image..."
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/k6_benchmark"
  terraform init -input=false && terraform apply -auto-approve -input=false
fi

# --- Phase 2-5: Sequential Accelerator Loop ---
IFS=',' read -ra ADDR <<<"${ACCELERATORS_INPUT}"
for ACCEL in "${ADDR[@]}"; do
  export ACCELERATOR_TYPE="${ACCEL}"
  echo ""
  echo "======================================================================"
  echo " STARTING SUITE FOR ACCELERATOR: ${ACCELERATOR_TYPE}"
  echo "======================================================================"

  if [[ "${SYNC_ONLY}" != "true" ]]; then
    # Refresh deployment config for this accelerator
    echo "[INFO] Configuring deployment for ${HF_MODEL_NAME} on ${ACCELERATOR_TYPE}..."
    CONFIG_DIR="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/k6-benchmark"
    pushd "${CONFIG_DIR}" >/dev/null
    source "./configure_deployment.sh"
    popd >/dev/null

    echo "[INFO] Cleaning up existing benchmark jobs..."
    kubectl delete --ignore-not-found --kustomize "${CONFIG_DIR}/${HF_MODEL_NAME}"
    kubectl wait --for=delete pod -l job-name="k6-benchmark-${HF_MODEL_NAME}" -n "${ira_online_gpu_kubernetes_namespace_name}" --timeout=60s || true

    echo "[INFO] Launching benchmark Job..."
    kubectl apply --kustomize "${CONFIG_DIR}/${HF_MODEL_NAME}"

    # --- Phase 4: Monitoring ---
    echo "[INFO] Monitoring benchmark Job..."

    LOG_PID=""

    # Smart Monitoring Loop
    (while true; do
      # Get current Pod name and status
      POD_INFO=$(kubectl get pods -n "${ira_online_gpu_kubernetes_namespace_name}" -l job-name="k6-benchmark-${HF_MODEL_NAME}" -o jsonpath='{.items[0].metadata.name} {.items[0].status.phase}' 2>/dev/null || echo "None None")
      read -r POD_NAME POD_STATUS <<<"$POD_INFO"

      TIMESTAMP=$(date +"%T")

      if [[ "${POD_STATUS}" == "Running" ]]; then
        # If Pod is running but we aren't tailing logs yet, start tailing
        if [[ -z "${LOG_PID}" ]] || ! kill -0 "${LOG_PID}" 2>/dev/null; then
          echo "[${TIMESTAMP}] Pod is Running. Starting log stream..."
          kubectl logs -n "${ira_online_gpu_kubernetes_namespace_name}" "${POD_NAME}" -c k6-benchmark -f &
          LOG_PID=$!
        fi
        echo "[HEARTBEAT] ${TIMESTAMP} | Pod: ${POD_NAME} | Status: ${POD_STATUS}"
      elif [[ "${POD_STATUS}" == "Pending" ]]; then
        # If pending, show the latest event to track scale-up/image pull
        EVENT=$(kubectl get events -n "${ira_online_gpu_kubernetes_namespace_name}" --field-selector involvedObject.name="${POD_NAME}" --sort-by='.lastTimestamp' -o jsonpath='{.items[-1].message}' 2>/dev/null || echo "Waiting for events...")
        echo "[HEARTBEAT] ${TIMESTAMP} | Status: Pending | Last Event: ${EVENT}"
      elif [[ "${POD_STATUS}" == "None" ]]; then
        echo "[HEARTBEAT] ${TIMESTAMP} | Waiting for Pod to be created..."
      else
        echo "[HEARTBEAT] ${TIMESTAMP} | Status: ${POD_STATUS}"
      fi

      sleep 60
    done) &
    MONITOR_PID=$!

    echo "[INFO] Waiting for Job completion (max 6h)..."
    TIMEOUT=21600 # 6 hours
    ELAPSED=0
    SLEEP_INTERVAL=10
    while true; do
      # Check terminal state
      STATUS=$(kubectl get job "k6-benchmark-${HF_MODEL_NAME}" -n "${ira_online_gpu_kubernetes_namespace_name}" -o jsonpath='{.status.conditions[?(@.status=="True")].type}' 2>/dev/null || echo "Unknown")

      if [[ "$STATUS" == *"Complete"* ]]; then
        echo "[INFO] Job completed successfully."
        break
      elif [[ "$STATUS" == *"Failed"* ]]; then
        echo "[ERROR] Job failed or was aborted by k6 thresholds. Check container logs for details."
        break
      elif [[ "$STATUS" == "Unknown" ]]; then
        if ! kubectl get job "k6-benchmark-${HF_MODEL_NAME}" -n "${ira_online_gpu_kubernetes_namespace_name}" &>/dev/null; then
          echo "[WARN] Job not found. Stopping wait."
          break
        fi
      fi

      if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        echo "[ERROR] Timeout reached waiting for Job completion."
        exit 1
      fi

      sleep $SLEEP_INTERVAL
      ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
    done

    kill $MONITOR_PID 2>/dev/null || true
    # Ensure the background log process (inside the monitor subshell) is also cleaned up
    # We kill the process group to be sure
    pkill -P $MONITOR_PID 2>/dev/null || true
  else
    echo "[INFO] --sync-only flag detected. Skipping Job deployment and monitoring."
  fi

  echo "[INFO] Syncing results from GCS..."
  RESULTS_DIR="${ACP_REPO_DIR}/${hub_models_bucket_bench_results_name}"
  mkdir -p "${RESULTS_DIR}"
  gcloud storage cp -r "gs://${hub_models_bucket_bench_results_name}/*.jsonl" "${RESULTS_DIR}/"

  # Find the most recent file for this SPECIFIC accelerator run
  LATEST_JSONL=$(ls -t "${RESULTS_DIR}"/*"${HF_MODEL_NAME}"*"${ACCELERATOR_TYPE}"*.jsonl | head -n 1)
  COST="${MANUAL_COST:-$(get_hourly_cost "${ACCELERATOR_TYPE}")}"

  echo "[INFO] ----------------------------------------------------------------------"
  echo "[INFO] Analyzing: ${LATEST_JSONL}"
  echo "[INFO] Accelerator: ${ACCELERATOR_TYPE} | Cost: \$${COST}/hr"
  echo "[INFO] DISCLAIMER: This rate represents public on-demand pricing."
  echo "[INFO] It does NOT account for CUDs, SUDs, or custom private pricing."
  echo "[INFO] For current and accurate pricing, visit:"
  echo "[INFO] https://cloud.google.com/products/compute/pricing"
  echo "[INFO] ----------------------------------------------------------------------"

  . "${ACP_REPO_DIR}/.venv/bin/activate"
  python3 "${ACP_REPO_DIR}/container-images/cpu/k6-benchmark/extract_metrics.py" \
    --file "${LATEST_JSONL}" \
    --hourly-cost "${COST}" \
    --project-id "${cluster_project_id}" \
    --namespace "${ira_online_gpu_kubernetes_namespace_name}" \
    --output-csv "${ACP_REPO_DIR}/k6-benchmark.csv"

  if [[ "${SYNC_ONLY}" != "true" ]]; then
    echo "[INFO] Cleaning up Job resources for ${ACCELERATOR_TYPE}..."
    kubectl delete --ignore-not-found --kustomize "${CONFIG_DIR}/${HF_MODEL_NAME}"
  fi
done

echo ""
echo "======================================================================"
echo " ALL BENCHMARK SUITES COMPLETE"
echo " Final Aggregated CSV: ${ACP_REPO_DIR}/k6-benchmark.csv"
echo "======================================================================"
