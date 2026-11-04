# GKE TPU/GPU Accelerator & `llm-d` Invariants (`I-x`, `P-x`, `Q-x`)

This reference combines the GKE/Kustomize deployment invariants (`I-1`–`I-7`)
established in `accelerated-platforms` with the TPU performance (`P-1`–`P-17`)
and quantization (`Q-1`–`Q-7`) standards from `vllm-torchtpu`'s
`docs/developers_guide/optimization_best_practices.md`.

---

## 1. GKE & Kustomize Overlay Invariants (`I-1` – `I-7`)

Whenever authoring or reviewing Kustomize overlays under
`platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/` or
`kubernetes-manifests/`, verify every invariant below against the upstream
`llm-d` base (`github.com/llm-d/llm-d//guides/...`).

### I-1: Node Memory & CPU Sizing vs Upstream TPU Base (`[BLOCKER]` if violated)

- **Mechanism**: Upstream `llm-d` TPU v6 base manifests
  (`.../tpu/v6/vllm/base/deployment.yaml`) are sized for 8-chip
  `ct6e-standard-8t` (`2x4`) nodes and request `memory: 256Gi`, `cpu: "64"`, and
  `google.com/tpu: "8"`.
- **Hazard**: When an ACP overlay targets a 4-chip `tpu-v6e-2x2`
  (`ct6e-standard-4t`) ComputeClass (112 vCPUs, ~167 GiB total node memory,
  ~150–155 GiB allocatable) and only patches `google.com/tpu: "4"` without
  overriding `memory` and `cpu`, Kustomize strategic merge retains
  `memory: 256Gi` from the upstream base. Every pod stays permanently `Pending`
  (`0/X nodes are available: Insufficient memory`).
- **Rule**: Any patch changing `google.com/tpu` chip count MUST explicitly
  override `resources.requests` and `resources.limits` for `memory` and `cpu` to
  fit the target machine type's allocatable capacity:

  | TPU v6e Topology | GCE Machine Type   | Chips | Node vCPUs / RAM                     | Recommended Pod `requests` & `limits`               |
  | :--------------- | :----------------- | :---- | :----------------------------------- | :-------------------------------------------------- |
  | `1x1`            | `ct6e-standard-1t` | 1     | 28 vCPU / 44 GiB                     | `cpu: "16"`, `memory: 34Gi`, `google.com/tpu: "1"`  |
  | `2x2`            | `ct6e-standard-4t` | 4     | 112 vCPU / 176 GiB (~167 GiB usable) | `cpu: "32"`, `memory: 140Gi`, `google.com/tpu: "4"` |
  | `2x4`            | `ct6e-standard-8t` | 8     | 224 vCPU / 352 GiB (~334 GiB usable) | `cpu: "64"`, `memory: 256Gi`, `google.com/tpu: "8"` |

### I-2: GKE Warden `nodeSelector` Replacement Trap (`[BLOCKER]` if violated)

- **Mechanism**: Upstream `llm-d` TPU bases set
  `cloud.google.com/gke-tpu-accelerator: tpu-v6e-slice` and
  `cloud.google.com/gke-tpu-topology: 2x4` on `spec.template.spec.nodeSelector`.
- **Hazard**: If an ACP overlay uses `$patch: replace` on `nodeSelector` to set
  only `cloud.google.com/compute-class: tpu-v6e-2x2`, it wipes out the
  `gke-tpu-accelerator` and `gke-tpu-topology` labels. GKE Warden's admission
  webhook (`tpu-accelerator-topology-constraints`) immediately rejects any pod
  requesting `google.com/tpu > 1` that lacks both labels on the pod spec itself.
- **Rule**: Whenever using `$patch: replace` on `nodeSelector` for multi-chip
  TPU workloads, always include all three labels:
  ```yaml
  nodeSelector:
    $patch: replace
    cloud.google.com/compute-class: tpu-v6e-2x2
    cloud.google.com/gke-tpu-accelerator: tpu-v6e-slice
    cloud.google.com/gke-tpu-topology: 2x2
  ```

### I-3: Kubernetes `env` vs `envFrom` & `HF_HOME` Volume Alignment (`[HIGH]`)

- **Mechanism**: In Kubernetes, explicit `container.env` entries always override
  keys imported via `container.envFrom` (`configMapRef: runtime`).
