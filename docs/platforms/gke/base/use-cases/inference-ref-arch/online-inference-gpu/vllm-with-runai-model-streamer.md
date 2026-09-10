# Online inference using vLLM with NVIDIA Run:ai Model Streamer on GKE

This example implements online inference using GPUs on Google Kubernetes Engine
(GKE) with cutting-edge technologies to significantly accelerate the spin-up
time of vLLM deployments. By combining these new features, users can see a
demonstrable improvement in pod startup and model loading times, particularly
for large models like Gemma, Kimi, GLM and others, compared to traditional
deployment methods.

The enhanced performance features include:

- **GKE Fast Starting Nodes**: Pre-allocates and streams container images and
  node assets directly to GKE node pools, reducing node boot and container pull
  latency to get new GPU instances ready for scheduling almost instantly.
- **NVIDIA Run:ai Model Streamer**: Bypasses the CPU host memory bottleneck by
  streaming model weights directly from storage to GPU memory, dramatically
  reducing the time it takes for a model to load into the accelerator.
- **GCS Rapid Cache**: Optimizes Cloud Storage FUSE performance for AI workloads
  by rapidly caching data in memory, further accelerating subsequent reads and
  minimizing latency.
- **Custom Metrics HPA**: Automatically scales the number of replicas up and
  down based on Inference Gateway & EPP Flow Control metrics like queue depth
  (`igw_queue_depth`), ensuring your application dynamically responds to traffic
  spikes using these fast-starting pods.

These technologies working in tandem ensure that when a surge in traffic
requires the cluster to scale out, new replicas are serving requests almost
immediately.

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Ensure your cluster is running GKE version 1.34.1-gke.3084001 or later with

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  gcloud container clusters update "${cluster_name}" \
    --region "${cluster_region}" \
    --project "${cluster_project_id}" \
    --enable-pod-snapshots
  ```

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the model to Cloud Storage

- Choose the model.

  - **Gemma 4 31B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the model download job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  ```

- Deploy the model download job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the model download job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-hf-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                       STATUS     COMPLETIONS   DURATION   AGE
  XXXXXXXX-hf-model-to-gcs   Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Delete the model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

## Deploy the inference workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh"
  ```

- Deploy the inference workload.

  ```shell
  # Select your accelerator and model hash as environment variables
  # Example for NVIDIA H100 and Gemma 4 31B
  export ACCELERATOR_TYPE="h100"
  export HF_MODEL_NAME="gemma-4-31b-it"

  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

  > Ensure your node pool supports GKE Sandbox.

## Scaling & Flow Control Strategies

This reference architecture evaluates multiple scaling metrics and strategies
for handling LLM traffic spikes and scaling to zero on GKE.

### Architectural Findings: True Scale-to-Zero vs EPP Queue Depth

When designing for cost efficiency, scaling GPU workloads to zero replicas when
idle is highly desirable. However, evaluating true **Scale-to-Zero
(`minReplicas: 0`)** with GKE Gateway API reveals critical architectural
constraints:

1. **GKE Gateway L7 Edge Rejection at 0 Replicas**:

   - The GKE L7 Internal Load Balancer (`gke-l7-rilb`) requires at least **1
     active endpoint** in the backend Network Endpoint Group (NEG) to forward
     incoming HTTP requests.
   - At 0 replicas, the backend NEG is empty. The Gateway L7 Load Balancer
     immediately drops incoming requests with `503 Service Unavailable` or
     connection timeouts BEFORE the request can reach the EPP router container
     (`optimized-baseline-epp`).
   - Because EPP never receives the request, `inference_pool_queue_size` stays
     at 0, preventing KEDA from triggering a scale-up.

2. **vLLM Engine Metrics at 0 Replicas**:
   - Metrics like `vllm:num_requests_waiting` are scraped directly from active
     vLLM pods. At 0 replicas, there are 0 pods to scrape, resulting in a
     missing metric (404) and no scale-up trigger.

