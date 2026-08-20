---
name: llm-d-new-model-support
description: Provides instructions and best practices for adding a new LLM model (including FP8/quantized variants) to the llm-d GKE inference reference architecture and benchmarking stack.
version: 0.1.0
allowed-tools: kubectl gcloud kustomize python3
mcp-servers: []
---

# LLM-D New Model Support Skill

Follow these instructions to add support for a new LLM model (or a new quantized variant such as FP8 block quantization) across accelerators in the GKE `llm-d` inference reference architecture.

## 1. Sizing Requirements & Memory Footprint

Before creating deployment overlays, calculate the required memory footprint and Tensor Parallelism (`TENSOR_PARALLEL_SIZE`):

1. **Weight Memory Calculation (`w_size`)**:
   - The workload tuner (`tune_workload.py`) calculates weight memory as:
     `w_size = params * BYTES_BF16 * MEM_MULT`
     where `BYTES_BF16 = 2.0` and `MEM_MULT = 1.2` (1.2x runtime buffer multiplier).
   - **FP8 & Quantized Models**: For FP8 block quantized models, set the effective parameter size in `model_specs.json` to half of the nominal BF16 parameter count (e.g., `16.0` for a 32B FP8 model) so that `w_size = 16.0 * 2.0 * 1.2 = 38.40 GB`, accurately reflecting the quantized footprint plus runtime overhead.
2. **Tensor Parallelism (`TENSOR_PARALLEL_SIZE`)**:
   - Determine minimum required chips based on accelerator HBM/VRAM capacity:
     - `nvidia-h100`: 80 GB VRAM per card.
     - `nvidia-h200`: 141 GB VRAM per card.
     - `rtx-pro-6000`: 96 GB VRAM per card (`gpu-rtx-pro-6000-96gb-x1` node selector in GKE).
     - `v6e`: 32 GB HBM per chip. Note that GKE Trillium node pools require a minimum slice size of `tpu-v6e-2x2` (4 chips = 128 GB HBM).

## 2. Creating Kustomize Overlays

Create the target Kustomize overlay directories for each supported accelerator:

- **Directory Path Format**:
  `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-[gpu|tpu]/llmd-[spec]/vllm/[prefix]-[suffix]`
  - `[gpu|tpu]`: Use `tpu` for `v6e`, otherwise `gpu`.
  - `[spec]`: Target routing spec (e.g., `optimized-baseline`, `precise-prefix-cache-routing`, `predicted-latency-routing`).
  - `[prefix]`: Accelerator prefix (e.g., `rtx-pro-6000`, `v6e`).
  - `[suffix]`: Model identifier suffix (e.g., `gemma-4-31b-it-fp8-block`).

- **Required Overlay Files**:
  1. `kustomization.yaml`: Specify `nameSuffix: -[prefix]-[suffix]` and reference standard ConfigMap/ServiceAccount replacements.
  2. `runtime.env`: Define `APP_LABEL`, `GPU_MEMORY_UTILIZATION`, `MAX_MODEL_LEN`, `MODEL_ID`, `MODEL_NAME`, `TENSOR_PARALLEL_SIZE`, and `HF_HOME`.
  3. `patch-resources.yaml`: Define container CPU, memory, and accelerator limit/request values (`nvidia.com/gpu` or `google.com/tpu`).
  4. `patch-nodeselector.yaml`: Patch the pod `nodeSelector` with the target compute class (`cloud.google.com/compute-class`).
  5. `patch-vllm-args.yaml`: Specify vLLM arguments (`--model`, `--tensor-parallel-size`, `--gpu-memory-utilization`, `--served-model-name`).

### 2.1 Strategy Specification Considerations (`--spec`)

When configuring `runtime.env` and `patch-vllm-args.yaml`, adapt parameters based on the target `[spec]` strategy:

1. **`optimized-baseline` (Standard Inference)**:
   - **`MAX_MODEL_LEN`**: Set to standard sequence lengths (e.g., `32768`).
   - **`TENSOR_PARALLEL_SIZE`**: Minimum chips needed for model weights + standard KV cache (e.g., `TP=1` for FP8 31B on RTX Pro 6000; `TP=4` on TPU v6e).
   - **vLLM Arguments**: Default chunked prefill settings.
2. **`precise-prefix-cache-routing` (PPCR - Multi-turn / Cache-Aware)**:
   - **`MAX_MODEL_LEN`**: Standard sequence length (`32768`).
   - **`GPU_MEMORY_UTILIZATION`**: Maintain high utilization (`0.95`) to maximize available KV cache blocks so that prefix caching routing can cache shared system prompts and conversation history across replicas.
   - **vLLM Arguments**: Ensure prefix caching is enabled in vLLM (`--enable-prefix-caching`).
3. **`predicted-latency-routing` (PLR - Dynamic Latency / Long-Context Routing)**:
   - **`MAX_MODEL_LEN`**: Set to extended context lengths (e.g., `131072` for Gemma-4-31B / Qwen-3-32B) to support heterogeneous long-context workloads.
   - **`TENSOR_PARALLEL_SIZE` & KV Cache Impact**: Because a 4x larger `MAX_MODEL_LEN` (`131072`) requires 4x more KV cache memory per sequence, models with large weight footprints may experience KV cache exhaustion. If necessary, increase `TENSOR_PARALLEL_SIZE` (e.g., from `TP=1` to `TP=2` on GPUs, or higher on TPUs) or lower `--max-num-batched-tokens` to guarantee sufficient KV cache blocks for peak context lengths.
   - **vLLM Arguments**: Enable `--enable-chunked-prefill` and tune `--max-num-batched-tokens` so long-context prefill operations do not block concurrent decode requests.

## 3. Registering the Model in Tuner & Deploy Skills

1. **Workload Tuner (`llm-d-workload-tuner`)**:
   - Add the model spec to `${ACP_REPO_DIR}/skills/llm-d-workload-tuner/references/model_specs.json`:
     ```json
     "<model_id>": [<params_b>, <layers>, <kv_heads>, <head_dim>, "<suffix>"]
     ```
   - Verify optimal sizing with the workload tuner script:
     ```bash
     python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
       --perf-yaml <workload_profile> \
       --accelerator-type <accelerator> \
       --spec <spec> \
       --model <model_id>
     ```
2. **Deploy Stack Skill (`llm-d-deploy-stack`)**:
   - Add the new model ID to the allowed model list in `${ACP_REPO_DIR}/skills/llm-d-deploy-stack/SKILL.MD`.

## 4. Updating Reference Architecture Guides

Update the corresponding well-lit path documentation guide under `${ACP_REPO_DIR}/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/`:
- Add `<model_id>` to the valid model options list.
- Add an entry row to the accelerator compatibility table indicating supported accelerators (`✅` / `❌`).

## 5. Verification & Testing

- Validate all new Kustomize overlays using:
  ```bash
  kustomize build <path_to_overlay_dir> > /dev/null
  ```
- Review the generated YAML to ensure all container arguments, environment variables, resource limits, and node selectors are correctly patched.
