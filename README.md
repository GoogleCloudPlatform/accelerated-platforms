# Google Cloud Accelerated Platforms

This repository is a collection of accelerated platform best practices,
reference architectures, example use cases, reference implementations, and
various other assets on Google Cloud.

An accelerated platform utilizes specialized hardware components, or
accelerators, such as
[GPUs (Graphics Processing Units)](https://cloud.google.com/gpu) and
[TPUs (Tensor Processing Units)](https://cloud.google.com/tpu), to significantly
increase the speed of computationally intensive tasks. These tasks may include
data analysis, machine learning, artificial intelligence, and graphics
rendering. By offloading demanding workloads from traditional CPUs to dedicated
hardware accelerators, which are capable of much faster parallel calculations,
the platform optimizes high-performance computing.

## Cloud Workstations (CWS)

> [!NOTE]  
> The Cloud Workstations (CWS) Platform is currently in beta and is still being
> actively developed.

The [Cloud Workstations (CWS) Platform](/docs/platforms/cws/README.md) is a
core, best practices, fully managed workstation environments built to meet the
needs of security-sensitive enterprises. It enhances the security of workstation
environments while accelerating onboarding and productivity.

- [Cloud Workstations reference architecture](/docs/platforms/cws/reference-architecture.md)
  - [Cloud Workstations reference implementation](/docs/platforms/cws/reference-implementation.md)

## Google Kubernetes Engine (GKE)

### GKE Base Platform

The [GKE Base Platform](/docs/platforms/gke/base/README.md) is an implementation
of a foundational platform built on GKE that incorporates best practices and
provides a core environment optimized for running accelerated workloads. It
offers a streamlined and efficient solution to leverage the benefits of GKE as
the primary runtime.

#### Example implementations

- [ComfyUI reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui/README.md)
- [Federated learning](/docs/platforms/gke/base/use-cases/federated-learning/README.md)
- [Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md)
  - [Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
    - [Online inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/README.md)
      - [Online inference using Diffusers with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/diffusers-with-hf-model.md)
      - [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)
    - [Online inference with TPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/README.md)
      - [Online inference using MaxDiffusion with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/max-diffusion-with-hf-model.md)
      - [Online inference using vLLM with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm-with-hf-model.md)
    - [Batch inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/batch-inference/README.md)
    - [Offline batch inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/offline-batch/README.md)
- [Training reference architecture](/docs/platforms/gke/base/use-cases/training-ref-arch/README.md)
  - [Model fine tuning](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/README.md)
    - [Data processing](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/data-processing.md)
    - [Data preparation](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/data-preparation.md)
    - [Fine tuning](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/fine-tuning.md)
    - [Model evaluation](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/model-evaluation.md)

### Guides

- [LLM Inference Optimization: Achieving faster Pod Startup with Google Cloud Storage](/use-cases/inferencing/cost-optimization/gcsfuse/AchievingFasterPodStartup.md)
- [Optimizing GKE Workloads with Custom Compute Classes](/docs/guides/optimizing-gke-workloads-with-custom-compute-classes/README.md)

### [Deprecated] Playground AI/ML Platform on GKE

The [Playground AI/ML Platform on GKE](/platforms/gke-aiml/playground/README.md)
is a quick-start implementation of the platform that can be used to familiarize
yourself with the GKE architecture and to get an understanding of various
concepts covered in the use cases.

- [GKE AI/ML Platform for enabling AI/ML Ops](/docs/platforms/gke-aiml/README.md)

#### Use cases

- [Scalable and Distributed LLM Inference on GKE with vLLM](/docs/use-cases/inferencing/README.md)
- [Retrieval Augmented Generation (RAG) pipeline](/docs/use-cases/rag-pipeline/README.md)

## Contributing

For more information about contributing to this repository, see
[CONTRIBUTING](/CONTRIBUTING.md).
