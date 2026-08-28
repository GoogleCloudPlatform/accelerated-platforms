# Multi-host Supervised Fine-Tuning (SFT) with TPUs on Google Kubernetes Engine (GKE) using MaxText

This example implements Supervised Fine-Tuning (SFT) on Multi-Host TPU
topologies using MaxText and Tunix post-training libraries on Google Kubernetes
Engine (GKE).

Multi-host TPU configurations (such as TPU `v5e-4x4` or `v6e-4x4` containing 16
chips or larger) span across multiple hosts. This setup uses **PathwaysJob**
resources to coordinate training natively across all TPU hosts with Pathways
orchestration.

This use-case is built on top of the
[GKE Training Reference Architecture](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md).

## Topology & Memory Sizing Guidelines

| Model            | Parameters | Full SFT Memory (Weights + AdamW States) | Recommended TPU Topology                                                     |
| :--------------- | :--------- | :--------------------------------------- | :--------------------------------------------------------------------------- |
| **Llama 3.1 8B** | 8B         | ~112 GB HBM                              | TPU v5e-16 (`v5e-4x4` - 2 hosts, 16 chips)                                   |
| **Gemma 4 31B**  | 31B        | ~434 GB HBM                              | TPU v6e-16 (`v6e-4x4` - 2 hosts, 16 chips, 512GB HBM) for full parameter SFT |

## Objectives

- Set up Google Cloud multi-host SFT infrastructure (dedicated GCS bucket,
  Kubernetes namespace, service account, and Workload Identity IAM bindings).
- Build and push a multi-host MaxText container image to Artifact Registry.
- Deploy the SFT workload using a `PathwaysJob` in GKE.
- Automatically convert Hugging Face checkpoints to MaxText format on the fly if
  needed.
- Track SFT experiment metrics using in-cluster MLflow.

## Before you begin

- Ensure the
  [GKE Training Reference Architecture](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
  is fully deployed.
- Request access to the model on Hugging Face:
  - **Llama 3.1 8B Instruction-Tuned**:
    [meta-llama/Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
  - **Gemma 4 31B Instruction-Tuned**:
    [google/gemma-4-31b-it](https://huggingface.co/google/gemma-4-31b-it)
- Add your Hugging Face read-access token to Google Secret Manager as detailed
  in
  [Hugging Face Initialize](/platforms/gke/base/core/huggingface/initialize/README.md).

## Create and configure the Google Cloud resources

- Deploy the SFT multi-host cloud infrastructure resources (dataset bucket,
  namespace, service accounts, and Workload Identity bindings):

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/sft-tpu-maxtext-multi-host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Deploy the SFT workload

- Source the environment configuration:

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the SFT multi-host deployment manifests:

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/configure_job.sh"
  ```

- Deploy the SFT multi-host workload using Kustomize:

  - **Llama 3.1 8B on TPU v5e (4x4, 16 chips)**:

    ```shell
    kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/v5e-4x4-llama-3-1-8b-instruct"
    ```

  - **Gemma 4 31B on TPU v6e (4x4, 16 chips)**:

    ```shell
    kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/v6e-4x4-gemma-4-31b-instruct"
    ```

- Watch the SFT training PathwaysJob until complete:

  ```shell
  kubectl get pathwaysjob -n ${sft_tpu_maxtext_multi_host_kubernetes_namespace_name}
  ```

## Viewing Metrics (MLflow)

Metrics are piped to MLflow during training.

1. **Port-forward the MLflow Service:**

   ```shell
   kubectl port-forward --namespace=${sft_cpu_mlflow_kubernetes_namespace_name} svc/mlflow-service-svc 5000:5000
   ```

2. **Open your Browser:** Navigate to `http://localhost:5000` to inspect
   experiment metrics logged under the `sft-tpu-maxtext-multi-host` experiment.
