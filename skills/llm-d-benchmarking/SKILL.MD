---
name: llm-d-benchmarking
description: Benchmarks a deployed llm-d well-lit path guide stack on GKE using llm-d-benchmark cli with inference-perf as the harness, the user a will select the appropriate  workload profiles from llm-d-benchmark. 
version: 0.2.0
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

- `SPEC` (passed via `SPEC` environment variable, previously `DEPLOYMENT_STRATEGY`): The name of the `llm-d` well-lit path guide targeted (e.g., `optimized-baseline`, `precise-prefix-cache-routing`, `predicted-latency-routing`, `pd-disaggregation`). It defines which GKE manifest subdirectory is active. Note that `pd-disaggregation` deploys **two** model server tiers (prefill and decode) rather than one; see section 6.1.
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

| Category                | Workload Profile Name                       | Description / Best For                             |
| ----------------------- | ------------------------------------------- | -------------------------------------------------- |
| **Smoke Run**           | `shared_prefix_synthetic.yaml`              | Quick smoke run with shared prefix.                |
|                         | `sanity_random.yaml`                        | Basic sanity check with random inputs.             |
| **Interactive Chat**    | `chatbot_synthetic.yaml`                    | Synthetic chatbot workload.                        |
|                         | `chatbot_sharegpt.yaml`                     | Replay ShareGPT dataset.                           |
| **Code Generation**     | `code_completion_synthetic.yaml`            | Code completion workload.                          |
|                         | `agentic_code_generation.yaml`              | Agentic code generation workload.                  |
| **Summarization**       | `summarization_synthetic.yaml`              | Summarization workload.                            |
| **Optimization Guides** | `guide_optimized-baseline_1.yaml`           | Reproduces optimized-baseline report.              |
|                         | `guide_precise-prefix-cache-routing_1.yaml` | Reproduces prefix-cache-routing report.            |
|                         | `guide_pd-disaggregation_1.yaml`            | Reproduces P/D report: 5000 in / 250 out, rate 45. |
|                         | `guide_pd-disaggregation_2.yaml`            | P/D balanced shape: 1024 in / 1024 out, rate 1.    |

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

> [!TIP] > **Load Balancer Timeouts on Large Sweeps**: External GKE Gateway Load Balancers default to a 30-second HTTP request timeout (or 300 seconds via the default `llm-d` Gateway recipe) unless configured with a `GCPBackendPolicy` setting `timeoutSec: 3600`. When running large multi-stage benchmarks (9+ stages or high concurrency), either patch your `GCPBackendPolicy` to `timeoutSec: 3600` (`kubectl -n <ns> patch gcpbackendpolicy <name> --type='merge' -p '{"spec":{"default":{"timeoutSec":3600}}}'`), or pass the direct in-cluster Service URL (e.g., `http://<service-name>.<namespace>.svc.cluster.local:8000`) to bypass the load balancer timeout.

## 6. Explanation of `run_benchmark.sh` Steps

The `run_benchmark.sh` script is an ultra-dense automated executor that directly calls the `llmdbenchmark` core library (bypassing CLI wrappers for user reproducibility). It automates the execution through the following condensed phases:

1.  **Dynamic Parameter Resolution & Bucket Provisioning**:
    - Resolves GCP regions dynamically from environment variables, removing multi-regional fallbacks.
    - Determines and enforces a GCS bucket (`inf-<platform_name>-bench-results`), auto-provisioning it via `gcloud storage` if missing.
2.  **Pre-flight Checks & Workload Validation**:
    - Checks if Managed Prometheus is enabled.
    - Invokes `tune_workload.py` to check for optimal specs, allowing an interactive auto-apply fix if sizing gaps are found.
    - For long-context workloads like `agentic_code_generation` (~262k prefill tokens), `tune_workload.py` checks `model_specs.json` to ensure `MAX_MODEL_LEN` and `TENSOR_PARALLEL_SIZE` accommodate both prompt prefill and generation tokens without clipping.
3.  **Phase 1: Setup Namespace & PVC**:
    - Executes `llmdbenchmark run` in `--dry-run` to validate syntax.
    - Executes harness setup steps `0,1,2,3,4,5,6` to create the namespace, RBAC permissions, and the workload PVC.
    - **Note**: The data-access pod is deliberately NOT deleted in this phase so that it can stage the workload profile onto the PVC. This architecture requires a `ReadWriteMany` (RWX) storage class, allowing the harness pod to mount the PVC concurrently from its own node.
4.  **Phase 2: Execute Benchmark Harness & Telemetry Collection**:
    - Captures the start timestamp, deploys the harness (step `7`), and explicitly waits for completion (step `8`) to establish an exact time window.
    - Captures the end timestamp, then triggers the `telemetry-collector.yaml` Kubernetes batch **`Job`** (with its mounted `ConfigMap` script) to retroactively capture GPU/TPU DCGM metrics precisely constrained to that execution window.
5.  **Phase 3: Result Retrieval**:
    - Executes step `9` to collect the `inference-perf` results. Because of the RWX storage class, this step natively reuses the original data-access pod from Phase 1
6.  **Phase 4: Report Generation & Cleanup**:
    - Uses `extract_csv.py` and inline python to synthesize `report_v0.2.json` and `output.csv`.
    - Automatically generates latency and throughput charts (`inference-perf -a`).
    - Runs `capture_vllm_config.py` to snapshot the live serving configuration into `vllm_config.json` (see 6.1), and archives all artifacts (`dcgm_metrics.json`, reports, CSVs, and PNG charts) to the target GCS bucket.
    - Manually forces deletion of the original data-access pod so it doesn't linger as a daemon indefinitely.

