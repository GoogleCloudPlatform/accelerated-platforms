# Benchmarking with Locust

We can run inference benchmark on our deployed model using locust.
Locust is an open source performance/load testing tool for HTTP and other protocols.
Refer to the documentation to [set up](https://docs.locust.io/en/stable/installation.html) locust locally or deploy as a container on GKE.

## Pre-requisites

- A model is deployed using one of the vLLM guides
  - [Serving the mode using vLLM and GCSFuse](/use-cases/inferencing/serving/vllm/gcsfuse/README.md)
  - [Serving the mode using vLLM and Persistent Disk](/use-cases/inferencing/serving/vllm/persistent-disk/README.md)
- Metrics are being scraped from the vLLM server ss shown in the [vLLM Metrics](/use-cases/inferencing/serving/vllm/metrics/README.md) guide.

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/inferencing/benchmark
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

#### Build the image of the source and execute bencmark job

- Build container image using Cloud Build and push the image to Artifact Registry.

  ```sh
  cd src
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --substitutions _DESTINATION=${MLP_BENCHMARK_IMAGE}
  cd -
  ```

- Configure the environment

  | Variable        | Description                                                                    | Example      |
  | --------------- | ------------------------------------------------------------------------------ | ------------ |
  | MODEL_NAME      | The name of the model folder in the root of the GCS model bucket               | model-gemma2 |
  | MODEL_VERSION   | The name of the version folder inside the model folder of the GCS model bucket | experiment   |
  | SERVE_NAMESPACE | Namespace where the model will be served                                       | ml-serve     |

  ```sh
  ACCELERATOR=l4
  MODEL_NAME=model-gemma2
  MODEL_STORAGE=pd
  MODEL_VERSION=experiment
  ```

  ```sh
  BENCHMARK_MODEL_PATH=/local/${MODEL_ID}/${MODEL_PATH}
  HOST="http://vllm-openai-${MODEL_STORAGE}-${ACCELERATOR}:8000"
  ```

- Replace variables in inference job manifest and deploy the job

  ```sh
  sed \
  -i -e "s|V_IMAGE_URL|${MLP_BENCHMARK_IMAGE}|" \
  -i -e "s|V_KSA|${MLP_MODEL_OPS_KSA}|" \
  -i -e "s|V_BENCHMARK_MODEL_PATH|${BENCHMARK_MODEL_PATH}|" \
  -i -e "s|V_HOST|${HOST}|" \
  manifests/locust-master-controller.yaml \
  manifests/locust-master-service.yaml \
  manifests/locust-worker-controller.yaml
  ```

  ```
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} apply -f manifests
  ```

- Access the locust dashboard and launch swarming requests.

  ```shell
  echo -e "\n${MLP_MODEL_OPS_NAMESPACE} Locust dashboard: ${MLP_LOCUST_NAMESPACE_ENDPOINT}\n"
  ```

  > Note : Locust service make take up to 5 minutes to load completely.
