#!/usr/bin/env bash
# Copyright 2026 Google LLC
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

# Shared script to run llm-d benchmark
# Should be run from the repository root.
# Assumes llmdbenchmark CLI and other tools are available.

set -e
# Parse CLI inputs
WORKLOAD=$1
ENDPOINT_URL=$2
NAMESPACE=${3:-"default"}
MODEL_NAME=${4:-"google/gemma-4-31b-it"}
# Resolve hardware and deployment specs
ACCELERATOR_TYPE=${ACCELERATOR_TYPE:-"nvidia-h100"}
SPEC=${SPEC:-${DEPLOYMENT_STRATEGY:-"optimized-baseline"}}
MODEL_SERVER=${MODEL_SERVER:-"vllm"}
REPO_DIR="${ACP_REPO_DIR:-$(pwd)}"
# Resolve GCP Region dynamically
REGION=${REGION:-${TF_VAR_cluster_region:-$TF_VAR_platform_default_region}}
[ -z "$REGION" ] && [ -n "$ZONE" ] && REGION=$(echo "$ZONE" | sed -E 's/-[a-z0-9]+$//')
export REGION LLMDBENCH_BASE_DIR="${LLMDBENCH_BASE_DIR:-$(cd "${REPO_DIR}/.." && pwd)/llm-d-benchmark}"
# Determine GCS bucket for results
RESULTS_BUCKET=${5:-$RESULTS_BUCKET}
if [ -z "$RESULTS_BUCKET" ]; then
    TFVARS_FILE="${REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
    PLATFORM_NAME=$(awk -F'"' '/platform_name/ {print $2}' "$TFVARS_FILE" || echo "llm-d-bench")
    RESULTS_BUCKET="inf-${PLATFORM_NAME:-llm-d-bench}-bench-results"
fi
export RESULTS_BUCKET="${RESULTS_BUCKET#gs://}"

# Enforce required args and provision bucket if missing
[ -z "$WORKLOAD" ] || [ -z "$ENDPOINT_URL" ] && { echo "Usage: $0 <workload> <url> [ns] [model] [bucket]"; exit 1; }
gcloud storage buckets describe "gs://${RESULTS_BUCKET}" &>/dev/null || gcloud storage buckets create "gs://${RESULTS_BUCKET}" ${REGION:+--location=$REGION} || true

# Preflight: check if the endpoint is working
preflight_endpoint() {
  local url="$1" ns="$2" gw="" http_code="" smoke_log=""
  if [[ "$url" == *"vllm-service"* ]]; then
    gw=$(kubectl -n "$ns" get gateway llm-d-inference-gateway -o jsonpath='{.status.addresses[0].value}' 2>/dev/null || true)
    echo "ERROR: '$url' is not valid for the llm-d stack (no Service named vllm-service in namespace '$ns')." >&2
    if [ -n "$gw" ]; then
      echo "Use the Gateway URL instead: http://${gw}" >&2
    else
      echo "Resolve the endpoint with: kubectl -n $ns get gateway llm-d-inference-gateway -o jsonpath='{.status.addresses[0].value}'" >&2
    fi
    exit 1
  fi
  kubectl -n "$ns" delete pod model-smoke-test --ignore-not-found --grace-period=0 --force &>/dev/null || true
  sed "s,REPLACE_ENDPOINT_URL,${url},g" "${REPO_DIR}/skills/llm-d-benchmarking/scripts/helper-pods/smoke-test.yaml" | kubectl apply -n "$ns" -f - >/dev/null
  if ! kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/model-smoke-test -n "$ns" --timeout=90s >/dev/null 2>&1; then
    smoke_log=$(kubectl logs pod/model-smoke-test -n "$ns" 2>&1 || true)
    kubectl -n "$ns" delete pod model-smoke-test --ignore-not-found --grace-period=0 --force &>/dev/null || true
    echo "ERROR: endpoint preflight failed for '$url' in namespace '$ns'." >&2
    echo "$smoke_log" >&2
    exit 1
  fi
  smoke_log=$(kubectl logs pod/model-smoke-test -n "$ns" 2>&1 || true)
  kubectl -n "$ns" delete pod model-smoke-test --ignore-not-found --grace-period=0 --force &>/dev/null || true
  http_code=$(echo "$smoke_log" | sed -n 's/^HTTP Code: //p' | tail -n1)
  if [ "$http_code" != "200" ]; then
    echo "ERROR: endpoint '$url' returned HTTP ${http_code:-unknown} for /v1/models (expected 200)." >&2
    echo "$smoke_log" >&2
    exit 1
  fi
  echo "Endpoint preflight OK: ${url}/v1/models -> HTTP 200"
  if [[ "$WORKLOAD" == *agentic_code_generation* ]]; then
    echo "WARNING: agentic_code_generation targets up to ~262k context; gemma-4-31b-it is 32k. Oversized prompts can cause Broken pipe / VLLMValidationError. Prefer sanity_random.yaml or chatbot_synthetic.yaml, or retune max_model_len." >&2
  fi
}
if [[ "${SKIP_ENDPOINT_PREFLIGHT:-false}" != "true" ]]; then
  preflight_endpoint "$ENDPOINT_URL" "$NAMESPACE"
