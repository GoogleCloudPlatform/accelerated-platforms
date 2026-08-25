# Single-Host Supervised Fine-Tuning (SFT) with TPUs on Google Kubernetes Engine (GKE) using MaxText

This guide provides a comprehensive production reference architecture and implementation guide for running **Single-Host** Supervised Fine-Tuning (SFT) on Cloud TPUs using **MaxText** and **Tunix** on Google Kubernetes Engine (GKE).

---

## 1. Architectural Overview

Single-host TPU slice topologies (`v5e-2x4`, `v6e-2x4`) contain 8 TPU chips attached to a single host VM. In single-host execution, JAX communicates directly with the TPU hardware through **PJRT** without network serialization overhead.

```mermaid
flowchart TD
    subgraph HostVM["Single-Host GKE TPU Node (e.g. ct6e-standard-8t)"]
        direction TB
        subgraph Pod["SFT Trainer Pod"]
            Trainer["MaxText SFT Trainer (train_sft.py)"]
            TokenStream["Hugging Face Streaming / Local Tokenizer"]
            PJRT["PJRT Hardware Runtime"]
            Trainer --> PJRT
        end
        subgraph Hardware["Cloud TPU v6e-8 Accelerator (256 GB HBM Total)"]
            Chip0["Chip 0 (32GB)"] --- Chip1["Chip 1 (32GB)"]
            Chip2["Chip 2 (32GB)"] --- Chip3["Chip 3 (32GB)"]
            Chip4["Chip 4 (32GB)"] --- Chip5["Chip 5 (32GB)"]
            Chip6["Chip 6 (32GB)"] --- Chip7["Chip 7 (32GB)"]
        end
        PJRT === Hardware
    end
    Pod -->|Step Metrics| MLflow["In-Cluster MLflow Server (Port 5000)"]
    Pod -->|Async Checkpoints| GCS["GCS Bucket (Orbax Format)"]
```

---

## 2. Hardware & Memory Sizing Formulas

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

### B. Sharding Across Single-Host Chips (8 Devices)
Under Fully Sharded Data Parallelism (FSDP / `fsdp_transposed`), parameters and optimizer states are sharded across the 8 TPU devices:
$$\text{Per-Device Memory} = \frac{16 \times P}{8\text{ devices}} + \text{Activation Memory}(B, S, H, L)$$

| Model | Parameters ($P$) | Total Static State ($16P$) | Sharded State / Chip | Available Activation Headroom / Chip |
| :--- | :--- | :--- | :--- | :--- |
| **Gemma 3 4B** | 4.30B | **`68.8 GB`** | **`8.6 GB / chip`** | **`23.4 GB`** (73% Headroom) |
| **Llama 3.1 8B** | 8.03B | **`128.5 GB`** | **`16.1 GB / chip`** | **`15.9 GB`** (50% Headroom) |

---

## 3. Unfinished Gradient Descent & Full-Epoch Convergence Dynamics

When fine-tuning on datasets like `HuggingFaceH4/ultrachat_200k` (207,865 training conversations, 23,110 test conversations):

### A. Subsampled Runs vs. Full Epoch Math
* In a 1,000-step baseline with global batch size = 16 (8 chips $\times$ `per_device_batch_size=2`):
  $$\text{Samples Processed} = 1,000 \times 16 = 16,000\text{ samples} \implies \mathbf{7.7\% \text{ of 1 Full Epoch}}$$
* **The "Unfinished Gradient Descent" Phenomenon**:
  Even though evaluation perplexity dropped by **`-70.7%`** (`10.663` $\rightarrow$ `3.128`), the loss gradient slope remained strictly negative with zero signs of overfitting.

### B. 1 Full Epoch SFT Configuration (`12,990 steps` on 8 Chips)
$$\text{Steps for 100\% Dataset Exposure} = \frac{207,865\text{ samples}}{16\text{ global batch size}} = \mathbf{12,990\text{ steps}}$$
* **Total Execution Time**: $12,990 \times 0.427\text{s} \approx \mathbf{92\text{ minutes}}$ (~1.54 hours).
* **Full Test Evaluation**: Evaluates across all **`23,110`** test conversations in `1,444` eval steps.

---

## 4. Activation Scaling & Gradient Accumulation