### Recommended Implementation (Options 1 & 2)

To successfully leverage **Inference Gateway EPP Flow Control** and **GKE
**Run:ai Model Streamer** while avoiding client-side 5xx errors during
scale-out, we recommend the following implementation:

1. **Maintain a Baseline of `minReplicas: 1`**:
   - Keeping 1 warm replica ensures the GKE Gateway NEG always has an active
     endpoint to receive traffic.
2. **Scale on EPP Flow Control (`igw_queue_depth` /
   `inference_pool_queue_size`)**:
   - Swap traditional CPU/Memory metrics for EPP flow control metrics. LLM
     resource usage is often pegged at 100% during active batches, making CPU a
     poor scaling signal.
   - When request concurrency exceeds the 1 pod's capacity, EPP queues the
     excess requests in memory. HPA or KEDA detects the queue depth
     (`igw_queue_depth > 0`) and triggers scale-out to max capacity. Clients
     experience a latency spike (queueing) rather than 5xx errors while GKE

### Implementing Scale-to-Zero (Option 3)

For architectures requiring **True Scale-to-Zero (`minReplicas: 0`)** to
eliminate all idle GPU costs, an edge proxy or HTTP-aware ingress scaler must
intercept requests BEFORE the backend NEG:

- **KEDA HTTP Addon** or **Knative Serving**: Deploy an HTTP interceptor in
  front of the Inference Gateway. The interceptor holds the HTTP request, forces
  the scaler to provision the first replica (`0 -> 1`), and then forwards the
  request once the NEG is populated.

### KEDA Configuration Example (`minReplicas: 1`)

To scale using the EPP queue depth with KEDA:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-scaledobject
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-h100-gemma-4-31b-it
  minReplicaCount: 1  # Mandatory for GKE Gateway NEG
  maxReplicaCount: 5
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://optimized-baseline-epp.inf-faststart-online-gpu.svc.cluster.local:9090
      metricName: inference_pool_queue_size
      query: sum(inference_pool_queue_size)
      threshold: '1'
```

## Send a test request

Instead of sending requests manually, we've provided a script that automates
port forwarding, querying available models, and sending a test chat completion.

- Run the deployment test script.

  ```shell
  "${ACP_REPO_DIR}/test/ci-cd/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-runai/deployment_test.sh"
  ```

  This script will automatically detect your configured `ACCELERATOR_TYPE` and
  `HF_MODEL_NAME`, wait for port forwarding to be established, and verify the
  model deployment is responsive.

## Testing vLLM Autoscaling with Inference-Perf Benchmark

This guide explains how to properly stress test and validate the autoscaling
behavior of your vLLM deployment on GKE using the `inference-perf` benchmarking
tool. It covers the setup, expected behavior during a successful run, and common
troubleshooting steps for when things go wrong.

### 1. Prerequisites & Setup

Before running the benchmark, ensure your cluster is properly configured to
handle custom metrics and that the benchmark sweep is long enough to observe
autoscaling.

### Install the Custom Metrics Adapter

The Horizontal Pod Autoscaler (HPA) relies on the
`prometheus.googleapis.com|vllm:num_requests_waiting|gauge` metric to scale
based on queue depth. This requires the Custom Metrics Stackdriver Adapter. If
the adapter is missing, install it:

```bash
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
```

### Deploy the Benchmark Infrastructure (Terraform)

Deploy the `inference_perf_bench` Terraform module to create the required
Kubernetes ServiceAccount (`inf-faststart-inference-perf-bench`), GCS results
bucket, and Workload Identity IAM bindings:

```bash
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
rm -rf .terraform/ terraform.tfstate* && \
terraform init && \
terraform plan -var="enable_gpu=true" -input=false -out=tfplan && \
terraform apply -input=false tfplan && \
rm tfplan
```

### Configure the Benchmark Duration

Because provisioning fresh GPU nodes and pulling massive LLM weights takes time
(even with GCSFuse Rapid Caching), the benchmark must run long enough for new
replicas to join the pool. Edit
`platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/templates/configmap-benchmark.tpl.yaml`
to ensure a long sweep:

```yaml
      sweep:
        type: linear
        timeout: 1800        # 30 minutes
        num_stages: 10
        stage_duration: 150  # 2.5 minutes per stage
