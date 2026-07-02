# GKE Reinforcement Learning reference architecture

> [!IMPORTANT]  
> 🚀 Dynamic Landscape 🚀: The field of AI training and reinforcement learning
> is experiencing continuous, rapid evolution. This document is regularly
> updated to reflect the latest products, features, and architectural patterns,
> ensuring it remains current with the advancements in AI, Google Cloud and
> Google Kubernetes Engine.
>
> Last Update: 2026-07-02 (YYYY-MM-DD)

This document outlines the reference architecture for deploying and managing
reinforcement learning (RL) workloads, particularly on Google Kubernetes Engine
(GKE). It serves as a foundational guide for building robust, performant, and
scalable RL training and fine-tuning solutions. This implementation is an
extension of the [GKE Base Platform](/docs/platforms/gke/base/README.md)
tailored for reinforcement learning workloads.

Refer to the [Getting Started](#getting-started) section below for instructions
on setting up the infrastructure described in this document.

## Purpose

The primary goal of this reference architecture is to provide a best-practices,
well-defined framework for running reinforcement learning workflows on GKE. It
aims to:

- **Standardize RL Workflows**: Offer a consistent methodology for deploying
  policy training, rollout generation, and reward scoring components on GKE.
- **Optimize Hardware Acceleration**: Efficiently leverage TPUs and GPUs on GKE
  for both high-throughput inference (rollouts) and compute-intensive policy
  optimization.
- **Enable Scalability**: Support scaling RL training jobs and generation
  workloads across single-host and multi-host accelerator configurations.
- **Promote MLOps Best Practices**: Integrate model checkpointing, Hugging Face
  Hub access, Secret Manager credential handling, and containerized job
  execution.

## Features & Capabilities

This reference architecture provides a foundation for:

- **Policy Optimization Algorithms**: Running modern RL algorithms such as Group
  Relative Policy Optimization (GRPO) for LLM post-training and reasoning
  alignment.
- **Accelerator Integration**: Leveraging Google Cloud TPUs (e.g., TPU v5e and
  v6e) and GPUs with optimized frameworks such as MaxText.
- **Job Orchestration**: Managing batch training jobs on GKE with automated
  manifest configuration and containerized image builds.

## Architectural Principles

- **Scalability & High Performance**: Optimize resource utilization during both
  rollout generation and gradient update steps.
- **Cost Efficiency**: Right-size accelerator node pools and leverage dynamic
  workload execution to minimize idle compute.
- **Security & Secret Management**: Store Hugging Face tokens and model access
  credentials securely in Google Cloud Secret Manager.
- **Observability & Monitoring**: Utilize Kubernetes job status monitoring and
  Cloud Logging to track execution metrics and training progress.

## Core Concepts and Technologies

### Reinforcement Learning Workloads

Reinforcement learning for Large Language Models (RLHF / RLAIF) involves
iterating between:

1. **Rollout Generation**: Generating completions for prompt datasets using the
   current policy model.
2. **Reward Evaluation**: Scoring generated completions using reward functions
   or reward models (e.g., GRPO relative scoring).
3. **Policy Optimization**: Updating policy weights using gradient updates
   calculated from advantage estimations.

### Google Kubernetes Engine (GKE)

- **TPU & GPU Node Pools**: Dedicated accelerator node pools optimized for low
  latency interconnects and high memory throughput.
- **Kubernetes Jobs**: Batch job execution for orchestrating RL training runs.
- **Secret Manager Integration**: Mounting secrets for accessing restricted
  model weights (e.g., Meta Llama models).

## Getting Started

A practical guide to setting up the infrastructure as described can be found in
the example pattern below:

This reference architecture is designed to support various reinforcement
learning patterns. Some example patterns provided are:

- [Single-host reinforcement learning with TPUs on Google Kubernetes Engine (GKE) using GRPO algorithm](/docs/platforms/gke/base/use-cases/reinforcement-learning/single-host-tpu-grpo/README.md):
  Single-host reinforcement learning workload on TPUs using MaxText and the
  Group Relative Policy Optimization (GRPO) algorithm.

Further use cases and patterns can be built upon this foundational architecture.

## Additional Reading

- [AI/ML orchestration on GKE documentation](https://cloud.google.com/kubernetes-engine/docs/integrations/ai-infra)
- [About TPU acceleration on GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/tpus)
