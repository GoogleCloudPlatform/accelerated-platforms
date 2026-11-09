# NVIDIA TensorRT-LLM and Nemotron-3 reference architecture on multi-region GKE

> [!IMPORTANT]
>
> Dynamic Landscape: The field of AI inference is experiencing continuous, rapid
> evolution. This document is regularly updated to reflect the latest products,
> features, and architectural patterns across Google Cloud, NVIDIA TensorRT-LLM,
> and Google Kubernetes Engine (GKE).
>
> Last Update: 2026-11-05 (YYYY-MM-DD)

This spoke guide builds on the
[Multi-region GKE inference foundation](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md)
to deploy **NVIDIA Nemotron-3** open-weight reasoning and tool-calling models
(`Nemotron-3-Nano-30B-A3B` in `NVFP4`, `FP8`, and `BF16`, and
`Nemotron-3-Super-120B-A12B-NVFP4`) on **NVIDIA TensorRT-LLM (`trtllm-serve`)**
across **NVIDIA RTX PRO 6000 Blackwell Server Edition (`g4-standard-48`, 96 GB
GDDR7, `SM120`)** GPUs.

Refer to the
[Multi-region GKE inference foundation](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md)
for multi-region capacity audits, CIDR allocation, `provision.sh --parallel` /
`teardown.sh --parallel`, Artifact Registry mirroring, HNS Cloud Storage
replication, and cross-region internal Application Load Balancer setup. For a
copy-paste live demo script, see the companion
[15-minute TensorRT-LLM Presenter Beat Sheet](/docs/platforms/gke/base/use-cases/inference-ref-arch/trtllm-poc-15min-demo-runbook.md).

---

## 1. Why TensorRT-LLM + NVIDIA Nemotron-3 + RTX PRO 6000 (`TP=1`)?

1. **Blackwell `NVFP4` fits models up to `120B` parameters on a single 96 GB GPU
   (`TP=1`)**:
   - **`g4-standard-48`** pairs `48` vCPUs and **`180 GiB` GCE VM memory**
     (`176.9 GiB` Kubernetes node capacity, `175.4 GiB` allocatable, `~43.8 GiB`
     ephemeral boot-disk storage) with
     `1× NVIDIA RTX PRO 6000 Blackwell Server Edition` (`96 GB` GDDR7,
     `94.97 GiB` physical VRAM, native `SM120` `NVFP4` and `FP8` Tensor Cores).
   - **`Nemotron-3-Nano-30B-A3B-NVFP4`** (`31.6B` total / `3.2B` active hybrid
     Mamba-2 + GQA + MoE, `18.03 GiB` checkpoint) uses **`20.01 GiB`** of VRAM
     for weights and CUDA context, leaving **`63.71 GiB`** (`13.44M` attention
     KV tokens + Mamba state pools) and reaching **`3,568.1 tok/s`** at
     concurrency `64` (**`+30.9%` higher throughput** than `FP8`'s
     `2,726.0 tok/s`).
   - **`Nemotron-3-Super-120B-A12B-NVFP4`** (`120.6B` total / `12.6B` active
     LatentMoE, `74.80 GiB` checkpoint) peaks at **`84.19 GiB` of VRAM** during
     Pass 1 memory profiling—exceeding an `80 GB` GPU's `79.1 GiB` usable VRAM
     by `5.1 GiB`, **yet fitting on `1× RTX PRO 6000` (`TP=1`)** with
     **`13.36 GiB` (`972,704` KV tokens)** of cache headroom and **`74.0 tok/s`
     single-stream** (`713.9 tok/s` at `c=32`).
