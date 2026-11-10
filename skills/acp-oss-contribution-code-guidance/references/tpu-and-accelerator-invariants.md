# GKE TPU/GPU Accelerator & `llm-d` Invariants (`I-x`, `P-x`, `Q-x`)

This reference holds the GKE/Kustomize deployment invariants (`I-1`–`I-10`) for
`accelerated-platforms` overlays, and the serving-evidence rules (`P-3`, `P-4`,
`Q-3`, `Q-6`) for PRs that change serving behavior.

---

## 1. GKE & Kustomize Overlay Invariants (`I-1` – `I-10`)

Whenever authoring or reviewing Kustomize overlays under
`platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/`, verify
every invariant below against the upstream `llm-d` base
(`github.com/llm-d/llm-d//guides/...?ref=v1.0.0`) and against the rendered
output of `kubectl kustomize`.

### I-1: Node Memory & CPU Sizing vs Upstream TPU Base (`[BLOCKER]` if violated)

- **Mechanism**: The upstream `llm-d` TPU v6 bases
  (`guides/<guide>/modelserver/tpu/v6/vllm/base/patch-vllm.yaml`, layered over
  `guides/recipes/modelserver/base/single-host/default/decode-deployment.yaml`)
  are sized for 8-chip `ct6e-standard-8t` (`2x4`) nodes. They set
  `memory: 256Gi` and `google.com/tpu: 8` in both `requests` and `limits`, plus
  `requests.cpu: "64"` with no CPU limit.
- **Hazard**: When an ACP overlay targets the 4-chip `tpu-v6e-2x2`
  (`ct6e-standard-4t`) ComputeClass and only patches the chip count, Kustomize
  strategic merge keeps `memory: 256Gi` and `cpu: "64"` from the upstream base,
  which is more than the node can allocate. Every pod stays `Pending`
  (`0/X nodes are available: Insufficient memory`).
- **Rule**: Any patch that changes the chip count MUST also override
  `resources.requests` and `resources.limits` for `memory` and `google.com/tpu`,
  plus `resources.requests.cpu` (and `resources.limits.cpu` only if the upstream
  base sets one, as the GPU bases do). The TPU overlays on `main` ship these
  values:

  | Topology | ComputeClass  | Chips | Shipped `requests.cpu` / `memory` | Example (`kubernetes-manifests/online-inference-tpu/`)                 |
  | :------- | :------------ | :---- | :-------------------------------- | :--------------------------------------------------------------------- |
  | `2x2`    | `tpu-v6e-2x2` | 4     | `"32"` / `128Gi`                  | `llmd-optimized-baseline/vllm/v6e-qwen3-32b/patch-resources.yaml`      |
  | `2x4`    | `tpu-v6e-2x4` | 8     | `"64"` / `256Gi`                  | `llmd-optimized-baseline/vllm/v6e-gemma-4-31b-it/patch-resources.yaml` |

### I-2: TPU `nodeSelector` Replacement Trap (`[BLOCKER]` if violated)

- **Mechanism**: The upstream `llm-d` TPU bases set
  `cloud.google.com/gke-tpu-accelerator: tpu-v6e-slice` and
  `cloud.google.com/gke-tpu-topology: "2x4"` on
  `spec.template.spec.nodeSelector`.
- **Hazard**: If an ACP overlay uses `$patch: replace` on `nodeSelector` to set
  only `cloud.google.com/compute-class: tpu-v6e-2x2`, it wipes out the
  `gke-tpu-accelerator` and `gke-tpu-topology` labels. GKE admission validation
  rejects multi-chip TPU pods (`google.com/tpu > 1`) that don't carry both
  labels on the pod spec.
- **Rule**: Whenever using `$patch: replace` on `nodeSelector` for multi-chip
  TPU workloads, include all three labels, as every TPU
  `patch-nodeselector.yaml` on `main` does:
  ```yaml
  nodeSelector:
    $patch: replace
    cloud.google.com/compute-class: tpu-v6e-2x2
    cloud.google.com/gke-tpu-accelerator: tpu-v6e-slice
    cloud.google.com/gke-tpu-topology: 2x2
  ```

