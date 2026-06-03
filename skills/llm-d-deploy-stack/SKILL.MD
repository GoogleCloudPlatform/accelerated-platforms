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
*   **Ask the user**: Is there an existing GKE cluster?
    *   If **yes**: Ensure `kubectl` is configured and points to the target existing GKE cluster.
        *   Command: `kubectl cluster-info` (or tool call: `kubernetes/get_cluster_info`)
    *   If **no**: We will start by running the steps in the [Terraform README](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md) to create one.

## 2. Configuration
*   Choose a model and accelerator from the list supported by the `accelerated-platforms` repo.
*   Ensure there is a valid custom compute class for the chosen accelerator.
    *   **Action**: Run the configuration and validation script: `scripts/configure_and_validate.sh` (which invokes `kubectl get customcomputeclasses`, or you can directly check using tool call: `kubernetes/list_custom_resources` for `customcomputeclasses`).
*   Select deployment options from the llm-d well-lit paths (default: `optimized-baseline`).

## 3. Deployment
*   **Rename Cluster**: Use the supporting script to update the cluster name in `platform.auto.tfvars`.
    *   Command: `./skills/llm-d-deploy-stack/scripts/deploy.sh <cluster_name>`
    *   Example: `./skills/llm-d-deploy-stack/scripts/deploy.sh llm-d-bench`
    *   *Note*: If infrastructure changes are needed, you must still run `terraform apply` in `platforms/gke/base/use-cases/inference-ref-arch/terraform` after running this script.

*   **Deploy llm-d Stack**:
    1.  The base Helm and Kustomize overlays will come from the official llm-d Github (e.g., `https://github.com/llm-d/llm-d/tree/main/guides/optimized-baseline`).
    2.  If a model other than the default (e.g., Qwen3-32B) is chosen, locate the specific "accelerator-model" folder in this repository under `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/` (e.g., `l4-qwen3-32b` or `l4-gemma-3-1b-it`).
    3.  Apply those specific manifests *in addition* to the llm-d ones (or use the tool call: `kubernetes/apply_manifest`).
    4.  Update the llm-d manifests with the appropriate model arguments (e.g., `--model`, `--tensor-parallel-size`, etc. matching the chosen model and accelerator configuration).
    5.  Apply the combined configuration to the cluster.


## 4. Verification
*   Check that all pods are running and services are accessible.
    *   Command: `kubectl get pods -n $NAMESPACE` (or tool call: `kubernetes/list_pods` with namespace)
*   Ensure no secrets (like HF token) are stored in plain text.
    *   Command: `kubectl describe secret hf-token -n $NAMESPACE` (or tool call: `kubernetes/get_secret` with namespace and secret name to verify existence and check metadata).

