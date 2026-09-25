# GKE Pod snapshots inference reference architecture

> [!IMPORTANT]
>
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2026-09-25 (YYYY-MM-DD)

This document outlines a reference architecture for **restoring GPU inference
replicas from a memory snapshot** on Google Kubernetes Engine (GKE). It extends
the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md),
which makes the first cold start fast, with a second technique that makes every
replica after that one nearly instant.

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
- **Make scale-out time independent of model size**: A 31-billion parameter
  model should not take longer to scale out than an 8-billion parameter one.
- **Keep the cold path fast as well**: The first replica, and any replica that
  cannot be restored, still starts from the fastest available loader.
- **Be explicit about where the technique does not help**: Snapshots remove
  initialization time. They do not provision GPU nodes, and they add operational
  obligations that not every workload should take on.

## Features & Capabilities

This reference architecture provides a foundation for:

- Restoring a warmed-up vLLM replica from a snapshot in single-digit seconds.
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

Measured on Gemma 4 31B on a single NVIDIA H100 80GB, the streamer loads 58.99
GiB of weights in about 48 seconds, yet the replica still takes 234 to 265
seconds to start serving. A replica restored from a snapshot served in 3 to 5
seconds. The streamer shortens the cold start, and the snapshot removes it for
every replica after the first.

### Cooperative trigger instead of a readiness trigger

A policy can trigger the checkpoint when the Pod passes its readiness probe, or
it can wait for the workload to request it (`triggerConfig.type: workload`).
This architecture uses the workload trigger. A wrapper in the container waits
for the vLLM health endpoint, removes anything left in the local model cache,
and then writes to `/proc/gvisor/checkpoint`. The captured state is therefore
deterministic, and it never includes an on-disk copy of the weights that would
otherwise be serialized into the image and read back on every restore. The cost
is a small amount of startup scripting in the container command.

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
the memory vLLM reserves. On H100, Llama 3.1 8B produced a 21.27 GB image with
`--gpu-memory-utilization=0.90`. Gemma 4 31B produced a 72.9 GB image on H100
and a 73.3 GB image on RTX Pro 6000, only 0.6% larger even though the RTX Pro
6000 allocated 14 GiB more KV cache. Choosing a GPU with more memory buys KV
cache capacity without a proportional increase in snapshot size.

### Capture is slow, restore is fast

Checkpointing uploads the full memory image. A roughly 21 GB image took about
four minutes to become available, and a roughly 73 GB image took 11 to 15
minutes. For most of that window the snapshot objects are not visible in the
bucket, because the largest object is written last. GKE pauses the Pod to take
the snapshot. In the RTX Pro 6000 validation, the replica stopped answering
requests about 20 seconds after the trigger and resumed when the memory image
finished uploading, 13 minutes later. Restore does not share this cost: in the
H100 measurements below, a 73 GB image restored as quickly as a 21 GB one. That
is a small number of data points, so measure it for your own model.

### Protecting the capture from eviction

The paused replica still reports `Ready`, because its readiness probe tolerates
long runs of failures, so nothing in its status shows that evicting it would
lose the snapshot. A Service also keeps routing requests to it, and they are not
answered until the upload completes. The GPU compute classes of the reference
implementation enable active migration, which drains a node to move its Pods to
a more preferred node configuration. On the Autopilot cluster used to validate
this architecture, the cluster autoscaler evicted the cold-start replica 13
minutes after the checkpoint was triggered, as the upload was finishing, and the
checkpoint failed. The deployment therefore includes a `PodDisruptionBudget`
that allows no voluntary disruptions, which active migration and autoscaler
scale-down respect. The cost is that the autoscaler does not move or consolidate
serving replicas. The `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"`
annotation is not used, because on Autopilot it requests extended run time,
which is not supported for Pods that target custom compute classes.

### Storage lifecycle and permissions

Snapshots are written to Cloud Storage by the workload's Kubernetes service
account through Workload Identity Federation. Deleting a snapshot is performed
by the Pod snapshot controller, which acts as the GKE service agent and needs
the Storage Object User role on the bucket. On the cluster used to develop this
architecture, that role was initially missing: `PodSnapshot` resources stayed in
`Deleting` for weeks, and their data remained in the bucket. After the role was
granted, deleting a `PodSnapshot` removed both the resource and its objects
within seconds.

In this architecture, snapshots share the model bucket created by the reference
implementation. That bucket already uses hierarchical namespace, which Pod
snapshots require, and it has soft delete at the Cloud Storage default of seven
days. A deleted snapshot is therefore retained, and billed, for seven days
before it is purged. Google recommends disabling soft delete for snapshot
buckets. Disabling it on the shared bucket also removes protection for the model
weights. Workloads that snapshot frequently should consider a dedicated snapshot
bucket with soft delete disabled.

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

| Model, GPU                            | Cold start   | Restore  | Snapshot size |
| ------------------------------------- | ------------ | -------- | ------------- |
| Llama 3.1 8B, NVIDIA L4               | 561 s        | 41 s     | 19.53 GB      |
| Llama 3.1 8B, NVIDIA H100 80GB        | 163 s        | 3 s      | 21.27 GB      |
| Gemma 4 31B, NVIDIA H100 80GB         | 234 to 265 s | 3 to 5 s | 72.9 GB       |
| Gemma 4 31B, NVIDIA RTX Pro 6000 96GB | 224 s        | 4 s      | 73.3 GB       |

Cold start is measured from the Pod being scheduled, or the container being
created, to the replica serving. Restore is measured from `PodScheduled` to
`Ready`. The L4 results were measured end to end with an earlier version of the
manifests in this repository, whose readiness probe polled `/health` every 10
seconds after an initial delay of 15 seconds. The L4 cold start includes
downloading the weights from the Hugging Face Hub, and the L4 restore was onto a
newly provisioned node. The 265 second and 5 second Gemma 4 31B results on H100,
and the RTX Pro 6000 results, also used a readiness probe on `/health`, and the
5 second restore was onto a node that had never run the model. The other
restores were confirmed by the absence of any model-loading work in the restored
Pod's logs and by a correct response to a request. The RTX Pro 6000 result was
measured with manifests that are not included in this repository.

The RTX Pro 6000 variant in this repository was later validated end to end on a
GKE Autopilot cluster where Image streaming had not yet cached the container
image. Each new node spent about four minutes pulling the image, so
`PodScheduled` to `Ready` was 401 seconds for the cold start and 255 seconds for
the restore onto a newly provisioned node. From the container starting to
`Ready`, the cold start took 164 seconds and the restore less than one second.
The restored Pod's `PodRestored` condition was set 17 seconds after its
container started. The first request that the test could send to the restored
Pod, 16 seconds after its container started, was answered in 2.3 seconds. The
first request to the cold-start replica, sent after its snapshot was uploaded,
took 1.6 seconds, and later requests to either replica took 0.4 seconds.

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