fi

# Function to validate and propose optimal sizing configs
validate_workload_config() {
  local f="$1"
  [ ! -f "$f" ] && f=$(find . "${LLMDBENCH_BASE_DIR:-.}" -path "*/workspaces" -prune -o -name "$1*" -print -quit 2>/dev/null)
  [ ! -f "$f" ] && return 0
  set +e; python3 "${REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" --perf-yaml "$f" --accelerator-type "$ACCELERATOR_TYPE" --spec "$SPEC" --model "$MODEL_NAME"; code=$?; set -e
  if [ $code -eq 2 ]; then
    read -p "There are gaps between the benchmark workload profile and the current vLLM config detected. Do you want to apply the tuned configuration? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
      echo "Applying tuned configuration updates to the manifests..."
      python3 "${REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" --perf-yaml "$f" --accelerator-type "$ACCELERATOR_TYPE" --spec "$SPEC" --model "$MODEL_NAME" --apply
      echo "Please review the updated files listed above. Run the suggested 'kubectl apply -k' command to push these changes to your cluster, then re-run this benchmark script."
      exit 0
    else
      echo "Skipping updates. The benchmark will proceed using the CURRENT (default) configuration."
    fi
  else
    echo "Configuration is optimal. Proceeding with the benchmark."
  fi
}

# Pre-flight Checks
[ -n "$CLUSTER_NAME" ] && [ -n "$ZONE" ] && { gcloud container clusters describe "$CLUSTER_NAME" --zone "$ZONE" --format="value(managedPrometheusConfig.enabled)" 2>/dev/null | grep -q "true" && echo "Managed Prometheus is enabled." || echo "Warning: Managed Prometheus may not be enabled."; }
if [[ "${RUN_TUNER:-true}" == "true" ]]; then
  validate_workload_config "$WORKLOAD"
else
  echo "RUN_TUNER is set to false. Skipping workload config validation."
fi

# Skill Mock Evaluation Mode fallback
if [ -n "$MOCK_LOG_FILE" ]; then
    curl -s "${ENDPOINT_URL}/v1/models" >/dev/null || true
    llmdbenchmark run --base-dir "$LLMDBENCH_BASE_DIR" --spec "guides/${SPEC}" --workload "$WORKLOAD" --endpoint-url "$ENDPOINT_URL" --namespace "$NAMESPACE" --harness inference-perf --output results.json
    echo '{"mock_key": "mock_value", "results": {"request_performance": {"aggregate": {"requests": {"input_length": {"mean": 10}, "output_length": {"mean": 20}}}}}}' > report_v0.2.json
    echo '{"mock_vllm_args": ["--model", "google/gemma-4-31b-it"]}' > ./vllm_config.json
    echo '{}' > ./dcgm_metrics.json
    echo -e "treatment,source_file,ttft_mean_s\ndefault,report_v0.2.json,0.5" > output.csv
    GCS_DIR_NAME="mock-run-$(date -u +%Y%m%d-%H%M%S)"
    gcloud storage cp report_v0.2.json vllm_config.json dcgm_metrics.json output.csv gs://${RESULTS_BUCKET}/${GCS_DIR_NAME}/
    exit 0
fi

# Configure Runtime Workspace
WORKSPACE_DIR="workspaces/run-$(date +%Y%m%d-%H%M%S)"
WORKLOAD_ARG="--workload $WORKLOAD"


