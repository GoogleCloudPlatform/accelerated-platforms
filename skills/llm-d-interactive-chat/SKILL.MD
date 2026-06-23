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

## 1. Execution Workflow (Baseline vs. Workload-Tuned)

To measure configuration improvements, you should run the benchmark twice: first as a **baseline**, and then under a **workload-tuned** configuration.

### Phase 1: Run Baseline Benchmark
Run the benchmark using the default repository configuration (no tuning applied):
1. **Command**:
   ```bash
   ./skills/scripts/run_benchmark.sh skills/llm-d-interactive-chat/config.json http://vllm-service:8000
   ```
2. **Result Verification**: Note down the throughput (QPS), Time to First Token (TTFT), and Inter-Token Latency from the generated report (`report_v0.2.json`).

### Phase 2: Run Workload-Tuned Benchmark
1. **Optimize Parameters:** Run the `llm-d-workload-tuner` skill to calculate and apply optimal model parameters:
   ```bash
   python3 ./skills/llm-d-workload-tuner/scripts/tune_workload.py \
       --config skills/llm-d-interactive-chat/config.json \
       --perf-yaml skills/llm-d-interactive-chat/inference-perf.yaml \
       --gpu-type <accelerator_name> \
       --strategy <strategy_name> \
       --apply
   ```
   *Review the printed parameter diff comparison to confirm changes.*
2. **Redeploy and Rollout:** Apply the patched overlays to the GKE cluster and wait for pods to restart:
   ```bash
   kubectl rollout restart deployment vllm -n <namespace>
   kubectl rollout status deployment vllm -n <namespace>
   ```
3. **Execute Tuned Benchmark:** Run the benchmark script again:
   ```bash
   ./skills/scripts/run_benchmark.sh skills/llm-d-interactive-chat/config.json http://vllm-service:8000
   ```
4. **Compare Outputs:** Compare the baseline metrics against the tuned run metrics (reproducibility configurations are saved under `vllm_config.json` in the GCS bucket).

Ensure you have set `CLUSTER_NAME` and `ZONE` environment variables if you want the script to verify Managed Prometheus.

## 2. Troubleshooting & Common Failures

If you encounter issues such as:
* GKE TLS / SSL validation errors
* Volume multi-attach lock errors (`FailedAttachVolume` / `ReadWriteOnce`)
* Model served mismatch or gateway connection errors

Please consult the central troubleshooting guide: [TROUBLESHOOTING.md](../TROUBLESHOOTING.md).

## 3. Customizing Workload Distributions

You can configure the sequence length distributions directly inside [config.json](config.json):
* `input_sequence_length`: Bounds and mean of user prompts (determines KV cache matching pressure).
* `output_sequence_length`: Bounds and mean of model output tokens (determines decode scheduling load).

These are dynamically loaded by `run_benchmark.sh` and override the defaults of the `chatbot_synthetic.yaml` profile.

## 4. Manual Steps & Verification (Reference)

If you need to run steps manually or understand what the script does, see below:

### IAM & Prerequisites

- Check identity: `gcloud config get-value account` (or tool call: `gcp/get_active_account`)
- Check endpoint: `curl $ENDPOINT_URL/v1/models` (or standard HTTP tool calls to check models)
- Check Prometheus: `gcloud container clusters describe $CLUSTER_NAME --zone $ZONE --format="value(managedPrometheusConfig.enabled)"` (or tool call: `gcp/get_gke_cluster_details`)
- Check DCGM: `gcloud monitoring metric-descriptors list --filter='metric.type="prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge"'` (or tool call: `gcp/list_metric_descriptors` with filter)

### Configuration

- Ensure `config.json` and `inference-perf.yaml` are correctly configured for Interactive Chat.
- Ensure HF token is registered as a Kubernetes secret: `kubectl describe secret llm-d-hf-token` (or check for `secretProviderClass` configurations).

### Dry Run & Execution

- Dry Run: `llm-d bench run --workload chatbot_synthetic.yaml --endpoint-url $ENDPOINT_URL --dry-run`
- Run: `llm-d bench run --workload chatbot_synthetic.yaml --endpoint-url $ENDPOINT_URL --harness inference-perf --output results.json`

### Results & Upload

- Generate Report: `llm-d report generate --input results.json --output report_v0.2.json`
- Collect DCGM: `gcloud monitoring time-series list --filter='metric.type="kubernetes.io/container/accelerator/duty_cycle"' --format=json > dcgm_metrics.json`
- Upload: `gcloud storage cp report_v0.2.json gs://${RESULTS_BUCKET}/`
- Extract CSV: `llm-d report extract-csv --input report_v0.2.json --output output.csv`
