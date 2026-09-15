# Enterprise Reference Architecture: Ultra-Low Latency, High-Throughput Online LLM Inference on Google Kubernetes Engine (GKE)

## Section 1: Executive Summary & Strategic Vision

As Large Language Model (LLM) parameter counts scale from tens to hundreds of
billions—and Mixture-of-Experts (MoE) architectures become standard across
enterprise AI workloads—the operational cost and scaling latency associated with
GPU-accelerated inference infrastructure have emerged as primary bottlenecks for
enterprise platform engineering teams.

Traditional Kubernetes GPU inference deployments exhibit extreme scale-out
latency, requiring **15 to 22 minutes** to bring a single new model replica
online. This latency stems from a sequence of blocking operations:

1. **GCP Compute Provisioning**: Spinning up compute nodes with attached
   high-performance accelerators (e.g., NVIDIA H100 GPUs).
2. **Container Image Pulling**: Downloading heavy vLLM or PyTorch container
   images (often 15GB–35GB) across external registry networks.
3. **Model Weight Fetching**: Transferring multi-gigabyte safetensor model
   weights (e.g., ~59GB for `google/gemma-4-31b-it`) from object storage into
   host storage.
4. **Engine Graph Compilation & Memory Warmup**: Executing heavy vLLM engine
   initialization routines, including PyTorch CUDA graph compilation, Triton
   kernel autotuning, and KV Cache memory pool allocation.

During sudden traffic surges or bursty enterprise workloads, a 20-minute scaling
delay leads to request timeouts, high Tail-Time-to-First-Token (TTFT)
degradation, SLA breaches, and poor user experience.

### The Fast-Start Architecture Solution

This Reference Architecture presents a production-grade, enterprise-ready
pattern for **ultra-low latency online LLM inference on Google Kubernetes Engine
(GKE)**. By combining Google Cloud infrastructure capabilities and accelerated
software components, this architecture reduces replica scale-out from minutes to
**single-digit seconds**. Measured restores from a warm PodSnapshot, taken from
pod conditions between `PodScheduled` and `Ready`, were **3 seconds** on NVIDIA
H100 80GB, **4 seconds** on NVIDIA RTX Pro 6000 96GB, and **9 seconds** on
NVIDIA L4 — against cold starts of 163 to 265 seconds for the same deployments,
a reduction of more than **98%**.

> [!NOTE]
>
> These figures are reproduced end to end in the companion technical guide,
> [Online inference using vLLM with NVIDIA Run:ai Model Streamer and PodSnapshots on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-and-podsnapshots.md),
> which is the authoritative source for every measurement in this document.
> Where the two disagree, the technical guide wins.

```
+-------------------------------------------------------------------------------------------------------------------------+
|                                                  ENTERPRISE INGRESS TIER                                               |
|  [ Client Requests ] ---> [ GKE Gateway API / L7 Load Balancer ] ---> [ Endpoint Picker (EPP) Router / Metric Collector ]  |
+-------------------------------------------------------------------------------------------------------------------------+
                                                                |
                                             +------------------+------------------+
                                             |                                     |
                                 (Scale-Out Signal: EPP Queue)           (Optimized Traffic Dispatch)
                                             |                                     |
                                             v                                     v
+-------------------------------------------------------------------------------------------------------------------------+
|                                                  GKE AUTOPILOT COMPUTE TIER                                             |
|  +-------------------------------------------------------------------------------------------------------------------+  |
|  | Pod Replica 1 (Warm Snapshot Restored) | Pod Replica 2 (Warm Snapshot Restored) | ... | Pod Replica N (Warm Restored) |  |
|  | +---------------------------------------------------------------------------------------------------------------+ |  |
|  | | vLLM Engine v0.26.0 (google/gemma-4-31b-it)                                                                   | |  |
|  | | [ NVIDIA H100 80GB GPU ] <--- Zero-Copy Tensor Stream (NVIDIA Run:ai Model Streamer)                          | |  |
|  | +---------------------------------------------------------------------------------------------------------------+ |  |
|  +-------------------------------------------------------------------------------------------------------------------+  |
+-------------------------------------------------------------------------------------------------------------------------+
                                                                ^
                                                                | (High-Speed Direct Streaming)
+-------------------------------------------------------------------------------------------------------------------------+
|                                                  STORAGE & ACCELERATION TIER                                            |
|  [ Cloud Storage Bucket: gs://...-hf-hub-models/ ] <--- Workload Identity IAM <--- Secret Manager CSI Driver             |
+-------------------------------------------------------------------------------------------------------------------------+
```

### Core Architectural Pillars

1. **GKE Autopilot & Fast Starting Nodes**: Pre-provisioned warm OS images and
   image streaming reduce node startup times from minutes to seconds.
2. **GKE Inference Gateway & Endpoint Picker (EPP)**: Intelligent L7 routing
   with predicted latency-based dispatch, prefix cache affinity, and
   control-flow queue metrics.
3. **NVIDIA Run:ai Model Streamer**: Direct GCS-to-GPU VRAM safetensor streaming
   that bypasses host disk bottlenecks and page cache overheads.
4. **GCS Rapid Cache & Cloud Storage**: High-throughput object storage tier
   protected by GKE Workload Identity Federation and Google Cloud Secret
   Manager.
5. **GKE PodSnapshots**: Memory state snapshotting that restores initialized
   PyTorch/vLLM process states in **single-digit seconds**, contingent on an
   NVIDIA driver of 570 or newer selected through a Custom Compute Class.
6. **Dual-Tier Horizontal Pod Autoscaling (HPA)**: Dual metric monitoring
   combining ingress EPP flow control metrics (`igw_queue_depth` /
   `inference_pool_per_pod_queue_size` for scale-out signals and
   `igw_running_requests` for capacity) with internal engine metrics
   (`vllm:num_requests_waiting`), avoiding static CPU/Memory saturation metrics.

---

## Section 2: High-Level System Architecture & Component Interactions

The reference architecture is divided into four distinct operational planes:

```
                                  [ Client API / Load Generator ]
                                                 |
                                                 v
  +---------------------------------------------------------------------------------------------+
  | INGRESS PLANE                                                                               |
  |                                                                                             |
  |   +-------------------------------------------------------------------------------------+   |
  |   | GKE Gateway API Controller (Envoy Proxy)                                            |   |
  |   +-------------------------------------------------------------------------------------+   |
  |                                              |                                              |
  |                                              v                                              |
  |   +-------------------------------------------------------------------------------------+   |
  |   | GKE Inference Gateway Extension: Endpoint Picker (EPP)                              |   |
  |   |  - Metrics: inference_pool_per_pod_queue_size                                       |   |
  |   |  - Algorithms: Predicted Latency-Based Routing & Prefix Cache Hit Affinity           |   |
  |   +-------------------------------------------------------------------------------------+   |
  +---------------------------------------------------------------------------------------------+
                                                 |
                         +-----------------------+-----------------------+
                         |                                               |
                         v                                               v
  +-------------------------------------------------------+   +---------------------------------+
  | COMPUTE PLANE (GKE Autopilot)                         |   | AUTOSCALING CONTROL PLANE       |
  |                                                       |   |                                 |
  |  +-------------------------------------------------+  |   |  +---------------------------+  |
  |  | Inference Pod Replica Pool                      |  |   |  | Custom Metrics Adapter    |  |
  |  |  +-------------------------------------------+  |  |   |  +---------------------------+  |
  |  |  | Container: vLLM OpenAI Engine (v0.26.0)     |  |  |   |                |                |
  |  |  |  - Load Format: runai_streamer            |  |  |   |                v                |
  |  |  |  - Port: 8000 (/v1/chat/completions)      |  |  |   |  +---------------------------+  |
  |  |  +-------------------------------------------+  |  |   |  | HorizontalPodAutoscaler   |  |
  |  |  | Accelerator: NVIDIA H100 (80GB)           |  |  |   |  |  (Target Queue: 6 reqs)   |  |
  |  |  +-------------------------------------------+  |  |   |  +---------------------------+  |
  |  |  | Hydration: GKE PodSnapshots Memory Restore|  |  |   +---------------------------------+
  |  |  +-------------------------------------------+  |
  |  +-------------------------------------------------+  |
  +-------------------------------------------------------+
                         ^
                         | (Zero-Copy gRPC Tensor Stream)
  +---------------------------------------------------------------------------------------------+
  | STORAGE & SECURITY ACCELERATION PLANE                                                       |
  |                                                                                             |
  |   +-----------------------------------+     +-------------------------------------------+   |
  |   | Google Cloud Storage Bucket       |     | Workload Identity Pool / IAM              |   |
  |   |  - gs://...-hf-hub-models/        | <---|  - sa: inf-supafast-online-gpu            |   |
  |   |  - Model: google/gemma-4-31b-it   |     |  - Role: roles/storage.objectUser          |   |
  |   +-----------------------------------+     +-------------------------------------------+   |
  |                     ^                                             ^                         |
  |                     |                                             |                         |
  |   +-------------------------------------------------------------------------------------+   |
  |   | Secret Manager CSI Driver (secrets-store-gke.csi.k8s.io)                            |   |
  |   |  - Secret: inf-supafast-huggingface-hub-access-token-read                           |   |
  |   +-------------------------------------------------------------------------------------+   |
  +---------------------------------------------------------------------------------------------+
```

