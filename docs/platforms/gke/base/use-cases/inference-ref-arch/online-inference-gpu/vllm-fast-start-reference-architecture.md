# Fast-start inference reference architecture

> [!IMPORTANT]
>
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2026-09-25 (YYYY-MM-DD)

This document outlines a reference architecture for **minimizing the time it
takes a new inference replica to start serving** on Google Kubernetes Engine
(GKE). It is a specialization of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md),
narrowed to one problem: the minutes a GPU replica spends loading a model before
it can answer a request, and what to do about it.

Refer to the [Getting Started](#getting-started) section below for instructions
on deploying the architecture described here.

## Purpose

A conventional GPU inference replica spends most of its startup time moving
model weights. That cost is paid on every scale-out event, which makes
autoscaling reactive at exactly the wrong timescale: by the time capacity
arrives, the traffic spike that called for it may be over. This architecture
aims to:

- **Remove the host disk from the loading path**: Stream weights directly from
  object storage into accelerator memory, eliminating both the staging disk and
  the redundant copy through host RAM.
- **Make load time a function of bandwidth, not of plumbing**: Weight loading
  should be limited by how fast bytes can move, not by serialized tensor reads
  or filesystem overhead.
- **Keep the storage layer out of the way**: Model repositories contain many
  files. The bucket should be organized so that listing and reading them is not
  itself a bottleneck.
- **Scale on signals that reflect demand**: Use the number of requests waiting
  in the model server queue rather than CPU or memory utilization, which
  saturate during normal continuous batching and carry no information about
  unmet demand.
- **Keep the deployment path reproducible**: The same manifests that produce the
  documented behaviour are the ones published in this repository.

## Features & Capabilities

This reference architecture provides a foundation for:

- Streaming model weights from Cloud Storage directly into GPU memory with no
  local staging disk.
- Serving across multiple GPU generations, including NVIDIA H100 and
  Blackwell-generation RTX PRO 6000.
- Autoscaling on the vLLM request queue, collected with Google Cloud Managed
  Service for Prometheus.
- Serving large open models, including Gemma 3 27B, Gemma 4 31B, and Qwen3.5 35B
  A3B.

## Architectural Principles

- **Move bytes once**: A weight tensor should travel from object storage to
  accelerator memory a single time, without intermediate materialization.
- **Prefer streaming to staging**: Work that can begin before a transfer
  finishes should not wait for it. Requiring the whole model on local disk
  before loading starts converts a bandwidth problem into a latency problem.
- **Do not pay for storage you only pass through**: If weights are never read
  from the node's disk a second time, the node should not be sized to hold them.
- **Scale on the queue, not on the machine**: Utilization metrics describe how
  busy a replica is. Queue depth describes whether there are enough replicas.
  Only the second is a scaling signal.
- **Measure time-to-serving, not time-to-`Ready`**: The meaningful measurement
  is when a replica answers a real request.

## Core Concepts and Technologies

### NVIDIA Run:ai Model Streamer

In a conventional deployment, weights travel from object storage across the
network, onto the host filesystem, through the Linux page cache into CPU RAM,
and only then across PCIe into GPU memory. This serializes tensor reads,
allocates the model twice, and requires the node to carry enough local storage
or memory to stage the entire model.

[NVIDIA Run:ai Model Streamer](https://github.com/dsx-ai-factory/model-streamer)
collapses this into a single streaming operation from Cloud Storage into GPU
memory, enabled in vLLM with `--load-format=runai_streamer` and a `gs://` model
path. It reads many tensors concurrently and hands them to the GPU as they
arrive, rather than reconstructing the full model on disk first.

Measured in `europe-west4` with a regional Cloud Storage bucket, vLLM loaded
Gemma 4 31B (58.99 GiB in GPU memory) in **27.0 seconds** on an NVIDIA H100 80GB
and **19.2 seconds** on an NVIDIA RTX PRO 6000 96GB, Gemma 3 27B (51.54 GiB) in
**11.6 seconds** on an RTX PRO 6000 96GB, and Qwen3.5 35B A3B (65.53 GiB) in
**11.5 seconds** on an RTX PRO 6000 96GB, without staging the weight files on
local storage.

### Cloud Storage with hierarchical namespace

Model weights are stored in a regional Cloud Storage bucket and read directly
over the `gs://` protocol, authenticated with GKE Workload Identity Federation.
No Persistent Volume and no Cloud Storage FUSE sidecar is involved in the
serving path.

The bucket is created with
[hierarchical namespace](https://cloud.google.com/storage/docs/hns-overview)
enabled. A hierarchical namespace bucket stores objects in folders rather than a
flat namespace, and offers up to 8 times higher initial queries per second (QPS)
limits for reading and writing objects than a bucket without hierarchical
namespace. Higher limits help when several replicas load the same model at the
same time, such as during a scale-out.

> [!NOTE]
>
> Hierarchical namespace must be chosen at bucket creation time and cannot be
> enabled on an existing bucket.

### Google Container File System (image streaming)

[Image streaming](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming)
lets a container start while its image layers are still being streamed on
demand, instead of waiting for the entire image to download. This matters
disproportionately for inference, because vLLM and PyTorch container images are
large, and the image pull is otherwise the first serial step of every cold
start.

### Horizontal Pod Autoscaling on inference metrics

CPU and memory utilization are poor scaling signals for inference: a vLLM engine
saturates both during normal continuous batching, even when serving a single
request. Scaling on them produces replicas that are not needed and misses
replicas that are.

This architecture scales on `vllm:num_requests_waiting`, the number of requests
waiting in the vLLM scheduler queue of each replica. It rises as soon as
requests arrive faster than the deployed replicas can admit them, and it returns
to zero when they catch up. GKE automatic application monitoring collects the
metric with Google Cloud Managed Service for Prometheus, and the Custom Metrics
Stackdriver Adapter makes it available to the autoscaler. The deployed
`HorizontalPodAutoscaler` targets an average of 5 waiting requests per replica,
adds replicas without a stabilization window, and removes them only after a
5-minute stabilization window.

Fast loading is what makes autoscaling on this signal worthwhile. A scale-out
signal is only actionable if capacity can arrive before the spike ends.

## Getting Started

A practical, step-by-step guide to deploying this architecture can be found in
[Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md).

The Kubernetes manifests are in
`platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai`,
with overlays for NVIDIA H100 and RTX PRO 6000 accelerators.

Related patterns built on the same reference architecture:

- [GKE Pod snapshots inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md),
  which builds on this architecture to restore later replicas from a memory
  snapshot instead of repeating the cold start
- [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)
- [Online inference using vLLM with speculative decoding and GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-spec-decoding-with-hf-model.md)
- [Online inference using vLLM with native KV cache offloading](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-native-kv-cache-offloading-single-tier.md)

## Additional Reading

- [Hierarchical namespace buckets](https://cloud.google.com/storage/docs/hns-overview)
- [Image streaming in GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming)
- [GKE Inference Gateway](https://cloud.google.com/kubernetes-engine/docs/concepts/about-gke-inference-gateway)
- [About custom compute classes in GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/about-custom-compute-classes)
- [NVIDIA Run:ai Model Streamer](https://github.com/dsx-ai-factory/model-streamer)
- [vLLM documentation](https://docs.vllm.ai/)