### Direct Batching vs. Gradient Accumulation
Activation memory scales proportionally with sequence length and batch size: $\mathcal{O}(B \times S \times H \times L)$.

* **The Problem (Direct Batching Crash)**:
  Setting `per_device_batch_size=8` directly causes physical memory consumption to spike to **`32.41 GB`**, exceeding the physical `31.57 GB` HBM capacity of Cloud TPU v6e and triggering an **Out-Of-Memory (OOM)** crash.
* **The Solution (Gradient Accumulation)**:
  Set `per_device_batch_size=2` and `gradient_accumulation_steps=4` (or `8`).
  * Physical activation memory remains locked at **`15.0 GB` (47% HBM)**.
  * Micro-batches are evaluated sequentially in SRAM, accumulating gradients before performing the AdamW weight update.
  * Effective global batch size scales to **`64`** or **`128`** with **zero memory risk**.

---

## 5. Empirical Benchmark Matrix (Empirical Results)

The following metrics were measured during live end-to-end SFT execution on Cloud TPU v6e-8 (`2x4`) instances:

| Experiment Configuration | Batch Size & Micro-steps | Context Length | Peak HBM Footprint | Compute Throughput | Final Eval Perplexity | Status / Outcome |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`bs=2, seq=1024`** | `bs=2, ga=1` (bs=2) | 1024 tokens | `9.5 GB` (30%) | **`230.1 TFLOP/s`** | `3.246` (-69.3%) | Baseline fast SFT run |
| **`bs=4, seq=1024`** | `bs=4, ga=1` (bs=4) | 1024 tokens | `14.5 GB` (45%) | **`230.9 TFLOP/s`** | `3.139` (-73.1%) | Optimal 1024 compute density |
| **`bs=8, seq=1024`** | `bs=8, ga=1` (bs=8) | 1024 tokens | **`32.41 GB`** | 0 | N/A | **OOM Crash** ($>31.57\text{ GB}$) |
| **`gradaccum=4`** | `bs=2, ga=4` (eff bs=8) | 2048 tokens | **`15.0 GB` (47%)** | **`229.8 TFLOP/s`** | `3.128` | **Fixed `bs=8` OOM failure** |
| **`gradaccum=8`** | `bs=2, ga=8` (eff bs=16)| 2048 tokens | **`15.0 GB` (47%)** | **`229.5 TFLOP/s`** | `3.110` | Linear effective batch scaling |
| **`seq4096`** | `bs=2, ga=1` (bs=2) | 4096 tokens | `22.0 GB` (69%) | **`228.0 TFLOP/s`** | **`3.070`** | **Highest Dialogue Accuracy** |

* **Hardware Efficiency**: Cloud TPU v6e achieves sustained **`228 - 231 TFLOP/s / device`** (~50% Model Flops Utilization).

---

## 6. Step-by-Step Deployment Guide

### Prerequisites
1. **GKE Cluster** with Cloud TPU node pool (`ct6e-standard-8t`) and GKE Workload Identity enabled.
2. **Hugging Face Token Secret**: Stored in Secret Manager and mounted via `SecretProviderClass`.
3. **GCS Bucket**: Configured for Orbax checkpoint saving and loading.

---

### Step 1: Deploy Full-Epoch Single-Host SFT Job (12,990 Steps)

```bash
kubectl apply -f platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-single-host/experiments/05-gemma3-4b-sft-full-epoch-v6e-8.yaml
```

Monitor the pod logs:
```bash
kubectl get pods -l app=gemma3-4b-sft-full-epoch -o wide
kubectl logs -l app=gemma3-4b-sft-full-epoch -f
```

---

## 7. Real-Time Metrics & MLflow Tracking

Metrics are logged per-step and streamed directly to the in-cluster MLflow tracking server (`http://mlflow-tracking-svc.<namespace>.svc.cluster.local:5000`).

### Port-Forward the MLflow UI:
```bash
kubectl port-forward -n rl-mul-slice-checkpoint-converter svc/mlflow-tracking-svc 5000:5000
```
Open `http://localhost:5000` in your browser to inspect:
* **Training Loss & Step Perplexity**
* **Evaluation Loss & Final Perplexity Reduction**
* **Hardware TFLOP/s / device & Model Flops Utilization (MFU)**
* **Step Latency & Checkpoint Serialization Speed**
