# GKE Reinforcement Learning reference architecture

> [!IMPORTANT]  
> 🚀 Dynamic Landscape 🚀: The field of AI training and reinforcement learning
> is experiencing continuous, rapid evolution. This document is regularly
> updated to reflect the latest products, features, and architectural patterns,
> ensuring it remains current with the advancements in AI, Google Cloud and
> Google Kubernetes Engine.
>
> Last Update: 2026-07-03 (YYYY-MM-DD)

This document outlines the reference architecture for deploying and managing
reinforcement learning (RL) workloads, particularly on Google Kubernetes Engine
(GKE). It serves as a foundational guide for building robust, performant, and
scalable RL training, reasoning alignment, and fine-tuning solutions. This
implementation is an extension of the
[GKE Base Platform](/docs/platforms/gke/base/README.md) tailored specifically
for reinforcement learning workloads.

Refer to the [Getting Started](#getting-started) section below for instructions
on setting up the infrastructure described in this document.

## What the Platform Does

The GKE Base Platform for Reinforcement Learning provides an end-to-end,
automated deployment mechanism for running complex RL workloads on Google Cloud.
Specifically, the platform:

- **Automates Infrastructure Provisioning**: Leverages modular Terraform
  (Terraservices) to provision GKE clusters equipped with high-performance TPU
  (e.g., TPU v5e, v6e) and GPU accelerator node pools.
- **Deploys Specialized Workload Controllers**: Installs core Kubernetes
  operator extensions, including **JobSet** for multi-pod batch lifecycle
  management and **Pathways** for decoupled TPU graph execution.
- **Provisions MLOps & Experiment Tracking**: Integrates an in-cluster
  **MLflow** tracking service for real-time monitoring and logging of RL metrics
  (e.g., reward statistics, policy loss, KL divergence, learning rates).
- **Streamlines Asset Ingestion**: Integrates Cloud Build for container image
  creation, Secret Manager for Hugging Face token handling, and automated shell
  and Kustomize scripts for job configuration and deployment.

## Why Tailored for Reinforcement Learning

Reinforcement learning for Large Language Models (such as RLHF, RLAIF, and GRPO)
introduces unique operational challenges compared to standard pre-training or
pure inference:

- **Tight Coupling of Generation and Optimization**: The RL loop continuously
  alternates between rollout generation (high-throughput LLM inference across
  prompt batches), reward scoring, and policy gradient updates
  (compute-intensive backpropagation).
- **Heterogeneous & Distributed Workload Topologies**: An RL job requires
  coordinating multiple replicated job groups—rollout workers, reward models,
  and trainer nodes—that must run concurrently and synchronize at each iteration
  boundary.
- **Accelerator Efficiency & Dynamic Scheduling**: Rollout generation and
  training steps have different compute patterns. The platform optimizes TPU and
  GPU slice utilization, preventing idle accelerator cycles during phase
  transitions.
- **Coordinated Failure Handling**: If an individual worker or pod fails during
  a multi-step RL iteration, standard Kubernetes Jobs may leave hanging
  dependencies. This platform enforces atomic job group creation, lifecycle
  management, and clean failure recovery.

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
  Hub access, Secret Manager credential handling, MLflow experiment tracking,
  and containerized job execution.

## Features & Capabilities

This reference architecture provides a foundation for:

- **Policy Optimization Algorithms**: Running modern RL algorithms such as Group
  Relative Policy Optimization (GRPO) for LLM post-training and reasoning
  alignment.
- **Accelerator Framework Integration**: Leveraging Google Cloud TPUs and GPUs
  with optimized frameworks such as MaxText and JAX.
- **Job Orchestration**: Managing complex multi-pod training jobs on GKE with
  automated manifest configuration, **JobSet**, and **Pathways**.
- **Experiment & Reward Tracking**: Utilizing **MLflow** to track rewards,
  policy loss, KL divergence, step metrics, and training performance.

## Architectural Principles

- **Scalability & High Performance**: Optimize resource utilization during both
  rollout generation and gradient update steps.
- **Cost Efficiency**: Right-size accelerator node pools and leverage dynamic
  workload execution to minimize idle compute.
- **Security & Secret Management**: Store Hugging Face tokens and model access
  credentials securely in Google Cloud Secret Manager.
- **Observability & Experiment Tracking**: Combine Kubernetes job status
  monitoring, MLflow metrics logging, and Cloud Logging to track execution
  metrics and training progress.

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

### Workload Orchestration & Acceleration Technologies

#### JobSet

[JobSet](https://github.com/kubernetes-sigs/jobset) (`jobset.x-k8s.io`) is an
open-source Kubernetes API extension designed specifically for managing
multi-pod batch workloads. In reinforcement learning architectures:

- **Unified Lifecycle Management**: Manages heterogeneous groups of pods (e.g.,
  policy trainers, rollout generators, and reward evaluators) as a single
  logical workload entity.
- **Coordinated Restart & Failure Recovery**: Ensures all pods in a replicated
  job group are restarted or recreated together if any single worker fails,
  preventing split-brain states.
- **Gang Scheduling Integration**: Works seamlessly with Kueue to ensure entire
  job topologies are scheduled atomically only when all required accelerator
  resources are available.

#### Pathways

[Pathways](https://github.com/google/pathways-job) (`pathways-job`) is a
distributed system for orchestrating TPU computation graphs and managing
accelerator scheduling. In reinforcement learning architectures:

- **Decoupled Accelerator Scheduling**: Decouples client Python runtime
  execution from physical TPU hardware, allowing TPU slices to be dynamically
  allocated and managed.
- **High-Performance TPU Graph Execution**: Optimizes inter-node TPU
  communication and memory transfers for JAX and MaxText workloads.
- **Fast Phase Switching**: Enables low-latency transitions between rollout
  generation (inference) and policy gradient updates (training) across shared
  TPU resources.

#### MLflow

[MLflow](https://www.mlflow.org/) is an open-source platform for managing the
machine learning lifecycle, including experiment tracking, metrics logging, and
artifact management. In reinforcement learning architectures:

- **RL Metrics Tracking**: Records real-time step metrics including policy loss,
  KL divergence, average rewards, and completion lengths.
- **Experiment & Hyperparameter Logging**: Tracks RL training runs, reward
  function parameters, and model checkpoint metadata across experiments.
- **In-Cluster Tracking Service**: Connects via `MLFLOW_TRACKING_URI` to capture
  metrics from training workers without interrupting accelerator computation
  loops.

### Google Kubernetes Engine (GKE)

- **TPU & GPU Node Pools**: Dedicated accelerator node pools optimized for low
  latency interconnects and high memory throughput.
- **Secret Manager Integration**: Mounting secrets for accessing restricted
  model weights (e.g., Meta Llama models).

## Getting Started

A practical guide to setting up the infrastructure as described can be found in
the
[Reinforcement learning reference implementation](/platforms/gke/base/use-cases/reinforcement-learning/terraform/README.md)

This reference architecture is designed to support various reinforcement
learning patterns. Some example patterns provided are:

- [Single-host reinforcement learning with TPUs on Google Kubernetes Engine (GKE) using GRPO algorithm](/docs/platforms/gke/base/use-cases/reinforcement-learning/single-host-tpu-grpo/README.md):
  Single-host reinforcement learning workload on TPUs using MaxText, MLflow
  tracking, and the Group Relative Policy Optimization (GRPO) algorithm.

Further use cases and patterns can be built upon this foundational architecture.

## Additional Reading

- [AI/ML orchestration on GKE documentation](https://cloud.google.com/kubernetes-engine/docs/integrations/ai-infra)
- [JobSet documentation](https://jobset.sigs.k8s.io/)
- [MLflow documentation](https://www.mlflow.org/docs/latest/index.html)
- [About TPU acceleration on GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/tpus)
