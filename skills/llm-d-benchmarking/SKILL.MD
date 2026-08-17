---
name: llm-d-benchmarking
description: Benchmarks a deployed llm-d well-lit path guide stack on GKE using llm-d-benchmark cli with inference-perf as the harness, the user a will select the appropriate  workload profiles from llm-d-benchmark. 
version: 0.1.0
allowed-tools: python3 kubectl gcloud llmdbenchmark curl
mcp-servers: []
dependencies:
  - kubernetes:
      reason: "Deploy helper pods, read PVC logs."
  - gcp:
      reason: "Collect Cloud Monitoring telemetry."
---

# LLM-D Benchmarking Skill

Follow these instructions to run benchmarks against a deployed llm-d stack.

## 1. Terminology & Variables

This skill utilizes the following core variables:

- `SPEC` (passed via `SPEC` environment variable, previously `DEPLOYMENT_STRATEGY`): The name of the `llm-d` well-lit path guide targeted (e.g., `optimized-baseline`, `precise-prefix-cache-routing`, `predicted-latency-routing`). It defines which GKE manifest subdirectory is active.
- `Workload Profile`: The load-test profile configuration (e.g., `chatbot_synthetic.yaml`, `agentic_code_generation.yaml`) chosen to run.
- `RESULTS_BUCKET` (passed via `RESULTS_BUCKET` environment variable or CLI argument). If not specified, it dynamically defaults to `inf-<platform_name>-bench-results` (resolving the platform name from tfvars) in the same region as the platform.

## 2. Prerequisites

- **Clone `llm-d-benchmark` locally**: Ensure you have a local clone of the `llm-d-benchmark` repository.
  ```bash
  git clone https://github.com/llm-d/llm-d-benchmark.git
  cd llm-d-benchmark
  # Create and activate virtual environment
  python3 -m venv .venv
  source .venv/bin/activate
  # Install CLI dependencies (standard installation)
  curl -sSL https://raw.githubusercontent.com/llm-d/llm-d-benchmark/main/install.sh | bash
  ```
  _Note: The `run_benchmark.sh` script assumes the upstream `llmdbenchmark` package is installed and available in the python path._
- The llm-d stack must be deployed and running on a GKE cluster.
  - Determine the inference endpoint URL and the gateway class (e.g. `epp-only` or `istio`).
  - Refer to [Deploy Stack Skill](../llm-d-deploy-stack/SKILL.MD) for details. If executing this skill immediately after `llm-d-deploy-stack`, the agent should retain context such as `SPEC` (strategy), accelerator type, and namespace. Otherwise, prompt the user for these details.

## 3. Select a Workload Profile

Ask the user to choose a workload profile from the table below, or input a custom one.

| Category                | Workload Profile Name                       | Description / Best For                  |
| ----------------------- | ------------------------------------------- | --------------------------------------- |
| **Smoke Run**           | `shared_prefix_synthetic.yaml`              | Quick smoke run with shared prefix.     |
|                         | `sanity_random.yaml`                        | Basic sanity check with random inputs.  |
| **Interactive Chat**    | `chatbot_synthetic.yaml`                    | Synthetic chatbot workload.             |
|                         | `chatbot_sharegpt.yaml`                     | Replay ShareGPT dataset.                |
| **Code Generation**     | `code_completion_synthetic.yaml`            | Code completion workload.               |
|                         | `agentic_code_generation.yaml`              | Agentic code generation workload.       |
| **Summarization**       | `summarization_synthetic.yaml`              | Summarization workload.                 |
| **Optimization Guides** | `guide_optimized-baseline_1.yaml`           | Reproduces optimized-baseline report.   |
|                         | `guide_precise-prefix-cache-routing_1.yaml` | Reproduces prefix-cache-routing report. |

_Note: For more profiles, refer to [llm-d-workload-profiles.md](../llm-d-workload-tuner/references/llm-d-workload-profiles.md)._

## 4. Tune & Validate Workload (Optional/Experimental)

Before running the benchmark, you can use the experimental `llm-d-workload-tuner` to check for optimal parameters or issues.
You can run the tuner against the chosen workload profile template:

```bash
python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
  --perf-yaml <path_to_workload_profile_yaml> \
  --accelerator-type <accelerator_type> \
  --spec <spec> \
  --model <model_name>
```

Example (for `chatbot_synthetic.yaml` and Gemma-4-31B on RTX 6000):
\_Note: You need to locate the profile template, typically under your `llm-d-benchmark` clone if available