### I-3: Kubernetes `env` vs `envFrom` & `HF_HOME` Volume Alignment (`[HIGH]`)

- **Mechanism**: In Kubernetes, explicit `container.env` entries always override
  keys imported via `container.envFrom` (`configMapRef: runtime`). The upstream
  `llm-d` `v1.0.0` TPU bases mount their cache volumes at different paths:

  | Upstream TPU guide             | Cache mounts                                                                                     | `HF_HOME` in upstream `container.env` | ACP `runtime.env` `HF_HOME` |
  | :----------------------------- | :----------------------------------------------------------------------------------------------- | :------------------------------------ | :-------------------------- |
  | `optimized-baseline`           | `torch-compile-cache` at `/.cache`                                                               | not set                               | `/.cache/huggingface`       |
  | `predicted-latency-routing`    | inherits `optimized-baseline`                                                                    | not set                               | `/.cache/huggingface`       |
  | `precise-prefix-cache-routing` | `torch-compile-cache` at `/root/.cache`                                                          | not set                               | `/root/.cache/huggingface`  |
  | `pd-disaggregation`            | `torch-compile-cache` at `/.cache`; `huggingface-cache` (hostPath) at `/root/.cache/huggingface` | `/root/.cache/huggingface`            | `/root/.cache/huggingface`  |

- **Hazard**: Setting `HF_HOME` in the `runtime` ConfigMap has no effect when
  `container.env` already defines it (as in `pd-disaggregation`). Pointing
  `HF_HOME` at a path with no matching `volumeMount` writes multi-tens-of-GB
  checkpoints into the container's writable layer and can trigger node
  disk-pressure evictions.
- **Rule**: Verify with `kubectl kustomize` that the effective `HF_HOME`
  (`container.env` first, then `runtime` `envFrom`) sits under a rendered
  `mountPath`, and that a `runtime.env` value isn't silently shadowed.

### I-4: Graceful Shutdown Timeout Budget (`[MEDIUM]`)

- **Mechanism**: Two components set `terminationGracePeriodSeconds: 75` and a
  `preStop` hook of `sleep 15` (for GKE Gateway / Envoy endpoint drain
  propagation):
  - upstream `llm-d`'s
    `guides/recipes/modelserver/components/graceful-shutdown`, which the `llm-d`
    guide bases include and which patches `Deployment`, `LeaderWorkerSet`, and
    `DisaggregatedSet`. Every `llmd-<guide>` overlay on `main` inherits it
    through its `../base`. (The older `online-inference-gpu/llmd/` family is not
    built on the upstream guides; check its rendered output directly.)
  - ACP's
    `kubernetes-manifests/online-inference-gpu/components/graceful-shutdown`,
    which patches `Deployment` only and is included by the `trtllm` and
    `dynamo-trtllm` overlays, not by any `llm-d` overlay.
- **Rule**: Every `vllm serve` overlay that inherits either component MUST pass
  `--shutdown-timeout=45` (in `patch-vllm-args.yaml`, or
  `patch-{prefill,decode}-vllm-args.yaml` for P/D) so in-flight requests finish
  draining within `15s (preStop) + 45s (vLLM) = 60s < 75s` before `SIGKILL`.
  Check the rendered `terminationGracePeriodSeconds`, not the component name.

### I-5: Fixed-Size TPU Node Pool Rollout Deadlock in `DisaggregatedSet` (`[HIGH]`)

- **Mechanism**: Upstream `llm-d`'s P/D base
  (`guides/recipes/modelserver/base/single-host/pd-disaggregatedset/base/disaggregatedset.yaml`)
  sets `maxSurge: 1, maxUnavailable: 0` on the `decode` role, and
  `maxSurge: 0, maxUnavailable: 1` on `prefill`.
- **Hazard**: When Terraform pins TPU node pools (`min_nodes == max_nodes`) or
  physical TPU reservations are fully allocated, `maxSurge: 1` requires a spare
  TPU slice before terminating the old replica, deadlocking rollouts on
  `Insufficient google.com/tpu`. Upstream's TPU `Deployment` bases avoid the
  same deadlock with `strategy: type: Recreate`; keep that in overlays.
