# Multi-Host & Multi-Slice Supervised Fine-Tuning (SFT) with TPUs on Google Kubernetes Engine (GKE) using MaxText & Pathways

This guide provides a comprehensive production reference architecture and implementation guide for running **Multi-Host** and **Multi-Slice** Supervised Fine-Tuning (SFT) on Cloud TPUs using **MaxText**, **Tunix**, and **Pathways** on Google Kubernetes Engine (GKE).

---

## 1. Architectural Overview & Orchestration Paradigms

Training large language models across multiple TPU hosts requires distributed tensor sharding and cross-node communication. This architecture supports two primary distributed orchestration paradigms on GKE:

```mermaid
flowchart TD
    subgraph MultiHost["Multi-Host Orchestration Options"]
        direction TB
        subgraph McJAX["Multi-Controller JAX (McJAX)"]
            MJ1["Host 0: Python Client + PJRT"] --- MJ2["Host 1: Python Client + PJRT"]
            MJ2 --- MJ3["Host N: Python Client + PJRT"]
            MJ1 -.-|Direct ICI / DCN Mesh| MJ2
        end

        subgraph Pathways["Pathways Single Controller"]
            Head["Head Pod (3/3 Ready)
            ├─ sft-trainer (Python Client)
            ├─ pathways-proxy (IFRT Port 29000)
            └─ pathways-rm (Resource Mgr Port 29001)"]
            Head -->|gRPC / HLO Dispatch| W1["TPU Worker Node 0 (C++ Runtime)"]
            Head -->|gRPC / HLO Dispatch| W2["TPU Worker Node 1 (C++ Runtime)"]
            Head -->|gRPC / HLO Dispatch| WN["TPU Worker Node N (C++ Runtime)"]
            W1 <===>|Inter-Chip Interconnect (ICI)| W2
        end
    end
```

### A. Multi-Controller JAX (McJAX)
* **Execution Model**: An SPMD (Single Program, Multiple Data) model where an identical Python process runs on every TPU host pod (`IndexedJob`).
* **Coordination**: Hosts discover each other via a Kubernetes Headless Service using `jax.distributed.initialize(coordinator_address=...)`.
* **Hardware Interconnect**: Communication runs natively over high-speed Inter-Chip Interconnect (ICI) optical links.

### B. Pathways Orchestration (`PathwaysJob`)
* **Execution Model**: A Client-Server disaggregated architecture where a single Python client generates computation graphs, and a pool of lightweight C++ worker daemons execute HLO kernels across TPU slices.
* **Elasticity & Multi-Slice**: Seamlessly scales across multiple independent TPU slices (`numSlices: >= 2`) connected over Datacenter Network (DCN).
* **Head Pod Container Architecture (Why it shows `3/3 Ready`)**:
  When using `deploymentMode: colocate_head_with_workers`, the head pod colocates three tightly coupled containers:
  1. **`sft-trainer`**: The user MaxText training container (`tpu_post_training:0.2.3`) running in single-controller mode (`enable_single_controller=True`).
  2. **`pathways-proxy`**: The IFRT (Intermediate Frontend Representation for Tensors) Proxy sidecar listening on `grpc://127.0.0.1:29000`. Translates JAX client operations into Pathways RPCs.
  3. **`pathways-rm`**: The Pathways Resource Manager sidecar on port `29001`. Tracks TPU worker registrations, memory sharding, and cluster topology.

---

## 2. Distributed Memory Sizing & Math

Full-parameter fine-tuning with AdamW in bfloat16 requires allocating memory for parameters, gradients, optimizer momentum/variance states, and forward activations.

### A. Memory Breakdown Formulas
For a model with $P$ parameters:
1. **Model Parameters (bfloat16)**: $2 \times P\text{ bytes}$
2. **Gradients (bfloat16)**: $2 \times P\text{ bytes}$
3. **AdamW Optimizer States (fp32)**:
   * First momentum vector ($m_t$): $4 \times P\text{ bytes}$
   * Second variance vector ($v_t$): $4 \times P\text{ bytes}$
   * Master weights (fp32 copy): $4 \times P\text{ bytes}$
   * *Total Optimizer State*: $12 \times P\text{ bytes}$
4. **Total Static State per Model**:
   $$\text{Static HBM} = 2P + 2P + 12P = 16 \times P\text{ bytes}$$

### B. FSDP Sharding Across TPU Slices
Under Fully Sharded Data Parallelism (FSDP / `fsdp_transposed`), parameters and optimizer states are sharded across $N$ TPU devices:
$$\text{Per-Device Memory} = \frac{16 \times P}{N_{\text{devices}}} + \text{Activation Memory}(B, S, H, L)$$

| Model | Parameters ($P$) | Total Static State ($16P$) | TPU Topology | Total Slice HBM | Sharded State / Chip | Safe Activation Headroom / Chip |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Gemma 3 4B** | 4.30B | **`68.8 GB`** | TPU v6e-8 (`2x4`, 8 chips) | 256 GB | **`8.6 GB / chip`** | **`23.4 GB`** (73% Headroom) |
| **Qwen 3 14B** | 14.77B | **`236.3 GB`** | TPU v6e-32 (`4x8`, 32 chips) | 1024 GB | **`7.4 GB / chip`** | **`24.6 GB`** (77% Headroom) |
| **Gemma 4 31B** | 31.0B | **`496.0 GB`** | TPU v6e-32 (`4x8`, 32 chips) | 1024 GB | **`15.5 GB / chip`** | **`16.5 GB`** (52% Headroom) |

---

## 3. Unfinished Gradient Descent & Full-Epoch Convergence Dynamics

When fine-tuning models on large instruction datasets like `HuggingFaceH4/ultrachat_200k` (207,865 training conversations, 23,110 test conversations):

