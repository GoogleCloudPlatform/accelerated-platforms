# LLM-D FP8 Sizing & Memory Calculation Matrix (3×3 Specification × Accelerator Reference)

This document explains the mathematical sizing formulas, KV cache budgeting, and architectural constraints behind the configuration values (`TENSOR_PARALLEL_SIZE`, `MAX_MODEL_LEN`, `GPU_MEMORY_UTILIZATION`) for **`qwen/qwen3-32b-fp8`** and **`redhatai/gemma-4-31b-it-fp8-block`** across the three `llm-d` well-lit path strategy specifications (`optimized-baseline`, `precise-prefix-cache-routing`, and `predicted-latency-routing`) on **NVIDIA H100**, **NVIDIA RTX Pro 6000**, and **Google TPU v6e** *(qwen3-32b-fp8 only; Gemma 4 FP8 is unsupported on TPU)*.

---

## 1. Mathematical Formulas & Base Sizing

### 1.1 Weight & Runtime Buffer Memory (`w_size`)
In the `llm-d-workload-tuner` (`tune_workload.py`), model weight memory plus baseline runtime execution buffers is calculated as:
$$\text{w\_size} = \text{params\_BF16\_effective} \times 2.0 \times 1.2$$
- **`2.0`**: Bytes per BF16 parameter element.
- **`1.2`**: `MEM_MULT` (1.2× runtime buffer multiplier to account for CUDA/XLA kernels, activation tensors, and NCCL/XLA scratch space).
- **FP8 Quantization Halving**: Because FP8 block quantization halves the model weight footprint compared to 16-bit precision, we register effective parameter sizes as half the nominal count in `model_specs.json`:
  - **`redhatai/gemma-4-31b-it-fp8-block`**: Effective params = `16.0B` $\rightarrow \text{w\_size} = 16.0 \times 2.0 \times 1.2 = \mathbf{38.40\text{ GB}}$.
  - **`qwen/qwen3-32b-fp8`**: Effective params = `16.25B` $\rightarrow \text{w\_size} = 16.25 \times 2.0 \times 1.2 = \mathbf{39.00\text{ GB}}$.

---

### 1.2 KV Cache Memory Demand per Sequence
The memory required to store key-value attention tensors per token for a sequence is:
$$\text{bytes\_per\_token} = 2 \times n_{\text{layers}} \times n_{\text{kv\_heads}} \times d_{\text{head}} \times \text{bytes\_per\_elem}$$
Using 16-bit (`2` bytes) KV cache storage:
- **Gemma-4-31B** ($n_{\text{layers}}=48, n_{\text{kv\_heads}}=8, d_{\text{head}}=256$):
  $$2 \times 48 \times 8 \times 256 \times 2 = \mathbf{393,216\text{ bytes/token}} \approx 0.375\text{ MB/token}$$
- **Qwen-3-32B** ($n_{\text{layers}}=64, n_{\text{kv\_heads}}=8, d_{\text{head}}=128$):
  $$2 \times 64 \times 8 \times 128 \times 2 = \mathbf{262,144\text{ bytes/token}} \approx 0.250\text{ MB/token}$$

#### KV Cache Requirement by Sequence Length (`MAX_MODEL_LEN`):
* **Standard Context (`32,768` tokens - Optimized Baseline & PPCR)**:
  * Gemma-4 sequence KV cache at max length: $32768 \times 0.375\text{ MB} = \mathbf{12.0\text{ GB}}$.
  * Qwen-3 sequence KV cache at max length: $32768 \times 0.250\text{ MB} = \mathbf{8.0\text{ GB}}$.
* **Extended Context (`131,072` tokens - Predicted Latency Routing / PLR)**:
  * Gemma-4 sequence KV cache at max length: $131072 \times 0.375\text{ MB} = \mathbf{48.0\text{ GB}}$.
  * Qwen-3 sequence KV cache at max length: $131072 \times 0.250\text{ MB} = \mathbf{32.0\text{ GB}}$.

---

## 2. Hardware Capacities & Usable Memory Boundaries

| Accelerator | Node Selector / Resource | Total Memory | Usable at `UTIL=0.95` | Memory Budget after FP8 Weights (`~39 GB`) |
| :--- | :--- | :---: | :---: | :---: |
| **NVIDIA H100** | `gpu-h100-80gb-x1` | **80 GB VRAM** | **76.0 GB** | **~37.0 GB** KV Cache Pool |
| **NVIDIA RTX Pro 6000** | `gpu-rtx-pro-6000-96gb-x1` | **96 GB VRAM** | **91.2 GB** | **~52.2 GB** KV Cache Pool |
| **Google TPU v6e** *(qwen3-32b-fp8 only)* | `tpu-v6e-2x2` (4 chips) | **128 GB HBM** *(32 GB/chip)* | **121.6 GB** | **~82.6 GB** Total KV Cache Pool (`20.65 GB`/chip at `TP=4`) |

