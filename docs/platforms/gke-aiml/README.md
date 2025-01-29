# GKE AI/ML Platform reference architecture for enabling Machine Learning Operations (MLOps)

## Platform Principles

This reference architecture demonstrates how to build a GKE platform that
facilitates Machine Learning. The reference architecture is based on the
following principles:

- The platform admin will create the GKE platform using IaC tool like
  [Terraform](https://www.terraform.io/). The IaC will come with re-usable
  modules that can be referred to create more resources as the demand grows.
- The platform will be based on
  [GitOps](https://about.gitlab.com/topics/gitops/).
- After the GKE platform has been created, cluster scoped resources on it will
  be created through
  [Config Sync](https://cloud.google.com/anthos-config-management/docs/config-sync-overview)
  by the admins.
- Platform admins will create a namespace per application and provide the
  application team member full access to it.
- The namespace scoped resources will be created by the Application/ML teams
  either via Config Sync or through a deployment tool like
  [Cloud Deploy](https://cloud.google.com/deploy)

For an outline of products and features used in the platform, see the
[Platform Products and Features](products-and-features.md) document.

## Critical User Journeys (CUJs)

### Persona : Platform Admin

- Offer a platform that incorporates established best practices.
- Grant end users the essential resources, guided by the principle of least
  privilege, empowering them to manage and maintain their workloads.
- Establish secure channels for end users to interact seamlessly with the
  platform.
- Empower the enforcement of robust security policies across the platform.

### Persona : Machine Learning Engineer

- Deploy the model with ease and make the endpoints available only to the
  intended audience
- Continuously monitor the model performance and resource utilization
- Troubleshoot any performance or integration issues
- Ability to version, store and access the models and model artifacts:
  - To debug & troubleshoot in production and track back to the specific model
    version & associated training data
  - To quick & controlled rollback to a previous, more stable version
- Implement the feedback loop to adapt to changing data & business needs:
  - Ability to retrain / fine-tune the model.
  - Ability to split the traffic between models (A/B testing)
  - Switching between the models without breaking inference system for the
    end-users
- Ability to scaling up/down the infra to accommodate changing needs
- Ability to share the insights and findings with stakeholders to take
  data-driven decisions

### Persona : Machine Learning Operator

- Provide and maintain software required by the end users of the platform.
- Operationalize experimental workload by providing guidance and best practices
  for running the workload on the platform.
- Deploy the workloads on the platform.
- Assist with enabling observability and monitoring for the workloads to ensure
  smooth operations.

## Prerequisites

- This guide is meant to be run on [Cloud Shell](https://shell.cloud.google.com)
  which comes preinstalled with the
  [Google Cloud SDK](https://cloud.google.com/sdk) and other tools that are
  required to complete this tutorial.
- Familiarity with following
  - [Google Kubernetes Engine](https://cloud.google.com/kubernetes-engine)
  - [Terraform](https://www.terraform.io/)
  - [git](https://git-scm.com/)
  - [Google Configuration Management root-sync](https://cloud.google.com/anthos-config-management/docs/reference/rootsync-reposync-fields)
  - [Google Configuration Management repo-sync](https://cloud.google.com/anthos-config-management/docs/reference/rootsync-reposync-fields)
  - [GitHub](https://github.com/)

## Deploy the platform

[Playground Reference Architecture](/platforms/gke-aiml/playground/README.md):
Set up an environment to familiarize yourself with the architecture and get an
understanding of the concepts.

## Use cases

- [Model Fine Tuning Pipeline](/docs/use-cases/model-fine-tuning-pipeline/README.md)
  - [Distributed Data Processing with Ray](/use-cases/model-fine-tuning-pipeline/data-processing/ray/README.md):
    Run a distributed data processing job using Ray.
  - [Dataset Preparation for Fine Tuning Gemma IT With Llama 3.1 on Vertex AI](/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/README.md):
    Generate prompts for fine tuning Gemma Instruction Tuned model with Llama
    3.1 on Vertex AI
  - [Fine Tuning Gemma2 9B IT model With FSDP](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md):
    Fine tune Gemma2 9B IT model with PyTorch FSDP
  - [Model evaluation and validation](/use-cases/model-fine-tuning-pipeline/model-eval/README.md):
    Evaluation and validation of the fine tuned Gemma2 9B IT model

## Resources

- [Packaging Jupyter notebooks](/docs/guides/packaging-jupyter-notebooks/README.md):
  Patterns and tools to get your ipynb's ready for deployment in a container
  runtime.