- **Hazard**: If the upstream `llm-d` base mounts the `model-cache` volume at
  `/root/.cache` and sets `HF_HOME: /root/.cache` in `container.env`, patching
  the `runtime` ConfigMap with `HF_HOME: /.cache` has zero effect on `HF_HOME`,
  or—if `HF_HOME` is pointed at `/.cache` without a matching
  `volumeMount`—causes multi-tens-of-GB HuggingFace checkpoints to download into
  container rootfs ephemeral storage and trigger node disk-pressure evictions.
- **Rule**: Verify with `kubectl kustomize` that `HF_HOME`, `VLLM_CACHE_ROOT`,
  and `XDG_CACHE_HOME` in the rendered `container.env` match the exact
  `mountPath` of the persistent/cache volume (`model-cache`).

### I-4: Graceful Shutdown Timeout Budget (`[MEDIUM]`)

- **Mechanism**: The `components/graceful-shutdown` Kustomize component sets
  `terminationGracePeriodSeconds: 75` and a `preStop` hook of `sleep 15` (for
  GKE Gateway / envoy endpoint drain propagation).
- **Rule**: Every overlay that includes `../../../components/graceful-shutdown`
  MUST pass `--shutdown-timeout=45` to `vllm serve` in `patch-vllm-args.yaml` so
  in-flight requests finish draining within
  `15s (preStop) + 45s (vLLM) = 60s < 75s` before `SIGKILL`.

### I-5: Fixed-Size TPU Node Pool Rollout Deadlock in `DisaggregatedSet` (`[HIGH]`)

- **Mechanism**: `DisaggregatedSet` (and `LeaderWorkerSet` v1.0.0+) defaults to
  rolling updates with `maxSurge: 1, maxUnavailable: 0`.
- **Hazard**: When Terraform pins TPU node pools (`min_nodes == max_nodes`) or
  physical TPU reservations are fully allocated, `maxSurge: 1` requires a spare
  TPU slice before terminating the old replica, deadlocking rollouts on
  `Insufficient google.com/tpu`.
- **Rule**: Explicitly configure `rolloutStrategy` on both `prefill` and
  `decode` roles in `DisaggregatedSet` overlays:
  ```yaml
  rolloutStrategy:
    type: RollingUpdate
    rollingUpdateConfiguration:
      maxSurge: 0
      maxUnavailable: 1
  ```

### I-6: `TPUConnector` `kv_role` Directionality in P/D Disaggregation (`[HIGH]`)

- **Mechanism**: In `vllm-torchtpu` / `llm-d` P/D disaggregation using
  `TPUConnector`, the prefill tier is the KV producer and the decode tier is the
  KV consumer.
- **Hazard**: Setting `"kv_role": "kv_both"` on the decode tier's
  `--kv-transfer-config` disables `skip_prefill_on_decode` (`is_kv_consumer`) in
  vLLM when `kv_connector_extra_config` lacks P2P peer metadata, causing the
  decode tier to silently recompute prefill on decode TPUs and negating P/D
  disaggregation.
- **Rule**: Always set `"kv_role": "kv_producer"` on `prefill` and
  `"kv_role": "kv_consumer"` on `decode`:
  ```json
  {"kv_connector":"TPUConnector","kv_connector_module_path":"vllm_torchtpu.distributed.kv_transfer.tpu_connector","kv_role":"kv_consumer"}
  ```

### I-7: Shared Memory (`/dev/shm`) & `TPU_KV_SHM_POOL_GB` Headroom (`[MEDIUM]`)

- **Rule**: When configuring `TPU_KV_SHM_POOL_GB` (e.g., `32` GiB) alongside a
  memory-backed `/dev/shm` `emptyDir` (`medium: Memory, sizeLimit: 64Gi`),
  remember that Kubernetes charges `medium: Memory` usage against the
  container's memory cgroup limit. Ensure `resources.limits.memory` (e.g.,
  `140Gi` on `2x2` or `256Gi` on `2x4`) has sufficient headroom for `/dev/shm` +
  `TPU_KV_SHM_POOL_GB`
  - PyTorch/XLA host buffers without triggering `OOMKilled` (exit code 137).

---

## 2. TPU Performance Best Practices (`P-1` – `P-17`)

From `vllm-torchtpu`'s `docs/developers_guide/optimization_best_practices.md`:

### 2.1 Evidence Standard: Traces, Not Guesses

- **P-1 — XProf Traces Are the Unit of Evidence**: End-to-end throughput numbers
  alone do not prove a kernel/runtime optimization. Attach an XProf trace plus a
  mechanism explanation under realistic large-batch conditions.
