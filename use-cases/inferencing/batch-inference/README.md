# Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE, it's ready to run a batch inference pipeline.
In this example batch inference pipeline, we would first send prompts to the hosted fine-tuned model and then validate the results based on ground truth.

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A model is deployed using one of the vLLM guides
  - [Distributed Inference and Serving with vLLM using GCSFuse](/use-cases/inferencing/serving/vllm/gcsfuse/README.md)
  - [Distributed Inference and Serving with vLLM using Hyperdisk ML](/use-cases/inferencing/serving/vllm/hyperdisk-ml/README.md)
  - [Distributed Inference and Serving with vLLM using Persistent Disk](/use-cases/inferencing/serving/vllm/persistent-disk/README.md)
- A bucket containing the prepared data from the [Data Preparation example](/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/README.md)

> NOTE: If you did not execute the data preparation example, follow [these instructions](/use-cases/prerequisites/prepared-data.md) to load the dataset into the bucket.

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
  git restore cloudbuild.yaml
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --substitutions _DESTINATION=${MLP_BATCH_INFERENCE_IMAGE}
  cd -
  ```

## Run the job

- Configure the environment.

  > Set the environment variables based on the accelerator and model storage type used to serve the model.
  > The default values below are set for NVIDIA L4 GPUs and persistent disk.

  | Variable            | Description                                                          | Example         |
  | ------------------- | -------------------------------------------------------------------- | --------------- |
  | ACCELERATOR         | Type of GPU accelerator used for the model server (a100, h100, l4)   | l4              |
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

- Configure the job.

  ```sh
  git restore manifests/job.yaml
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

  ```
  job.batch/batch-inference created
  ```

  Depending on the dataset, it takes approximately 10 - 60 minutes for the job to complete.

- Check the status of the job

  ```
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get job/batch-inference
  ```

  ```
  NAME              STATUS    COMPLETIONS   DURATION   AGE
  batch-inference   Running   0/1           ###        ###
  ```

- Watch the job till it is complete.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get job/batch-inference | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'"
  ```

  ```
  NAME              STATUS     COMPLETIONS   DURATION   AGE
  batch-inference   Complete   1/1           #####      #####
  ```

Once the job is complete, the predictions result will be stored in the `MLP_DATA_BUCKET` in the `predictions` folder.
A sample prediction output file [`example_predictions.txt`](/use-cases/inferencing/batch-inference/example_predictions.txt) has been provided for reference.
