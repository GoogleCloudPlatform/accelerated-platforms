---
name: gke-inference-stack-deploy
description: Deploys the GKE base platform and inference-specific terra-services (GPU/TPU) for accelerated workloads.
version: 0.1.0
allowed-tools: kubectl gcloud terraform python3
mcp-servers:
  - kubernetes:
      reason: "Inspect cluster info, custom compute classes, pod statuses."
  - gcp:
      reason: "Verify GKE cluster status."
---

# Deploy GKE Inference Stack Skill

Follow these instructions to provision the GKE Base Platform and inference-specific terra-services.

## 1. Prerequisites & Platform Configuration

1.  **Ask the user** (only for information not provided in the user's prompt):

    - "What is the path to the repository?" -> Set ACP_REPO_DIR
    - "What is your Google Cloud project ID?" -> Set platform_default_project_id
    - "What GKE region would you like to use?" -> Set cluster_region
    - "What platform name would you like to set?" -> Set platform_name
    - "Would you like to deploy an Autopilot or Standard cluster?" -> Set cluster_type

2.  **Action**: Inject these values into the appropriate `tfvars` files (`${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars` and `cluster.auto.tfvars`) using `sed`.

    ```bash
    # Update platform variables
    sed -i 's/^platform_name.*/platform_name = "<platform_name>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
    grep -q "^platform_default_project_id" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars" || echo "platform_default_project_id = \"\"" >> "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
    sed -i 's/^platform_default_project_id.*/platform_default_project_id = "<project_id>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"

    # Update cluster variables
    sed -i 's/^cluster_region.*/cluster_region = "<cluster_region>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
    ```

## 2. Accelerator & Hardware Configuration

1.  **Ask the user**: "Which accelerator(s) would you like to deploy for inference? You can select GPU, TPU, or both."

    - **Options**: GPU (`rtx-pro-6000`, `h100`, `h200`), TPU (`v6e`), or both.

2.  **Action**:
    - Determine if the target inference terra-services are `online_gpu`, `online_tpu`, or both based on the chosen accelerator(s).
    - Update accelerator configurations in the shared `tfvars` if necessary based on user selection.

## 3. Deploy Core Platform Terra-Services

Run the appropriate core deployment script based on the cluster type selected by the user. Always refer to existing scripts for execution rather than defining the `CORE_TERRASERVICES_APPLY` array explicitly.

- **For Standard Cluster**:
  ```bash
  "${ACP_REPO_DIR}/platforms/gke/base/core/deploy-standard.sh"
  ```
- **For Autopilot Cluster**:
  ```bash
  "${ACP_REPO_DIR}/platforms/gke/base/core/deploy-ap.sh"
  ```

## 4. Deploy Inference Terra-Services

Navigate to the specific inference terra-service directories (`online_gpu`, `online_tpu`, or both) and execute Terraform commands.

```bash
# Depending on what the user chose, add "online_gpu" and/or "online_tpu" to this array
declare -a selected_terraservices=( "online_gpu" "online_tpu" )

for inference_terraservice in "${selected_terraservices[@]}"; do
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/${inference_terraservice}/"
  terraform init
  terraform plan -input=false -out=tfplan
  terraform apply -input=false tfplan
  rm tfplan
done
```

## 5. Verification

Retrieve GKE cluster credentials and verify the deployment. Note: if using NAP (Node Auto-Provisioning), nodes may not be visible until workloads are deployed.

```bash
gcloud container clusters get-credentials "<platform_name>" --region "<cluster_region>" --project "<project_id>" --dns-endpoint
kubectl get computeclasses
kubectl get namespaces # You should see the online_gpu and/or online_tpu namespace depending on what was deployed
```