2. **GKE Pod snapshots bypass `~121–132s` of Blackwell JIT & autotuning on
   scale-out**:
   - Even when weights load from RAM into VRAM in `5.8–7.6s` via
     `rank_striped_read_ahead`, `trtllm-serve` spends `~121–132s` running
     `sampling_module_prewarm` (`~46s`), `TRTLLM-Gen FMHA` `attention_jit`
     (`~16s`), `autotuner` (`~33s` across `90` `NVFP4`/MoE tactics), Mamba
     warmup (`~25s`), and CUDA graph capture (`[1..64]`).
   - Composing
     [`components/gke-pod-snapshot`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/components/gke-pod-snapshot)
     with regional Artifact Registry GCFS Image Streaming (`3.885s` pull for the
     `17.26 GB` image) restores a new `RTX PRO 6000` replica to `Ready` in
     **`23.0s`** and serves `/v1/chat/completions` in **`46.0s`** (`LOADING=0`,
     **`7.83×` faster** than an uncached `nvcr.io` cold start).

---

## 2. Summary of measured results on `NVIDIA RTX PRO 6000`

Measured across three GKE Autopilot clusters (`us-central1`, `europe-west2`,
`asia-southeast1`) using
`nvcr.io/nvidia/tensorrt-llm/release:1.4.0rc2@sha256:93a3eaf1fa574813d608a7147735134bcfbd06d18d1aa98e8ee0d5da09e51e3a`
on `g4-standard-48`:

| Lifecycle Stage / Metric                                       | Baseline (Unoptimized)                                                | TensorRT-LLM Reference Architecture                                                                                                         | Measured Impact                                                                           |
| -------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| **Container image pull (`17.26 GB` / `16.07 GiB` compressed)** | Direct pull from `nvcr.io`: **`178.4s – 182.9s`**                     | Regional Artifact Registry (`mirror_image_to_ar` in `152s`) + **GCFS Image Streaming**: **`3.885s`** on scale-out nodes                     | **`47.1×` faster** image pull on new nodes                                                |
| **Model staging (`Hugging Face -> HNS Cloud Storage`)**        | Workstation download + re-upload (`15–45 min`)                        | In-cluster `stage_hf_model` Job (`c4-standard-4-lssd`): **`101s`** (`Nano-30B NVFP4`), **`171s`** (`FP8`), **`383s`** (`Super-120B NVFP4`)  | Server-side `replicate_hf_model` copies across regions at `50–214 MiB/s`                  |
| **Weight read into VRAM (`Nano-30B NVFP4`, `18.03 GiB`)**      | Uncached sequential FUSE reads (`45–90s`)                             | Bounded RAM `gcsfuse` pre-warm (**`3.59s – 4.63s`**) + `rank_striped_read_ahead` (**`5.80s – 6.04s`**)                                      | **`~9.5s` end-to-end** from HNS Cloud Storage to VRAM                                     |
| **Weight read into VRAM (`Super-120B NVFP4`, `74.80 GiB`)**    | Requires `TP=2` on `80 GB` GPUs                                       | Fits on **`1× RTX PRO 6000` (`TP=1`)**; `rank_striped_read_ahead` loads `80.32 GB` from RAM in **`43.40s` (`1.85 GB/s`)**                   | **`50%` fewer GPUs** vs. `TP=2` `80 GB` deployments                                       |
| **Horizontal scale-out (`PodScheduled -> First HTTP 200`)**    | Cold `nvcr.io` pull + stream + `144.9s` init = **`360.4s`** (`6m00s`) | **GKE Pod Snapshot (`23.06 GiB`) + GCFS (`3.885s`)**: `Ready` in **`23.0s`**, `PodRestored` in **`45.0s`**, `First Response` in **`46.0s`** | **`7.83×` faster** than cold `nvcr.io` (`3.95×` faster than GCFS cold start; `LOADING=0`) |
| **Single-GPU serving throughput (`max_tokens=256`)**           | `Nano-30B FP8`: `2,726.0 tok/s` at `c=64` (`22.90 ms` TPOT)           | `Nano-30B NVFP4`: **`3,568.1 tok/s`** at `c=64` (`17.40 ms` TPOT; `239.4 tok/s` at `c=1`); `Super-120B NVFP4`: **`713.9 tok/s`** at `c=32`  | **`+30.9%` higher throughput** with Blackwell `NVFP4`                                     |

