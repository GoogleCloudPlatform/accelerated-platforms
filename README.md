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

## Google Kubernetes Engine (GKE)

### Base GKE Accelerated Platform

The [Base GKE Accelerated Platform](/platforms/gke/base/README.md) is an
implementation of a foundational platform built on GKE that incorporates best
practices and provides a core environment optimized for running accelerated
workloads. It offers a streamlined and efficient solution to leverage the
benefits of GKE as the primary runtime.

#### Example implementations

- [GKE AI/ML Platform for enabling AI/ML Ops](/docs/platforms/gke-aiml/README.md)
- [Federated learning](/docs/use-cases/federated-learning/README.md)
- [Inference reference architecture](/platforms/gke/base/use-cases/inference-ref-arch/README.md)

### Playground AI/ML Platform on GKE

The [Playground AI/ML Platform on GKE](/platforms/gke-aiml/playground/README.md)
is a quick-start implementation of the platform that can be used to familiarize
yourself with the GKE architecture and to get an understanding of various
concepts covered in the use cases.

#### Use cases

- [Model Fine Tuning Pipeline](/docs/use-cases/model-fine-tuning-pipeline/README.md)
- [Scalable and Distributed LLM Inference on GKE with vLLM](/docs/use-cases/inferencing/README.md)
- [Retrieval Augmented Generation (RAG) pipeline](/docs/use-cases/rag-pipeline/README.md)

## Contributing

For more information about contributing to this repository, see
[CONTRIBUTING](/CONTRIBUTING.md).
