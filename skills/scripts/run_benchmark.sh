#!/bin/bash
# Shared script to run llm-d benchmark
# Should be run from the repository root.
# Assumes llm-d CLI and other tools are available.

set -e

CONFIG_FILE=$1
ENDPOINT_URL=$2
NAMESPACE=${3:-"default"}

if [ -z "$CONFIG_FILE" ] || [ -z "$ENDPOINT_URL" ]; then
    echo "Usage: $0 <config_file> <endpoint_url> [namespace]"
    echo "Example: $0 skills/llm-d-code-gen-bench/config.json http://localhost:8000"
    exit 1
fi

echo "=== 1. IAM Validation ==="
echo "Current account:"
gcloud config get-value account

echo "=== 2. Prerequisites ==="
echo "Validating endpoint $ENDPOINT_URL..."
curl -s "$ENDPOINT_URL/v1/models" || { echo "Failed to connect to endpoint or endpoint returned error."; exit 1; }

if [ -n "$CLUSTER_NAME" ] && [ -n "$ZONE" ]; then
    echo "Checking Google Managed Prometheus for cluster $CLUSTER_NAME in $ZONE..."
    gcloud container clusters describe "$CLUSTER_NAME" --zone "$ZONE" --format="value(managedPrometheusConfig.enabled)"
else
    echo "Skipping Managed Prometheus check (CLUSTER_NAME or ZONE not set)."
fi

echo "Checking DCGM Metrics availability in Cloud Monitoring..."
gcloud monitoring metric-descriptors list --filter='metric.type="prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge"' | head -n 5

echo "=== 3. Dry Run ==="
echo "Running dry run..."
llm-d bench run --config "$CONFIG_FILE" --endpoint-url "$ENDPOINT_URL" --dry-run

echo "=== 4. Execution ==="
echo "Running benchmark..."
llm-d bench run --config "$CONFIG_FILE" --endpoint-url "$ENDPOINT_URL" --harness inference-perf --output results.json

echo "=== 5. Result Collection ==="
echo "Generating v0.2 report..."
llm-d report generate --input results.json --output report_v0.2.json

echo "Collecting DCGM metrics..."
gcloud monitoring time-series list --filter='metric.type="kubernetes.io/container/accelerator/duty_cycle"' --format=json > dcgm_metrics.json

echo "=== 6. Upload ==="
echo "Uploading to GCS..."
gcloud storage cp report_v0.2.json gs://llm-d-benchmark/
echo "Extracting CSV..."
llm-d report extract-csv --input report_v0.2.json --output output.csv

echo "Benchmark flow completed successfully."
