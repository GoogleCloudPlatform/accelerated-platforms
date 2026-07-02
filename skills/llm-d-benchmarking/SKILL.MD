---
name: llm-d-benchmarking
description: Benchmarks a deployed llm-d well-lit path guide stack on GKE using llm-d-benchmark cli with inference-perf as the harness, the user a will select the appropriate  workload profiles from llm-d-benchmark. 
version: 0.1.0
allowed-tools: python3 kubectl gcloud
mcp-servers: []
dependencies:
  - kubernetes:
      reason: "Deploy helper pods, read PVC logs."
  - gcp:
      reason: "Collect Cloud Monitoring telemetry."
---

# LLM-D Benchmarking Skill

Follow these instructions to run benchmarks against a deployed llm-d stack.

## 1. Prerequisites

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
  _Note: The `run_benchmark.sh` script assumes `llm-d` CLI is installed and available in the path._
- The llm-d stack must be GKE deployed and running.
- Determine the inference endpoint URL and the gateway class (e.g. `epp-only` or `istio`).
  - Refer to [Deploy Stack Skill](../llm-d-deploy-stack/SKILL.MD) for details.

## 2. Select a Workload Profile

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

## 3. Tune & Validate Workload (Optional/Experimental)

Before running the benchmark, you can use the experimental `llm-d-workload-tuner` to check for optimal parameters or issues.
You can run the tuner against the chosen workload profile template:

```bash
python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
  --perf-yaml <path_to_workload_profile_yaml> \
  --accelerator-type <accelerator_type> \
  --strategy <strategy> \
  --model <model_name>
```

Example (for `chatbot_synthetic.yaml` and Gemma-4-31B on RTX 6000):
_Note: You need to locate the profile template, typically under your `llm-d-benchmark` clone if available, or if you have a local copy. If you don't have a local copy, you might need to skip this step or use the default configs._
If you have `llm-d-benchmark` repository cloned at `llm-d-benchmark`:

```bash
python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
  --perf-yaml llm-d-benchmark/workload/profiles/inference-perf/chatbot_synthetic.yaml.in \
  --accelerator-type rtx-pro-6000 \
  --strategy precise-prefix-cache-routing \
  --model google/gemma-4-31b-it
```

## 4. Run Benchmark

Run the consolidated benchmark script with the chosen workload profile and endpoint.

```bash
"${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" <workload_profile_name> <endpoint_url> [namespace] [model_name]
```

### Examples:

- Run chatbot benchmark:

  ```bash
  "${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" chatbot_synthetic.yaml http://vllm-service:8000 default google/gemma-4-31b-it
  ```

- Run code completion benchmark:
  ```bash
  "${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" code_completion_synthetic.yaml http://vllm-service:8000 default google/gemma-4-31b-it
  ```

## 5. Explanation of `run_benchmark.sh` Steps

The `run_benchmark.sh` script automates the execution of the benchmark through the following phases:

1.  **IAM Validation & Prerequisites**:
    - Prints the current GCP account.
    - Performs a smoke check on the target endpoint using `curl` to verify availability.
    - Verifies if Managed Prometheus is enabled on the GKE cluster to ensure metric collection.
2.  **Workspace Setup**:
    - Creates a unique timestamped workspace directory (e.g., `workspaces/run-YYYYMMDD-HHMMSS`) to hold all configurations and results.
3.  **Dry Run**:
    - Executes `llm-d bench run` with the `--dry-run` flag to validate the workload configuration syntax before deployment.
4.  **Phase 1: Setup Namespace & PVC**:
    - Deploys GKE base namespace resources, creates Persistent Volume Claims (PVC) for workload data, and spins up a temporary `data-access` helper pod.
    - The `data-access` pod acts as a bridge to copy configuration files and datasets into the GKE PVC.
    - Once the copy setup completes, the `data-access` pod is deleted to release the PVC lock (since GKE PVC storage is typically ReadWriteOnce), allowing the benchmark runner pod to mount it.
5.  **Phase 2: Deploy & Run Harness**:
    - Records the start time.
    - Deploys the `llmdbench-harness-launcher` pod and starts the actual benchmark using the selected harness (defaulting to `inference-perf`).
    - Blocks and waits for the benchmark run to finish.
    - Records the end time.
6.  **Telemetry Collection**:
    - Deploys an in-cluster `telemetry-collector` pod.
    - This pod queries GKE system metrics (`duty_cycle`, `memory_used`, `memory_total`) from Google Cloud Monitoring for the duration of the benchmark, filtered by the target namespace.
    - Saves metrics to `dcgm_metrics.json`.
7.  **Phase 3: Result Collection & Cleanup**:
    - Re-deploys the `data-access` helper pod to mount the PVC again. This is necessary because it is RWO storage, and we need the helper pod to bridge and copy the result files out of the cluster.
    - Runs the final `llm-d bench run` teardown steps (steps 8-11) to clean up harness resources.
8.  **Report Generation & GCS Upload**:
    - Copies raw metrics and summary files.
    - Invokes `llm-d report generate` to compile the standard performance report (`report_v0.2.json`).
    - Extracts key metrics into a flat CSV format (`output.csv`).
    - Retrieves the running vLLM cluster deployment YAML state configuration (`vllm_config.json`).
    - Uploads all report assets (`report_v0.2.json`, `vllm_config.json`, `dcgm_metrics.json`, `output.csv`) to the target GCS bucket.

## 6. Analyzing Hardware Utilization

To verify if your hardware (GPU or TPU) is fully utilized and healthy during the benchmark, monitor the metrics collected in `dcgm_metrics.json`.

### 6.1 GPU (NVIDIA DCGM Metrics via Managed Prometheus)

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

### 6.2 TPU (GKE System Metrics)

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
