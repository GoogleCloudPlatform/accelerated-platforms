# Model evaluation and validation

Once a model has completed fine-tuning, the model must be validated for precision and accuracy
against the dataset used to fine-tune the model. The fine-tuned model in this example has been, Built with Meta Llama 3.1. In this example, the model is deployed on an
inference serving engine to host the model for the model validation to take place. Two steps are performed
for this activity, the first is to send prompts to the fine-tuned model, the second is to validate the results.

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A bucket containing the model weights from the [Fine tuning example](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md)

## Preparation

- Clone the repository and change directory to the guide directory

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms/use-cases/model-fine-tuning-pipeline/model-eval
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

## Data Preparation (Optional)

To execute this scenario without going through the [Fine tuning example](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md)

Select a path between **Full dataset** and **Smaller dataset (subset)**. The smaller dataset is a quicker way to experience the pipeline, but the evaluation results would be on a smaller sample.

- If you would like to use the **Smaller dataset (subset)**, set the variable below.

  ```sh
  DATASET_SUBSET=-subset
  ```

- Download the Hugging Face CLI library

  ```sh
  pip3 install -U "huggingface_hub[cli]==0.26.2"
  ```

- Download the prepared dataset from Hugging Face and copy it into the GCS bucket

  ```sh
  DATAPREP_REPO=gcp-acp/flipkart-dataprep${DATASET_SUBSET}

  ${HOME}/.local/bin/huggingface-cli download --repo-type dataset ${DATAPREP_REPO} --local-dir ./temp

  gcloud storage cp -R ./temp/* \
    gs://${MLP_DATA_BUCKET}/dataset/output && \

  rm -rf ./temp
  ```

- Download the fine-tuned model from Hugging Face and copy it into the GCS bucket.

  > NOTE: Due to the limitations of Cloud Shell’s storage and the size of our model we need to run this job to perform the transfer to GCS on the cluster.

  - Get credentials for the GKE cluster

    ```sh
    gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
    ```

  - Replace the respective variables required for the job

    ```sh
    MODEL_REPO=gcp-acp/Llama-gemma-2-9b-it-ft

    sed \
      -i -e "s|V_KSA|${MLP_MODEL_EVALUATION_KSA}|" \
      -i -e "s|V_BUCKET|${MLP_MODEL_BUCKET}|" \
      -i -e "s|V_MODEL_REPO|${MODEL_REPO}|" \
      manifests/transfer-to-gcs.yaml
    ```

  - Deploy the job

    ```sh
    kubectl apply --namespace ${MLP_KUBERNETES_NAMESPACE} \
      -f manifests/transfer-to-gcs.yaml
    ```

  - Trigger the wait for job completion (the job will take ~5 minutes to complete)

    ```sh
    kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait \
      --for=condition=complete --timeout=900s job/transfer-to-gcs
    ```

  - Example output of the job completion

    ```sh
    job.batch/transfer-to-gcs condition met
    ```

## Build the container image

- Build container image using Cloud Build and push the image to Artifact Registry

  ```
  cd src
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --substitutions _DESTINATION=${MLP_MODEL_EVALUATION_IMAGE}
  cd ..
  ```

## Run the job

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

- Configure the deployment

  | Variable       | Description                                     | Example                                  |
  | -------------- | ----------------------------------------------- | ---------------------------------------- |
  | ACCELERATOR    | Type of GPU accelerator to use (l4, a100)       | l4                                       |
  | VLLM_IMAGE_URL | The image url for the vllm image                | vllm/vllm-openai:v0.6.3.post1            |
  | MODEL          | The output folder path for the fine-tuned model | /model-data/model-gemma2-a100/experiment |

  ```sh
  ACCELERATOR="l4"
  VLLM_IMAGE_URL="vllm/vllm-openai:v0.6.3.post1"
  MODEL="/model-data/model-gemma2/experiment"
  ```

  ```sh
  sed \
  -i -e "s|V_IMAGE_URL|${VLLM_IMAGE_URL}|" \
  -i -e "s|V_KSA|${MLP_MODEL_EVALUATION_KSA}|" \
  -i -e "s|V_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_PATH|${MODEL}|" \
  manifests/deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/deployment-${ACCELERATOR}.yaml
  ```

- Wait for the deployment to be ready

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait --for=condition=ready --timeout=900s pod -l app=vllm-openai-${ACCELERATOR}
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

  ```sh
  DATASET_OUTPUT_PATH="dataset/output"
  ENDPOINT="http://vllm-openai-${ACCELERATOR}:8000/v1/chat/completions"
  MODEL_PATH="/model-data/model-gemma2/experiment"
  PREDICTIONS_FILE="predictions.txt"
  ```

  ```sh
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

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job.yaml
  ```
