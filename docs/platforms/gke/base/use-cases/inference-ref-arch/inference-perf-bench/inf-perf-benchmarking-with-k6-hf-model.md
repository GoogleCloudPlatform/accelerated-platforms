# GKE Inference Benchmarking with k6

This example sets up a benchmarking job on Google Kubernetes Engine (GKE),
leveraging the Inference reference-architecture for model deployment and the k6
open-source tool for scalable benchmarking.

This implementation deploys the k6 as a Kubernetes Job and can be customized
with different load scenarios and datasets.

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

1. Deploy and configure the
   [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).

### Requirements

This guide was designed to be run from
[Cloud Shell](https://cloud.google.com/shell) in the Google Cloud console. Cloud
Shell has the following tools installed:

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
- `curl`
- `envsubst`
- `jq`
- `kubectl`
- `sponge`

## Create and configure the Google Cloud resources

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

1. Update terraform environment variables depending on the accelerators being
   used (GPU/TPU/BOTH). Example:

   ```shell
   export TF_VAR_enable_gpu=true
   export TF_VAR_enable_tpu=false
   ```

1. Deploy the benchmark infrastructure:

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   rm -rf "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench/.terraform/terraform.tfstate" && \
   terraform -chdir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench" init && \
   terraform -chdir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench" plan -input=false -out=tfplan && \
   terraform -chdir="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench" apply -input=false tfplan && \
   rm "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench/tfplan"
   ```

## Define the Benchmarking Configuration

1. Choose a model:

   - [**FLUX.2-klein-4B**](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B):

     ```shell
     export HF_MODEL_ID="black-forest-labs/flux.2-klein-4b"
     ```

1. Select an accelerator:

   | Model           | l4  | RTX Pro 6000 |
   | --------------- | --- | ------------ |
   | flux.2-klein-4b | ✅  | ✅           |

   - 1x **NVIDIA Tesla L4 24GB**, running on a `g2-standard-16` Google
     Kubernetes Engine node:

     ```shell
     export ACCELERATOR_TYPE="l4"
     ```

   - **NVIDIA RTX Pro 6000**:

     - 1x **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000"
       ```

     - 1/2 (half) of a **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000-1-2"
       ```

     - 1/4 (one fourth) of a **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000-1-4"
       ```

     - 1/8 (one eight) of a **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000-1-8"
       ```

   Ensure that you have enough quota in your project to provision the selected
   accelerator type. For more information, see about viewing GPU quotas, see
   [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

1. Configure sequential benchmarking scenarios using the `K6_SCENARIOS_JSON`
   variable. This variable accepts a JSON array of objects, where each object
   represents a specific load configuration to be tested sequentially.

   ```shell
   export K6_SCENARIOS_JSON='[{"batch": 1, "vus": 1, "width": 512, "height": 512, "steps": 10}, {"batch": 2, "vus": 4, "width": 512, "height": 512, "steps": 10}]'
   ```

   **JSON Attribute Definitions:**

   - **`batch`**: The number of prompts sent in a single inference request.
     Larger batch sizes generally increase GPU utilization but also increase
     request latency.
   - **`vus`**: Virtual Users. The number of concurrent worker threads sending
     requests to the server. Increasing VUs helps saturate the GPU by filling
     compute gaps between individual requests.
   - **`duration`** (Optional): The length of time to run this specific scenario
     (e.g., `"10m"`, `"300s"`). Defaults to `10m` if not specified.
   - **`width` and `height`**: resolution of output images.
   - **`steps`**: inference steps.

   **Execution Workflow:** The k6 script automatically performs a **5-minute
   warmup** using the first configured scenario's VU count to ensure the model
   is loaded and compiled. Between each subsequent scenario, the script enforces
   a **30-second cool-down period** to allow hardware metrics to return to
   baseline for clean analysis.

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

### Destructive Testing & Stability

When testing "frontier" configurations (e.g., Batch Size > 18 on RTX 6000),
there is a high risk of triggering a **CUDA Out-of-Memory (OOM)** error. This
will cause the inference server Pod to crash and restart.

To ensure benchmark integrity, follow these stability guidelines:

1. **Order Destructive Tests Last**: Always place scenarios that are likely to
   crash the server at the very end of your `K6_SCENARIOS_JSON` array. This
   prevents a crash from polluting the results of subsequent tests.
1. **The Re-compilation Penalty**: The inference server uses `torch.compile`
   with CUDA Graphs. If the server restarts due to an OOM, it requires **3-5
   minutes** to re-warm and re-compile before it can achieve peak performance.
1. **Recovery Warmups**: If you must run more tests after a potentially
   destructive scenario in the same Job, insert a "Recovery Warmup" scenario
   immediately after the risky one. A recovery scenario should use a small load
   (e.g., `{"batch": 1, "vus": 1, "duration": "5m"}`) to give the server time to
   restart and re-compile while k6 records the errors during the transition.

### Tested Configurations Summary

The following table illustrates the configurations that we tested serving
`flux.2-klein-4b`, and which ones run the benchmark suite to completion,
assuming no other load on the inference server.

| Accelerator          | Backend | Resolution | Batch Size | VUs | Steps | Status   |
| -------------------- | ------- | ---------- | ---------- | --- | ----- | -------- |
| **NVIDIA L4**        | SGLang  | 1024x1024  | 1          | 1-4 | 20    | ✅       |
| **NVIDIA L4**        | SGLang  | 1024x1024  | 2+         | 1   | 20    | ❌ (OOM) |
| **NVIDIA L4**        | SGLang  | 768x768    | 1          | 1   | 20    | ✅       |
| **NVIDIA L4**        | SGLang  | 512x512    | 1-4        | 1-4 | 10-20 | ✅       |
| **NVIDIA L4 x2**     | SGLang  | 1024x1024  | 1          | 1-4 | 20    | ✅       |
| **NVIDIA L4 x2**     | SGLang  | 1024x1024  | 2+         | 1   | 20    | ❌ (OOM) |
| **NVIDIA L4 x2**     | SGLang  | 512x512    | 1          | 1   | 20    | ✅       |
| **NVIDIA L4 x4**     | SGLang  | 1024x1024  | 1          | 1-2 | 20    | ✅       |
| **NVIDIA L4 x4**     | SGLang  | 1024x1024  | 2+         | 1   | 20    | ❌ (OOM) |
| **NVIDIA L4 x4**     | SGLang  | 512x512    | 1          | 1   | 20    | ✅       |
| **RTX Pro 6000**     | SGLang  | 1024x1024  | 1-24       | 1-8 | 10-50 | ✅       |
| **RTX Pro 6000**     | SGLang  | 512x512    | 1-4        | 1-4 | 10-20 | ✅       |
| **RTX Pro 6000**     | SGLang  | 768x768    | 1          | 1   | 20    | ✅       |
| **RTX Pro 6000 1/2** | SGLang  | 1024x1024  | 1-24       | 1-8 | 10-50 | ✅       |
| **RTX Pro 6000 1/2** | SGLang  | 512x512    | 1-4        | 1-4 | 10-20 | ✅       |
| **RTX Pro 6000 1/2** | SGLang  | 768x768    | 1          | 1   | 20    | ✅       |
| **RTX Pro 6000 1/4** | SGLang  | 1024x1024  | 1-3        | 1-4 | 10-20 | ✅       |
| **RTX Pro 6000 1/4** | SGLang  | 1024x1024  | 4+         | 1-8 | 10-20 | ❌ (OOM) |
| **RTX Pro 6000 1/4** | SGLang  | 512x512    | 1-4        | 1-4 | 10-20 | ✅       |
| **RTX Pro 6000 1/4** | SGLang  | 768x768    | 1          | 1   | 20    | ✅       |
| **RTX Pro 6000 1/8** | SGLang  | All        | N/A        | N/A | N/A   | ❌ (OOM) |

## Automated Execution (Recommended)

You can use the provided orchestrator script to automate the entire lifecycle
(build, deploy, monitor, and analyze) in a single command using the environment
variables defined in the previous steps. The script supports running benchmarks
sequentially across multiple accelerators by providing a comma-separated list:

```shell
# Example: Testing multiple resolutions and batch sizes in one run
export ACCELERATOR_TYPE="l4,rtx-pro-6000"
export K6_SCENARIOS_JSON='[
  {"batch": 1, "vus": 1, "width": 512, "height": 512, "steps": 10},
  {"batch": 4, "vus": 4, "width": 768, "height": 768, "steps": 20},
  {"batch": 16, "vus": 1, "width": 1024, "height": 1024, "steps": 50}
]'

./platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/run_benchmark.sh \
  --accelerator "${ACCELERATOR_TYPE}" \
  --model "${HF_MODEL_ID}" \
  --scenarios "${K6_SCENARIOS_JSON}" \
  --build
```

**Script Flags:**

- `--accelerator`: The accelerator type(s). Supports a single value (e.g., `l4`)
  or a comma-separated list for sequential runs (e.g., `l4,rtx-pro-6000`).
- `--model`: The Hugging Face model ID.
- `--scenarios`: The JSON array of benchmark scenarios. Each scenario MUST
  specify `batch`, `vus`, `width`, `height`, and `steps`.
- `--build`: (Optional) Rebuild and push the k6 benchmark container image once
  before starting the runs.
- `--sync-only`: (Optional) Skip executing the benchmark workload on the
  cluster, and jump straight to downloading the latest results from GCS and
  running the data aggregation pipeline.
- `--manual-cost`: (Optional) Override the default on-demand hourly price.

## Manual Execution

If you prefer to run the benchmarking steps individually, follow the
instructions below.

### Build the benchmark container image

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

1. Build the container image for the Diffusers inference server.

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   rm -rf ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/k6_benchmark/.terraform/ terraform.tfstate* && \
   terraform -chdir=${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/k6_benchmark init && \
   terraform -chdir=${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/k6_benchmark plan -input=false -out=tfplan && \
   terraform -chdir=${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/k6_benchmark apply -input=false tfplan && \
   rm ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/k6_benchmark/tfplan
   ```

   The build usually takes about 1 minute.