> [!NOTE]
> **TPU v6e GKE Trillium Slicing Rule:** In Google Kubernetes Engine (GKE), the smallest deployable Trillium (`v6e`) node pool slice is `tpu-v6e-2x2`, which contains **4 chips** (128 GB HBM total). While 2 chips (64 GB) could technically hold 39 GB of weights, GKE scheduling mandates allocating the 4-chip pod, making `TENSOR_PARALLEL_SIZE=4` the optimal configuration for `qwen/qwen3-32b-fp8` that distributes weights (`9.75 GB`/chip) and maximizes the KV cache pool (`82.6 GB` total). Gemma 4 FP8 is unsupported on TPU due to missing XLA dequantization kernels for fused parallel linear layers.

---

## 3. The 3×3 Specification × Accelerator Sizing Matrix

The following table summarizes the configuration values and mathematical justification for every combination of the 3 strategy specifications and hardware accelerators for `qwen/qwen3-32b-fp8` and `redhatai/gemma-4-31b-it-fp8-block`:

| Strategy Spec (`--spec`) | Accelerator | `TP` | `MAX_MODEL_LEN` | `GPU_MEMORY_UTILIZATION` | Usable KV Cache Pool | Mathematical & Architectural Justification |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **`llmd-optimized-baseline`**<br>*(Standard baseline throughput)* | **GPU (H100)** | **1** | `32768` | `0.95` | **37.0 GB** | **Fits on 1 GPU.** Leaves 37 GB VRAM for KV cache, supporting ~3 to 4 concurrent full-length (`32k`) sequences per replica without tensor parallelism overhead. |
| | **GPU (RTX Pro 6000)** | **1** | `32768` | `0.95` | **52.2 GB** | **Fits on 1 GPU.** The 96 GB VRAM capacity leaves a generous 52.2 GB KV cache pool, supporting ~4 to 6 concurrent full-length (`32k`) sequences. |
| | **TPU (v6e) - Qwen FP8** | **4** | `32768` | `0.95` | **82.6 GB** *(total)* | **4 Chips (`2x2` slice).** Distributes weight footprint to `9.75 GB/chip`. Provides 82.6 GB total KV cache across 4 chips for high-concurrency batching. *(Qwen 3 FP8 only)* |
| **`llmd-precise-prefix-cache-routing`**<br>*(Multi-turn / Shared-prefix caching)* | **GPU (H100)** | **1** | `32768` | `0.95` | **37.0 GB** | **Fits on 1 GPU.** High `0.95` utilization is critical to keep the maximum number of KV cache blocks resident in memory for prefix routing cache hit rates. |
| | **GPU (RTX Pro 6000)** | **1** | `32768` | `0.95` | **52.2 GB** | **Fits on 1 GPU.** The 52.2 GB cache pool allows storing tens of thousands of prefix tokens (system prompts, multi-turn chat history) across active requests. |
| | **TPU (v6e) - Qwen FP8** | **4** | `32768` | `0.95` | **82.6 GB** *(total)* | **4 Chips (`2x2` slice).** High HBM headroom across 4 chips ensures prefix caching routing can cache shared context histories across TPU replicas. *(Qwen 3 FP8 only)* |
| **`llmd-predicted-latency-routing`**<br>*(Dynamic latency / Long-context routing)* | **GPU (H100)** | **1** | `131072` | `0.95` | **37.0 GB** | **Fits on 1 GPU with Chunked Prefill.** A single maximum 131k sequence takes 32–48 GB; however, PLR distributes heterogeneous workloads using chunked prefill (`--enable-chunked-prefill`) and batched token limits (`--max-num-batched-tokens=2048/4096`), preventing OOMs while serving 131k context. |
| | **GPU (RTX Pro 6000)** | **1** | `131072` | `0.95` | **52.2 GB** | **Fits on 1 GPU with ample long-context headroom.** The 96 GB RTX Pro 6000 card can hold a full 131k sequence (`32–48 GB KV cache`) plus additional concurrent decode requests. |
| | **TPU (v6e) - Qwen FP8** | **4** | `131072` | `0.95` | **82.6 GB** *(total)* | **4 Chips (`2x2` slice).** The 82.6 GB combined HBM pool comfortably accommodates multiple simultaneous 131k long-context requests under PLR routing. *(Qwen 3 FP8 only)* |

---

## 4. Key Takeaways for FP8 Deployment

1. **FP8 Halves Weight Memory, Not KV Cache Memory:**
   - While FP8 block quantization cuts model weight memory from ~65 GB (BF16) down to **~39 GB**, attention KV cache tensors remain in 16-bit precision by default. Thus, context length scaling (`MAX_MODEL_LEN`) impacts KV cache demand identically to BF16 models.
2. **Why `TP=1` is Optimal for GPUs:**
   - Because `39 GB` weights + runtime overhead (`<40 GB`) is well under the capacity of both H100 (`80 GB`) and RTX Pro 6000 (`96 GB`), tensor parallelism is unnecessary on GPUs. Avoiding TP=2 eliminates inter-GPU NVLink/PCIe communication overhead, maximizing throughput per dollar.
3. **Why `TP=4` is Mandatory for TPU v6e (`qwen/qwen3-32b-fp8`):**
   - GKE Trillium (`v6e`) node pools enforce a minimum topology slice of `2x2` (4 chips). Setting `TENSOR_PARALLEL_SIZE=4` aligns with the physical pod allocation, distributing weights across all 4 chips and unlocking the full `128 GB` HBM pool. *(Note: Gemma 4 FP8 is not supported on TPU v6e due to missing XLA dequantization kernels for fused parallel linear layers).*