### 6.1 What `vllm_config.json` Captures

`capture_vllm_config.py` snapshots the serving topology as it is actually
running, so a benchmark result can be traced back to the exact configuration
that produced it. It records **every** vLLM model server in the namespace, which
matters for disaggregated guides:

| Field                                | Contents                                                                                                                                                                                            |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `detected_architecture`              | Platform (`gpu`/`tpu`), manifest pattern, model, compute class, accelerator type/topology/count, KV connector, and whether the topology is disaggregated.                                           |
| `model_servers[]`                    | One entry per model server, each tagged with its `role` (`prefill`, `decode`, or `monolithic`).                                                                                                     |
| `model_servers[].serving_parameters` | Every vLLM CLI flag parsed into a named map — `max_model_len`, `tensor_parallel_size`, `dtype`, `kv_cache_dtype`, `gpu_memory_utilization`, `block_size`, `quantization`, `load_format`, and so on. |
| `model_servers[].tuning_env`         | Behaviour-changing environment variables (`VLLM_*`, `TPU_*`, `JAX_*`, `LIBTPU_*`, `PJRT_*`), such as the TPU KV transfer ports.                                                                     |
| `model_servers[].kv_transfer`        | Parsed `--kv-transfer-config`, exposing `kv_connector`, `kv_role`, and any CPU offload buffer.                                                                                                      |
| `model_servers[].sidecars`           | Sidecars including native sidecars (initContainers with `restartPolicy: Always`), such as the disaggregation routing proxy.                                                                         |
| `model_servers[].live_pods`          | Running pods with node names and resolved container **image IDs** (digests), not just tags.                                                                                                         |
| `router`                             | The endpoint picker (EPP) name, replica counts, image, and args.                                                                                                                                    |
| Top-level legacy keys                | `scaling_state`, `resolved_runtime_env`, `resolved_container_args` — mirroring the primary model server, retained for backward compatibility.                                                       |

`serving_parameters` is the field to read when comparing runs. The values are
fully resolved, so a `--max-model-len=$(MAX_MODEL_LEN)` arg wired to a
`runtime.env` entry is recorded as the number the engine actually received.

The capture is roughly 10 KB and is meant to be read directly. The raw
Kubernetes manifests are **not** included by default because they trebled the
file size; pass `--include-raw` to embed the primary Deployment. The script
also prints a short summary to stdout, so the benchmark log records what was
captured:

```text
vllm-config: guide=pd-disaggregation namespace=llmd
  model=qwen/qwen3-32b platform=tpu accel=tpu-v6e-slice topology=2x4 count=8 (tpu-v6e-2x4)
  disaggregated=True servers=2 kv_connector=TPUConnector
  [decode] pd-disaggregation-tpu-vllm-decode-v6e-qwen3-32b 1/1 ready | kv_role=kv_both | image=docker.io/vllm/vllm-tpu:v0.27.0
      max_model_len=9216 tensor_parallel_size=8 dtype=bfloat16 load_format=runai_streamer
      env TPU_KV_TRANSFER_PORT=9100
      env TPU_SIDE_CHANNEL_PORT=9600
      + native-sidecar: routing-proxy (ghcr.io/llm-d/llm-d-router-disagg-sidecar:v0.10.0)
  [prefill] pd-disaggregation-tpu-vllm-prefill-v6e-qwen3-32b 1/1 ready | kv_role=kv_producer | image=docker.io/vllm/vllm-tpu:v0.27.0
      max_model_len=9216 tensor_parallel_size=8 dtype=bfloat16 load_format=runai_streamer
      env VLLM_HTTP_TIMEOUT_KEEP_ALIVE=120
  [router] pd-disaggregation-epp 1/1 ready
```

> [!IMPORTANT]
> For `pd-disaggregation` the capture contains two model servers, one per role.
> The prefill tier runs `kv_role: kv_producer` and the decode tier runs
> `kv_role: kv_both` with the routing proxy sidecar. If only one appears, the
> deployment is incomplete and the benchmark numbers are not meaningful.

> [!NOTE]
> Environment values sourced from a Secret or the downward API are recorded as
> opaque markers (for example `<secretKeyRef:llm-d-hf-token/HF_TOKEN>`), never
> as values. `vllm_config.json` is uploaded to GCS, so it must never contain a
> secret.

Accelerator facts are resolved from two sources, and
`model_servers[].accelerator.source` records which one was used:

1. **`node`** — labels on the node the pod actually landed on
   (`cloud.google.com/gke-tpu-accelerator`, `gke-tpu-topology`,
   `gke-accelerator`, `node.kubernetes.io/instance-type`).
2. **`computeclass`** — the `ComputeClass` named by the pod's
   `cloud.google.com/compute-class` nodeSelector. Its highest-priority rule
   declares the same `type`, `topology`, and `machineType` values that GKE
   later stamps onto the node.

The second source matters because every llm-d overlay selects hardware by
compute class rather than by a raw accelerator label, so the accelerator is
still identified correctly when a benchmark is captured before pods are
scheduled, or where reading Node objects is not permitted.

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

Monitor these metrics for GPU runs (_Note: In GKE Managed Prometheus, these are also exposed under `kubernetes.io/container/accelerator/*` time series such as `duty_cycle`, `memory_used`, `memory_total`, and `memory_bandwidth_utilization`_):

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
   - For `pd-disaggregation`:
     ```bash
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/teardown-llmd-pd-disaggregation.sh"
     ```