---

## 3. Composable Kustomize overlays & node memory sizing (`trtllm/`)

All six overlays live under
[`kubernetes-manifests/online-inference-gpu/trtllm/`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm)
and compose a single
[`trtllm/base`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm/base)
with
[`components/accelerators/rtx-pro-6000-x1`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/components/accelerators/rtx-pro-6000-x1),
[`components/graceful-shutdown`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/components/graceful-shutdown),
[`trtllm/components/runtime-bindings`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm/components/runtime-bindings),
and (for `-podsnapshot` variants)
[`components/gke-pod-snapshot`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/components/gke-pod-snapshot):

| Hugging Face Model ID (`MODEL_ID`)                   | Precision | Checkpoint  | Overlay Directory (`online-inference-gpu/trtllm/`)                     | Weight + Context VRAM              | `MambaHybridCacheManagerV2` Pool         | `MAX_SEQ_LEN` / `MAX_BATCH_SIZE` |
| ---------------------------------------------------- | --------- | ----------- | ---------------------------------------------------------------------- | ---------------------------------- | ---------------------------------------- | -------------------------------- |
| **`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4`**    | `NVFP4`   | `18.03 GiB` | `rtx-pro-6000-nvidia-nemotron-3-nano-30b-a3b-nvfp4` (+ `-podsnapshot`) | **`20.01 GiB`**                    | **`63.71 GiB`** (`13,437,376` KV tokens) | `65536` / `64`                   |
| **`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8`**      | `FP8`     | `30.44 GiB` | `rtx-pro-6000-nvidia-nemotron-3-nano-30b-a3b-fp8` (+ `-podsnapshot`)   | `~32.0 GiB`                        | `~51.7 GiB`                              | `65536` / `64`                   |
| **`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16`**     | `BF16`    | `~58.8 GiB` | `rtx-pro-6000-nvidia-nemotron-3-nano-30b-a3b-bf16`                     | `~60.5 GiB`                        | `~20.2 GiB`                              | `32768` / `64`                   |
| **`nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`** | `NVFP4`   | `74.80 GiB` | `rtx-pro-6000-nvidia-nemotron-3-super-120b-a12b-nvfp4`                 | **`70.81 GiB`** (`84.19 GiB` peak) | **`13.36 GiB`** (`972,704` KV tokens)    | `32768` / `32`                   |

> [!NOTE]
>
> **Why bounded RAM `gke-gcsfuse-cache` + Guaranteed QoS**: On `g4-standard-48`,
> default ephemeral boot-disk allocatable storage is `~43.8 GiB`, which cannot
> hold the `58.8 GiB` (`BF16`) or `74.8 GiB` (`Super-120B`) checkpoints.
> Standard overlays therefore bound `gke-gcsfuse-cache` (`medium: Memory` >
> `sizeLimit`) and set matching `requests == limits` on both the
> `gke-gcsfuse-sidecar` and `inference-server` containers so total Pod memory
> stays safely within `175.4 GiB` allocatable RAM without cgroup OOMs.
>
> **Hybrid Mamba-2 + Attention cache (`enable_block_reuse: false`)**: Nemotron-3
> interleaves recurrent Mamba-2 state pools with GQA KV pools in
> `MambaHybridCacheManagerV2`. Cross-request prefix block reuse is disabled in
> [`trtllm/base/extra-llm-api-config.yaml`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm/base/extra-llm-api-config.yaml)
> (`enable_block_reuse: false`), as required by TensorRT-LLM `1.4.0rc2`.

---

## 4. Deploy Path A (standard fast-start) & Path B (`-podsnapshot` fast-restore)

