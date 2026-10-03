# Fast-start inference reference architecture

> [!IMPORTANT]
>
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2026-10-02 (YYYY-MM-DD)

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
  in the model server queue rather than CPU or memory utilization, which don't
  show whether requests are waiting.
- **Keep the deployment path reproducible**: The same manifests that produce the
  documented behaviour are the ones published in this repository.

## Features & Capabilities

This reference architecture provides a foundation for:

- Streaming model weights from Cloud Storage directly into GPU memory with no
  local staging disk.
- Optionally caching the model in Rapid Cache caches in the zones of the GPU
  nodes, for scale-outs that add several replicas at once.
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

Measured in `europe-west4` with a regional Cloud Storage bucket, on newly
provisioned Spot nodes, vLLM loaded Gemma 4 31B (58.99 GiB in GPU memory) in a
median of **20.1 seconds** (range 19.0–27.8 seconds) on an NVIDIA H100 80GB and
**11.1 seconds** (10.6–16.5 seconds) on an NVIDIA RTX PRO 6000 96GB, Gemma 3 27B
(51.54 GiB) in **9.1 seconds** (8.2–16.2 seconds) on an RTX PRO 6000 96GB, and
Qwen3.5 35B A3B (65.53 GiB) in **15.2 seconds** (12.6–22.2 seconds) on an RTX
PRO 6000 96GB, without staging the weight files on local storage.

Weight loading is only part of the time it takes a new replica to start serving.
Scaling a deployment from zero replicas until the new replica answered its first
request took 4.3–7.4 minutes. Most of that time was spent provisioning the GPU
node, starting vLLM, and running `torch.compile`, CUDA graph capture, and
warm-up after the weights loaded. For the measurement conditions and the
per-model results, see
[Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md).

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
namespace. Loads can still slow down when many replicas load the same model at
the same time. In our tests in one zone, each of 6 replicas that loaded the same
model at the same time took 13.2–16.8 seconds, compared to 10.1–10.5 seconds for
each of 2 replicas.

> [!NOTE]
>
> Hierarchical namespace must be chosen at bucket creation time and cannot be
> enabled on an existing bucket.

### Rapid Cache (optional)

[Rapid Cache](https://cloud.google.com/storage/docs/rapid/rapid-cache) is an
SSD-backed read cache for a Cloud Storage bucket. Each cache serves only clients
in its own zone. This architecture can create a cache for the model bucket in
each zone that you list in the `ira_online_gpu_rapid_cache_zones` Terraform
variable. By default, it doesn't create any caches.

Rapid Cache can help when several replicas load the same model in the same zone
at the same time. Measured on 2026-10-02 with Qwen3.5 35B A3B on Spot RTX PRO
6000 nodes in one zone of `europe-west4`, each of 6 concurrent loads took
10.5–12.5 seconds when the cache served more than 99.9% of the bytes, and
13.2–16.8 seconds without Rapid Cache (3 tests each). The loads without Rapid
Cache read from a newer bucket, which might account for part of the difference.
With 2 concurrent loads, and with a single load, Rapid Cache didn't make loading
faster.

A cache doesn't help right away. In our tests, 3 of 5 new caches reported that
they were running but served no reads for more than an hour, and two of them
still served none about 18 hours later. A cache also fills gradually as replicas
read the model. Before you use Rapid Cache, see
[Optional: Cache the model with Rapid Cache](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md#optional-cache-the-model-with-rapid-cache).

### Google Container File System (image streaming)

[Image streaming](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming)
lets a container start while its image layers are still being streamed on
demand, instead of waiting for the entire image to download. This matters
disproportionately for inference, because vLLM and PyTorch container images are
large, and without image streaming the whole image must be downloaded before the
container can start. In our tests, the kubelet reported the vLLM image as pulled
in 1.4–2.3 seconds on new nodes.

### Fast-starting nodes

When a scale-out needs a new GPU node, the new replica can't start until the
node is provisioned. In our tests, that took 1–3 minutes. GKE Autopilot can
shorten this time with
[fast-starting nodes](https://cloud.google.com/kubernetes-engine/docs/concepts/fast-starting-nodes):
GKE pre-initializes hardware resources and uses them, on a best-effort basis and
at no extra charge, when a workload uses a compatible configuration.
Fast-starting nodes don't need any configuration.

G4 machine types, which provide the RTX PRO 6000 GPUs, are eligible. Spot VMs
aren't eligible, and the A3 High machine types that provide the H100 GPUs aren't
on the list of eligible machine types. The compute classes in this architecture
prefer reservations and on-demand capacity to flex-start and Spot capacity, so
an on-demand G4 node can be a fast-starting node. Every GPU node in our tests
was a Spot node, so we haven't measured the effect of fast-starting nodes. For
the requirements, see the guide's
[considerations for production](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md#considerations-for-production).

### Horizontal Pod Autoscaling on inference metrics

CPU and memory utilization are poor scaling signals for inference, because they
don't show whether requests are waiting. GPU memory use doesn't show it either:
vLLM reserves most of the GPU memory for the KV cache when it starts, so GPU
memory use doesn't change with load.

This architecture scales on `vllm:num_requests_waiting`, the number of requests
waiting in the vLLM scheduler queue of each replica. It rises as soon as
requests arrive faster than the deployed replicas can admit them, and it returns
to zero when they catch up. GKE automatic application monitoring collects the
metric with Google Cloud Managed Service for Prometheus, and the Custom Metrics
Stackdriver Adapter makes it available to the autoscaler. The deployed
`HorizontalPodAutoscaler` targets an average of 5 waiting requests per replica,
adds replicas without a stabilization window, and removes them only after a
5-minute stabilization window.

Fast loading shortens the time it takes to add capacity, and a scale-out signal
is only actionable if capacity can arrive before the spike ends. Weight loading
is only a small part of that time, though. In our tests, the
`HorizontalPodAutoscaler` added a replica about 80 seconds after the load
started, and a new replica on a new GPU node took 4.3–7.4 minutes from the
scale-up to its first response. Set the minimum number of replicas so that it
absorbs the bursts that you expect, and use autoscaling for sustained increases
in load.

## Getting Started

A practical, step-by-step guide to deploying this architecture can be found in
[Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md).
Before you run this architecture in production, review the guide's
[considerations for production](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md#considerations-for-production),
including how GKE can evict serving replicas to move them to other nodes.

The Kubernetes manifests are in
`platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai`,
with overlays for NVIDIA H100 and RTX PRO 6000 accelerators.

Related patterns built on the same reference architecture:

- [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)
- [Online inference using vLLM with speculative decoding and GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-spec-decoding-with-hf-model.md)
- [Online inference using vLLM with native KV cache offloading](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-native-kv-cache-offloading-single-tier.md)

## Additional Reading

- [Hierarchical namespace buckets](https://cloud.google.com/storage/docs/hns-overview)
- [Rapid Cache](https://cloud.google.com/storage/docs/rapid/rapid-cache)
- [Image streaming in GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming)
- [About quicker workload startup with fast-starting nodes](https://cloud.google.com/kubernetes-engine/docs/concepts/fast-starting-nodes)
- [GKE Inference Gateway](https://cloud.google.com/kubernetes-engine/docs/concepts/about-gke-inference-gateway)
- [About custom compute classes in GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/about-custom-compute-classes)
- [NVIDIA Run:ai Model Streamer](https://github.com/dsx-ai-factory/model-streamer)
- [vLLM documentation](https://docs.vllm.ai/)
