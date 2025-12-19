# Model evaluation and validation

Once a model has completed fine-tuning, the model must be validated for
precision and accuracy against the dataset used to fine-tune the model. The
fine-tuned model in this example has been, Built with Meta Llama 3.1. In this
example, the model is deployed on an inference serving engine to host the model
for the model validation to take place. Two steps are performed for this
activity, the first is to send prompts to the fine-tuned model, the second is to
validate the results.

## Prerequisites

- The
  [GKE Training reference implementation](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
  is deployed and configured in your repository.

  - The
    [model_fine_tuning](/platforms/gke/base/use-cases/training-ref-arch/terraform/model_fine_tuning/README.md)
    terraservice is deployed and configured.

## Before you begin

- A bucket containing the prepared data from the
  [Data Preparation example](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/data-preparation.md)

- A bucket containing the model weights from the
  [Fine tuning example](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/fine-tuning.md)

## Preparation

> [!NOTE]  
> This guide is designed to be run on
> [Cloud Shell](https://cloud.google.com/shell) as it has all of the most of the
> required tools preinstalled.

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/_shared_config/scripts/set_environment_variables.sh"
  ```

## Build the container image

- Build the container image using Cloud Build and push the image to Artifact
  Registry

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/model_fine_tuning/images/model_evaluation && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Run the job

- Select an accelerator.

  - **NVIDIA A100**:

    ```shell
    export ACCELERATOR_TYPE="a100"
    ```

  - **NVIDIA H100 80GB**:

    ```shell
    export ACCELERATOR_TYPE="h100"
    ```

  - **NVIDIA Tesla L4 24GB**:

    ```shell
    export ACCELERATOR_TYPE="l4"
    ```

  Ensure that you have enough quota in your project to provision the selected
  accelerator type. For more information, see about viewing GPU quotas, see

- Configure the Kubernetes manifest

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/model-evaluation/configure.sh"
  ```

- Create the deployment

  ```sh
  kubectl --namespace ${mft_kubernetes_namespace} apply \
  --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/model-evaluation/deployment-${ACCELERATOR_TYPE}.yaml"
  ```

- Wait for the deployment to be ready

  ```
  kubectl --namespace ${mft_kubernetes_namespace} wait --for=condition=ready --timeout=900s pod -l app=vllm-openai-${ACCELERATOR_TYPE}
  ```

  When they deployment is ready your should see output similar to:

  ```output
  pod/vllm-openai-XXXXXXXXXX-XXXXX condition met
  ```

- Create the job

  ```sh
  kubectl --namespace ${mft_kubernetes_namespace} apply \
  --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/model-evaluation/job.yaml"
  ```

- Wait for the job to complete

- Delete the job

  ```sh
  kubectl --namespace ${mft_kubernetes_namespace} delete \
  --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/model-evaluation/job.yaml"
  ```
