---
name: llm-d-deploy-stack
description: Deploys the llm-d stack on GKE using well-lit paths specification.
version: 0.3.1
allowed-tools: kubectl gcloud helm kustomize curl terraform python3
mcp-servers:
  - kubernetes:
      reason: "Inspect cluster info, custom compute classes, pod statuses, and secrets."
  - gcp:
      reason: "Verify GKE cluster status."
--- 

# Deploy llm-d Stack Skill

Follow these instructions to deploy the llm-d benchmarking stack on GKE.

## Terminology & Variables

This skill utilizes the following core variables:

- `SPEC` (also referred to as `strategy` or `guide`): This represents the name of the `llm-d` well-lit path guide being targeted. It maps directly to GKE overlay folder structures (`llmd-<spec>`)
  - **Allowed Values:**
    - `optimized-baseline` (Standard optimized baseline configuration).
    - `precise-prefix-cache-routing` (Includes precise cache routing for multi-turn workloads).
    - `predicted-latency-routing` (Includes dynamic latency-based routing overlays).

- **CRITICAL WARNING:**
    1. **NEVER run any `teardown-*.sh` scripts** (e.g., `teardown-llmd-optimized-baseline.sh`) when attempting to "fix and rerun" a deployment or remove a workload. These scripts default to a full core platform teardown (`ACP_TEARDOWN_CORE_PLATFORM=true`) and will completely destroy the GKE cluster and all its resources. If a deployment fails, debug in place or re-run the `deploy` scripts. ONLY run teardown script when the user explicitly asks to tear down the stack and confirm with you first.
    2. **NEVER Store a secret value or retrieve a value of a secret** in memory or write it to any file. Instead, always use gcloud secrets describe [SECRET_NAME] OR kubectl get kubectl get secret [SECRET_NAME] -o yaml. If a secret does not exist ask the user to create it. 


## 1. Prerequisites & Cluster Setup

1.  **Ask the user**: "Is there an existing GKE cluster? (yes/no)"
2.  **If NO**:
    - **Ask the user**: "What platform name would you like to use for the new cluster, and what is your Google Cloud project ID?"
    - Use `sed` to inject these values into `${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars`:
      ```bash
      sed -i 's/^platform_name.*/platform_name = "<platform_name>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
      # If platform_default_project_id doesn't exist, append it:
      grep -q "^platform_default_project_id" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars" || echo "platform_default_project_id = \"\"" >> "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
      sed -i 's/^platform_default_project_id.*/platform_default_project_id = "<project_id>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
      ```
    - Proceed to **Section 2: Configure Model & Accelerator** (to configure variables and create cluster).
3.  **If YES**:
    - Verify connectivity to the target cluster:
      ```bash
      kubectl cluster-info
      ```
    - **Ask the user**: "Is the llm-d stack already deployed on this cluster? (yes/no)"
    - **If YES**:
      - Skip to **Section 4: Hugging Face Token Setup** (we only need to deploy the model server, which is done in Section 5).
    - **If NO**:
      - Proceed to **Section 2: Configure Model & Accelerator** (to configure the deployment variables).

## 2. Configure Model & Accelerator

1.  **Ask the user**: "Which model would you like to run?"
    - **Allowed Models**:
      - `google/gemma-4-31b-it`
      - `qwen/qwen3-32b` (default)
    - _Validation_: If the user inputs anything else, flag it as invalid, display the allowed models, and ask again.
2.  **Ask the user**: "Which accelerator would you like to use?"
    - **Allowed Accelerators**:
      - `rtx-pro-6000` (default)
      - `h100` (translates to `nvidia-h100`)
      - `h200` (translates to `nvidia-h200`)
      - `v6e` (TPU, translates to `google-tpu-v6e`)
    - _Validation_: If the user inputs anything else, flag it as invalid, display the allowed accelerators, and ask again.
3.  **Update configuration**:
    - Use `sed` to inject the chosen model and accelerator into `${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd.auto.tfvars`:
      ```bash
      echo "llmd_model_id = \"<chosen_model>\"" >> "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd-shared.auto.tfvars"
      echo "llmd_accelerator_type = \"<chosen_accelerator>\"" >> "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/llmd-shared.auto.tfvars"
      ```

## 3. Select & Deploy Well-Lit Path Guide

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
4.  **Run validation**:
    - Run the following command to verify the chosen custom compute class exists on the cluster:
      ```bash
      kubectl get computeclasses
      ```
    - Ensure that the accelerator type you chose appears in the list. If it does not, warn the user that the accelerator is unsupported or missing its custom compute class.


## 4. Hugging Face Token Setup

1.  **Instruct the user** to add their Hugging Face Read Token to Google Secret Manager and as a Kubernetes secret:
    Provide them with these commands, replacing `<YOUR_HUGGINGFACE_READ_TOKEN>` with their actual token. Note that the `source` command must be run in the same shell session as the subsequent commands so the environment variables are preserved:

    ```bash
    # Source environment variables
    source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"

    # Add to Secret Manager
    HF_TOKEN_READ=<YOUR_HUGGINGFACE_READ_TOKEN>
    echo ${HF_TOKEN_READ} | gcloud secrets versions add ${huggingface_hub_access_token_read_secret_manager_secret_name} --data-file=- --project=${huggingface_secret_manager_project_id}

    # Add to Kubernetes
    kubectl -n ${llmd_namespace} create secret generic llm-d-hf-token --from-literal=HF_TOKEN="${HF_TOKEN_READ}"
    ```

2.  **WAIT**: Stop calling tools and ask the user to confirm once they add the HF token to secret manager and kubernetes secret Do not proceed until the user confirms.

## 5. Deploy Model Download Job & Model Server

Once the user confirms the token is configured, proceed with the deployment:

1.  **Deploy the model download job**:
    ```bash
    # Configure
    "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
    # Apply
    kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
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
        "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd-<spec>/vllm/configure_vllm.sh"
        ```
      - If TPU:
        ```bash
        "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-<spec>/vllm/configure_vllm.sh"
        ```
    - Deploy using the appropriate overlay directory. Construct the directory path as:
      `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-[gpu|tpu]/llmd-[spec]/vllm/[prefix]-[suffix]`
      - `[gpu|tpu]`: Use `tpu` if the accelerator is `v6e`, otherwise `gpu`.
      - `[spec]`: The well-lit path chosen in Section 3.
      - `[prefix]`: The accelerator prefix (e.g., `rtx-pro-6000`, `h100`, `h200`, `v6e`).
      - `[suffix]`: The model name suffix (e.g., `gemma-4-31b-it`, `qwen3-32b`).
      ```bash
      kubectl apply --kustomize "${ACP_REPO_DIR}/<constructed_overlay_dir>"
      ```

## 6. Verification

- Check that all pods are running and services are accessible. (Note: You may need to source the environment variables script first to get `$llmd_namespace`):
  ```bash
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
  kubectl get pods -n ${llmd_namespace}
  kubectl get svc -n ${llmd_namespace}
  ```
- Verify the model downloader job has completed and the model files are in the GCS bucket:
  ```bash
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
  kubectl get jobs -n ${llmd_namespace}
  gcloud storage ls gs://${huggingface_hub_models_bucket_name}/${llmd_model_id}/
  ```
- Ensure the Hugging Face token is securely configured:
  ```bash
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/_shared_config/scripts/set_environment_variables.sh"
  kubectl describe secretProviderClass huggingface-tokens -n ${llmd_namespace}
  kubectl describe secret llm-d-hf-token -n ${llmd_namespace}
  ```
