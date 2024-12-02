# Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , its ready to run batch Inference pipeline.
In this example batch inference pipeline, we would first send prompts to the hosted fine-tuned model and then validate the results based on ground truth.

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A model is deployed using one of the vLLM guides
  - [Serving the mode using vLLM and GCSFuse](/use-cases/inferencing/serving/vllm/gcsfuse/README.md)
  - [Serving the mode using vLLM and Hyperdisk ML](/use-cases/inferencing/serving/vllm/hyperdisk-ml/README.md)
  - [Serving the mode using vLLM and Persistent Disk](/use-cases/inferencing/serving/vllm/persistent-disk/README.md)

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/inferencing/batch-inference
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

## Build the container image

- Build the container image using Cloud Build and push the image to Artifact Registry

  ```sh
  cd src
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --substitutions _DESTINATION=${MLP_BATCH_INFERENCE_IMAGE}
  cd -
  ```

## Run the job

- Configure the job

  | Variable            | Description                                                          | Example         |
  | ------------------- | -------------------------------------------------------------------- | --------------- |
  | ACCELERATOR         | Type of GPU accelerator used for the model server (l4, a100, h100)   | l4              |
  | DATASET_OUTPUT_PATH | The folder path of the generated output data set in the data bucket. | dataset/output  |
  | MODEL_NAME          | The name of the model folder on the model server                     | model-gemma2    |
  | MODEL_STORAGE       | Type of storage used for the model (gcs, hdml, pd)                   | pd              |
  | MODEL_VERSION       | The name of the version folder on the model server                   | experiment      |
  | PREDICTIONS_FILE    | The predictions file                                                 | predictions.txt |

  ```sh
  ACCELERATOR="l4"
  DATASET_OUTPUT_PATH="dataset/output"
  MODEL_NAME="model-gemma2"
  MODEL_STORAGE="pd"
  MODEL_VERSION="experiment"
  PREDICTIONS_FILE="prediction.txt"
  ```

  ```sh
  INFERENCE_ENDPOINT="http://vllm-openai-${MODEL_STORAGE}-${ACCELERATOR}:8000/v1/chat/completions"
  INFERENCE_MODEL_PATH="/${MODEL_STORAGE}/${MODEL_NAME}/${MODEL_VERSION}"
  ```

  ```sh
  sed \
  -i -e "s|V_DATA_BUCKET|${MLP_DATA_BUCKET}|" \
  -i -e "s|V_DATASET_OUTPUT_PATH|${DATASET_OUTPUT_PATH}|" \
  -i -e "s|V_IMAGE_URL|${MLP_BATCH_INFERENCE_IMAGE}|" \
  -i -e "s|V_INFERENCE_ENDPOINT|${INFERENCE_ENDPOINT}|" \
  -i -e "s|V_INFERENCE_MODEL_PATH|${INFERENCE_MODEL_PATH}|" \
  -i -e "s|V_KSA|${MLP_BATCH_INFERENCE_KSA}|" \
  -i -e "s|V_PREDICTIONS_FILE|${PREDICTIONS_FILE}|" \
  manifests/job.yaml
  ```

- Create the job

  ```
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} apply -f manifests/job.yaml
  ```

- Wait for the job to show completion.

  ```sh
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get job/batch-inference
  ```

  The job runs for about an hour. Once it is completed, you can review predictions result in file named `<MODEL_NAME>-predictions.txt` under /dataset/output folder in the bucket. A sample prediction output file named `example_predictions` has been provided in this directory for reference.
