---
name: llm-d-deploy-stack
description: Deploys the llm-d benchmarking stack on an existing GKE cluster.
version: 0.2.0
allowed-tools: kubectl gcloud helm kustomize curl cat source
mcp-servers:
  - kubernetes:
      reason: "Inspect cluster info, custom compute classes, pod statuses, and secrets."
  - gcp:
      reason: "Verify GKE cluster status."
---

# Deploy llm-d Stack Skill

Follow these instructions to deploy the llm-d benchmarking stack on an existing GKE cluster.

## 1. Prerequisites

- **Ask the user**: Is there an existing GKE cluster?
  - If **yes**: Ensure `kubectl` is configured and points to the target existing GKE cluster.
    - Command: `kubectl cluster-info` (or tool call: `kubernetes/get_cluster_info`)
  - If **no**: We will start by running the steps in the [Terraform README](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md) to create one.

## 2. Configuration

- Choose a model (`google/gemma-4-31b-it` or `Qwen/Qwen3-32B-Instruct`) and accelerator (`rtx-pro-6000`, `nvidia-h100`, or `v6e` TPU).
- Ensure there is a valid custom compute class for the chosen accelerator.
  - **Action**: Run the configuration and validation script: `scripts/configure_and_validate.sh` (which checks compute classes and overlay structures).
- Select deployment options from the llm-d well-lit paths: `optimized-baseline`, `precise-prefix-cache-routing`, or `predicted-latency-routing`.

## 3. Deployment

- **Rename Cluster**: Use the supporting script to update the cluster name in `platform.auto.tfvars`.

  - Command: `./skills/llm-d-deploy-stack/scripts/deploy.sh <cluster_name>`
  - Example: `./skills/llm-d-deploy-stack/scripts/deploy.sh llm-d-bench`
  - _Note_: If infrastructure changes are needed, you must still run `terraform apply` in `platforms/gke/base/use-cases/inference-ref-arch/terraform` after running this script.

- **Deploy llm-d Stack**:
  1. The base Helm and Kustomize overlays come from the official llm-d Github repository strategy directories.
  2. Locate the specific "accelerator-model" folder in this repository under `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-<platform>/llmd-<strategy>/vllm/` (e.g., `rtx-pro-6000-gemma-4-31b-it` or `h100-qwen3-32b`).
  3. Apply those specific manifests in addition to the llm-d routing manifests.
  4. Ensure model parameters (e.g. `--model`, `--tensor-parallel-size`) match the chosen accelerator and model configuration.
  5. Apply the combined configuration overlay to the cluster.

## 4. Verification

- Check that all pods are running and services are accessible.
  - Command: `kubectl get pods -n $NAMESPACE`
- Ensure the Hugging Face token is securely configured via GCP Secret Manager and exposed via SecretProviderClass:
  - Command: `kubectl describe secretProviderClass huggingface-tokens -n $NAMESPACE`
  - Command: `kubectl describe secret llm-d-hf-token -n $NAMESPACE`