```bash
python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
  --perf-yaml llm-d-benchmark/workload/profiles/inference-perf/chatbot_synthetic.yaml.in \
  --accelerator-type rtx-pro-6000 \
  --spec precise-prefix-cache-routing \
  --model google/gemma-4-31b-it
```

## 5. Run Benchmark

Run the consolidated benchmark script with the chosen workload profile and endpoint.

```bash
"${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" <workload_profile_name> <endpoint_url> [namespace] [model_name] [results_bucket]
```

### Examples:

- Run chatbot benchmark in the workload's namespace (e.g., `default`):

  ```bash
  ENDPOINT_URL="http://$(kubectl -n ${llmd_namespace} get gateway llm-d-inference-gateway -o jsonpath='{.status.addresses[0].value}')"
  "${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" chatbot_synthetic.yaml ${ENDPOINT_URL} <namespace> google/gemma-4-31b-it
  ```

- Run chatbot benchmark with explicit GCS bucket override:
  ```bash
  ENDPOINT_URL="http://$(kubectl -n ${llmd_namespace} get gateway llm-d-inference-gateway -o jsonpath='{.status.addresses[0].value}')"
  "${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" chatbot_synthetic.yaml ${ENDPOINT_URL} <namespace> google/gemma-4-31b-it my-custom-bench-bucket
  ```

## 6. Explanation of `run_benchmark.sh` Steps

The `run_benchmark.sh` script is an ultra-dense automated executor that directly calls the `llmdbenchmark` core library (bypassing CLI wrappers for user reproducibility). It automates the execution through the following condensed phases:

1.  **Dynamic Parameter Resolution & Bucket Provisioning**:
    - Resolves GCP regions dynamically from environment variables, removing multi-regional fallbacks.
    - Determines and enforces a GCS bucket (`inf-<platform_name>-bench-results`), auto-provisioning it via `gcloud storage` if missing.
2.  **Pre-flight Checks & Workload Validation**:
    - Checks if Managed Prometheus is enabled.
    - Invokes `tune_workload.py` to check for optimal specs, allowing an interactive auto-apply fix if sizing gaps are found.
3.  **Phase 1: Setup Namespace & PVC**:
    - Executes `llmdbenchmark run` in `--dry-run` to validate syntax.
    - Executes harness setup steps `0,1,2,3,4,5,6` to create the namespace, RBAC permissions, and the workload PVC.
    - **Note**: The data-access pod is deliberately NOT deleted in this phase so that it can stage the workload profile onto the PVC. This architecture requires a `ReadWriteMany` (RWX) storage class, allowing the harness pod to mount the PVC concurrently from its own node.
4.  **Phase 2: Execute Benchmark Harness & Telemetry Collection**:
    - Captures the start timestamp, deploys the harness (step `7`), and explicitly waits for completion (step `8`) to establish an exact time window.
    - Captures the end timestamp, then triggers the `telemetry-collector.yaml` pod to retroactively capture GPU/TPU DCGM metrics precisely constrained to that execution window.
5.  **Phase 3: Result Retrieval**:
    - Executes step `9` to collect the `inference-perf` results. Because of the RWX storage class, this step natively reuses the original data-access pod from Phase 1
6.  **Phase 4: Report Generation & Cleanup**:
    - Uses `extract_csv.py` and inline python to synthesize `report_v0.2.json` and `output.csv`.
    - Dumps the live vLLM config state and archives all artifacts (`dcgm_metrics.json`, reports) to the target GCS bucket.
    - Manually forces deletion of the original data-access pod so it doesn't linger as a daemon indefinitely.

## 7. Analyze Benchmark Results

After running the benchmark, analyze the generated results using `inference-perf analyze`.

```bash
# Analyze the local results.json or downloaded report_v0.2.json
inference-perf analyze <path_to_results.json>
```

When interpreting the output for the user, make sure to highlight:

- **Performance by Stage & QPS**: Summarize Time to First Token (TTFT), Inter-Token Latency (ITL), and Queries Per Second (QPS).
- **Throughput Metrics**: Highlight input and output token throughput (tokens/sec).
- **HW Config & HPA**: Note the hardware configuration used and any Horizontal Pod Autoscaler scaling behaviors.
- **Error Rate**: Explicitly point out the error rate and any failed requests.

## 8. Analyzing Hardware Utilization

To verify if your hardware (GPU or TPU) is fully utilized and healthy during the benchmark, monitor the metrics collected in `dcgm_metrics.json`.

### 8.1 GPU (NVIDIA DCGM Metrics via Managed Prometheus)

Monitor these metrics for GPU runs:

#### A. Compute & Core Utilization