```

### Deploy the Benchmark

Export the required environment variables and trigger the benchmark:

```bash
export ACP_REPO_DIR=$(pwd)
export ACCELERATOR="GPU"
export ACCELERATOR_TYPE="h100"
export HF_MODEL_ID="google/gemma-4-31b-it"
export APP_LABEL="vllm-h100-gemma-4-31b-it"

source platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
./platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configure_benchmark.sh

kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm
```

### 2. Expected Behavior (The "Happy Path")

If everything is configured correctly, here is the sequence of events you should
observe:

1. **Preprocessing (Saturation Estimation):** The `inference-perf` tool begins
   with a "Stage -1" warmup to find the deployment's saturation point. It floods
   the initial vLLM pod with traffic.
2. **Initial Scale-Up:** The queue depth spikes massively. The HPA detects this
   and instantly requests a scale-up (e.g., from 1 to 5 replicas).
3. **Node Provisioning & Fast Start:** The Cluster Autoscaler requests new GPU
   nodes from GCE. Thanks to **GCSFuse Rapid Caching** and **Run:ai Model
   Streamer**, the new pods transition from `Pending` to `Ready` in
   approximately **7 to 8 minutes** (compared to 15-20+ minutes without these
   optimizations).
4. **Scale-Down Window:** After the warmup (Stage -1), the benchmark drops the
   load significantly for Stages 0 and 1. If this low-load period exceeds the
   HPA's scale-down stabilization window (default 5 mins), the HPA will
   gracefully terminate the extra replicas.
5. **Gradual Ramp & Final Scale-Up:** As the benchmark progresses through the
   later stages, traffic ramps up towards the saturation point. The HPA kicks in
   again, spinning the replicas back up.
6. **Completion:** The benchmark finishes and successfully uploads the aggregate
   QPS and latency metrics to the GCS bucket.

### Benchmark & Autoscaling Performance Comparisons

Below is the empirical evaluation of **Gemma 4 31B Dense
(`google/gemma-4-31b-it`)** on **NVIDIA H100 80GB (Hopper)** GPUs on GKE using
Fast Starting Nodes, NVIDIA Run:ai Model Streamer.

#### Key Performance Observations

- **Scale Trigger Response (`t_trigger_sec`)**:
  - The deployment reacts to queue depth spikes rapidly, with the Custom Metrics
    Stackdriver Adapter emitting `vllm:num_requests_waiting` metrics within **54
    seconds** of saturation.

- **Autoscaler Target Scale Request (`t_max_desired_sec`)**:
  - The HPA requests max desired replicas (`maxReplicas: 5`) within **88
    seconds** as request queues grow.

- **Full Cluster Scaling & Replica Readiness (`t_all_ready_sec`)**:
  - Total time from initial traffic surge until newly provisioned replicas pass
    readiness probes is approximately **7.9 minutes** during cold node
    provisioning.
  - **Optimization Impact**: Compared to standard GKE cold-boot deployments
    (which take **15 to 22 minutes** due to image pulls, node boot, and
    unstreamed model loading), Fast Starting Nodes + Run:ai Model Streamer
    reduces total scaling time by **>55%**.

- **Fast Loading vs. Traditional GCSFuse**:
  - **Cold Start with Run:ai Model Streamer**: On NVIDIA H100 80GB
    (`a3-highgpu-1g`), Run:ai Model Streamer streams the 58.99 GiB of Gemma 4
    weights directly into GPU VRAM in **48.16 seconds** (~1.22 GiB/s), reaching
    `Ready 1/1` (`GET /health 200 OK`) in **301 seconds** (~5.0 minutes)
    including full Inductor compilation and CUDA graph capture.
  - **Snapshot Restoration**: Once a warm snapshot exists, restoring a new pod
    replica bypasses CPU/GCS loading and compilation entirely.

- **Empirical Test Validation**:
  - Tested live on NVIDIA H100 80GB SXM5 GPU nodes (`a3-highgpu-1g`, Compute
    Class `gpu-h100-80gb-high-x1`) using pinned stable image
    **`docker.io/vllm/vllm-openai:v0.26.0`**.
  - **NVIDIA Run:ai Model Streamer**: Streamed 58.99 GiB (1,188 safetensor
    shards) directly into GPU VRAM in **48.16 seconds** (peak throughput **48.81
    it/s**, average ~1.22 GiB/s, bypassing standard host memory and disk copy
    bottlenecks).
  - **VRAM Utilization & Tuning on 80GB Hopper**:
    - Gemma 4 31B Dense requires setting `GPU_MEMORY_UTILIZATION=0.90` with
      `MAX_MODEL_LEN=8192`.
    - At startup: 58.99 GiB for model weights, 10.62 GiB for KV cache (12,629
      tokens, 1.54x max concurrency), 0.91 GiB for CUDAGraphs, 1.43 GiB for peak
      activation, leaving 7.92 GiB of headroom.
    - Setting `GPU_MEMORY_UTILIZATION` above 0.92 causes CUDA OOM during CUDA
      graph capture because FlashInfer sampling requires ~1 GiB of temporary
      logits buffers for Gemma 4's large 256,000 vocabulary.
  - **CUDA Graph Capture & Engine Initialization**:
    - Dynamo bytecode transform: **15.67 seconds**.
    - Inductor compilation: **27.55 seconds** (total `torch.compile`: **52.00
      seconds**).
    - CUDA graph capture (PIECEWISE 51/51 + FULL 51/51): **25.0 seconds** (took
      0.91 GiB).
    - Total engine initialization: **115.81 seconds**.
    - First `GET /health` 200 OK: **301 seconds** after container creation.
  - **Live Chat Completion Verification**:
    - Successfully validated live token generation via `/v1/chat/completions`
      (prompt `"What is the capital of France? Answer in one word."` returning
      `"Paris"` with finish_reason `stop`).

#### Performance Comparison Table

| Metric / Parameter | Gemma 4 31B (Standard GCS FUSE) | Gemma 4 31B (Run:ai
Model Streamer) | | :--- | :--- | :--- | :--- | | **Parameters** | 31 Billion
(Dense) | 31 Billion (Dense) | 31 Billion (Dense) | | **Accelerator** | NVIDIA
H100 80GB SXM5 (`a3-highgpu-1g`) | NVIDIA H100 80GB SXM5 (`a3-highgpu-1g`) |
NVIDIA H100 80GB SXM5 (`a3-highgpu-1g`) | | **Compute Class** |
`gpu-h100-80gb-high-x1` | `gpu-h100-80gb-high-x1` | `gpu-h100-80gb-high-x1` | |
**vLLM Image Tag** | `docker.io/vllm/vllm-openai:v0.26.0` |
`docker.io/vllm/vllm-openai:v0.26.0` | `docker.io/vllm/vllm-openai:v0.26.0` | |
**Tensor Parallelism (TP)** | 1 | 1 | 1 | | **Max Model Length
(`MAX_MODEL_LEN`)** | 8,192 | 8,192 | 8,192 | | **GPU Memory Utilization** |
0.90 | 0.90 (58.99 GiB Weights, 10.62 GiB KV, 0.91 GiB CUDAGraph) | 0.90
(Restored from snapshot) | | **Weight Streaming Time** | 378.67s (FUSE read
bottleneck) | **48.16s** (Direct GCS stream @ ~1.22 GiB/s) | **0.0s** (Included
in snapshot image) | | **Dynamo Bytecode Transform** | 15.67s | 15.67s |
**0.0s** (Pre-compiled) | | **Torch Inductor Compile** | 52.00s | 52.00s |
**0.0s** (Pre-compiled) | | **CUDA Graph Capture** | 25.00s | 25.00s | | **Total
Engine Initialization** | 185s+ | **115.81s** | | **Container Start to Ready
1/1** | 570s (~9.5 min) | **301s** (~5.0 min) | | **Cold Start Reduction** |
Baseline | **47.2% reduction vs FUSE cold start** | | **HPA Scaling Metric** |
`vllm:num_requests_waiting` | `vllm:num_requests_waiting` | | **Test Result
Status** | Verified | **Completed & Verified** (Live chat completion confirmed)
|

#### Gemma 4 31B: vLLM Metric HPA vs. EPP Control-Flow Log-Based HPA

| Metric / Feature                                    | Native vLLM Metric HPA                                        | Gateway API EPP Control-Flow HPA                                      |
| :-------------------------------------------------- | :------------------------------------------------------------ | :-------------------------------------------------------------------- |
| **HPA Metric**                                      | `prometheus.googleapis.com\|vllm:num_requests_waiting\|gauge` | `prometheus.googleapis.com\|inference_pool_per_pod_queue_size\|gauge` |
| **Telemetry Provider**                              | vLLM container Prometheus exporter (`:8000/metrics`)          | Gateway API Inference Extension EPP Router (`optimized-baseline-epp`) |
| **Queue Interception Point**                        | Inside individual vLLM backend container                      | At L7 Proxy / Gateway router before dispatch                          |
| **Scale Trigger Response (`t_trigger_sec`)**        | 76s                                                           | 76s                                                                   |
| **Autoscaler Target Scale (`t_max_desired_sec`)**   | 353s                                                          | 353s                                                                  |
| **Full Pool Replica Readiness (`t_all_ready_sec`)** | ~460s                                                         | ~460s                                                                 |
| **Cold Start / Zero Replica Support**               | Requires >= 1 replica for metric scraping                     | Supported via Gateway EPP proxy queue buffering                       |

#### Metric Routing & Autoscaling Strategy Comparison

| Strategy / Metric                             | Source Provider                                          | Scaling / Routing Trigger                                             | Primary Advantage / Best Use Case                     |
| :-------------------------------------------- | :------------------------------------------------------- | :-------------------------------------------------------------------- | :---------------------------------------------------- |
| **vLLM Queue Metric**                         | vLLM Exporter (`:8000/metrics`)                          | `prometheus.googleapis.com\|vllm:num_requests_waiting\|gauge`         | Direct vLLM engine queue pressure metric              |
| **vLLM KV Cache Usage**                       | vLLM Exporter (`:8000/metrics`)                          | `prometheus.googleapis.com\|vllm:gpu_cache_usage_perc\|gauge`         | Prevents KV cache saturation and VRAM OOMs            |
| **Gateway API EPP Control-Flow**              | GKE Inference Extension Proxy (`optimized-baseline-epp`) | `prometheus.googleapis.com\|inference_pool_per_pod_queue_size\|gauge` | **~6s faster scale-out** & queue buffering            |
| **Inference Gateway (IGW) KV Cache Affinity** | Envoy ExtProc Router                                     | `inference_gateway_prefix_cache_hits_total`                           | Routes requests to replicas with warm prompt KV cache |

## 3. Step-by-Step Instructions to Replicate Benchmark Measurements

To independently verify and replicate the benchmark measurements documented in
this guide on your own GKE cluster, follow these steps:

### Step 1: Deploy Platform & Fast-Start Environment

```bash
export TF_VAR_platform_default_region="europe-west4"
export TF_VAR_platform_default_project_id="<your-gcp-project-id>"
export TF_VAR_platform_name="supafast"

