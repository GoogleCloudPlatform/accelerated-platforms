---
name: llm-d-interactive-chat
description: Runs the interactive chat benchmarking scenario on GKE with accelerators.
version: 0.2.0
allowed-tools: kubectl gcloud inference-perf curl cat source
mcp-servers:
  - kubernetes:
      reason: "Verify HuggingFace token secret existence."
  - gcp:
      reason: "Retrieve active account identity, check GKE Prometheus options, read Cloud Monitoring metrics, and upload reports to Cloud Storage (GCS)."
---

# Interactive Chat Scenario Skill

Follow these instructions to run the interactive chat benchmarking scenario.

## 1. Execution via Supporting Script

All steps (Validation, Dry Run, Execution, Collection, and Upload) are bundled into a supporting shell script.

*   **Command**: `./skills/scripts/run_benchmark.sh <config_file> <endpoint_url> [namespace]`
*   **Example**:
    ```bash
    ./skills/scripts/run_benchmark.sh skills/llm-d-interactive-chat/config.json http://vllm-service:8000
    ```

Ensure you have set `CLUSTER_NAME` and `ZONE` environment variables if you want the script to verify Managed Prometheus.

## 2. Manual Steps & Verification (Reference)

If you need to run steps manually or understand what the script does, see below:

### IAM & Prerequisites
*   Check identity: `gcloud config get-value account` (or tool call: `gcp/get_active_account`)
*   Check endpoint: `curl $ENDPOINT_URL/v1/models` (or standard HTTP tool calls to check models)
*   Check Prometheus: `gcloud container clusters describe $CLUSTER_NAME --zone $ZONE --format="value(managedPrometheusConfig.enabled)"` (or tool call: `gcp/get_gke_cluster_details`)
*   Check DCGM: `gcloud monitoring metric-descriptors list --filter='metric.type="prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge"'` (or tool call: `gcp/list_metric_descriptors` with filter)

### Configuration
*   Ensure `config.json` and `inference-perf.yaml` are correctly configured for Interactive Chat.
*   Ensure HF token is a secret: `kubectl describe secret hf-token` (or tool call: `kubernetes/get_secret` with name `hf-token`)

### Dry Run & Execution
*   Dry Run: `llm-d bench run --config config.json --endpoint-url $ENDPOINT_URL --dry-run`
*   Run: `llm-d bench run --config config.json --endpoint-url $ENDPOINT_URL --harness inference-perf --output results.json`

### Results & Upload
*   Generate Report: `llm-d report generate --input results.json --output report_v0.2.json`
*   Collect DCGM: `gcloud monitoring time-series list --filter='metric.type="kubernetes.io/container/accelerator/duty_cycle"' --format=json > dcgm_metrics.json` (or tool call: `gcp/list_time_series` with metric type filter)
*   Upload: `gcloud storage cp report_v0.2.json gs://llm-d-benchmark/` (or tool call: `gcp/upload_object_to_bucket`)
*   Extract CSV: `llm-d report extract-csv --input report_v0.2.json --output output.csv`

