# Model evaluation and validation

Once a model has completed fine-tuning, the model must be validated for
precision and accuracy against the dataset used to fine-tune the model. The
fine-tuned model in this example has been, Built with Meta Llama 3.1. In this
example, the model is deployed on an inference serving engine to host the model
for the model validation to take place. Two steps are performed for this
activity, the first is to send prompts to the fine-tuned model, the second is to
validate the results.

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.
- A bucket containing the prepared data from the
  [Data Preparation example](/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/README.md)
  > NOTE: If you did not execute the data preparation example, follow
  > [these instructions](/use-cases/prerequisites/prepared-data.md) to load the
  > dataset into the bucket.
- A bucket containing the model weights from the
  [Fine tuning example](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md)
  > NOTE: If you did not execute the fine-tuning example, follow
  > [these instructions](/use-cases/prerequisites/fine-tuned-model.md) to load
  > the model into the bucket.

## Preparation

- Clone the repository.

  ```shell
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```shell
  cd use-cases/model-fine-tuning-pipeline/model-eval
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```shell
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster.

  ```shell
  gcloud container clusters get-credentials ${MLP_CLUSTER_NAME} \
  --dns-endpoint \
  --location=${MLP_REGION} \
  --project=${MLP_PROJECT_ID}
  ```

## Build the container image

- Build container image using Cloud Build and push the image to Artifact
  Registry

  ```shell
  cd src
  git restore cloudbuild.yaml && \
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml && \
  gcloud beta builds submit \
  --config=cloudbuild.yaml \
  --gcs-source-staging-dir=gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project=${MLP_PROJECT_ID} \
  --substitutions=_DESTINATION=${MLP_MODEL_EVALUATION_IMAGE}
  cd ..
  ```

  It takes approximately 2 minutes for the build to complete.

## Run the job

- Configure the deployment

  | Variable       | Description                                     | Example                                  |
  | -------------- | ----------------------------------------------- | ---------------------------------------- |
  | ACCELERATOR    | Type of GPU accelerator to use (l4, a100)       | l4                                       |
  | VLLM_IMAGE_URL | The image url for the vllm image                | vllm/vllm-openai:v0.6.3.post1            |
  | MODEL          | The output folder path for the fine-tuned model | /model-data/model-gemma2-a100/experiment |

  ```shells
  ACCELERATOR="l4"
  VLLM_IMAGE_URL="vllm/vllm-openai:v0.6.3.post1"
  MODEL="/model-data/model-gemma2/experiment"
  ```

  ```shell
  git restore manifests/deployment-${ACCELERATOR}.yaml && \
  sed \
  -i -e "s|V_IMAGE_URL|${VLLM_IMAGE_URL}|" \
  -i -e "s|V_KSA|${MLP_MODEL_EVALUATION_KSA}|" \
  -i -e "s|V_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_PATH|${MODEL}|" \
  manifests/deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment

  ```shell
  kubectl --namespace=${MLP_KUBERNETES_NAMESPACE} apply --filename=manifests/deployment-${ACCELERATOR}.yaml
  ```

- Wait for the deployment to be ready

  ```shell
  kubectl --namespace=${MLP_KUBERNETES_NAMESPACE} wait --for=condition=ready --timeout=900s pod --selector=app=vllm-openai-${ACCELERATOR}
  ```

  When they deployment is ready your should see output similar to:

  ```output
  pod/vllm-openai-XXXXXXXXXX-XXXXX condition met
  ```

- Configure the job

  | Variable            | Description                                                                                               | Example                                          |
  | ------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
  | DATASET_OUTPUT_PATH | The folder path of the generated output data set.                                                         | dataset/output                                   |
  | ENDPOINT            | This is the endpoint URL of the inference server                                                          | <http://vllm-openai-l4:8000/v1/chat/completions> |
  | MODEL_PATH          | The output folder path for the fine-tuned model. This is used by model evaluation to generate the prompt. | /model-data/model-gemma2/experiment              |
  | PREDICTIONS_FILE    | The predictions file                                                                                      | predictions.txt                                  |

  ```shell
  DATASET_OUTPUT_PATH="dataset/output"
  ENDPOINT="http://vllm-openai-${ACCELERATOR}:8000/v1/chat/completions"
  MODEL_PATH="/model-data/model-gemma2/experiment"
  PREDICTIONS_FILE="predictions.txt"
  ```

  ```shell
  git restore manifests/job.yaml && \
  sed \
  -i -e "s|V_DATA_BUCKET|${MLP_DATA_BUCKET}|" \
  -i -e "s|V_DATASET_OUTPUT_PATH|${DATASET_OUTPUT_PATH}|" \
  -i -e "s|V_ENDPOINT|${ENDPOINT}|" \
  -i -e "s|V_IMAGE_URL|${MLP_MODEL_EVALUATION_IMAGE}|" \
  -i -e "s|V_KSA|${MLP_MODEL_EVALUATION_KSA}|" \
  -i -e "s|V_MODEL_PATH|${MODEL_PATH}|" \
  -i -e "s|V_PREDICTIONS_FILE|${PREDICTIONS_FILE}|" \
  manifests/job.yaml
  ```

- Create the job

  ```shell
  kubectl --namespace=${MLP_KUBERNETES_NAMESPACE} apply --filename=manifests/job.yaml
  ```