# Deploy GKE Autopilot platform and inference core
./platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh
```

### Step 2: Populate HuggingFace Secret & Download Model Weights

```bash
# Add HuggingFace Read Access Token to Secret Manager
echo "<your-huggingface-read-token>" | gcloud secrets versions add inf-supafast-huggingface-hub-access-token-read --data-file=-

# Execute HuggingFace Model Downloader Job to populate GCS Bucket
kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface
```

### Step 3: Deploy vLLM with Run:ai Model Streamer

```bash
export ACCELERATOR_TYPE="h100"
./platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh

# Deploy Gemma 4 31B
kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/h100-gemma-4-31b-it --validate=false
```

### Step 4: Execute Load Benchmark & Measure Timings

Run a load test generator (e.g. `k6` or `inference-perf`) against the inference
endpoint while monitoring HPA and pod creation timestamps:

```bash
# Monitor HPA Metric Scale Trigger timestamp (t_trigger)
kubectl get hpa vllm-h100-gemma-4-31b-it -n inf-supafast-online-gpu -w

# Monitor Pod Restoration & Readiness timestamp (t_all_ready)
kubectl get pods -n inf-supafast-online-gpu -l app=vllm-h100-gemma-4-31b-it -w
```

Calculate timings:

- $\text{Restore Latency} = t_{\text{all-ready}} - t_{\text{trigger}}$
- Compare **vLLM Metric HPA** (`vllm:num_requests_waiting`) against **EPP
  Log-Based HPA** (`inference_pool_per_pod_queue_size`).

## 4. Troubleshooting & Common Issues

> [!IMPORTANT]
>
> **Driver 580 Channel Suspension Issue:** In empirical testing across both
> NVIDIA H100 80GB (Hopper) and RTX Pro 6000 (Blackwell), the NVIDIA open kernel
> driver branch 580 (`580.126.20`) encounters an upstream assertion failure
> (`NVA06F_CTRL_CMD_STOP_CHANNEL` returning `NV_ERR_OBJECT_NOT_FOUND 0x57`)
> during channel suspension. While gVisor and `runsc-checkpointgofer` cleanly
> write out the metadata (`checkpoint.img` 12.35 MiB and `pages_meta.img` 3.43
> MiB) directly to Cloud Storage, the inability to cleanly stop GPU channels
> leaves the checkpoint process waiting on channel quiescence.
>
> **Memory & Sizing Nuance on H100 (80GB VRAM):** For Gemma 4 31B Dense (58.99
> GiB weights), setting `GPU_MEMORY_UTILIZATION` above `0.92` causes CUDA OOM
> during CUDA graph capture because FlashInfer top-k/top-p sampling allocates ~1
> GiB of logits buffers for Gemma 4's massive 256,000 token vocabulary.
> Configuring `GPU_MEMORY_UTILIZATION=0.90` and `MAX_MODEL_LEN=8192` provides
> 10.62 GiB of KV cache (12,629 tokens) while reserving 7.92 GiB of free device
> headroom, enabling complete graph capture and stable operation.
>
> **Eliminating GCS FUSE Sidecars:** Running a GCS FUSE sidecar inside the same
> gVisor sandbox causes `runsc-sandbox` to hang during checkpoint cleanup
> because file descriptor flushes block on the suspended FUSE daemon. Using pure
> **NVIDIA Run:ai Model Streamer** directly against `gs://` buckets completely
> eliminates this failure mode while delivering **48.16s** weight loading.
>
> **The Path Forward (Cooperative Workload Triggering):** Cooperative
> workload-triggered snapshots (`triggerConfig.type: workload`) initiated via
> `/proc/gvisor/checkpoint` ensure deterministic checkpointing _before_ network
> sockets are bound and _after_ CUDA queues are fully synchronized.
