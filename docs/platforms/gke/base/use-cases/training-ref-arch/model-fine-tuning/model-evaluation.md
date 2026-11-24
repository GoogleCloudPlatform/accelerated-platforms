# Model evaluation and validation

Once a model has completed fine-tuning, the model must be validated for
precision and accuracy against the dataset used to fine-tune the model. In this
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
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
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

  - **NVIDIA Tesla L4 24GB**:

    ```shell
    export ACCELERATOR_TYPE="l4"
    ```

  The deployment for the NVIDIA A100 accelerators was run with the inference
  server version of this guide. The deployment for the NVIDIA Tesla L4
  accelerators uses the same version and was not run with it.

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

  ```sh
  kubectl --namespace ${mft_kubernetes_namespace} wait --for=condition=complete --timeout=1200s job/model-eval
  ```

  The job takes approximately 5 minutes. It sends the questions to the model
  concurrently. The `CONCURRENT_REQUESTS` environment variable of the job is the
  number of questions that are sent at the same time. When the job is complete,
  the logs of the job show the results:

  ```sh
  kubectl --namespace ${mft_kubernetes_namespace} logs job/model-eval | grep -o -E '"message": "(Test dataset size|True Positives|False Positives|Number of predictions|Accuracy|Precision|Correct Products|Exact Answers|Product details accuracy)[^"]*"'
  ```

  The output should be similar to:

  ```output
  "message": "Test dataset size: 3350"
  "message": "True Positives Count: 3350"
  "message": "False Positives Count: 0"
  "message": "Number of predictions with no product details: 0"
  "message": "Accuracy of Gemma2 9B IT model on test dataset is 100.0%"
  "message": "Precision of Gemma2 9B IT model on test dataset is 100.0%"
  "message": "Correct Products Count: 3350"
  "message": "Exact Answers Count: 3009"
  "message": "Product details accuracy of Gemma2 9B IT model on test dataset is 98.24%"
  ```

  The test dataset of the evaluation is the validation and the test data sets of
  the data preparation together: 1,655 + 1,695 = 3,350 questions.

  For the meaning of the results, see
  [Accuracy Calculation](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/README.md#accuracy-calculation).

- Delete the job

  ```sh
  kubectl --namespace ${mft_kubernetes_namespace} delete \
  --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/model-evaluation/job.yaml"
  ```
