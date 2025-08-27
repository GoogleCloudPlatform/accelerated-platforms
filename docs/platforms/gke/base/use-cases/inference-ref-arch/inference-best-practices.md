# GKE Inference reference architecture design

This document describes the Google Kubernetes Engine (GKE) Inference reference
architecture design. For more information about the reference architecture, see
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

The GKE Inference reference architecture supports deploying various inference
use cases. This document describes the design choices that are applicable to all
supported use cases, and also the choices that are specific to each supported
use case:

- [GKE Inference reference architecture design choices](#gke-inference-reference-architecture-design-choices)
- [Online inference with GPUs design choices](#online-inference-with-gpus-design-choices)

## GKE Inference reference architecture design choices

This section focuses on the GKE Inference reference architecture design choices.
These design choices apply to the reference architecture and all supported use
cases.

### AI models in scope as examples

The GKE inference reference architecture is not limited to deploying specific
models. It illustrates how to deploy the following models:

- Google Gemma: Google’s open, cost-effective model family. Recommended for most
  inference use cases, delivering state-of-the-art results for a wide range of
  model sizes.
- Meta Llama: Meta open model family.
- GPT-OSS: OpenAI open model family.
- Qwen: Alibaba Cloud open model family.

### Accelerators obtainability

To increase the chances of obtaining the required accelerators, such as GPUs and
TPUs, the GKE Inference reference architecture defines
[Custom Compute Classes (CCC)](https://cloud.google.com/kubernetes-engine/docs/concepts/about-custom-compute-classes).
In GKE, a compute class is a profile that consists of a set of node attributes
that GKE uses to provision the nodes that run your workloads during autoscaling
events. Compute classes can target specific optimizations, like provisioning
high-performance nodes or prioritizing cost-optimized configurations for cheaper
running costs. Custom compute classes let you define profiles that GKE then uses
to autoscale nodes to closely meet the requirements of specific workloads.

The GKE Inference reference architecture includes CCCs that implement
[profiles to maximize accelerators obtainability](/platforms/gke/base/core/custom_compute_class/templates/manifests).

<!-- For more information about GKE Inference reference architecture CCCs, see
[Optimizing GKE Workloads with Custom Compute Classes](LINK HERE) -->

### Model Downloader and storage backend selection

To avoid downloading models every time you deploy an inference workload, the GKE
Inference reference architecture includes a Model Downloader. We recommend that
you download the models you need for your inference workloads before deploying
them, using the Model Downloader.

The Model Downloader is responsible for efficiently downloading models from a
supported model repository, and for storing models in
[Cloud Storage](https://cloud.google.com/storage/docs/introduction). Cloud
Storage provides highly durable, scalable, and cost-effective object storage,
ensuring that large model files are readily available to inference workloads.
For more information about storage services recommendations, see
[Storage services](https://cloud.google.com/ai-hypercomputer/docs/storage).

The Model Downloader supports downloading models from the following
repositories:

- Hugging Face

The Model Downloader is implemented as Kubernetes Job that, upon startup,
authenticates against the model repository, and initiates the transfer of
required model files from the model repository to a
[Cloud Storage bucket](https://cloud.google.com/storage/docs/buckets).

Inference workloads deployed on the GKE Inference reference architecture, do the
following:

1. Mount the Cloud Storage buckets where the Model Downloader stored model files
   as volumes using
   [Cloud Storage FUSE CSI driver](https://cloud.google.com/kubernetes-engine/docs/concepts/cloud-storage-fuse-csi-driver)
2. Configures the Cloud Storage FUSE mount for the best performance for model
   serving, and then pre-fetches the model to reduce the inference workload
   startup time.

For more information about how the GKE Inference reference architecture
configures the Cloud Storage FUSE CSI driver, see
[LLM Inference Optimization on GKE: Achieving faster Pod Startup with Google Cloud Storage](/use-cases/inferencing/cost-optimization/gcsfuse/AchievingFasterPodStartup.md).

### Exposing inference workloads

Implementing load balancing and advanced traffic routing policies helps you
ensure that your inference workloads remain accessible and performant even
during unexpected spikes in demand or unanticipated failures, ultimately leading
to a more resilient and efficient inference infrastructure, and to a more
optimized and distributed traffic across geographies.

To expose inference workloads to clients, the GKE Inference reference
architecture uses the
[GKE Inference Gateway](https://cloud.google.com/kubernetes-engine/docs/concepts/about-gke-inference-gateway).
GKE Inference Gateway is an extension to the GKE Gateway for optimized serving
of generative AI applications. GKE Inference Gateway provides features aimed at
efficiently serving generative AI models for generative AI applications on GKE.

In some architectures, you can combine both the GKE Gateway and the GKE
Inference Gateway to implement fine-grained load balancing policies. For
example, you can use GKE Gateways as the first load-balancing layer to
distribute traffic based on factors such as geography and health checks. After
traffic reaches a specific region, you can use GKE Inference Gateways to perform
AI-aware load balancing to route requests to the optimal inference server. For
more information, see
[Choose a load balancing strategy for AI/ML model inference on GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/machine-learning/choose-lb-strategy).

### Multi-region deployments

To help you make your inference workloads more resilient and highly available,
you can deploy multiple instances of the GKE Inference reference architecture
across different regions. When you deploy your inference workloads across
multiple regions, you lay down the foundation to help you implement better fault
tolerance and disaster recovery, and reduced latency for globally distributed
users.

When you deploy your inference workloads across different regions, we recommend
that you consider the following:

- Implement robust traffic routing mechanisms and automated failover procedures
  to ensure continuous service availability. For more information, see
  [Exposing inference workloads and global load balancing](#exposing-inference-workloads).
- Minimize inter-region network traffic by making model files for your inference
  workloads available across different regions. For example, you can:

  - Store model files in a
    [dual- or multi-region bucket](https://cloud.google.com/storage/docs/locations).
    When model files are stored in dual- or multi-region buckets, we recommend
    that you enable
    [Anywhere Cache](https://cloud.google.com/storage/docs/anywhere-cache) to
    help you speed up scaling up your inference workloads, and to help optimize
    Cloud Storage costs.
  - Store model files in a single-region bucket, and replicate its data across
    regions using
    [Storage Transfer Service](https://cloud.google.com/storage-transfer/docs/overview).
  - Store model files in single-region buckets, and run at least one instance of
    the Model Downloader for each region to download model files for inference
    workloads running in that region.

## Online inference with GPUs design choices

This section focuses on the design choices that apply to the
[Online inference with GPUs](/platforms/gke/base/use-cases/inference-ref-arch/examples/online-inference-gpu/README.md)
use case. The Online inference with GPUs use case builds on top of the GKE
Inference reference architecture. The design choices described in this section
apply to the Online inference with GPUs use case, in addition to the
[GKE Inference reference architecture design choices](#gke-inference-reference-architecture-design-choices).

The Online inference with GPUs use case design choices cover the following:

- GPU selection
- GPUs obtainability

### GPU selection

To implement the Online inference with GPUs use case, we selected GPUs by
considering the following selection criteria:

- Obtainability
- Cost-effectiveness
- Performance

For the Online inference with GPUs, we selected the following GPUs:

- **NVIDIA** **L4 GPUs (G2 machines)**: Ideal for cost-effective,
  high-throughput online inference scenarios, offering a good balance of
  performance and efficiency.
- **NVIDIA H100 (A3 machines)**: Selected for demanding inference workloads
  where maximum throughput and low latency are critical.
- **NVIDIA H200 (A3 machines)**: Selected for providing unparalleled performance
  for the most memory-intensive inference workloads.

The following table provides a general overview of model compatibility and
recommended machine types, for the
[models that are in scope as examples](#ai-models-in-scope-as-examples):

| GPU  | Compatible Models        | Machine type            | GPU count |
| ---- | ------------------------ | ----------------------- | --------- |
| L4   | Gemma 3 27B IT           | g2-standard-96 (8 GPUs) | 8         |
|      | gpt-oss 20B              | g2-standard-96 (8 GPUs) | 8         |
|      | Qwen 3 32B               | g2-standard-96 (8 GPUs) | 8         |
| H100 | Gemma 3 27B IT           | a3-highgpu-1g (1 GPU)   | 1         |
|      | gpt-oss 20B              | a3-highgpu-1g (1 GPU)   | 1         |
|      | Qwen 3 32B               | a3-highgpu-1g (1 GPU)   | 1         |
|      | Llama 3.3 70B IT         | a3-highgpu-4g (4 GPUs)  | 4         |
|      | Llama 4 Scout 17B 16E IT | a3-highgpu-8g (8 GPUs)  | 8         |
| H200 | Gemma 3 27B IT           | a3-ultragpu-8g (8 GPUs) | 1         |
|      | gpt-oss 20B              | a3-ultragpu-8g (8 GPUs) | 1         |
|      | Qwen 3 32B               | a3-ultragpu-8g (8 GPUs) | 1         |
|      | Llama 3.3 70B IT         | a3-ultragpu-8g (8 GPUs) | 4         |
|      | Llama 4 Scout 17B 16E IT | a3-ultragpu-8g (8 GPUs) | 8         |

For more information about machine types and the available NVIDIA GPU models,
see [GPU machine types](https://cloud.google.com/compute/docs/gpus).

The Online inference with GPUs use case follows the recommendations in the
previous table, and selects the right CCC according to the requirement of each
supported model. For more information, see
[Accelerators obtainability](#accelerators-obtainability).
