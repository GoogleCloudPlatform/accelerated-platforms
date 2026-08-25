# Cloud TPU v6e Gemma 3 4B SFT Benchmarking & Memory Sizing Guide

This guide documents the empirical benchmarking results, memory sizing boundaries, and operational troubleshooting learned from multi-experiment Cloud TPU v6e and v5e SFT training.

---

## 1. Cloud TPU v6e Empirical Performance Matrix

| Experiment | Batch / Device | Seq Length | Global Batch (8 chips) | Tokens / Chip | Step Speed | Device Throughput | Device MFU / Compute | Status | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Baseline** | **1** | **1024** | 8 | 1,024 | 0.349 s | 5,862 Tokens/s | 140.4 TFLOP/s | **SUCCESS** | Small memory footprint, lower TPU duty cycle (~10%) due to CPU data loading dominance. |
| **** | **4** | **1024** | 32 | **4,096** | **0.422 s** | **9,701 Tokens/s** | **230.0 TFLOP/s** | **SUCCESS** | **Optimal for 1024 context**. +63.8% MFU increase and +65.5% token throughput boost. |
| **** | **2** | **2048** | 16 | **4,096** | **0.431 s** | **9,506 Tokens/s** | **227.7 TFLOP/s** | **SUCCESS** | **Optimal for 2048 context**. Sits at peak TPU memory saturation without OOM. |
| ** (bs=1)**| **1** | **4096** | 8 | **4,096** | 0.445 s | 9,200 Tokens/s | 224.5 TFLOP/s | **SUCCESS** | **Optimal for 4096 context**. Long-context dialogue fine-tuning. |
| **** | 8 | 1024 | 64 | 8,192 | N/A | N/A | N/A | **FAILED (OOM)** | Requires 12.32 GB activation memory; exceeded 6.20 GB free HBM without activation remat. |
| ** (bs=2)**| 2 | 4096 | 16 | 8,192 | N/A | N/A | N/A | **FAILED (OOM)** | Requires 12.21 GB activation memory; exceeded 6.20 GB free HBM without activation remat. |

---

## 2. Hardware Memory Sizing Rules & Boundary Limits

### The 4,096 Tokens-per-Chip Golden Rule (Cloud TPU v6e / 32 GB HBM)

On Cloud TPU v6e with Gemma 3 4B (3.88B params) and standard AdamW optimizer:
* **Static Memory Allocated**:
  * BF16 Model Weights: .76	ext{ GB}$
  * FP32 AdamW Optimizer States (1st & 2nd moments): 5.52	ext{ GB}$
  * BF16 Gradients: .94	ext{ GB}$
  * **Remaining Free HBM for Activations**: **$pprox 6.20	ext{ GB}*

* **Dynamic Activation Footprint Formula**:
  2383953	ext{Active Token Load} = 	ext{Batch Size per Device} 	imes 	ext{Sequence Length}2383953
  * **$\le 4,096	ext{ tokens/chip}*: Fits comfortably within .20	ext{ GB}$ free memory $ightarrow$ **Peak Performance (230 TFLOP/s)**.
  * **$> 4,096	ext{ tokens/chip}*: Triggers `RESOURCE_EXHAUSTED` error during XLA JIT compilation unless activation rematerialization is enabled.

---

## 3. Troubleshooting & Failure Modes Log

### Issue 1: JAX Runtime Resource Exhausted on High Batch / Long Sequence
* **Failing Configurations**: `per_device_batch_size=8, seq=1024` and `per_device_batch_size=2, seq=4096`
* **Exact Error**:
  ```text
  jax.errors.JaxRuntimeError: RESOURCE_EXHAUSTED: E0101: RuntimeProgramAllocationFailure:
  Error loading program 'jit_train_step': Attempting to reserve 12.21G at the bottom of memory.
  That was not possible. There are 6.20G free, 0B reserved, and 6.20G reservable.
  ```
* **Resolution**: Keep $	ext{Batch Size} 	imes 	ext{Sequence Length} \le 4096$ per chip (e.g. `bs=4, seq=1024`, `bs=2, seq=2048`, or `bs=1, seq=4096`).

---

### Issue 2: MLflow 3.x Host Header Validation (DNS Rebinding)
* **Exact Error**:
  ```text
  mlflow.exceptions.MlflowException: API request to endpoint /api/2.0/mlflow/experiments/get-by-name 
  failed with error code 403 != 200. Response body: 'Invalid Host header - possible DNS rebinding attack detected'
  ```
* **Root Cause**: MLflow 3.10+ rejects cluster-internal DNS names (`mlflow-tracking-svc...`) by default.
* **Resolution**: Added `--allowed-hosts "*"` to the MLflow server deployment args.

---

### Issue 3: JAX Distributed Initialization Ordering
* **Exact Error**:
  ```text
  RuntimeError: jax.distributed.initialize() must be called before any JAX calls that might 
  initialise the XLA backend. This includes any computation, but also calls to jax.devices.
  ```
* **Root Cause**: Early calls to `jax.devices()` initialized the XLA backend before MaxText's internal distributed init.
* **Resolution**: Set `skip_jax_distributed_system=True` in single-host training configs and remove top-level `jax.devices()` calls.