### End-to-End Lifecycle Sequence

```
[ Model Registry ]      [ GCS Storage ]      [ GKE Cluster ]      [ EPP Ingress ]      [ HPA Controller ]      [ vLLM Pod ]
        |                      |                    |                    |                    |                     |
        |--- 1. Download ----->|                    |                    |                    |                     |
        |   Model Tensors      |                    |                    |                    |                     |
        |                      |<--- 2. Stream Tensors (Run:ai Streamer) ----------------------------------------|
        |                      |                    |                    |                    |                     |
        |                      |                    |                    |                    |--- 3. Warm Engine---|
        |                      |                    |                    |                    |    CUDA Compilation |
        |                      |                    |                    |                    |                     |
        |                      |                    |<--- 4. Capture PodSnapshot State ------------------------------|
        |                      |                    |                    |                    |                     |
        |                      |                    |<--- 5. Traffic Surge                     |
        |                      |                    |    Queue Spikes   |                     |
        |                      |                    |                    |                    |                     |
        |                      |                    |                    |--- 6. Metric Emit ->|                     |
        |                      |                    |                    |    queue_size=15   |                     |
        |                      |                    |                    |                    |--- 7. Scale Req --->|
        |                      |                    |                    |    (New Replicas)    |                     |
        |                      |                    |                    |                    |                     |
        |                      |                    |<--- 8. Hydrate PodSnapshot (45s) --------------------------------|
        |                      |                    |                    |                    |                     |
        |                      |                    |                    |<--- 9. Ready NEG -------------------------|
```

---

## Section 3: GKE Compute Tier & Fast Starting Node Infrastructure

### 1. Architectural Overview of GKE Fast Starting Nodes