After provisioning your cluster(s) with `MIRROR_IMAGES` set to
`nvcr.io/nvidia/tensorrt-llm/release:1.4.0rc2@sha256:93a3eaf1fa574813d608a7147735134bcfbd06d18d1aa98e8ee0d5da09e51e3a=tensorrt-llm/release:1.4.0rc2`
and staging weights via `stage_hf_model` (see the
[foundation quick-start](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#quick-start-multi-region-provisioning-and-teardown)),
both deployment paths use the same
[`online-inference-gpu/trtllm/`](/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh)
test scripts and `TF_VAR_ira_online_gpu_trtllm_image_url`:

### Path A: Standard `trtllm` overlay (bounded RAM `gcsfuse` + `rank_striped_read_ahead`)

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
use_region "americas" "us-central1" 0

export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4"
export TF_VAR_ira_online_gpu_trtllm_image_url="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/tensorrt-llm/release:1.4.0rc2"

"${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
"${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_test.sh"
```

#### Measured cold-start breakdown across regions & models (Path A)

| Deployment & Region                            | Consumption Model | RAM `gcsfuse` Pre-Warm              | `rank_striped_read_ahead` (RAM -> VRAM) | Pass 1: `profiling_executor_creation` | Pass 2: `final_executor_creation` | Total `workers_ready` |
| ---------------------------------------------- | ----------------- | ----------------------------------- | --------------------------------------- | ------------------------------------- | --------------------------------- | --------------------- |
| **`Nano-30B-NVFP4` (`us-central1`)**           | `FLEX_START`      | **`4.13s`**                         | **`5.89s`**                             | `121.50s`                             | `3.63s`                           | **`132.52s`**         |
| **`Nano-30B-NVFP4` (`europe-west2`)**          | `STANDARD`        | **`3.59s`**                         | **`5.80s`**                             | `120.72s`                             | `3.68s`                           | **`131.74s`**         |
| **`Nano-30B-NVFP4` (`asia-southeast1`)**       | `SPOT`            | **`4.63s`**                         | **`6.04s`**                             | `121.71s`                             | `3.59s`                           | **`132.84s`**         |
| **`Nano-30B-FP8` (`europe-west2`)**            | `STANDARD`        | **`15.41s`**                        | **`5.59s`**                             | `122.85s`                             | `3.39s`                           | **`133.34s`**         |
| **`Super-120B-NVFP4` (`us-central1`, `TP=1`)** | `FLEX_START`      | `255.52s` _(incl. 1 GCS 503 retry)_ | **`43.40s`** (`1.85 GB/s`)              | `121.34s`                             | `2.82s`                           | **`171.31s`**         |

### Path B: Sub-minute horizontal restore with `TRTLLM_VARIANT_SUFFIX="-podsnapshot"`

Pass `TRTLLM_VARIANT_SUFFIX="-podsnapshot"` to select the `-podsnapshot`
overlays (`APP_LABEL=trtllm-snap-rtx6000-nemotron-3-nano-30b-nvfp4`).
`deployment_test.sh` waits for the initial cold start and `PodSnapshot`
`AllSnapshotsAvailable` (`~41s` upload for `23.06 GiB`), then runs
[`measure_restore.sh`](/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/measure_restore.sh)
to raise HPA `minReplicas` from `1` to `2` and verify `LOADING=0` on the
restored replica:

```shell
use_region "americas" "us-central1" 0
export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4"
export TRTLLM_VARIANT_SUFFIX="-podsnapshot"
export TF_VAR_ira_online_gpu_trtllm_image_url="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/tensorrt-llm/release:1.4.0rc2"

"${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
"${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_test.sh"
```

<!-- cspell:ignore plnwn -->

```text
POD (suffix)             NODE_AGE IMAGE                READY POD_RESTORED  FIRST_RESPONSE   LATENCY  LOADING
b-nvfp4-856985859d-plnwn    32.0s in 3.885s            23.0s        45.0s           46.0s     22.8s        0
```

`measure_restore.sh` probes the restored Pod as soon as it gets an IP (`23.0s`)
while `gVisor` finishes paging in `23.05 GiB` of GPU state (`POD_RESTORED` at
`45.0s`); `1.0s` later (`46.0s`) the first completion finishes, and subsequent
completions return in **`78.9 ms`**.

---

## 5. OpenAI API features, concurrency benchmarks, GMP HPA & multi-region routing

### Reasoning control (`nano-v3`) & structured tool calling (`qwen3_coder`)

All overlays enable `--reasoning_parser nano-v3` and
`--tool_parser qwen3_coder`:

- **Reasoning ON (default)**: Chain-of-thought in
  `choices[0].message.reasoning_content` and final answer in `content`.
- **Non-thinking mode (`79–194 ms`)**: Pass
  `"chat_template_kwargs": {"enable_thinking": false}` in the request body.
- **Structured tool calling**: Pass OpenAI `tools` definitions to receive parsed
  `choices[0].message.tool_calls`.

### Measured single-GPU concurrency sweep on `NVIDIA RTX PRO 6000`

Measured in-cluster (`http://127.0.0.1:8000/v1/chat/completions`, streaming SSE,
`max_tokens=256`, `0` errors at every concurrency level):

| Model (`TP=1` on `1× RTX PRO 6000 96GB`) | Concurrency | Output Throughput (`tok/s`) | Per-User Speed (`tok/s/user`) | p50 TTFT (`ms`) | p95 TTFT (`ms`) | p50 TPOT (`ms`) | p50 E2E (`s`) |
| ---------------------------------------- | ----------- | --------------------------- | ----------------------------- | --------------- | --------------- | --------------- | ------------- |
| **`Nemotron-3-Nano-30B-A3B-NVFP4`**      | `1`         | **`239.4`**                 | **`239.4`**                   | `73.7`          | `88.0`          | **`3.90`**      | `1.07`        |
| `Nemotron-3-Nano-30B-A3B-NVFP4`          | `8`         | **`1,011.7`**               | `126.7`                       | `142.8`         | `143.7`         | `7.45`          | `2.04`        |
| `Nemotron-3-Nano-30B-A3B-NVFP4`          | `16`        | **`1,536.4`**               | `96.1`                        | `156.8`         | `161.0`         | `9.97`          | `2.66`        |
| `Nemotron-3-Nano-30B-A3B-NVFP4`          | `32`        | **`2,352.5`**               | `73.7`                        | `91.3`          | `95.0`          | `13.28`         | `3.48`        |
| **`Nemotron-3-Nano-30B-A3B-NVFP4`**      | **`64`**    | **`3,568.1`**               | **`55.9`**                    | `142.5`         | `149.4`         | **`17.40`**     | `4.58`        |
| **`Nemotron-3-Nano-30B-A3B-FP8`**        | `1`         | `230.9`                     | `231.0`                       | `71.2`          | `88.5`          | `4.05`          | `1.10`        |
| `Nemotron-3-Nano-30B-A3B-FP8`            | `16`        | `1,184.6`                   | `74.1`                        | `159.1`         | `163.4`         | `12.99`         | `3.46`        |
| **`Nemotron-3-Nano-30B-A3B-FP8`**        | **`64`**    | **`2,726.0`**               | `42.7`                        | `158.7`         | `165.0`         | `22.90`         | `6.00`        |
| **`Nemotron-3-Super-120B-A12B-NVFP4`**   | `1`         | **`74.0`**                  | **`74.0`**                    | `98.3`          | `120.2`         | **`13.11`**     | `3.44`        |
| `Nemotron-3-Super-120B-A12B-NVFP4`       | `16`        | **`476.6`**                 | `29.8`                        | `224.9`         | `228.9`         | `33.01`         | `8.59`        |
| **`Nemotron-3-Super-120B-A12B-NVFP4`**   | **`32`**    | **`713.9`**                 | **`22.3`**                    | `223.1`         | `226.2`         | **`44.10`**     | `11.47`       |

### Dual-metric GMP HPA & cross-region internal ALB failover

Each `trtllm` overlay deploys a `PodMonitoring` CR scraping
`/prometheus/metrics` every `15s` and a `HorizontalPodAutoscaler` scaling on
both `trtllm_num_requests_waiting` (target `4`) and
`trtllm_num_requests_running` (target `16`). In `shared-vpc` mode, expose each
region's `Service` (`trtllm-<suffix>`) via `expose_service_neg` and apply
[`terraform/multi-region/global_lb.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh)
(`WATERFALL_BY_REGION` + `LEAST_REQUEST`) for automatic cross-region capacity
spillover and health-checked regional failover; in `island` mode, see the
foundation guide for independent regional ingress options.

---

## 6. Troubleshooting & manifest design notes

1. **Prometheus gauge registration in TensorRT-LLM `1.4.0rc2`
   (`enable_iter_perf_stats: true` + `sitecustomize.py`)**:
   - `return_perf_metrics: true` alone leaves `trtllm_num_requests_waiting`,
     `trtllm_num_requests_running`, and `trtllm_kv_cache_utilization`
     unregistered unless `enable_iter_perf_stats: true` is also set in
     [`trtllm/base/extra-llm-api-config.yaml`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm/base/extra-llm-api-config.yaml),
     and
     [`trtllm-runtime/sitecustomize.py`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm-runtime/sitecustomize.py)
     exposes live iteration gauges so Cloud Monitoring's Custom Metrics Adapter
     never hits `404` before traffic arrives.
2. **OpenMPI `5.0` (`PRTE`) launch via `mpirun ... trtllm-llmapi-launch`**:
   - Bare `trtllm-serve` as PID 1 invokes `MPI.COMM_SELF.Spawn()`, which can
     fail with `MPI_ERR_UNKNOWN` inside Kubernetes and `gVisor` containers.
     [`trtllm/base/deployment.yaml`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm/base/deployment.yaml)
     launches `trtllm-llmapi-launch trtllm-serve` under `mpirun` with loopback
     MCA variables (`OMPI_MCA_btl_tcp_if_include=lo`,
     `OMPI_MCA_oob_tcp_if_include=lo`,
     `OMPI_MCA_btl_vader_single_copy_mechanism=none`).
3. **`gVisor` `nvproxy` library precedence (`checkpoint-wrapper.sh`)**:
   - NGC containers ship CUDA forward-compatibility libraries under
     `/usr/local/cuda/compat` and re-prepend them via `/etc/bash.bashrc`.
     [`components/gke-pod-snapshot/checkpoint-wrapper.sh`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/components/gke-pod-snapshot/checkpoint-wrapper.sh)
     strips `/usr/local/cuda/compat/*` ahead of `/usr/local/nvidia/lib64` and
     runs `unset BASH_ENV` so `gVisor` binds to host-matched `nvproxy` drivers.
4. **Quota-safe rolling updates (`maxSurge: 0, maxUnavailable: 1`) + graceful
   drain**:
   - `trtllm/base/deployment.yaml` configures `RollingUpdate` with
     `maxSurge: 0, maxUnavailable: 1` alongside `components/graceful-shutdown`
     (`terminationGracePeriodSeconds: 75` + `15s` `preStop` sleep), reusing the
     existing GPU node on single-replica updates without surge quota while
     rolling one replica at a time when scaled out.
5. **Measure latency in-cluster rather than over `kubectl port-forward`**:
   - Control-plane `port-forward` tunnels add `~180–550 ms` of RTT. Always
     benchmark against `127.0.0.1:8000`, the Service `ClusterIP`, or the in-VPC
     internal Application Load Balancer VIP.