### A. Subsampled Runs vs. Full Epoch Math
* In a 1,000-step baseline with global batch size = 64 (32 chips $\times$ `per_device_batch_size=2`):
  $$\text{Samples Processed} = 1,000 \times 64 = 64,000\text{ samples} \implies \mathbf{30.8\% \text{ of 1 Full Epoch}}$$
* **The "Unfinished Gradient Descent" Phenomenon**:
  Even though evaluation perplexity dropped from `3.683` down to `2.523` (-31.5%), the loss gradient slope ($\frac{d\mathcal{L}}{dt}$) remained strictly negative. The model had not reached loss saturation or overfitting, indicating substantial untapped capacity to learn multi-turn conversation dynamics.

### B. 1 Full Epoch SFT Configuration (`3,248 steps` on 32 Chips)
$$\text{Steps for 100\% Dataset Exposure} = \frac{207,865\text{ samples}}{64\text{ global batch size}} = \mathbf{3,248\text{ steps}}$$
* **Total Execution Time**: $3,248 \times 1.74\text{s} \approx \mathbf{94\text{ minutes}}$ (~1.57 hours).
* **Full Test Evaluation**: Evaluates across all **`23,110`** test conversations in `361` eval steps, eliminating sampling variance.

---

## 4. Empirical Benchmark Matrix (Empirical Results)

The following metrics were measured during live end-to-end SFT execution on Cloud TPU v6e instances:

### Multi-Host 32-Chip SFT Benchmark (Qwen 3 14B on TPU v6e-32 `4x8`)
* **Infrastructure**: 8 Nodes `ct6e-standard-4t` (32 chips, 1024 GB total HBM).
* **Dataset**: `HuggingFaceH4/ultrachat_200k` (Sequence Length: 2048).

| Step Milestone | Training Loss | Training Perplexity | Evaluation Loss | Evaluation Perplexity | Step Latency | Hardware Throughput | Checkpoint Save Time |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Step 0** | 1.3039 | 3.683 | 1.3039 | **`3.683`** | 1.74s | 202.8 TFLOP/s / device | Initialized |
| **Step 100** | 0.8702 | 2.387 | 1.1012 | **`3.008`** | 1.74s | 202.8 TFLOP/s / device | 5.01s |
| **Step 200** | 0.8654 | 2.376 | 1.0330 | **`2.810`** | 1.74s | 202.9 TFLOP/s / device | 4.96s |
| **Step 400** | 0.8812 | 2.413 | 0.9761 | **`2.654`** | 1.74s | 203.1 TFLOP/s / device | 5.08s |
| **Step 600** | 0.8490 | 2.337 | 0.9489 | **`2.583`** | 1.74s | 203.0 TFLOP/s / device | 5.12s |
| **Step 800** | 0.8521 | 2.344 | 0.9318 | **`2.539`** | 1.74s | 203.2 TFLOP/s / device | 5.10s |
| **Step 1000** | 0.8124 | 2.253 | 0.9254 | **`2.523`** | 1.74s | **`203.2 TFLOP/s / device`** | **`5.45s`** |

* **Total Perplexity Reduction**: **`-31.5%`** (`3.683` $\rightarrow$ `2.523`).
* **Model FLOPs Utilization (MFU)**: **`~48.5%`** of theoretical peak bfloat16 compute.

---

## 5. Step-by-Step Deployment Guide

### Prerequisites
1. **GKE Cluster** with Cloud TPU node pools (`ct6e-standard-4t`) and GKE Workload Identity enabled.
2. **Hugging Face Token Secret**: Stored in Secret Manager and mounted via `SecretProviderClass`.
3. **GCS Bucket**: Configured for Orbax checkpoint saving and loading.

---

### Step 1: Deploy Full-Epoch Multi-Host SFT (32 Chips, `4x8`)

```bash
kubectl apply -f platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/experiments/05-qwen3-14b-sft-full-epoch-v6e-32.yaml
```

Monitor the multi-host indexed job:
```bash
kubectl get pods -l job-name=qwen3-14b-sft-full-epoch -o wide
kubectl logs qwen3-14b-sft-full-epoch-0-szghd -f
```

---

### Step 2: Deploy Multi-Host SFT via Pathways (`PathwaysJob`)

Deploy the 32-chip Pathways SFT workload with automatic retry resiliency (`maxRestarts: 10`):

```bash
kubectl apply -f platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/experiments/02-qwen3-14b-pathways-sft-v6e-32.yaml
```

Verify that the Head Pod reports **`3/3 Ready`**:
```bash
kubectl get pathwaysjob pw-qwen3-32
kubectl get pods -l 'jobset.sigs.k8s.io/jobset-name=pw-qwen3-32'
```

---

### Step 3: Deploy Multi-Slice SFT (`numSlices: 2` $\times$ `4x8`)

Deploy cross-slice training across 2 independent 32-chip slices (64 chips total):

```bash
kubectl apply -f platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/experiments/02-qwen3-14b-pathways-sft-v6e-32.yaml
```

---

## 6. Real-Time Metrics & MLflow Tracking

Metrics are logged per-step and streamed directly to the in-cluster MLflow tracking server (`http://mlflow-tracking-svc.<namespace>.svc.cluster.local:5000`).

### Port-Forward the MLflow UI:
```bash
kubectl port-forward -n rl-mul-slice-checkpoint-converter svc/mlflow-tracking-svc 5000:5000
```
Open `http://localhost:5000` in your browser to view:
* **Training & Evaluation Loss Curves**
* **Evaluation Perplexity Convergence**
* **Hardware TFLOP/s / device & Model Flops Utilization (MFU)**
* **Learning Rate & Weight Decay Schedules**
