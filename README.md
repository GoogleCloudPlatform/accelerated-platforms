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

### GKE Base Platform

The [GKE Base Platform](/docs/platforms/gke/base/README.md)
([reference implementation](/platforms/gke/base/core/README.md)) is an
opinionated, foundational platform built on GKE using modular Terraform
(Terraservices) that incorporates security, networking, observability, and
autoscaling best practices optimized for running accelerated AI/ML workloads.

#### Inference Reference Architecture

Standardized, production-grade patterns and automated deployments for serving
real-time, streaming, async, and batch AI inference across single-region and
multi-region GKE clusters with GPUs and TPUs.

- [GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md)
  - [GKE Inference reference implementation (Terraform)](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  - [GKE Inference architecture design and best practices](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-best-practices.md)
- **Multi-region GKE inference, NVIDIA Dynamo, and NVIDIA TensorRT-LLM**
  - [Multi-region GKE inference foundation](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md)
    and
    [Multi-region Terraform foundation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/README.md)
    — Hub-and-spoke multi-cluster GKE topology with deterministic VPC subnets,
    fleet service exports, and global cross-region Envoy Gateway failover.
  - [NVIDIA Dynamo and TensorRT-LLM reference architecture on multi-region GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md)
    — KV-cache-aware routing, pinned host-memory KV cache offloading,
    disaggregated prefill/decode (P/D), and cross-region failover on NVIDIA
    Blackwell `RTX PRO 6000` GPUs.
    - [15-minute live demo runbook: Multi-region NVIDIA Dynamo KV routing, host KV cache offloading, disaggregated P/D, and cross-region failover](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-poc-15min-demo-runbook.md)
  - [NVIDIA TensorRT-LLM and Nemotron-3 reference architecture on multi-region GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/trtllm-nemotron3-reference-architecture.md)
    — Global open-model inference with `NVFP4` quantization, Multi-Token
    Prediction (MTP), Cloud Storage Anywhere Cache, and GKE Pod snapshots on
    `RTX PRO 6000` GPUs.
    - [15-minute live demo runbook: Global open-model inference with TensorRT-LLM, NVIDIA Nemotron-3, and GKE Pod snapshots](/docs/platforms/gke/base/use-cases/inference-ref-arch/trtllm-poc-15min-demo-runbook.md)
- **Rapid PoC, fast-start model streaming, and GKE Pod snapshots**
  - [AI inference proof-of-concept (PoC) and capacity-finding guide](/docs/platforms/gke/base/use-cases/inference-ref-arch/poc-capacity-and-rapid-deployment-guide.md)
    - [15-minute live demo runbook: Multi-region GPU capacity farming, fast-start model streaming, and sub-minute GKE Pod snapshot restore](/docs/platforms/gke/base/use-cases/inference-ref-arch/poc-15min-demo-runbook.md)
  - [GKE Pod snapshots inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md)
    - [Online inference using vLLM with GKE Pod snapshots and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-podsnapshots.md)
  - [Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md)
    - [Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md)
- **[Online inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/README.md)**
  - [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)
  - [Online inference using vLLM with speculative decoding and GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-spec-decoding-with-hf-model.md)
  - [Online inference using vLLM native KV cache offloading on GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-native-kv-cache-offloading-single-tier.md)
  - [Automated vLLM server parameter tuning on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-auto-tuner.md)
  - [Online inference using Diffusers with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/diffusers-with-hf-model.md)
- **[Online inference with TPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/README.md)**
  - [Online inference using vLLM with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm-with-hf-model.md)
  - [Online inference using MaxDiffusion with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/max-diffusion-with-hf-model.md)
- **Intelligent inference scheduling with `llm-d`**
  - [Intelligent inference scheduling with llm-d](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/llmd-vllm-with-hf-model.md)
  - [llm-d Well-Lit paths on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-well-lit-paths.md)
    - [Optimized Baseline](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-optimized-baseline-vllm-with-hf-model.md)
    - [Predicted Latency Routing](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-predicted-latency-routing-vllm-with-hf-model.md)
    - [Precise Prefix Cache Routing](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-precise-prefix-cache-routing-vllm-with-hf-model.md)
    - [Prefill/Decode Disaggregation](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-pd-disaggregation-vllm-with-hf-model.md)
- **Async, batch, and inference benchmarking**
  - [Async inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/async-inference/README.md)
  - [Batch inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/batch-inference/README.md)
  - [Benchmarking online inference performance with inference-perf](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/inf-perf-benchmarking-with-hf-model.md)
  - [Benchmarking online inference performance with k6](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/inf-perf-benchmarking-with-k6-hf-model.md)

#### Training Reference Architecture

Scalable distributed training and fine-tuning blueprints on GKE with GPUs and
Cloud TPUs.

- [GKE Training reference architecture](/docs/platforms/gke/base/use-cases/training-ref-arch/README.md)
  - [GKE Training reference implementation (Terraform)](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
- [Model fine-tuning pipeline](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/README.md)
  - [Data processing](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/data-processing.md)
  - [Data preparation](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/data-preparation.md)
  - [Fine-tuning](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/fine-tuning.md)
  - [Model evaluation](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/model-evaluation.md)
- **Supervised fine-tuning (SFT) on Cloud TPUs**
  - [Single-host SFT using MaxText with TPUs](/docs/platforms/gke/base/use-cases/training-ref-arch/sft-tpu-maxtext-single-host/README.md)
  - [Multi-host SFT using MaxText with TPUs](/docs/platforms/gke/base/use-cases/training-ref-arch/sft-tpu-maxtext-multi-host/README.md)

#### Reinforcement Learning

End-to-end infrastructure and workload orchestration for reinforcement learning
(RL), reasoning alignment, and post-training on GKE with JobSet, Pathways, and
Cloud TPUs.

- [Reinforcement Learning reference architecture](/docs/platforms/gke/base/use-cases/reinforcement-learning/README.md)
  - [Reinforcement Learning reference implementation (Terraform)](/platforms/gke/base/use-cases/reinforcement-learning/terraform/README.md)
  - [Single-host reinforcement learning with TPUs using GRPO algorithm](/docs/platforms/gke/base/use-cases/reinforcement-learning/single-host-tpu-grpo/README.md)

#### Secure Runtimes for AI Agents Reference Architecture (GKE Agent Sandbox & Agent Substrate)

Defense-in-depth runtime architecture and interactive Red Team vs. Blue Team
testbed for autonomous AI agents on GKE using GKE Sandbox (`gVisor`),
zero-secret egress credential injection, and millisecond memory snapshot
recovery.

- [Secure Runtimes for AI Agents reference architecture (GKE Agent Sandbox & Agent Substrate)](/docs/platforms/gke/base/use-cases/agent-substrate-security-demo/README.md)
  - [Secure Runtimes for AI Agents reference implementation (gVisor sandboxing, zero-secret egress, millisecond memory snapshot restore)](/platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/README.md)

#### ComfyUI Reference Implementation

End-to-end reference implementation for deploying ComfyUI image and video
generation workflows on GKE with GPU acceleration and Cloud Storage integration.

- [ComfyUI reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui/README.md)

#### Federated Learning

Isolated, multi-tenant GKE blueprint for running cross-silo and cross-device
federated learning workloads on Google Cloud.

- [Federated learning reference architecture](/docs/platforms/gke/base/use-cases/federated-learning/README.md)
  - [Deploy the Federated learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md)
    - [Cross-device federated computation example](/platforms/gke/base/use-cases/federated-learning/examples/cross-device/README.md)
    - [NVIDIA FLARE cross-silo federated learning example](/platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/README.md)

### Guides

- [LLM Inference Optimization: Achieving faster Pod Startup with Google Cloud Storage](/use-cases/inferencing/cost-optimization/gcsfuse/AchievingFasterPodStartup.md)
- [Optimizing GKE Workloads with Custom Compute Classes](/docs/guides/optimizing-gke-workloads-with-custom-compute-classes/README.md)
- [Packaging Jupyter notebook as deployable code](/docs/guides/packaging-jupyter-notebooks/README.md)

## Cloud Workstations (CWS)

> [!NOTE]  
> The Cloud Workstations (CWS) Platform is currently in beta and is still being
> actively developed.

The [Cloud Workstations (CWS) Platform](/docs/platforms/cws/README.md) is a
core, best practices, fully managed workstation environment built to meet the
needs of security-sensitive enterprises. It enhances the security of workstation
environments while accelerating onboarding and productivity.

- [Cloud Workstations reference architecture](/docs/platforms/cws/reference-architecture.md)
  - [Cloud Workstations reference implementation](/docs/platforms/cws/reference-implementation.md)

## Contributing

For more information about contributing to this repository, see
[CONTRIBUTING](/CONTRIBUTING.md) and the
[GKE Base Platform developers guide](/platforms/gke/base/use-cases/DEVELOPER.md).