- **Rule**: Explicitly configure `rolloutStrategy` on both `prefill` and
  `decode` roles in `DisaggregatedSet` overlays, as
  `llmd-pd-disaggregation/vllm/v6e-qwen3-32b/patch-deployment-strategy.yaml`
  does on `main`:
  ```yaml
  rolloutStrategy:
    rollingUpdateConfiguration:
      maxSurge: 0
      maxUnavailable: 1
  ```

### I-6: `TPUConnector` `kv_role` Directionality in P/D Disaggregation (`[HIGH]`)

- **Mechanism**: In `vllm-torchtpu` / `llm-d` P/D disaggregation using
  `TPUConnector`, the prefill tier is the KV producer and the decode tier is the
  KV consumer.
- **Hazard**: vLLM defines the roles as overlapping sets, so `kv_both` sets
  `is_kv_producer=True`. `TPUConnector` collapses the roles into
  `self.is_producer = self.config.is_kv_producer` and returns `(0, False)` from
  `get_num_new_matched_tokens` whenever `self.is_producer` is true, without
  consulting `is_kv_consumer`. Under `kv_both`, decode never pulls the KV blocks
  prefill staged (they expire with `KV transfer timeout`), and decode silently
  recomputes prefill. Both pods report ready and answers stay correct, so the
  failure is invisible without metrics. See the comment in
  `llmd-pd-disaggregation/vllm/v6e-qwen3-32b/patch-decode-vllm-args.yaml`.
- **Rule**: Set `"kv_role": "kv_producer"` on `prefill`,
  `"kv_role": "kv_consumer"` on `decode`, and `"kv_ip": "$(POD_IP)"` on both,
  matching the shipped decode value:
  ```json
  {"kv_connector":"TPUConnector","kv_connector_module_path":"vllm_torchtpu.distributed.kv_transfer.tpu_connector","kv_role":"kv_consumer","kv_ip":"$(POD_IP)"}
  ```

### I-7: Shared Memory (`/dev/shm`) & `TPU_KV_SHM_POOL_GB` Headroom (`[MEDIUM]`)

- **Mechanism**: `TPUConnector` stages KV blocks in a host shared-memory pool
  sized by `TPU_KV_SHM_POOL_GB`. Upstream `llm-d` `v1.0.0` TPU P/D sets
  `TPU_KV_SHM_POOL_GB: "8"` (the Torch TPU default is 128 GB) and a
  `medium: Memory` `/dev/shm` `emptyDir` with `sizeLimit: 100Gi`
  (`guides/pd-disaggregation/modelserver/tpu/{common,v6/vllm/base}/patch-decode.yaml`).
  ACP's P/D overlay inherits both values.
- **Rule**: Kubernetes charges `medium: Memory` usage against the container's
  memory cgroup limit. When changing `TPU_KV_SHM_POOL_GB`, the `/dev/shm`
  `sizeLimit`, or `resources.limits.memory` (`256Gi` on `2x4`, `128Gi` on
  `2x2`), keep the pool below the `/dev/shm` size and leave room in the memory
  limit for `/dev/shm`, model loading buffers (for example
  `RUNAI_STREAMER_MEMORY_LIMIT`), and host runtime memory without triggering
  `OOMKilled` (exit code 137).

### I-8: Pod Memory Includes Memory-Backed Volumes & Sidecars (`[HIGH]`)

- **Rule**: Total pod memory is the sum of container limits, every
  `emptyDir: {medium: Memory}` usage (charged to the container cgroup), and
  injected sidecars (for example the `gke-gcsfuse/memory-limit` annotation).
  Every memory-backed `emptyDir` an overlay adds must set `sizeLimit`, and the
  total must stay below node allocatable with headroom (for example `175.4 GiB`
  allocatable on `g4-standard-48`, as measured in
  `docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md`).
  The upstream TPU `optimized-baseline` `dshm` volume has no `sizeLimit`, so it
  is bounded only by the container memory limit.