- **Metric**: `prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge` (or `DCGM_FI_PROF_GR_ENGINE_ACTIVE/gauge`)
  - **Goal**: Check if the GPU is busy.
  - **Analysis**: Consistently high values (>80%) indicate good utilization. Low values suggest bottlenecks elsewhere (e.g., CPU, I/O, or small batch size).
- **Metric**: `prometheus.googleapis.com/DCGM_FI_PROF_SM_ACTIVE/gauge`
  - **Goal**: Measure SM parallelism.
  - **Analysis**: Represents the fraction of time SMs have warps active. High parallelism is key for efficiency.

#### B. Memory Utilization

- **Metric**: `prometheus.googleapis.com/DCGM_FI_DEV_FB_USED/gauge` (vs `DCGM_FI_DEV_FB_TOTAL`)
  - **Goal**: Monitor GPU VRAM footprint.
  - **Analysis**: In LLM inference, we want to maximize KV cache size to fit more requests. High FB_USED is expected, but running out of memory (OOM) will cause failures.
- **Metric**: `prometheus.googleapis.com/DCGM_FI_DEV_MEM_COPY_UTIL/gauge` (or `DCGM_FI_PROF_DRAM_ACTIVE/gauge`)
  - **Goal**: Track memory bandwidth usage.
  - **Analysis**: High memory copy utility combined with low GPU utility indicates a memory bandwidth bottleneck.

#### C. Compute Pipelines (Tensor Cores)

- **Metric**: `prometheus.googleapis.com/DCGM_FI_PROF_PIPE_TENSOR_ACTIVE/gauge`
  - **Goal**: Verify Tensor Core utilization (crucial for LLM matrix multiplications).
  - **Analysis**: Ensure this value is active during benchmark execution. If it is 0, the model is not utilizing Tensor Cores (e.g., wrong precision or layout).
- **Metric**: `prometheus.googleapis.com/DCGM_FI_PROF_PIPE_FP16_ACTIVE/gauge` (or `FP32_ACTIVE`)
  - **Goal**: Track standard floating point pipeline usage.

#### D. Hardware Health & Throttling

- **Metric**: `prometheus.googleapis.com/DCGM_FI_DEV_GPU_TEMP/gauge` & `DCGM_FI_DEV_MEMORY_TEMP/gauge`
  - **Goal**: Monitor thermal state.
  - **Analysis**: Temperatures should stay within safe operating limits (typically < 80-85°C). Overheating leads to throttling.
- **Metric**: `prometheus.googleapis.com/DCGM_FI_DEV_SM_CLOCK/gauge`
  - **Goal**: Detect clock throttling.
  - **Analysis**: If the clock frequency drops significantly under load, it indicates the GPU is throttling due to thermal limits or power constraints, affecting benchmark performance.

### 8.2 TPU (GKE System Metrics)

Monitor these GKE system metrics for TPU runs (e.g., TPU v5e, v6e):

#### A. Core Utilization

- **Metric**: `kubernetes.io/container/accelerator/duty_cycle`
  - **Goal**: Measure TPU Tensor Core utilization.
  - **Analysis**: Represents the percentage of time the Tensor Cores were active. If this is low, check for host-to-device transfer bottlenecks or increase the workload batch size.

#### B. Memory Utilization

- **Metric**: `kubernetes.io/container/accelerator/memory_used` (vs `kubernetes.io/container/accelerator/memory_total`)
  - **Goal**: Monitor High Bandwidth Memory (HBM) footprint.
  - **Analysis**: Verify HBM usage is optimized. Approaching 100% usage risks Out-Of-Memory (OOM) crashes.
- **Metric**: `kubernetes.io/container/accelerator/memory_bandwidth_utilization`
  - **Goal**: Track HBM bandwidth utilization.
  - **Analysis**: High memory bandwidth utilization with low duty cycle indicates the workload is memory-bandwidth bound.

## 9. Teardown Serving Stack

You should tear down the serving stack to release cluster resources only when you are done with all the benchmarks.

1. **Ask the user**: "Do you want to tear down the deployed serving stack? This will delete the vLLM server, gateway, and routing resources. (yes/no)"
2. **If yes**, run the official teardown script corresponding to the chosen guide:
   - For `optimized-baseline`:
     ```bash
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/teardown-llmd-optimized-baseline.sh"
     ```
   - For `precise-prefix-cache-routing`:
     ```bash
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/teardown-llmd-precise-prefix-cache-routing.sh"
     ```
   - For `predicted-latency-routing`:
     ```bash
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/teardown-llmd-predicted-latency-routing.sh"
     ```
