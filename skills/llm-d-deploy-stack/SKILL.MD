---
name: llm-d-deploy-stack
description: Deploys the llm-d benchmarking stack on GKE using well-lit paths.
version: 0.3.1
allowed-tools: kubectl gcloud helm kustomize curl cat source
mcp-servers:
  - kubernetes:
      reason: "Inspect cluster info, custom compute classes, pod statuses, and secrets."
  - gcp:
      reason: "Verify GKE cluster status."
---

# Deploy llm-d Stack Skill

Follow these instructions to deploy the llm-d benchmarking stack on GKE.

## 1. Prerequisites & Cluster Setup

1.  **Ask the user**: "Is there an existing GKE cluster? (yes/no)"
2.  **If NO**:
    - **Ask the user**: "What platform name would you like to use for the new cluster?"
    - Update the platform name in configuration:
      ```bash
      "${ACP_REPO_DIR}/skills/llm-d-deploy-stack/scripts/deploy.sh" <platform_name>
      ```
    - Proceed to **Section 2: Select & Deploy Well-Lit Path Guide** (to create cluster and deploy stack).
3.  **If YES**:
    - Verify connectivity to the target cluster:
      ```bash
      kubectl cluster-info
      ```
    - **Ask the user**: "Is the llm-d stack already deployed on this cluster? (yes/no)"
    - **If YES**:
      - Skip to **Section 3: Configure Model & Accelerator** (we only need to deploy the model server).
    - **If NO**:
      - Proceed to **Section 2: Select & Deploy Well-Lit Path Guide** (to deploy stack on existing cluster).

## 2. Select & Deploy Well-Lit Path Guide

1.  **Ask the user**: "Which llm-d well-lit path guide would you like to deploy?"

    - **Allowed Options**:
      - `optimized-baseline` (corresponds to [llmd-optimized-baseline-vllm-with-hf-model.md](../../docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-optimized-baseline-vllm-with-hf-model.md))
      - `precise-prefix-cache-routing` (corresponds to [llmd-precise-prefix-cache-routing-vllm-with-hf-model.md](../../docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-precise-prefix-cache-routing-vllm-with-hf-model.md))
      - `predicted-latency-routing` (corresponds to [llmd-predicted-latency-routing-vllm-with-hf-model.md](../../docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-predicted-latency-routing-vllm-with-hf-model.md))
    - _Validation_: If the user inputs anything else, flag it as invalid, display the list of allowed options, and ask again.

2.  **Deploy the baseline stack**:
    Run the deployment script corresponding to the chosen guide to create the cluster (if new) and deploy the baseline infra/services:
    - For `optimized-baseline`:
      ```bash
      "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/deploy-llmd-optimized-baseline.sh"
      ```
    - For `precise-prefix-cache-routing`:
      ```bash
      "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/deploy-llmd-precise-prefix-cache-routing.sh"
      ```
    - For `predicted-latency-routing`:
      ```bash
      "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/deploy-llmd-predicted-latency-routing.sh"
      ```

## 3. Configure Model & Accelerator

1.  **Ask the user**: "Which model would you like to run?"
    - **Allowed Models**:
      - `google/gemma-4-31b-it`
      - `qwen/qwen3-32b` (default)
    - _Validation_: If the user inputs anything else, flag it as invalid, display the allowed models, and ask again.
2.  **Ask the user**: "Which accelerator would you like to use?"
    - **Allowed Accelerators**:
      - `rtx-pro-6000` (default)
      - `h100`
      - `h200`
      - `v6e` (TPU)
    - _Validation_: If the user inputs anything else, flag it as invalid, display the allowed accelerators, and ask again.
3.  **Update configuration**:
    - Write the chosen model to `llmd_model_id` in `platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd-shared.auto.tfvars`.
    - Write the chosen accelerator to `llmd_accelerator_type` in `platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd-shared.auto.tfvars`.
4.  **Run validation**:
    - Execute the configuration and validation script to verify custom compute classes and overlay structure:
      ```bash
      HF_MODEL_ID="<chosen_model>" ACCELERATOR_TYPE="<chosen_accelerator>" DEPLOYMENT_STRATEGY="<strategy>" MODEL_SERVER="vllm" "${ACP_REPO_DIR}/skills/llm-d-deploy-stack/scripts/configure_and_validate.sh"
      ```
      _(Note: Map the chosen guide to DEPLOYMENT_STRATEGY: `optimized-baseline`, `precise-prefix-cache-routing`, or `predicted-latency-routing`. MODEL_SERVER specifies the engine, e.g., `vllm`)._

## 4. Hugging Face Token Setup

1.  **Source environment variables**:
    ```bash
    source "platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
    ```
2.  **Instruct the user** to add their Hugging Face Read Token to Google Secret Manager and as a Kubernetes secret:
    Provide them with these commands, replacing `<YOUR_HUGGINGFACE_READ_TOKEN>` with their actual token:

    ```bash
    # Add to Secret Manager
    HF_TOKEN_READ=<YOUR_HUGGINGFACE_READ_TOKEN>
    echo ${HF_TOKEN_READ} | gcloud secrets versions add ${huggingface_hub_access_token_read_secret_manager_secret_name} --data-file=- --project=${huggingface_secret_manager_project_id}

    # Add to Kubernetes
    kubectl -n ${llmd_namespace} create secret generic llm-d-hf-token --from-literal=HF_TOKEN="${HF_TOKEN_READ}"
    ```

3.  **WAIT**: Stop calling tools and ask the user to confirm once they have run these commands. Do not proceed until the user confirms.

## 5. Deploy Model Download Job & Model Server

Once the user confirms the token is configured, proceed with the deployment:

1.  **Deploy the model download job**:
    ```bash
    # Configure
    "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
    # Apply
    kubectl apply --kustomize "platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
    ```
2.  **Wait for download to complete**:
    Monitor the job:
    ```bash
    kubectl get job -n ${huggingface_hub_downloader_kubernetes_namespace_name}
    ```
    Wait until the job status shows `Complete`.
3.  **Clean up the download job**:
    Once the download is complete, delete the job to free up GKE resources:
    ```bash
    kubectl delete job -n ${huggingface_hub_downloader_kubernetes_namespace_name} hf-model-to-gcs
    ```
4.  **Deploy the Model Server**:
    - Configure the model server (run the script for GPU or TPU as indicated by the chosen accelerator):
      - If GPU:
        ```bash
        "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd-<strategy>/vllm/configure_vllm.sh"
        ```
      - If TPU:
        ```bash
        "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-<strategy>/vllm/configure_vllm.sh"
        ```
    - Deploy using the overlay directory (obtained from `configure_and_validate.sh` output):
      ```bash
      kubectl apply --kustomize <overlay_dir>
      ```

## 6. Verification

- Check that all pods are running and services are accessible.
  ```bash
  kubectl get pods -n $NAMESPACE
  ```
- Ensure the Hugging Face token is securely configured:
  ```bash
  kubectl describe secretProviderClass huggingface-tokens -n $NAMESPACE
  kubectl describe secret llm-d-hf-token -n $NAMESPACE
  ```