### I-9: Multi-Region / Dynamo Load Balancer Readiness & NEG Teardown (`[HIGH]`)

- **Readiness Health Check Target**: Load balancer health checks for Dynamo
  inference workloads must target model readiness (`/v1/models/<model>/ready`),
  never the frontend `/health` endpoint (which returns healthy before backend
  workers finish loading the model).
- **Frontend Service & NEG Teardown Order**: Always run
  `platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh apply`
  without the backend (or `global_lb.sh destroy`) **before** deleting an
  attached frontend `Service`. Deleting the `Service` while the backend service
  still references its `ServiceNetworkEndpointGroup` (NEG) leaves the NEG stuck
  in a terminating state.

### I-10: No Package Installs at Container Start (`[HIGH]`)

- **Hazard**: A `pip install`, `apt-get install`, or `curl | bash` in a
  container `command`/`args` makes every pod start depend on a package index,
  adds minutes to cold start and rollouts, and pulls code nobody reviewed at
  runtime. Version pins without hashes don't stop a compromised or yanked
  package.
- **Rule**: Shipped manifests don't install packages at startup. Use an image
  that already contains the dependency (an upstream release or a repository
  image under `container-images/`). If an upstream image is missing a
  dependency, cite the upstream issue or fix and treat any temporary shim as a
  `R-3.4` override with a removal condition, pinned with
  `pip install --require-hashes`.
- **Known exception on `main`**: the TPU P/D overlay
  (`llmd-pd-disaggregation/vllm/v6e-qwen3-32b/patch-{prefill,decode}-vllm-args.yaml`)
  installs `runai-model-streamer[gcs]==0.17.1` at startup because
  `docker.io/vllm/vllm-torchtpu:v0.29.0` doesn't bundle it. Don't copy that
  pattern into new overlays; remove it once the image ships the dependency.

---

## 2. Serving Evidence for Performance & Quantization Changes (`P-x`, `Q-x`)

These IDs come from `vllm-torchtpu`'s
`docs/developers_guide/optimization_best_practices.md`. ACP keeps only the rules
that apply to serving configuration, reworded for overlays and benchmarks; the
other `P-x` and `Q-x` numbers cover kernel and model code in `vllm-torchtpu` and
aren't used here. For `vllm-torchtpu` changes, follow that document directly.

Produce the numbers with the repository's benchmark tooling
(`skills/llm-d-benchmarking`, `kubernetes-manifests/inference-perf-bench/`, or
`kubernetes-manifests/k6-benchmark/`) and include the exact commands in the PR
description (`R-8.10`).

- **P-3 — Quantify Both Throughput and Latency**: Changes to routing, scheduler
  or chunked-prefill flags, `--max-num-seqs`, `--max-num-batched-tokens`, or
  replica counts report both throughput (tokens/s) and latency (TTFT, TPOT, ITL)
  across workload profiles, before and after, on the same hardware.
- **P-4 — Compare Parallelism at a Matched Token Budget**: When comparing
  data-parallel replicas against a larger tensor-parallel size (for example 2 ×
  TP4 on `2x2` vs 1 × TP8 on `2x4`), hold the total token budget equal
  (`per_replica_budget * replicas`) and state the chip count of each side.
- **Q-3 — Numeric and Performance Validation for Quantized Overlays**: A PR that
  adds or changes a quantized overlay (for example the `*-fp8` or `*-fp8-block`
  overlays) includes a before/after accuracy eval (for example MMLU or GSM8K)
  against the unquantized overlay and a serving benchmark on the same hardware,
  in separate **Numeric validation** and **Performance validation** sections
  with exact reproduction commands.
- **Q-6 — Accelerator Memory Validation**: A change to the model, quantization,
  `--max-model-len`, tensor-parallel size, or weight-loading path (for example
  `--load-format=runai_streamer`) reports before/after accelerator memory use
  (HBM on TPU, GPU memory on GPU), the KV-cache capacity vLLM logs at startup,
  and model load time. Resident weight growth directly shrinks the KV cache.