- **P-2 — Prove Compiler Impact From HLO Dumps**: Verify fusions and layouts
  from compiled HLO dumps or graph viewer—never guess what XLA did.
- **P-3 — Quantify Both Throughput and Latency**: Scheduler, chunked-prefill,
  and routing changes must report both throughput (tokens/s) and latency (TTFT,
  TPOT, ITL) across workload profiles.
- **P-4 — Compare Parallelism at Matched Global Token Budget**: Compare DP vs TP
  at equal total tokens across ranks (`per_rank_budget * num_ranks`).

### 2.2 Let the Compiler Work & Reason at the Hardware Level

- **P-5**: Shard via `jit` signatures (`in_shardings`/`out_shardings`) and the
  global mesh context rather than manual reshard helpers.
- **P-6**: Cast to `bf16` before collectives when numerics permit (and verify
  per `Q-3`).
- **P-7 (VREG Lifetime)**: Quantize per-loop-iteration to avoid register spills;
  write directly to `out_ref` on the final step rather than scratch-then-copy.
- **P-8 (HBM Traffic)**: Avoid redundant zero-initialization; fuse ops to
  eliminate HBM round-trips.
- **P-9 (MXU Dtype Throughput)**: `w8a16` beats `w16a16`—never silently upcast
  weights or activations to 16-bit compute; keep 4-bit weights on the `fp8` path
  (`u4 -> fp8`, not `u4 -> bf16`); unpack packed formats with bit shifts/masks.
- **P-10 (SMEM Headroom)**: Never allocate maximum SMEM; leave compiler
  headroom.
- **P-11 (DMA Pipelining)**: Small DMAs are latency-bound; never call
  `start(); wait()` back-to-back—pipeline with double buffering.
- **P-12 (Layout Preprocessing)**: Fix interleaved splits by preprocessing
  weights once at load time rather than calling `jnp.repeat` inside a kernel.
- **P-13 (No Optimization Barriers in Hot Loops)**: Avoid `jax.named_scope` or
  `lax.cond` inside the main kernel loop.

### 2.3 Weight Loading, Cost Models & Tuned Tables

- **P-14 — Heavy Tensor Work Belongs at Weight-Loading Time**: Dequantization,
  scale broadcasting, KV-head replication, and weight transposes happen once in
  `process_weights_after_loading`.
- **P-15 — Compute Thresholds From Cost Models**: Derive split crossovers from
  DMA latency vs bandwidth and VMEM budgets per TPU generation.
- **P-16 — Tuned Block Sizes Live in Python Tables**: Store tuned block sizes in
  `kernels/*/tuned_block_sizes.py` imported as Python data (never JSON via
  `__file__`), logging `warning_once` with the full lookup key on misses.
- **P-17 — Gate Callers on Explicit Kernel Envelopes**: Check mesh rank, EP-only
  constraints, dtype packing, and JAX version bounds via `is_supported_by_*`.

---

## 3. Quantization & HBM Validation Rules (`Q-1` – `Q-7`)

- **Q-1 — Generic Subchannel Machinery**: Parameterize formats by
  `(block_size, weight_dtype, scale_dtype)` rather than cloning per-format
  forks.
- **Q-2 — Standard Quant Method Recipe**: Config class -> linear method ->
  `process_weights_after_loading` -> `apply` -> unit test loading a real model.
- **Q-3 — Non-Negotiable Numeric + Perf Verification**: Every quantization PR
  includes before/after accuracy eval (e.g., MMLU / GSM8K) AND serving benchmark
  on the identical rig with exact reproduction commands in separate **Numeric
  validation** and **Performance validation** PR sections.
- **Q-4 — Quality-Neutral Requantization**: Allowed at load time when proven
  quality-neutral; expose approximate modes behind an explicit option
  (`R-6.2c`).
- **Q-5 — Track Scale Tensors Independently**: Weight transpose does not imply
  scale transpose; assert on untested block granularities.
- **Q-6 — HBM Memory Validation (`total_hbm_used_gb`)**: Any weight-loading or
  model-level change must report before/after server HBM usage
  (`total_hbm_used_gb`) and load times on the largest checkpoint that fits the
  rig—resident HBM growth directly shrinks available KV cache.
- **Q-7 — Hardware-Driven Dtype & Stochastic Rounding**: State
  per-TPU-generation dtype support explicitly and use TPU-native stochastic
  rounding when requantizing at load time.