# Function to capture GPU DCGM metrics
collect_dcgm() {
  sed -e "s/TARGET_NAMESPACE_PLACEHOLDER/$1/g" -e "s/START_TIME_PLACEHOLDER/$2/g" -e "s/END_TIME_PLACEHOLDER/$3/g" skills/llm-d-benchmarking/scripts/helper-pods/telemetry-collector.yaml | kubectl apply -f - -n "$1"
  kubectl wait --for=jsonpath='{.status.phase}'=Succeeded pod/telemetry-collector -n "$1" --timeout=120s || true
  kubectl delete pod telemetry-collector -n "$1" --grace-period=0 --force
}

# Phase 1: Setup Namespace & PVC
llmdbenchmark run --base-dir "$LLMDBENCH_BASE_DIR" --spec "guides/${SPEC}" $WORKLOAD_ARG --model "$MODEL_NAME" --endpoint-url "$ENDPOINT_URL" --namespace "$NAMESPACE" --workspace "$WORKSPACE_DIR" --dry-run

# The data-access pod pulls a ~3GB image, which exceeds the 120s default wait on a cold node.
llmdbenchmark run --base-dir "$LLMDBENCH_BASE_DIR" --spec "guides/${SPEC}" $WORKLOAD_ARG --model "$MODEL_NAME" --endpoint-url "$ENDPOINT_URL" --namespace "$NAMESPACE" --workspace "$WORKSPACE_DIR" --data-access-timeout "${DATA_ACCESS_TIMEOUT:-900}" -s 0,1,2,3,4,5,6


# Phase 2: Execute Benchmark Harness
BENCHMARK_START_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
set +e; llmdbenchmark run --base-dir "$LLMDBENCH_BASE_DIR" --spec "guides/${SPEC}" $WORKLOAD_ARG --model "$MODEL_NAME" --endpoint-url "$ENDPOINT_URL" --namespace "$NAMESPACE" --harness inference-perf --workspace "$WORKSPACE_DIR" -s 7,8; set -e
BENCHMARK_END_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ)
collect_dcgm "$NAMESPACE" "$BENCHMARK_START_TIME" "$BENCHMARK_END_TIME"

# Phase 3: Result Retrieval & Cleanup
llmdbenchmark run --base-dir "$LLMDBENCH_BASE_DIR" --spec "guides/${SPEC}" -s 9 --model "$MODEL_NAME" --endpoint-url "$ENDPOINT_URL" --namespace "$NAMESPACE" --harness inference-perf --workspace "$WORKSPACE_DIR"


# Phase 4: Report Generation & Archival
RESULTS_DIR=$(ls -td "$WORKSPACE_DIR"/*/results/inference-perf-* 2>/dev/null | head -n 1 || true)
[ -z "$RESULTS_DIR" ] && { echo "ERROR: no results under $WORKSPACE_DIR -- the harness produced no metrics. Check the harness pod logs." >&2; exit 1; }
cp "$RESULTS_DIR/summary_lifecycle_metrics.json" ./results.json
python3 -c "from llmdbenchmark.analysis.benchmark_report.native_to_br0_2 import import_inference_perf; import_inference_perf('./results.json').export_json('./report_v0.2.json')"
python3 "${REPO_DIR}/skills/llm-d-benchmarking/scripts/extract_csv.py" --input report_v0.2.json --output output.csv
kubectl get $(kubectl get deployment -n "$NAMESPACE" -o name | grep -i 'vllm' | head -n 1) -n "$NAMESPACE" -o json > ./vllm_config.json 2>/dev/null || echo '{"error": "not found"}' > ./vllm_config.json
cp report_v0.2.json output.csv vllm_config.json "$RESULTS_DIR/"
[ -f "./dcgm_metrics.json" ] && cp "./dcgm_metrics.json" "$RESULTS_DIR/"

GCS_DIR_NAME=$(basename "$WORKSPACE_DIR")
gcloud storage cp -r "$RESULTS_DIR/"* gs://${RESULTS_BUCKET}/${GCS_DIR_NAME}/

# Cleanup manual data-access pod
kubectl delete pod access-to-harness-data-workload-pvc -n "$NAMESPACE" --ignore-not-found --grace-period=0 --force