### Deploy the benchmark workload

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

1. Set the benchmark parameters:

   ```shell
   export K6_SCENARIOS_JSON='[{"batch": 1, "vus": 1, "width": 1024, "height": 1024, "steps": 20}]'
   ```

1. Configure the deployment:

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/k6-benchmark/configure_deployment.sh"
   ```

1. Deploy the benchmark workload.

   ```shell
   kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/k6-benchmark/${HF_MODEL_NAME}"
   ```

1. Watch the deployment until it is ready.

   ```shell
   watch --color --interval 5 --no-title \
   "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get job/k6-benchmark-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
   echo '\nLogs(last 10 lines):'
   kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs job/k6-benchmark-${HF_MODEL_NAME} --all-containers --tail 10"
   ```

   When the deployment is ready, you will see the following:

   ```text
   NAME                                           READY   UP-TO-DATE   AVAILABLE   AGE
   k6-benchmark-<HF_MODEL_NAME>                   1/1     1            1           ###
   ```

   You can press `CTRL`+`c` to terminate the watch.

### Analyze and Interpret Results

1. Download the files where the benchmarker collected data points:

   ```shell
     gcloud storage cp -r gs://${hub_models_bucket_bench_results_name}/ .
   ```

1. Set up the environment to run the metrics summarization script:

   ```shell
   # Create and activate a Python virtual environment
   python3 -m venv .venv
   . .venv/bin/activate

   # Install dependencies
   pip install --require-hashes -r "${ACP_REPO_DIR}/container-images/cpu/k6-benchmark/requirements.txt"
   ```

1. Set the hourly cost in USD for the Compute Engine machine you're using to run
   the model by initializing the `MODEL_MACHINE_HOURLY_COST_USD` variable. For
   example, if a machine costs `1.147208384` USD per hour, you initialize
   `MODEL_MACHINE_HOURLY_COST_USD` as follows:

   ```shell
   export MODEL_MACHINE_HOURLY_COST_USD="1.147208384"
   ```

   For more information about machine pricing, see:

   - [Accelerator-optimized pricing](https://cloud.google.com/products/compute/pricing/accelerator-optimized)

1. Run the metrics aggregation and reporting script:

   ```shell
   for f in "${hub_models_bucket_bench_results_name}"/*"${HF_MODEL_NAME}"*"${ACCELERATOR_TYPE}"*.jsonl; do
    echo "Processing $f..."
    python3 "${ACP_REPO_DIR}/container-images/cpu/k6-benchmark/extract_metrics.py" \
      --file "$f" \
      --hourly-cost "${MODEL_MACHINE_HOURLY_COST_USD}" \
      --project-id "${cluster_project_id}" \
      --output-csv k6-benchmark.csv
   done
   ```

1. Review aggregated results for each run by examining the contents of the
   aggregated results files:

   ```shell
   for f in "${hub_models_bucket_bench_results_name}"/*report.txt; do
     echo "Visualizing $f contents:"
     cat "$f"
   done
   ```

   The output is similar to the following:

   ```text
   ==================================================
    GKE Performance Consolidated Report
    Source: k6-diffusers-flux-2-klein-4b-rtx-pro-6000-20260422T123505Z.jsonl
   ==================================================
   SUMMARY TABLE:
   Scenario             Img/s      Lat p50    GPU %      Cost/1k
   ------------------------------------------------------------
   bench_b1_v1          0.3779     2.648      84.95%     $3.3074
   bench_b2_v4          0.4497     9.087      99.89%     $2.7798

   --------------------------------------------------
    SCENARIO: bench_b2_v4 (Batch: 2, VUs: 4)
   --------------------------------------------------
    UX Metrics: 0.4497 Img/s, 0.2248 RPS, Success: 100.00%
    Latency (Req): p50=18.174s, p95=18.196s, p99=30.436s
    Latency (Img): p50=9.087s, p95=9.098s, p99=15.218s
    Hardware: VRAM=25984.0 MiB (26.43%), Compute=99.89%, Power=591.53 W
    Economics: Cost/1k Images = $2.7798
   ```

1. Review the aggregated results across all runs:

   ```shell
   column -s, -t < k6-benchmark.csv | less -S
   ```

   The output is similar to the following:

   ```text
   Source File                                             Deployment Name               Target URL                               Model            Accelerator   Resolution  Inference Steps  Batch Size  VUs  Start Time (UTC)     End Time (UTC)       Total Time (s)  Total Requests  Throughput (Images/s)  Request Latency p50 (s)  Peak VRAM    Average Compute  Cost per 1k Images ($)
   k6-diffusers-flux-2-klein-4b-rtx-pro-6000-20260421.jsonl  diffusers-rtx-pro-6000-flux   http://...                               flux-2-klein-4b  rtx-pro-6000  1024x1024   20               2           4    2026-04-22 12:40:28  2026-04-22 12:50:10  582.66          131             0.4497                 18.174                  25984.0 MiB  99.89%           2.7798
   ```

## Key LLM Performance Metrics Metric Description Optimization Focus

- **_Time-to-First-Token (TTFT)_**: Latency from request start to the first
  output token. Crucial for perceived responsiveness in chatbots.

- **_Time-per-Output-Token (TPOT)_**: Average time to generate subsequent
  tokens. Key measure of generation speed and sustained throughput.

- **_Total Latency (P95/P99)_**: End-to-end time for the entire response.
  Represents the experience of users with the slowest responses.

- **_Throughput (Tokens/s)_**: Total tokens generated per second under load.
  Measure of infrastructure efficiency and capacity.

## Clean up

1. Delete the benchmarking job.

   ```shell
   kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/k6-benchmark/${HF_MODEL_NAME}"
   ```

1. Destroy the benchmarking resources.

   > Note: This will only destroy your benchmarking results GCS bucket only if
   > its empty

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
   rm -rf .terraform/ terraform.tfstate* && \
   terraform init &&
   terraform destroy -auto-approve
   ```
