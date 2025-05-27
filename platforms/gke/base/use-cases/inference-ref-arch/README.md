# Inference reference architecture

This document outlines the reference architecture for deploying and managing
inference workloads, particularly on Google Kubernetes Engine (GKE). It serves
as a foundational guide for building robust and scalable inference solutions.
This implementation is an extension of the
[Base GKE Accelerated Platform](/platforms/gke/base/README.md) tailored for
inference workloads.

## Purpose

The primary goal of this reference architecture is to provide a best practices,
well-defined framework for serving models. It aims to:

- **Standardize Deployments:** Offer a consistent and repeatable methodology for
  deploying inference workloads, reducing operational complexity.
- **Optimize for Performance & Cost:** Leverage GKE's capabilities, including
  autoscaling and potential hardware acceleration (GPUs, TPUs), to ensure
  low-latency, high-throughput inference while managing costs effectively.
- **Enable Scalability:** Design workloads that can automatically scale based on
  real-time demand, ensuring responsiveness and resource efficiency.
- **Promote \*Ops Best Practices:** Incorporate industry best practices for the
  model lifecycle, including model versioning, monitoring, logging, and security
  in an inference context.
- **Accelerate Implementation:** Provide a clear and actionable path to a
  working inference workloads through well-defined components and examples.

## Key Features & Capabilities

This reference architecture provides a foundation for:

- Deploying various types of models for real-time (online) or batch (offline)
  inference.
- Utilizing hardware accelerators like GPUs and TPUs for computationally
  intensive models.
- Implementing robust monitoring and logging for inference workloads.
- Managing model versions and rollouts.
- Integrating with broader \*Ops pipelines.
- Ensuring secure and reliable model serving.

## Getting Started

A practical guide to setting up the infrastructure as described can be found in
the
[Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)

This reference architecture is designed to support various inference patterns.
Some example patterns provided are:

- [ComfyUI reference implementation](platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui/README.md)
- [Online inference with GPUs](/platforms/gke/base/use-cases/inference-ref-arch/examples/online-inference-gpu/README.md)

Further use cases and patterns can be built upon this foundational architecture.

## Additional Reading

- [AI/ML orchestration on GKE documentation](https://cloud.google.com/kubernetes-engine/docs/integrations/ai-infra)
- [About AI/ML model inference on GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/machine-learning/inference)
- [Best practices for running cost-optimized Kubernetes applications on GKE](https://cloud.google.com/architecture/best-practices-for-running-cost-effective-kubernetes-applications-on-gke)