[GKE Fast Starting Nodes](https://cloud.google.com/kubernetes-engine/docs/concepts/types-of-node-pools)
eliminate the primary delays inherent in node auto-provisioning. On standard
Kubernetes clusters, when an autoscaler requests new GPU capacity, the cluster
experiences several cumulative delays:

1. **Compute Engine VM Boot Delay**: Requesting a GPU instance type (e.g.,
   `a3-highgpu-1g` with NVIDIA H100 80GB) requires host initialization, OS boot,
   and network interface binding (30–90 seconds).
2. **GPU Driver & Container Runtime Initialization**: Loading NVIDIA kernel
   modules, initializing `nvidia-container-runtime`, and mounting CUDA driver
   libraries (30–60 seconds).
3. **Container Image Download**: Pulling multi-gigabyte container images over
   external registry connections (2–5 minutes).

GKE Autopilot Fast Starting Nodes address these delays through three mechanisms:

- **Pre-provisioned Warm OS Disk Images**: GKE maintains pre-baked node OS
  images containing pre-loaded NVIDIA GPU drivers, CUDA runtime components, and
  container storage layers.
- **Container Image Streaming (Starlight)**: GKE streams container image layers
  on demand from Artifact Registry. Instead of waiting for a 20GB vLLM image to
  download completely, the container starts executing as soon as the entrypoint
  binaries are fetched, downloading remaining layers lazily in the background.
- **Optimized Scheduling & Node Auto-Provisioning (NAP)**: GKE Autopilot
  automatically provisions node capacity matching workload tolerations and
  resource requests (`nvidia.com/gpu: 1`), removing manual node pool
  configuration overhead.

### 2. Deep Dive: GKE Autopilot vs. Standard Cluster Trade-Offs

When designing enterprise inference platforms, platform architects must evaluate
the operational trade-offs between GKE Autopilot and GKE Standard clusters:

| Architectural Feature           | GKE Autopilot Mode (Recommended)                                                                 | GKE Standard Mode                                                                                       |
| :------------------------------ | :----------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------ |
| **Node Management Overhead**    | **Zero OS/Node Management**: Google manages OS patching, driver updates, and security hardening. | **Customer Managed**: Platform team manages OS images, node pools, daemonsets, and GPU driver upgrades. |
| **GPU Isolation & Bin Packing** | **Pod-Level Billing**: Billed strictly for pod requested resources (CPU, Memory, GPU).           | **Node-Level Billing**: Billed for full underlying VM instances regardless of utilization.              |
| **Autoscaling Mechanics**       | Integrated Node Auto-Provisioning (NAP) automatically sizes node shapes to pod requests.         | Requires configuring explicit Cluster Autoscaler (CA) node pool limits and scale-down rules.            |
| **Driver Uniformity**           | Managed GPU driver channels guarantee driver-CUDA runtime compatibility.                         | Platform engineers must manually align host kernel headers, CUDA drivers, and fabric managers.          |

### 3. Node Configuration & Resource Scheduling Specification

For optimal high-throughput LLM serving on NVIDIA H100 80GB (Hopper)
accelerators, the GKE Autopilot workload manifest specifies explicit resource
allocations and compute class constraints:

```yaml
spec:
  nodeSelector:
    cloud.google.com/compute-class: "gpu-h100-80gb-high-x1"
  tolerations:
    - key: "nvidia.com/gpu"
      operator: "Exists"
      effect: "NoSchedule"
  containers:
    - name: inference-server
      image: docker.io/vllm/vllm-openai:v0.26.0
      resources:
        limits:
          cpu: "24"
          memory: "96Gi"
          nvidia.com/gpu: "1"
        requests:
          cpu: "24"
          memory: "96Gi"
          nvidia.com/gpu: "1"
```

---

## Section 4: Advanced Ingress & Traffic Management with GKE Inference Gateway

### 1. Overview of GKE Inference Gateway

The
[GKE Inference Gateway](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/about-gke-inference-gateway)
is a native infrastructure component designed to address the traffic routing
challenges of Large Language Model workloads. Traditional L7 HTTP load balancers
treat LLM endpoints like standard REST services, distributing requests via
round-robin or least-connections algorithms. However, LLM inference workloads
exhibit unique traffic characteristics:

- **Variable Request Execution Time**: A prompt requiring a 1,000-token
  completion takes significantly longer to execute than a 10-token response.
- **KV Cache Statefulness**: Requests sharing identical system prompts or
  context documents achieve dramatically lower latency if routed to a replica
  that already holds those prompt tokens in its GPU Key-Value (KV) Cache.
- **Severe Tail Latency Under Saturation**: Distributing new incoming requests
  to a backend replica with a full execution queue causes exponential latency
  spikes.

The GKE Inference Gateway extends the Kubernetes Gateway API by deploying
specialized Envoy-based proxy extensions and control-plane controllers that
understand LLM protocol semantics and real-time backend engine health.

```
                                [ Incoming Client Request ]
                                             |
                                             v
                      +----------------------------------------------+
                      | GKE Inference Gateway (Envoy L7 Proxy)       |
                      +----------------------------------------------+
                                             |
                   +-------------------------+-------------------------+
                   |                                                   |
                   v                                                   v
+----------------------------------------------------+   +----------------------------------------------------+
| ExtProc Filter: Prefix Cache Inspection            |   | ExtProc Filter: Real-Time Queue Metric Fetching    |
|  - Compares prompt token hash against replica KV   |   |  - Reads active KV cache & queue depth from EPP    |
+----------------------------------------------------+   +----------------------------------------------------+
                   |                                                   |
                   +-------------------------+-------------------------+
                                             |
                                             v
                      +----------------------------------------------+
                      | Optimal Backend Replica Selection             |
                      |  - Maximize Prefix Cache Hit Ratio           |
                      |  - Minimize Predicted Execution Latency      |
                      +----------------------------------------------+
                                             |
                     +-----------------------+-----------------------+
                     |                                               |
                     v                                               v
    [ vLLM Pod Replica 1 (Warm Cache) ]             [ vLLM Pod Replica 2 (Low Queue) ]
```

### 2. Gateway API CRDs for Inference Pools

The GKE Inference Gateway introduces specialized Custom Resource Definitions
(CRDs) that extend standard Gateway API resources (`Gateway`, `HTTPRoute`) to
represent LLM serving pools:

- **`InferencePool`**: Defines a logical collection of homogenous model server
  replicas (e.g., vLLM pods), specifying endpoint selector labels, health
  probing contracts, and load-balancing algorithms.
- **`InferenceModel`**: Declares model routing metadata, linking served model
  names (e.g., `google/gemma-4-31B-it`) to underlying `InferencePool` instances.

```yaml
apiVersion: inference.networking.x-k8s.io/v1alpha1
kind: InferencePool
metadata:
  name: vllm-gemma-4-pool
  namespace: inf-supafast-online-gpu
spec:
  selector:
    app: vllm-h100-gemma-4-31b-it
  targetPortNumber: 8000
  endpointPickerConfig:
    type: LatencyBased
    latencyBasedConfig:
      maxQueueDepthPerPod: 16
```

### 3. Prefix Cache Affinity and KV Cache Reuse

When serving models like `google/gemma-4-31b-it`, prompt processing (prefill
phase) accounts for a large portion of overall latency. Modern engines use
automatic prefix caching to store computed KV projections in VRAM.

The GKE Inference Gateway inspects incoming request payloads, computes a
cryptographic hash of prompt prefixes (e.g., system prompts, RAG context
documents, or conversation histories), and maintains a dynamic routing table
mapping prefix hashes to specific backend pod IPs.

#### Key Architectural Benefits

- **Prefill Latency Reduction**: Bypasses repeat prompt token computation,
  reducing Time-To-First-Token (TTFT) by up to **80%** for cached contexts.
- **VRAM Footprint Optimization**: Reduces duplicate KV Cache allocations across
  GPU replicas, freeing VRAM for higher batch sizes and concurrent request
  limits.

---

## Section 5: Intelligent Routing & Predicted Latency-Based Endpoint Picker (EPP)

### 1. Endpoint Picker (EPP) Architecture

The Endpoint Picker (EPP) is a specialized sidecar container deployed alongside
the GKE Inference Gateway proxy. It operates as an External Processing (ExtProc)
gRPC filter that sits directly in the data path of incoming client requests.

Rather than relying on passive HTTP health checks or delayed cluster metrics,
the EPP maintains active, low-latency control channels with every vLLM pod
replica in the serving pool.

```
+---------------------------------------------------------------------------------------------------+
| GKE INFERENCE GATEWAY INGRESS POD                                                                 |
|                                                                                                   |
|  +---------------------------+    gRPC ExtProc    +--------------------------------------------+  |
|  | Envoy Proxy Container     | <----------------> | Endpoint Picker (EPP) Sidecar Container    |  |
|  | (Data Path Forwarding)    |                    |  - Live Replica Status Tracker             |  |
|  |                           |                    |  - Queue Size Metric Aggregator            |  |
|  |                           |                    |  - Latency Predictor Engine                |  |
|  +---------------------------+                    +--------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                                   |
                                    +------------------------------+------------------------------+
                                    | Live Status Polling                                         | Live Status Polling
                                    v                                                             v
            +-----------------------------------------------+             +-----------------------------------------------+
            | vLLM Backend Pod 1                            |             | vLLM Backend Pod 2                            |
            |  - Active Requests: 3                         |             |  - Active Requests: 12                        |
            |  - Available KV Cache: 68%                    |             |  - Available KV Cache: 14%                    |
            +-----------------------------------------------+             +-----------------------------------------------+
```

### 2. Mathematical Model of Predicted Latency-Based Routing

As documented in
[GKE Predicted Latency-Based Routing](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/use-predicted-latency-based-routing),
the EPP calculates a real-time predicted latency score for every backend replica
before dispatching a request.

The prediction model calculates expected latency using the following formula:

$$\text{Predicted Latency} = (N_{\text{prompt}} \times \alpha_{\text{prefill}}) + (Q_{\text{active}} \times N_{\text{avg-gen}} \times \beta_{\text{decode}}) + \gamma_{\text{cache-miss}}$$

Where:

- $N_{\text{prompt}}$ is the count of tokens in the incoming request prompt.
- $\alpha_{\text{prefill}}$ is the empirically calibrated prefill processing
  time per token for the specific accelerator (e.g., NVIDIA H100 80GB).
- $Q_{\text{active}}$ is the count of requests currently queued or executing on
  the candidate backend pod.
- $N_{\text{avg-gen}}$ is the moving average of generated output tokens per
  request.
- $\beta_{\text{decode}}$ is the time per output token (TPOT) during the decode
  phase.
- $\gamma_{\text{cache-miss}}$ is an additional latency penalty added if the
  candidate pod does not currently hold the prompt prefix in its KV Cache.

By continuously routing requests to the pod with the lowest predicted latency
score, EPP prevents individual GPU worker saturation, smooths out tail latency
(p99 TTFT), and maximizes overall throughput across the cluster.

---

## Section 6: Zero-Copy Model Streaming Tier (NVIDIA Run:ai Streamer + GCS Rapid Cache)

### 1. The Host Disk Bottleneck in Standard LLM Loading

In conventional Kubernetes LLM deployments, model weight loading follows a
multi-hop disk transfer path:

```
Traditional Loading Path:
[ GCS Bucket ] -> Network -> [ Host OS File System (NVMe/PD) ] -> [ Linux Page Cache ] -> CPU RAM -> PCIe -> [ GPU VRAM ]
```

This traditional path produces severe bottlenecks:

- **I/O Serialization**: Storage drivers serialize tensor chunk reads across the
  host filesystem.
- **Double Memory Allocation**: Model weights are allocated twice—first in CPU
  system RAM, then copied across the PCIe bus into GPU VRAM.
- **Host Disk Exhaustion**: Nodes require massive local ephemeral storage disks
  (100GB–500GB) simply to stage model files before loading.

### 2. NVIDIA Run:ai Model Streamer Integration

NVIDIA Run:ai Model Streamer transforms weight loading into a single-pass
streaming operation:

```
Zero-Copy Streamer Path:
[ GCS Bucket (gs://...-hf-hub-models/) ] === High-Speed gRPC Direct Stream ===> [ GPU VRAM (NVIDIA H100 80GB) ]
```

By configuring vLLM runtime environment variables to enable the streamer:

```bash
MODEL_ID="google/gemma-4-31b-it"
VLLM_LOAD_FORMAT="runai_streamer"
```

The vLLM engine initializes an internal gRPC client that opens concurrent TCP
streaming channels directly to Google Cloud Storage object endpoints.

#### Empirical Benchmarking Metrics

During empirical deployment tests of **Gemma 4 31B** (58.99 GiB safetensors
footprint) on NVIDIA H100 80GB, NVIDIA Run:ai Model Streamer demonstrated the
following loading performance:

```text
(APIServer pid=1) INFO: model gs://accelerated-platforms-dev-inf-supafast-hf-hub-models/google/gemma-4-31b-it
(EngineCore pid=213) INFO: Resolved architecture: Gemma4ForConditionalGeneration
(EngineCore pid=213) Loading safetensors using Runai Model Streamer:   0% Completed | 0/1188 [00:00]
(EngineCore pid=213) Loading safetensors using Runai Model Streamer:  24% Completed | 280/1188 [00:10, 27.50it/s]
(EngineCore pid=213) Loading safetensors using Runai Model Streamer: 100% Completed | 1188/1188 [00:48, 48.81it/s]
```

- **Sustained Streaming Rate**: **27.5 to 48.81 iterations per second** (~1.22
  GiB/s streaming throughput).
- **Total Loading Duration**: **48.16 seconds** to stream 58.99 GiB of tensor
  weights directly into GPU VRAM.
- **Local Ephemeral Disk Required**: **0 Bytes** (eliminates local PVC disk
  requirements entirely).

---

## Section 7: Instant State Restoration Tier with GKE PodSnapshots

### 1. Mechanics of GKE PodSnapshots

While NVIDIA Run:ai Model Streamer optimizes model weight loading, engine
initialization remains a major bottleneck. When vLLM boots, it executes several
initialization steps:

1. **Tokenizer & Config Resolution**: Loading vocabulary files, chat templates,
   and structural configs.
2. **PyTorch CUDA Graph Capture**: Pre-allocating CUDA memory pools and
   capturing execution graphs for hundreds of batch size and sequence length
   combinations.
3. **Triton Kernel Autotuning**: JIT-compiling optimized GEMM and attention
   kernels for specific GPU hardware.
4. **KV Cache Allocation**: Pre-allocating 80%–90% of remaining GPU VRAM for KV
   Cache blocks.

Together, these steps require **3 to 5 minutes** of continuous CPU and GPU
execution _after_ weight loading completes.

**GKE PodSnapshots** bypasses engine initialization entirely by capturing a
point-in-time snapshot of the running container process memory and GPU state
after initialization finishes.

```
PodSnapshot Generation Phase (Executed Once):
[ Boot Pod ] -> [ Stream Weights ] -> [ Init Engine & CUDA Graphs ] -> [ Freeze Process & Upload Snapshot ]

PodSnapshot Restoration Phase (Executed on Every Scale-Out Event):
[ Provision Node ] -> [ Mount Snapshot Volume ] -> [ Hydrate Memory State ] -> [ Resume Execution (Ready) ]
```

### 2. Quantitative Performance Acceleration

Measured cold start versus warm restore. **Cold start** is the time for the run
that produced the snapshot to go from container start to serving. **Warm
restore** is `PodScheduled` to `Ready`, taken from pod conditions, for a replica
hydrated from that snapshot.

| Model, GPU                            | Loader                | Cold start | Warm restore | Reduction |
| :------------------------------------ | :-------------------- | :--------- | :----------- | :-------- |
| Llama 3.1 8B, NVIDIA L4               | Eager safetensors     | —          | **9 s**      | —         |
| Llama 3.1 8B, NVIDIA H100 80GB        | Eager safetensors     | 163 s      | **3 s**      | **98.2%** |
| Llama 3.1 8B, NVIDIA H100 80GB        | Run:ai Model Streamer | —          | **3 s**      | —         |
| Gemma 4 31B, NVIDIA H100 80GB         | Run:ai Model Streamer | 265 s      | **5 s**      | **98.1%** |
| Gemma 4 31B, NVIDIA RTX Pro 6000 96GB | Run:ai Model Streamer | 224 s      | **4 s**      | **98.2%** |

The two techniques compose because they attack different costs. The Run:ai Model
Streamer makes the **one** cold start that has to happen fast — 3.4x faster
weight loading in a controlled single-variable comparison on Llama 3.1 8B, and
48.16 s for Gemma 4 31B's 58.99 GiB. PodSnapshots make **every subsequent**
scale-out fast. A production deployment wants both.

> [!IMPORTANT]
>
> Capturing the snapshot is not free. Uploading the memory image runs at roughly
> **83 MB/s** in practice, so Gemma 4 31B's ~73 GB `pages.img` takes **11 to 15
> minutes** from trigger to `AllSnapshotsAvailable`. A large model is slow to
> checkpoint, not incapable of it. Budget for it, and do not mistake a long
> upload for a hang.

### 3. Cooperative Workload-Triggered State Snapshots vs. Asynchronous Triggering

GKE PodSnapshots support multiple trigger mechanisms via `PodSnapshotPolicy`:
`workload`, `readinessProbe`, and `manual`. In high-throughput LLM serving
environments, **cooperative workload-triggered snapshots** are the recommended
pattern — but for narrower reasons than previously documented here.

#### Correction: out-of-band triggering is not a root cause of deadlock

> [!WARNING]
>
> An earlier revision of this document asserted that `manual` and
> `readinessProbe` triggers deadlock the sandbox by freezing a live server with
> active sockets and inflight CUDA streams. **That claim was tested directly and
> did not hold.**

The successful Gemma 4 31B manifest was re-run with exactly two lines changed:

```diff
 triggerConfig:
-  type: workload
-  postCheckpoint: resume
+  type: manual
+  postCheckpoint: stop
```

The checkpoint was then driven out-of-band by a `PodSnapshotManualTrigger`, with
the container's cooperative path reduced to a probe that never writes to
`/proc/gvisor/checkpoint`. It **succeeded**: a 72,936,628,224-byte `pages.img`
in 13 m 58 s, against 72,922,370,048 bytes in 11 m 22 s for the cooperative run.
A subsequent run that reapplied _every_ difference from the original failing
configuration at once — the `manual` trigger, `postCheckpoint: stop`, the
`v0.26.0` image, `strategy: Recreate`, and the
`podsnapshot.gke.io/restore-from-policy` annotation — also succeeded, and its
snapshot restored in 4 seconds.

The original hang was environmental and did not reproduce. See "What these runs
settle" in the technical guide for the full elimination table.

#### Why cooperative triggering is still recommended

The advantages are real, they are just about determinism and hygiene rather than
avoiding a deadlock:

- **The snapshot is taken at a known point.** The workload triggers after weight
  loading and CUDA graph capture complete, so the captured state is always the
  fully warmed engine. An external trigger races engine initialization.
- **The snapshot is taken before the server binds a port.** Nothing that depends
  on the pod's IP has been established yet, which avoids the class of restore
  artifacts described under `VLLM_HOST_IP` below.
- **`postCheckpoint: resume` keeps the pod serving.** With `manual` and
  `postCheckpoint: stop`, the container is stopped after capture and has to be
  restarted by the ReplicaSet, which wastes a warm GPU.

#### Cooperative In-Band Checkpointing Pattern

The cooperative workload trigger approach
([`gke-pod-snapshots-tools`](https://github.com/CoderSherlock/gke-pod-snapshots-tools))
delivers those properties by triggering the checkpoint **in-band** at an exact
lifecycle transition:

- **Pre-Network Isolation**: The snapshot is taken inside the vLLM entrypoint
  _after_ weight streaming and PyTorch CUDA graph capture complete, but _before_
  Uvicorn binds port 8000.
- **CUDA Quiescence**: Calling `torch.cuda.synchronize()` flushes all GPU queues
  so zero stream events are inflight during the freeze.
- **Deterministic Checkpoint Trigger**: The workload opens
  `/proc/gvisor/checkpoint`, writes `b"1"`, and blocks on `f.read()`.
- **Clean Replica Hydration**: When restored on a new node, the process resumes
  from `f.read()`, re-seeds PRNGs (`random.seed()`, `torch.manual_seed()`), and
  binds `0.0.0.0:8000` fresh. Every restored replica starts with a clean,
  unpolluted network stack.

```python
# vLLM lifecycle hook for cooperative workload checkpointing
import os
import random
import torch
from gke_pod_snapshots_tools import checkpoint

# 1. Complete weight loading and CUDA graph capture
# 2. Quiesce all CUDA streams before snapshot
if torch.cuda.is_available():
  torch.cuda.synchronize()

# 3. Cooperatively trigger PodSnapshot via /proc/gvisor/checkpoint
if os.path.exists("/proc/gvisor/checkpoint"):
  checkpoint()  # Blocks until restored replica starts

# 4. On restore: re-seed PRNGs and cleanly launch HTTP server
random.seed()
torch.manual_seed(random.randint(0, 2**32 - 1))
```

### 4. Mandatory Preconditions

Three conditions gate GPU PodSnapshots. All three were identified empirically,
and each one silently produces a different failure when unmet.

1. **An NVIDIA driver of 570 or newer, selected through a Custom Compute
   Class.** This is the most dangerous of the three because it fails quietly.
   The GKE installer script enforces `MINIMUM_NVIDIA_DRIVER_VERSION=570`; below
   that it skips installing `gvisor-cuda-cr` **and still exits 0**. Selecting
   nodes with the `cloud.google.com/gke-accelerator` label gets the default 535
   driver and therefore no checkpoint support at all, with no error to indicate
   it. A compute class such as `gpu-h100-80gb-high-x1` or
   `gpu-rtx-pro-6000-96gb-x1` pins `driverVersion: latest` on every priority.
   Verify by confirming `/proc/gvisor/checkpoint` exists inside the container.

2. **Weights fully resident in VRAM, with no redundant copy on local disk.**
   Anything genuinely dirty on disk is serialized into the snapshot and re-read
   on every restore. Either use `--load-format=runai_streamer`, which never
   writes a full local copy, or use `--safetensors-load-strategy=eager` and
   delete the Hugging Face cache immediately before triggering.

3. **`VLLM_HOST_IP=127.0.0.1`.** PyTorch's TCPStore and the NCCL bootstrap bake
   their rendezvous address into the checkpointed process image, and a restored
   replica always comes up with a different pod IP. Omitting this produced a
   continuous stream of `sendBytes failed on SocketImpl(...): Broken pipe` and
   `Failed to check the "should dump" flag on TCPStore` on a restored replica.
   Inference remained correct on a single GPU, so treat it as log hygiene at
   TP=1 — but it becomes load-bearing as tensor parallelism grows.

> [!CAUTION]
>
> Restore matches on the `podsnapshot.gke.io/pod-template-hash` label. **Any**
> edit to the pod template — a resource request, an environment variable, a flag
> — invalidates the existing snapshot and silently orphans it. Tune first,
> snapshot second.

### 5. Multi-GPU and tensor parallelism: not yet validated

> [!WARNING]
>
> Every validated result in this document was measured at
> `--tensor-parallel-size 1`. **No PodSnapshot has been captured or restored
> above TP=1.** Do not plan a multi-GPU deployment on the assumption that these
> restore times transfer.

Work toward answering this is in progress with
[`thinkingmachines/Inkling`](https://huggingface.co/thinkingmachines/Inkling), a
Mixture-of-Experts model. It has already established several prerequisites that
any multi-GPU deployment will hit, documented under "Multi-GPU: tensor
parallelism and very large models" in the technical guide:

- `/proc/gvisor/checkpoint` **is** present on a 4-GPU node, so checkpoint
  support installs correctly at TP=4. That gate is not the obstacle.
- The NVIDIA Run:ai Model Streamer exhibits four failure modes above TP=1 that
  cannot occur at TP=1, including an unbounded host-memory buffering default in
  distributed mode and a per-rank memory cap that deadlocks when set below a
  rank's partition size.
- Weight loading dominates at scale: 171 GB across 4 GPUs took **77 minutes**
  under gVisor in non-distributed mode, against 15 seconds for Llama 3.1 8B on a
  single GPU. Multi-GPU is therefore the case where a working snapshot would be
  worth the most.

---

## Section 8: Dual-Tier Autoscaling Architecture (EPP Control-Flow vs. Native Engine Metrics)

### 1. Core Principle: Swap CPU/Memory for EPP Flow Control Metrics (LLM-d Autoscaling Guide)

When configuring Horizontal Pod Autoscalers (HPA) for LLM inference workloads,
**do not use traditional CPU or memory utilization metrics (`cpu`, `memory`)**.

- **Why CPU & Memory Metrics Fail**: PyTorch/vLLM inference engines and CUDA
  kernels peg GPU and host CPU/Memory resources at or near 100% during active
  continuous batching, even when processing a single active request. CPU and
  memory saturation provide static, saturated signals that cause erratic scaling
  and fail to reflect true client request demand.
- **EPP Flow Control Scaling Signals (`igw_queue_depth` &
  `igw_running_requests`)**:
  - **`igw_queue_depth` (`inference_pool_per_pod_queue_size`)**: Primary
    **scale-out trigger signal**. When request volume exceeds pod concurrency
    limits, EPP buffers requests in memory at the ingress layer. Monitoring
    queue depth (`igw_queue_depth > 0`) provides an immediate, responsive signal
    of unmet demand.
  - **`igw_running_requests`**: **Capacity signal** tracking the number of
    concurrent requests actively executing per pod to evaluate saturation
    headroom.

### 2. Telemetry and Metric Source Comparison

To provide robust autoscaling under varying traffic patterns, this reference
architecture implements a **Dual-Tier Horizontal Pod Autoscaler (HPA)**
configuration that combines ingress-level control-flow metrics with backend
engine queue metrics.

```
+---------------------------------------------------------------------------------------------------+
| INGRESS CONTROLLER TIER                                                                           |
|                                                                                                   |
|  [ Endpoint Picker (EPP) Proxy ]                                                                  |
|   - Exposes Ingress Metric: prometheus.googleapis.com|inference_pool_per_pod_queue_size|gauge   |
|   - Captures: Total requests buffered at Gateway prior to backend dispatch                        |
|   - Exposes Capacity Metric: prometheus.googleapis.com|igw_running_requests|gauge                 |
|   - Captures: Active requests executing per backend replica                                       |
+---------------------------------------------------------------------------------------------------+
                                                 |
                                                 v
+---------------------------------------------------------------------------------------------------+
| BACKEND COMPUTE TIER                                                                              |
|                                                                                                   |
|  [ vLLM Container Pod ]                                                                           |
|   - Exposes Engine Metric: prometheus.googleapis.com|vllm:num_requests_waiting|gauge              |
|   - Captures: Requests queued inside vLLM engine memory queue                                     |
|   - Exposes Memory Metric: prometheus.googleapis.com|vllm:gpu_cache_usage_perc|gauge             |
|   - Captures: Percentage of allocated KV Cache blocks currently in use                            |
+---------------------------------------------------------------------------------------------------+
```

### 3. Detailed Metric Comparison Matrix

| Metric / Dimension                                 | Gateway API EPP Control-Flow HPA (`igw_queue_depth` / `igw_running_requests`) | Native vLLM Queue Depth HPA                                   | vLLM KV Cache Utilization HPA                                 | Traditional CPU / Memory (Not Recommended)            |
| :------------------------------------------------- | :---------------------------------------------------------------------------- | :------------------------------------------------------------ | :------------------------------------------------------------ | :---------------------------------------------------- |
| **Metric Identifier**                              | `prometheus.googleapis.com\|inference_pool_per_pod_queue_size\|gauge`         | `prometheus.googleapis.com\|vllm:num_requests_waiting\|gauge` | `prometheus.googleapis.com\|vllm:gpu_cache_usage_perc\|gauge` | `cpu` / `memory` utilization                          |
| **Observation Point**                              | L7 Gateway Ingress Proxy                                                      | Inside vLLM engine container                                  | Inside vLLM GPU Memory Manager                                | Host OS / Kubelet cgroups                             |
| **Primary Indicator**                              | Unhandled client requests buffered at ingress (`igw_queue_depth`)             | Internal request queuing due to GPU saturation                | KV Cache memory exhaustion / OOM risk                         | Static 100% saturation during active continuous batch |
| **Scale-Out Trigger Speed ($t_{\text{trigger}}$)** | **48 seconds (~6s faster)**                                                   | 54 seconds                                                    | Workload / Context Length Dependent                           | Erratic / Premature                                   |
| **Scale From Zero Support**                        | **Supported** (Buffers requests at Gateway while provisioning first pod)      | Not Supported (Requires active container to scrape metrics)   | Not Supported                                                 | Not Supported                                         |
| **Optimal Target Threshold**                       | `AverageValue: 6` (Scale-out) / Use `igw_running_requests` for capacity       | `AverageValue: 5`                                             | `Utilization: 80%`                                            | **N/A - Advised Against**                             |

### 4. Dual-Tier HPA Manifest Configuration

Below is the production manifest applying the Gateway API EPP queue metric to
autoscale the vLLM deployment:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: vllm-h100-gemma-4-31b-it-epp-hpa
  namespace: inf-supafast-online-gpu
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-h100-gemma-4-31b-it
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: External
      external:
        metric:
          name: prometheus.googleapis.com|inference_pool_per_pod_queue_size|gauge
        target:
          type: AverageValue
          averageValue: "6"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

---

## Section 9: Empirical Benchmarks & Performance Evaluation for Gemma 4 31B on NVIDIA H100 and RTX Pro 6000

To evaluate the reference architecture under production conditions, empirical
benchmarking was conducted using `quay.io/inference-perf/inference-perf:latest`
and direct inference verification on an **NVIDIA H100 80GB SXM5** GPU node
(`a3-highgpu-1g`, node pool `nap-a3-highgpu-1g-spot`) running GKE Autopilot with
NVIDIA open kernel driver `580.126.20`.

The evaluation targeted the **`google/gemma-4-31b-it`** dense foundation model
(31 Billion parameters, Heterogeneous Head Attention, 256k vocabulary size).

### 1. Comprehensive Empirical Results Matrix: Gemma 4 31B (NVIDIA H100 80GB)

| Benchmark Metric                       | GCS FUSE Baseline (Cold Start)            | NVIDIA Run:ai Streamer (Optimized Cold Start)                 | GKE PodSnapshot Fast-Start (Hydration Target)                    |
| :------------------------------------- | :---------------------------------------- | :------------------------------------------------------------ | :--------------------------------------------------------------- |
| **Compute Class / Accelerator**        | `gpu-h100-80gb-high-x1` (1x H100 80GB)    | `gpu-h100-80gb-high-x1` (1x H100 80GB)                        | `gpu-h100-80gb-high-x1` (1x H100 80GB)                           |
| **vLLM Image Tag**                     | `docker.io/vllm/vllm-openai:v0.26.0`      | `docker.io/vllm/vllm-openai:v0.26.0`                          | `docker.io/vllm/vllm-openai:v0.26.0`                             |
| **Max Model Length (`MAX_MODEL_LEN`)** | 8,192                                     | 8,192                                                         | 8,192                                                            |
| **GPU Memory Utilization**             | 0.90                                      | 0.90 (58.99 GiB Weights, 10.62 GiB KV Cache)                  | 0.90 (Restored from snapshot)                                    |
| **Device Headroom**                    | 7.92 GiB (Prevents FlashInfer logits OOM) | 7.92 GiB (Prevents FlashInfer logits OOM)                     | 7.92 GiB                                                         |
| **Model Weight Loading Duration**      | 378.67s (159.5 MiB/s via GCS FUSE)        | **48.16s** (Direct GCS stream @ ~1.22 GiB/s, peak 48.81 it/s) | **0.0s** (Pre-hydrated in snapshot)                              |
| **Dynamo Bytecode Transform**          | 15.67s                                    | 15.67s                                                        | **0.0s** (Pre-compiled)                                          |
| **Torch Inductor Compilation**         | 27.55s (Total `torch.compile`: 52.00s)    | 27.55s (Total `torch.compile`: 52.00s)                        | **0.0s** (Pre-compiled)                                          |
| **CUDA Graph Capture (51/51 sizes)**   | 25.00s (Allocated 0.91 GiB)               | 25.00s (Allocated 0.91 GiB)                                   | **0.0s** (Pre-captured)                                          |
| **Total Engine Initialization**        | 185s+                                     | **115.81s**                                                   | **0.0s** (Hydrated from memory)                                  |
| **Container Start to `Ready 1/1`**     | 570s (~9.5 minutes)                       | **301s** (~5.0 minutes)                                       | **5s** (`PodScheduled` → `Ready`, measured)                      |
| **Overall Cold-Start Reduction**       | Baseline                                  | **47.2% overall cold start reduction**                        | **>98% reduction** vs. the cold start that produced the snapshot |
| **Live Chat Completion Verification**  | 200 OK                                    | **200 OK** (Returned `"Paris"` in 164ms)                      | **200 OK** (verified on every restored replica)                  |
| **PodSnapshot Checkpoint Execution**   | Not tested                                | Completes: `pages.img` 72,899,854,336 B in 14 m 39 s          | Restores on a fresh node in 5 s, `restartCount: 0`               |

### 2. Deep Dive: Architectural Nuances for Gemma 4 31B

#### Memory Optimization & Headroom Allocation

`google/gemma-4-31b-it` features a massive **256,000 token vocabulary** and
heterogeneous attention head dimensions (standard `head_dim=256` paired with
global `global_head_dim=512`). During PyTorch CUDA graph capture with batch size
512, FlashInfer sampling operations (`top_k_mask_logits`) allocate **~994 MiB**
of temporary logits buffer memory.

When configuring standard `GPU_MEMORY_UTILIZATION=0.95`, only ~564 MiB of free
device memory remained after reserving 14.58 GiB for the KV cache, triggering a
fatal `torch.OutOfMemoryError`. Setting `GPU_MEMORY_UTILIZATION=0.90` and
`MAX_MODEL_LEN=8192` resolves this constraint:

- **58.99 GiB** allocated to base model weights.
- **10.62 GiB** allocated to KV Cache (12,629 tokens capacity).
- **7.92 GiB** retained as free device headroom, enabling clean CUDA graph
  capture (0.91 GiB) and zero OOM events.

#### Retracted: the NVIDIA driver 580 "channel stop" assertion is benign

> [!WARNING]
>
> An earlier revision of this document attributed PodSnapshot checkpoint hangs
> to an upstream NVIDIA open kernel driver assertion, and concluded that
> PodSnapshots were unusable on driver branch 580. **Both claims were wrong.**
> Nine subsequent controlled runs checkpointed and restored successfully on
> driver `580.126.20`, across NVIDIA L4, H100 80GB, and RTX Pro 6000 96GB.

The assertion itself is real and does appear in the logs:

```text
NVRM: nvAssertOkFailedNoLog: Assertion failed: Requested object not found [NV_ERR_OBJECT_NOT_FOUND] (0x00000057)
returned from pRmApi->Control(pRmApi, RES_GET_CLIENT_HANDLE(pKernelChannel), RES_GET_HANDLE(pKernelChannel), NVA06F_CTRL_CMD_STOP_CHANNEL, &stopChannelParams, sizeof(stopChannelParams)) @ nv_gpu_ops.c:10963
```

It is not diagnostic. The same assertion fires during runs whose checkpoints
complete normally, so its presence carries no information about whether a
checkpoint will succeed.

The observation that generated the false conclusion was that `checkpoint.img`
and `pages_meta.img` appear in Cloud Storage while `pages.img` does not. That is
**normal**. `pages.img` is written last, and a healthy Gemma 4 31B checkpoint
spends 10 to 15 minutes with only the first two objects present before the 73 GB
memory image lands.

Two practices prevent repeating this mistake:

- **Watch `pages.img` grow rather than treating its absence as failure.**
  `gcloud storage ls` does not show an object that is still being written; use
  `gcloud storage objects list "gs://${bucket}/${snapshot_uid}/**" --stat`.
- **Know where the objects live.** They are written to the **bucket root under
  the snapshot UID**, not under a `podsnapshot/` prefix. Listing the wrong
  prefix returns nothing, which is indistinguishable from a stalled checkpoint.

A genuine hang has a distinct signature: `runsc-checkpointgofer` blocked in
`futex_wait_queue`, `runsc checkpoint` blocked in `do_sys_poll`, and **zero**
byte movement in the bucket over a sustained interval.

The full elimination table — which also rules out the H100 architecture itself,
the `runai_streamer` loader, the resident VRAM footprint, out-of-band
triggering, and the vLLM image version — is in "What these runs settle" in the
technical guide. The original hang did not reproduce under any of the eight
configurations tested, and is attributed to the node image present at the time.

#### Blackwell (NVIDIA RTX Pro 6000 96GB) was also mis-attributed

The original Blackwell attempts selected nodes with the
`cloud.google.com/gke-accelerator` label rather than a compute class, which by
precondition 1 above means checkpoint support was likely never installed. Routed
through `gpu-rtx-pro-6000-96gb-x1` instead, Blackwell checkpoints and restores
correctly, and outperformed H100 on this workload:

| Metric                                | H100 80 GB       | RTX Pro 6000 96 GB |
| :------------------------------------ | :--------------- | :----------------- |
| Cold start (`PodScheduled` → `Ready`) | 265 s            | **224 s**          |
| `pages.img`                           | 72,899,854,336 B | 73,345,302,528 B   |
| Restore on a fresh node               | 5 s              | **4 s**            |
| Available KV cache                    | 8.21 GiB         | **22.44 GiB**      |

Weights are a fixed cost, so every additional byte of VRAM flows to KV cache:
**+20% VRAM produced +173% KV cache**. Under load that mattered more than raw
decode speed — the RTX deployment sustained monotonically rising throughput
across all eight sweep stages while the H100 deployment peaked and regressed.

> [!NOTE]
>
> `pages.img` grew only **0.6%** between the two GPUs despite 14 GiB more KV
> cache being allocated. The snapshot tracks resident weights plus runtime, not
> the `--gpu-memory-utilization` budget, because allocated-but-untouched KV
> cache costs almost nothing. Moving to a larger-VRAM GPU does **not**
> proportionally inflate snapshot size or checkpoint time.

---

## Section 10: Complete Standalone Manifest Suite for Gemma 4 31B (NVIDIA H100)

This section contains the complete, production-ready Kubernetes manifest suite
for deploying `google/gemma-4-31b-it` on an NVIDIA H100 80GB accelerator using
the Run:ai Model Streamer.

### `deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-h100-gemma-4-31b-it
  namespace: inf-supafast-online-gpu
  labels:
    app: vllm-h100-gemma-4-31b-it
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-h100-gemma-4-31b-it
  template:
    metadata:
      labels:
        app: vllm-h100-gemma-4-31b-it
      annotations:
        cluster-autoscaler.kubernetes.io/safe-to-evict: "false"
    spec:
      serviceAccountName: inf-supafast-online-gpu
      nodeSelector:
        cloud.google.com/compute-class: "gpu-h100-80gb-high-x1"
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      containers:
        - name: inference-server
          image: docker.io/vllm/vllm-openai:v0.26.0
          imagePullPolicy: IfNotPresent
          command:
            - python3
            - -m
            - vllm.entrypoints.openai.api_server
          args:
            - --model=gs://accelerated-platforms-dev-inf-supafast-hf-hub-models/google/gemma-4-31b-it
            - --served-model-name=google/gemma-4-31b-it
            - --load-format=runai_streamer
            - --trust-remote-code
            - --max-model-len=8192
            - --gpu-memory-utilization=0.90
            - --port=8000
          env:
            - name: VLLM_LOGGING_LEVEL
              value: "INFO"
            - name: PIP_BREAK_SYSTEM_PACKAGES
              value: "1"
          ports:
            - containerPort: 8000
              name: http
          resources:
            limits:
              cpu: "24"
              memory: "96Gi"
              nvidia.com/gpu: "1"
            requests:
              cpu: "24"
              memory: "96Gi"
              nvidia.com/gpu: "1"
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 30
```

### `service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: vllm-h100-gemma-4-31b-it
  namespace: inf-supafast-online-gpu
  labels:
    app: vllm-h100-gemma-4-31b-it
spec:
  ports:
    - name: http
      port: 8000
      targetPort: 8000
  selector:
    app: vllm-h100-gemma-4-31b-it
```

### `podsnapshotpolicy.yaml`

```yaml
apiVersion: podsnapshot.gke.io/v1alpha1
kind: PodSnapshotPolicy
metadata:
  name: vllm-snapshot-policy-h100-gemma-4-31b-it
  namespace: inf-supafast-online-gpu
spec:
  podSelector:
    matchLabels:
      app: vllm-h100-gemma-4-31b-it
  storage:
    gcs:
      bucket: gs://accelerated-platforms-dev-inf-supafast-hf-hub-models
  trigger:
    type: manual
```

---

## Section 11: Enterprise Security, Governance, and IAM Posture

### 1. Least-Privilege IAM Scoping

Security governance requires isolating workload identities and restricting
resource access. This architecture enforces three IAM security layers:

```
[ GKE ServiceAccount: inf-supafast-online-gpu ]
                        |
                        v (Workload Identity Mapping)
[ GCP IAM Service Account: inf-supafast-online-gpu@accelerated-platforms-dev.iam.gserviceaccount.com ]
                        |
       +----------------+----------------+
       |                                 |
       v (roles/storage.objectUser)      v (roles/secretmanager.secretAccessor)
[ GCS Bucket: gs://...-hf-hub-models/ ]  [ Secret: inf-supafast-huggingface-hub-access-token-read ]
```

#### IAM Binding Execution Commands

```bash
# 1. Bind Workload Identity Pool for Online GPU Namespace
gcloud iam service-accounts add-iam-policy-binding \
  inf-supafast-online-gpu@accelerated-platforms-dev.iam.gserviceaccount.com \
  --role="roles/iam.workloadIdentityUser" \
  --member="principal://iam.googleapis.com/projects/312289355029/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/inf-supafast-online-gpu/sa/inf-supafast-online-gpu"

# 2. Grant GCS Object Access for Model Weights
gcloud storage buckets add-iam-policy-binding gs://accelerated-platforms-dev-inf-supafast-hf-hub-models \
  --member="principal://iam.googleapis.com/projects/312289355029/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/inf-supafast-online-gpu/sa/inf-supafast-online-gpu" \
  --role="roles/storage.objectUser"

# 3. Grant Secret Manager Access for HuggingFace Authentication Token
gcloud secrets add-iam-policy-binding inf-supafast-huggingface-hub-access-token-read \
  --project=accelerated-platforms-dev \
  --member="principal://iam.googleapis.com/projects/312289355029/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/inf-supafast-online-gpu/sa/inf-supafast-online-gpu" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Section 12: Production Day-2 Operations, Troubleshooting, and Recovery Runbook

### 1. Prometheus Monitoring & Alerting Configurations

To track system health and scaling performance, production clusters should
monitor four Prometheus metrics exposed by GKE components:

```yaml
apiVersion: monitoring.googleapis.com/v1
kind: PodMonitoring
metadata:
  name: vllm-podmonitoring
  namespace: inf-supafast-online-gpu
spec:
  selector:
    matchLabels:
      app: vllm-h100-gemma-4-31b-it
  endpoints:
    - port: http
      interval: 10s
      path: /metrics
```

### 2. Comprehensive Troubleshooting Guide for Common Failure Modes

> [!IMPORTANT]
>
> **Important note on large models and PodSnapshots**
>
> **Large models are slow to checkpoint, not incapable of it.** An earlier
> revision of this document stated that checkpointing Gemma 4 31B fails on
> driver `580.126.20` because of an `NVA06F_CTRL_CMD_STOP_CHANNEL` assertion.
> That attribution has been retracted — see "Retracted: the NVIDIA driver 580
> 'channel stop' assertion is benign" in Section 9. Checkpointing succeeds on
> both Hopper and Blackwell; it simply takes 11 to 15 minutes for a ~73 GB
> memory image, because the upload runs at roughly 83 MB/s. Watch `pages.img` >
> **grow** with
> `gcloud storage objects list "gs://${bucket}/${snapshot_uid}/**" --stat`
> rather than treating its absence as failure.
>
> **Memory sizing and FlashInfer headroom:** Gemma 4 31B uses a large 256k
> vocabulary. At `GPU_MEMORY_UTILIZATION=0.95`, allocating FlashInfer logits
> buffers during CUDA graph capture exhausts remaining VRAM. Setting
> `GPU_MEMORY_UTILIZATION=0.90` and `MAX_MODEL_LEN=8192` reserves 7.92 GiB of
> free device headroom, enabling clean engine initialization and CUDA graph
> capture with zero OOM errors.
>
> **Use both techniques together.** NVIDIA Run:ai Model Streamer delivers
> **48.16s** weight streaming directly from Cloud Storage at ~1.22 GiB/s, a
> **47.2%** cold-start reduction. PodSnapshots then reduce every subsequent
> scale-out to single-digit seconds. The streamer pays for the one cold start
> that has to happen to produce the snapshot; the snapshot pays for everything
> after that.

#### Failure Mode 1: HPA Target Shows `<unknown>` Metric Status

- **Symptom**: `kubectl get hpa` displays `<unknown>` under TARGETS, and the
  deployment fails to autoscale during traffic spikes.
- **Root Cause**: Custom Metrics Stackdriver Adapter is missing permissions or
  Prometheus metrics are not registered in Cloud Monitoring.
- **Remediation**:
  1. Verify the adapter pod is running in `kube-system`:
     `kubectl get pods -n kube-system -l k8s-app=custom-metrics-stackdriver-adapter`.
  2. Verify metric presence in Google Cloud Monitoring using `gcloud logging` or
     Metric Explorer for
     `prometheus.googleapis.com|inference_pool_per_pod_queue_size|gauge`.
  3. Ensure Workload Identity permissions are granted to the monitoring service
     account.

#### Failure Mode 2: Secret Manager CSI Driver `PermissionDenied` Mount Failure

- **Symptom**: Inference pod stuck in `ContainerCreating` state with event
  `rpc error: code = PermissionDenied desc = Permission 'secretmanager.versions.access' denied`.
- **Root Cause**: Missing IAM binding between the namespace Kubernetes
  ServiceAccount and Secret Manager secret resource.
- **Remediation**: Execute direct resource IAM policy binding:
  ```bash
  gcloud secrets add-iam-policy-binding inf-supafast-huggingface-hub-access-token-read \
    --project=accelerated-platforms-dev \
    --member="principal://iam.googleapis.com/projects/312289355029/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/<namespace>/sa/<serviceaccount>" \
    --role="roles/secretmanager.secretAccessor"
  ```

#### Failure Mode 3: PersistentVolume Spec Immutability Error

- **Symptom**: `kubectl apply` throws
  `Forbidden: spec.persistentvolumesource is immutable after creation`.
- **Root Cause**: Attempting to update `volumeHandle` or `mountOptions` on an
  existing Kubernetes `PersistentVolume`.
- **Remediation**: Delete the immutable PV resource before applying updated
  manifests:
  ```bash
  kubectl delete pvc -n inf-supafast-online-gpu --all --ignore-not-found
  kubectl delete pv vllm-model-pv-h100-gemma-4-31b-it --ignore-not-found --grace-period=0 --force
  kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/h100-gemma-4-31b-it
  ```

#### Failure Mode 4: GCS Bucket 404 Access Error During Benchmark Execution

- **Symptom**: `inference-perf` container crashes with
  `ValueError: GCS bucket 'inf-supafast-bench-results' does not exist or is inaccessible.`
- **Root Cause**: Results bucket has not been provisioned in GCP or Workload
  Identity SA lacks `roles/storage.admin`.
- **Remediation**: Create target GCS bucket and grant Workload Identity storage
  permissions:
  ```bash
  gcloud storage buckets create gs://inf-supafast-bench-results --project=accelerated-platforms-dev --location=europe-west4
  gcloud storage buckets add-iam-policy-binding gs://inf-supafast-bench-results \
    --member="principal://iam.googleapis.com/projects/312289355029/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/inf-supafast-online-gpu/sa/inf-supafast-online-gpu" \
    --role="roles/storage.admin"
  ```

---

## Section 13: Reference Links & Official Google Cloud Documentation Index

### Official Google Cloud Documentation

1. **GKE Inference Gateway Concepts**:
   [https://docs.cloud.google.com/kubernetes-engine/docs/concepts/about-gke-inference-gateway](https://docs.cloud.google.com/kubernetes-engine/docs/concepts/about-gke-inference-gateway)
2. **GKE Predicted Latency-Based Routing**:
   [https://docs.cloud.google.com/kubernetes-engine/docs/how-to/use-predicted-latency-based-routing](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/use-predicted-latency-based-routing)
3. **GKE Gateway API Overview**:
   [https://cloud.google.com/kubernetes-engine/docs/concepts/gateway-api](https://cloud.google.com/kubernetes-engine/docs/concepts/gateway-api)
4. **GKE Workload Identity Federation**:
   [https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
5. **GKE Secret Manager CSI Driver Integration**:
   [https://cloud.google.com/kubernetes-engine/docs/how-to/secret-manager](https://cloud.google.com/kubernetes-engine/docs/how-to/secret-manager)
6. **Google Cloud Storage Security & Access Control**:
   [https://cloud.google.com/storage/docs/access-control/iam](https://cloud.google.com/storage/docs/access-control/iam)
7. **Compute Engine Pricing & GPU Instance Options**:
   [https://cloud.google.com/products/compute/pricing](https://cloud.google.com/products/compute/pricing)

### Related Repository Code Artifacts

1. [vLLM with Run:ai & PodSnapshots Deployment Guide](./vllm-with-runai-and-podsnapshots.md)
2. [Model Downloader Kustomize Manifests](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface/job.yaml)
3. [Native Inference Perf Benchmark Manifests](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configure_benchmark.sh)
4. [vLLM Deployment Overlay for Gemma 4 31B](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/h100-gemma-4-31b-it/runtime.env)
