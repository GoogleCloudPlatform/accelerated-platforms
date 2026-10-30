# GKE Pod snapshots inference reference architecture

> [!IMPORTANT]
>
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2026-10-19 (YYYY-MM-DD)

This document outlines a reference architecture for **restoring GPU inference
replicas from a memory snapshot** on Google Kubernetes Engine (GKE). It extends
the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md),
which makes the first cold start fast, with a second technique that starts every
replica after that one in a fraction of the cold-start time.

Refer to the [Getting Started](#getting-started) section below for instructions
on deploying the architecture described here.

## Purpose

Streaming weights with the NVIDIA Run:ai Model Streamer shortens weight loading,
but weight loading is only part of a cold start. After the weights arrive, vLLM
still profiles memory, compiles kernels, captures CUDA graphs, and allocates its
KV cache. That work takes minutes, it is identical on every replica, and it is
repeated on every scale-out. This architecture aims to:

- **Pay for initialization once per configuration, not once per replica**:
  Capture a fully warmed-up replica and restore every later replica from it.
- **Make scale-out time independent of initialization work**: A restored replica
  skips compilation, CUDA graph capture, and memory profiling. Its start-up time
  depends on how much memory it has to read back, not on how long the engine
  took to initialize.
- **Keep the cold path fast as well**: The first replica, and any replica that
  cannot be restored, still starts from the fastest available loader.
- **Be explicit about where the technique does not help**: Snapshots remove
  initialization time. They do not provision GPU nodes, and they add operational
  obligations that not every workload should take on.

## Features & Capabilities

This reference architecture provides a foundation for:

- Restoring a warmed-up vLLM replica from a snapshot to its first response in
  under a minute, independent of how long the model takes to initialize.
- Composing snapshots with the Run:ai Model Streamer, so the one required cold
  start is also fast.
- Capturing snapshots at a deterministic, workload-chosen point in the startup
  sequence.
- Serving single-GPU models on NVIDIA L4, H100, and RTX Pro 6000 accelerators.

## Architectural Principles

- **Separate the one-time cost from the recurring cost**: Loading a model must
  happen at least once. Initializing it again on every replica is waste.
  Optimize the cold path with streaming and the warm path with restore.
- **Treat a snapshot as a build artifact**: A snapshot corresponds to exactly
  one pod template. Changing a flag, an environment variable, a resource
  request, or the container image produces a different template and requires a
  new snapshot. Tune first, snapshot second.
- **Capture on purpose, not by accident**: A snapshot taken at a known point in
  the lifecycle is worth more than one taken quickly, because every future
  replica inherits that state.
- **Own the storage lifecycle**: A snapshot is tens of gigabytes of Cloud
  Storage. Its creation is automatic. Its deletion depends on a permission that
  must be granted separately, and on the bucket's soft delete policy.
- **Measure time-to-serving, not time-to-`Ready`**: A restore is proven by a
  replica that answers a request and whose logs contain no model-loading work.

## Core Concepts and Technologies

### GKE Pod snapshots

[GKE Pod snapshots](https://cloud.google.com/kubernetes-engine/docs/concepts/pod-snapshots)
capture the memory of a running Pod, including GPU memory, into Cloud Storage.
When a new Pod matching the snapshot is scheduled, GKE restores it from the
image instead of starting it from scratch. The restored vLLM process resumes
with its weights already in GPU memory, its CUDA graphs already captured, and
its engine already initialized.

A `PodSnapshotPolicy` drives both halves of the lifecycle through a label
selector. The first matching Pod is checkpointed. Every matching Pod scheduled
after the snapshot becomes available is restored from it. No annotation on the
Deployment is required.

Pod snapshots are implemented with
[GKE Sandbox](https://cloud.google.com/kubernetes-engine/docs/concepts/sandbox-pods),
so the workload runs with `runtimeClassName: gvisor`.

### NVIDIA Run:ai Model Streamer

Covered in depth in the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md#nvidia-runai-model-streamer).
In this architecture it serves two roles: it makes the one cold start that
produces the snapshot faster, and it leaves no copy of the weights on local disk
for the snapshot to serialize.

## Design choices and tradeoffs

### Streamer and snapshots attack different costs

| Cost                               | Streamer only         | Streamer and snapshots |
| ---------------------------------- | --------------------- | ---------------------- |
| Weight transfer into GPU memory    | Every replica, faster | First replica only     |
| Engine initialization              | Every replica         | First replica only     |
| Checkpoint upload to Cloud Storage | Never                 | Once per configuration |
| GPU node provisioning              | Unchanged             | Unchanged              |

Measured on Gemma 4 31B on a single NVIDIA H100 80GB inside GKE Sandbox
(`runtimeClassName: gvisor`), the streamer loads 58.9 GiB of weights in about 48
seconds on a single-pod stream (56.8 seconds on RTX Pro 6000, compared with 20.1
seconds on H100 and 11.1 seconds on RTX Pro 6000 for the unsandboxed vLLM
`v0.26.0` deployment in the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md)),
yet the replica still takes 210 to 275 seconds to finish starting up because
`torch.compile` and CUDA graph capture add another 38 to 83 seconds. A replica
restored from a snapshot served its first response 36 to 56 seconds after it was
scheduled on H100 (and 35 to 105 seconds on RTX Pro 6000). The streamer shortens
the cold start, and the snapshot replaces it for every replica after the first.

### Cooperative trigger instead of a readiness trigger

A policy can trigger the checkpoint when the Pod passes its readiness probe, or
it can wait for the workload to request it (`triggerConfig.type: workload`).
This architecture uses the workload trigger. A wrapper in the container waits
for the vLLM health endpoint, removes anything left in the local model cache,
and then writes to `/proc/gvisor/checkpoint`. The captured state is therefore
deterministic, and it never includes an on-disk copy of the weights that would
otherwise be serialized into the image and read back on every restore. The cost
is a small amount of startup scripting in the container command.

Because a Pod snapshot serializes process memory and environment variables into
Cloud Storage, credentials must not be kept in long-lived environment variables
(`os.environ`). For Hugging Face Hub downloads (Path A), the deployment mounts
the `huggingface-token` Secret as a native Kubernetes `Secret` volume
(`optional: true`, because GKE Pod snapshots do not support Secret Store CSI
volumes on checkpointed Pods and Path B overlays do not need the token), copies
it to `/root/.cache/huggingface/token` before starting vLLM, and deletes the
token files and large weight files (`*.safetensors`, `*.bin`, `*.pt`, `*.lock`)
from `/root/.cache/huggingface` right before writing to
`/proc/gvisor/checkpoint` while keeping small tokenizer and configuration files
in case a restored replica lazily re-reads them.

### Driver selection through a compute class

GPU checkpointing requires an NVIDIA driver of version 570 or newer. Selecting a
node with the `cloud.google.com/gke-accelerator` label is satisfied by the
default driver, which is older, and in that case the checkpoint helper is not
installed. That failure is silent until the first checkpoint is attempted. Every
overlay in this architecture therefore selects its node with a custom compute
class, which pins `driverVersion: latest`.

### A stable rendezvous address

PyTorch and NCCL record the address they bind to inside the process memory that
gets checkpointed. A restored Pod always has a different IP address. The
deployment sets `VLLM_HOST_IP=127.0.0.1` so the restored process never refers to
an address that no longer exists.

### Snapshot size follows resident memory

A snapshot is roughly the size of the GPU memory that is actually in use, not of
the memory vLLM reserves. With vLLM `v0.26.0` and
`--gpu-memory-utilization=0.90` on GKE Autopilot (`1.36.4-gke.2046002`), Llama
3.1 8B produced a 20.8 GiB image on H100 (with 54.9 GiB of KV cache, 449,968
tokens) and an 18.9 GiB image on L4 (with 3.75 GiB of KV cache, 30,736 tokens).
Gemma 4 31B produced a 68.3 GiB image on H100 (with 10.6 GiB of KV cache, 12,629
tokens) and a 70.3 GiB image on RTX Pro 6000 (with 24.9 GiB of KV cache, 29,628
tokens), only 2.9% larger even though the RTX Pro 6000 has 16 GB more GPU memory
and more than double the KV cache capacity. Choosing a GPU with more memory buys
KV cache capacity without a proportional increase in snapshot size.

### Capture is slow, restore is fast

Checkpointing uploads the full memory image. A roughly 19 to 21 GiB image took
four to six minutes to become available, and a roughly 68 to 70 GiB image took
11 to 13.5 minutes. For most of that window the snapshot objects are not visible
in the bucket, because the largest object is written last. GKE pauses the Pod to
take the snapshot. In validation, the replica stopped answering requests within
seconds of the trigger and resumed when the memory image finished uploading, 4
to 6 minutes later for Llama 3.1 8B and 11 to 13.5 minutes later for Gemma 4
31B.

Restore reads the same image back, much faster. Every restore reads it from
Cloud Storage, whether or not the node has run the model before. The time GKE
took to complete a restore depended on more than the size of the image:

| Model, GPU                | Snapshot (`v0.26.0` / `v0.19.1`) | KV cache (`v0.26.0` / `v0.19.1`) | `POD_RESTORED`, `v0.26.0` (Autopilot) | `POD_RESTORED`, `v0.19.1` (Standard) |
| ------------------------- | -------------------------------- | -------------------------------- | ------------------------------------- | ------------------------------------ |
| Llama 3.1 8B, L4          | 18.9 GiB / 18.3 GiB              | 3.75 GiB / 1.88 GiB              | 26 s                                  | 24 to 27 s                           |
| Llama 3.1 8B, H100 80GB   | 20.8 GiB / 19.8 GiB              | 54.9 GiB / 54.2 GiB              | 40 s                                  | 44 to 50 s                           |
| Gemma 4 31B, H100 80GB    | 68.3 GiB / 67.9 GiB              | 10.6 GiB / 8.2 GiB               | 52 to 56 s                            | 32 to 35 s                           |
| Gemma 4 31B, RTX Pro 6000 | 70.3 GiB / 68.4 GiB              | 24.9 GiB / 12.1 GiB              | 103 s                                 | 32 to 39 s                           |

Llama 3.1 8B on H100 restored more slowly than Gemma 4 31B on the same GPU, from
an image less than a third the size. Measure the restore of your own
configuration rather than estimating it from the snapshot size. Four RTX Pro
6000 replicas restoring onto four new nodes at the same time each took as long
as a single restore.

### Protecting the capture from eviction

The deployment separates `startupProbe` (which allows up to 1 hour for the cold
start) from `readinessProbe` (`periodSeconds: 2`, `failureThreshold: 3`). When
the cooperative checkpoint trigger pauses the cold-start replica, the readiness
probe marks the Pod not ready after about six seconds so the Service stops
routing requests to it until the upload finishes and the replica resumes. The
GPU compute classes of the reference implementation enable active migration,
which drains a node to move its Pods to a more preferred node configuration. On
the Autopilot cluster used to validate this architecture, the cluster autoscaler
evicted the cold-start replica 13 minutes after the checkpoint was triggered, as
the upload was finishing, and the checkpoint failed. The deployment therefore
includes a `PodDisruptionBudget` with `minAvailable: 1`, which active migration
and autoscaler scale-down respect while a single cold-start replica is capturing
the snapshot (note that while at 1 replica, `minAvailable: 1` also blocks
voluntary node upgrade or auto-repair drains for up to an hour before GKE
force-evicts, which is acceptable because the single-replica cold-start phase is
short-lived), while still permitting voluntary evictions once the deployment is
scaled out to two or more ready replicas. The
`cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` annotation is not
used, because on Autopilot it requests extended run time, which is not supported
for Pods that target custom compute classes.

### Storage lifecycle and permissions

Snapshots are written to Cloud Storage by the workload's Kubernetes service
account through Workload Identity Federation. Deleting a snapshot is performed
by the Pod snapshot controller, which acts as the GKE service agent and needs
the Storage Object User role on the bucket. When
`cluster_addons_pod_snapshots_enabled` is `true` (enabled by the
`inference-ref-arch` `deploy-standard.sh` and `deploy-ap.sh` scripts), the core
cluster terraservices (`core/container_cluster` and `core/container_cluster_ap`)
enable the GKE Pod Snapshots add-on on the cluster, and the
`terraform/online_gpu` module creates a dedicated `*-pod-snapshots` Cloud
Storage bucket with hierarchical namespace enabled and soft delete disabled
(`retention_duration_seconds = 0`), granting `roles/storage.objectUser` on
that bucket to both the workload's Kubernetes service account and the GKE
service agent
(`service-${project_number}@container-engine-robot.iam.gserviceaccount.com`). On
the cluster used to develop this architecture, before the GKE service agent
grant was added, `PodSnapshot` resources stayed in `Deleting` for weeks, and
their data remained in the bucket. After the role was granted, deleting a
`PodSnapshot` removed both the resource and its objects within seconds. Using a
dedicated snapshot bucket with soft delete disabled follows Google's
recommendation for Pod snapshot storage (avoiding seven-day soft-delete
retention charges on 19 to 70 GiB parallel composite uploads) while keeping the
default seven-day soft delete policy on the separate model weights bucket.

### Rapid Cache and fast-starting nodes

The
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md)
describes two optional additions that also apply to this architecture:

- [Rapid Cache](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md#rapid-cache-optional)
  caches for the model weights bucket (`*-hf-hub-models`) to accelerate Path B
  cold starts. Because Pod snapshots are stored in the separate
  `*-pod-snapshots` bucket, snapshot uploads and restores do not consume Rapid
  Cache capacity. In our tests without Rapid Cache, GKE's restore took 31 to 33
  seconds on each node when 1, 2, or 4 replicas restored at the same time, so
  the throughput of the standard Cloud Storage bucket doesn't appear to limit
  restores at that scale.
- [Fast-starting nodes](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md#fast-starting-nodes),
  which can shorten GPU node provisioning, a delay that snapshots don't reduce.
  GKE Autopilot uses them on a best-effort basis for compatible configurations.
  The G2 (L4) and G4 (RTX Pro 6000) machine series are eligible, subject to
  version and boot disk requirements. Spot VMs aren't eligible, and the A3 High
  machine types that provide the H100 GPUs aren't on the list of eligible
  machine types. The documented limitations don't include GKE Sandbox, but we
  didn't test it. The results in this document were measured on Spot VMs, and
  one H100 restore on a flex-start VM, so they don't include fast-starting
  nodes.

### Sandbox runtime

The workload runs in GKE Sandbox. This adds a layer of isolation between the
container and the node. It also means the workload runs on sandboxed nodes and
is subject to gVisor's compatibility surface. Validate the serving performance
of your own model under the sandbox before adopting the pattern.

On the GPU sandbox nodes of the GKE Standard cluster used for this architecture,
gVisor enabled core tagging, and every sandboxed Pod then failed to start. The
implementation ships a DaemonSet that disables the setting on each sandbox node
as it joins. Treat it as a workaround to remove once the platform no longer
needs it. GKE Autopilot does not allow the DaemonSet, and the Autopilot GPU
sandbox nodes used to validate this architecture started sandboxed Pods without
it.

## When to add Pod snapshots

| Situation                                                               | Recommendation                                                                                                                        |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| A stable model configuration that scales out often                      | Add snapshots. This is the case the technique was designed for                                                                        |
| GPU capacity is held for scale-out, for example with a reservation      | Add snapshots. Restore then dominates time-to-serving                                                                                 |
| Every scale-out must provision a new GPU node                           | Snapshots still remove minutes of initialization, but node provisioning can take longer than both. Pair them with a capacity strategy |
| The configuration changes frequently, for example during tuning         | Use the streamer only. Each change invalidates the snapshot and costs a new checkpoint                                                |
| The model is sharded across several GPUs (`--tensor-parallel-size` > 1) | Use the streamer only. Restore has only been validated at tensor-parallel size 1, and a checkpoint attempt at size 4 failed           |

> [!WARNING]
>
> All results for this architecture were measured at `--tensor-parallel-size 1`.
> One attempt at tensor-parallel size 4 on four NVIDIA H100 GPUs served
> correctly but failed to checkpoint. Multi-GPU snapshots are not supported by
> this architecture.

## Measured results

| Model, GPU                            | Cold start, `v0.26.0` (Autopilot) | Cold start, `v0.19.1` (Standard) | Restore first response, `v0.26.0` (Autopilot) | Restore first response, `v0.19.1` (Standard) | Restore `Ready` (`v0.26.0` / `v0.19.1`) | Snapshot size (`v0.26.0` / `v0.19.1`) |
| ------------------------------------- | --------------------------------- | -------------------------------- | --------------------------------------------- | -------------------------------------------- | --------------------------------------- | ------------------------------------- |
| Llama 3.1 8B, NVIDIA L4               | 162 s                             | 433 s                            | 28.2 s                                        | 26 to 29 s                                   | 17 s / 12 to 15 s                       | 18.9 GiB / 18.3 GiB                   |
| Llama 3.1 8B, NVIDIA H100 80GB        | 68 s                              | 168 s                            | 41.0 s                                        | 46 to 52 s                                   | 8 s / 5 to 9 s                          | 20.8 GiB / 19.8 GiB                   |
| Gemma 4 31B, NVIDIA H100 80GB         | 240 s                             | 224 s                            | 53.3 to 56.3 s                                | 36 to 38 s                                   | 13 to 14 s / 3 to 5 s                   | 68.3 GiB / 67.9 GiB                   |
| Gemma 4 31B, NVIDIA RTX Pro 6000 96GB | 215 s                             | 210 s                            | 104.9 s                                       | 35 to 43 s                                   | 41 s / 7 to 20 s                        | 70.3 GiB / 68.4 GiB                   |

All times are measured from the Pod's `PodScheduled` condition, so they exclude
waiting for a GPU node. Note that both the vLLM version and the GKE cluster mode
differ between the two measurement columns (`v0.26.0` on GKE Autopilot vs
`v0.19.1` on GKE Standard). The cold start is measured to `Ready`, when vLLM
first answers `/health` and immediately triggers the cooperative checkpoint
(pausing the cold-start replica until the snapshot upload finishes). The restore
is measured to the first successful `/v1/completions` response, with requests
sent every half second from the moment the Pod has an IP address, and to `Ready`
for comparison. No restored Pod logged any model loading.

The `v0.26.0` results were measured on a GKE Autopilot cluster
(`1.36.4-gke.2046002`) in `us-central1` across all four overlays on Spot VMs. On
RTX Pro 6000 (`g4-standard-48`), vLLM `v0.26.0` uses the `TRITON_ATTN` backend
and JIT-compiles `kernel_unified_attention` on the first prefill request after
restore, which accounts for the 104.9-second first response (subsequent 32-token
`/v1/chat/completions` requests complete in 366 to 397 ms). On H100
(`a3-highgpu-1g`), vLLM `v0.26.0` uses FlashAttention 4 (`FA4`) across all Gemma
4 31B layers (heterogeneous head dimensions 256 and 512), serving steady-state
32-token `/v1/chat/completions` requests in 216 to 221 ms (and 59 to 70 ms on
Llama 3.1 8B, compared with 537 to 539 ms on L4).

The `v0.19.1` multi-node and fan-out results were measured on a GKE Standard
cluster (`1.36.4-gke.1391000`) in `europe-west4` on Spot VMs (with one H100
restore onto a flex-start VM when Spot capacity ran out), with
[Image streaming](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming)
enabled by the compute classes: 2 new nodes on L4, 8 new nodes plus 2 reused
nodes (34.4 and 34.6 s) on RTX Pro 6000, and 3 runs per model on H100. Pulling
the vLLM image onto a new node took 1.3 to 10 seconds with Image streaming; on
an Autopilot cluster before Image streaming had cached the image, pulls onto new
nodes took about four minutes and added directly to the restore. The L4 cold
start includes downloading the weights from the Hugging Face Hub, which varies.
The guide's
[measurement script](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/measure_restore.sh)
reports the same intervals.

- **`Ready` is not restore time.** A restored replica reports `Ready` as soon as
  gVisor resumes vLLM, while GKE is still loading its memory. Requests sent in
  that window wait, then succeed. The first response arrived 2 to 5 seconds
  after GKE set `PodRestored`, and later requests were as fast as on the
  cold-start replica, for an 8-token completion: 0.36 seconds for Gemma 4 31B on
  RTX Pro 6000, 0.20 seconds on H100, and 0.49 seconds for Llama 3.1 8B on L4,
  0.06 seconds on H100.
- **Node history barely matters.** Restoring onto a node that had just run a
  restored replica, with the image already on disk, reached `Ready` in 3
  seconds, but first served after 34.4 to 34.6 seconds on RTX Pro 6000, against
  35 to 43 seconds on new nodes. The snapshot is read from Cloud Storage every
  time.
- **Concurrent restores do not slow each other down.** Restoring onto 1, 2, and
  4 new RTX Pro 6000 nodes at the same time, GKE's restore took 31 to 33 seconds
  on every node.
- **GPU capacity dominates in practice.** New RTX Pro 6000 and H100 Spot nodes
  usually took one to three minutes. H100 Spot capacity in the region was
  unavailable for about 40 minutes. L4 capacity, on demand and Spot, was
  unavailable for more than an hour, and a Spot L4 node was preempted 12 minutes
  after its snapshot completed. The snapshot survived and later replicas
  restored from it.

## Getting Started

A practical, step-by-step guide to deploying this architecture can be found in
[Online inference using vLLM with GKE Pod snapshots and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-podsnapshots.md).

The Kubernetes manifests are in
`platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore`,
with overlays for NVIDIA L4, H100, and RTX Pro 6000 accelerators.

Related patterns built on the same reference architecture:

- [Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md)
- [Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md)
- [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)

## Additional Reading

- [About Pod snapshots](https://cloud.google.com/kubernetes-engine/docs/concepts/pod-snapshots)
- [Prepare for Pod snapshots](https://cloud.google.com/kubernetes-engine/docs/how-to/pod-snapshots-prepare)
- [Trigger a Pod snapshot](https://cloud.google.com/kubernetes-engine/docs/how-to/pod-snapshots-trigger)
- [About GKE Sandbox](https://cloud.google.com/kubernetes-engine/docs/concepts/sandbox-pods)
- [About custom compute classes in GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/about-custom-compute-classes)
- [NVIDIA Run:ai Model Streamer](https://github.com/run-ai/runai-model-streamer)
- [vLLM documentation](https://docs.vllm.ai/)
