# Use GCS to store model and GCSFuse to download

In this guide, we will store Llama-3.3-70B-Instruct model in GCS bucket and use GCSFuse to download the model to start inference using vllm.
You will start with running the model inference with no fine tuning in GCSFuse configuration. Then you will add the fine tuning to the speed up the inference startup.

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.

- Follow  [these instructions](/use-cases/prerequisites/storage-benchmarking.md) to download the Llama-3.3-70B-Instruct model into GCS bucket.

## Preparation

- Clone the repository.

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```sh
  cd use-cases/inferencing/cost-optimization/storage-benchmarking/gcsfuse
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster.

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

## Serve the model with vLLM

- Configure the environment.

  | Variable      | Description                                                                    | Example      |
  | ------------- | ------------------------------------------------------------------------------ | ------------ |
  | ACCELERATOR   | Type of GPU accelerator to use (a100, h100, l4)                                | a100           |
  | MODEL_NAME    | The name of the model folder in the root of the GCS model bucket               | meta-llama |
  | MODEL_VERSION | The name of the version folder inside the model folder of the GCS model bucket | Llama-3.3-70B-Instruct |

  ```sh
  ACCELERATOR="a100"
  MODEL_NAME="meta-llama"
  MODEL_VERSION="Llama-3.3-70B-Instruct"
  ```

- Configure the deployment.

  ```
  VLLM_IMAGE_NAME="vllm/vllm-openai:v0.6.6.post1"
  ```

  ```sh
  git restore manifests/model-deployment-${ACCELERATOR}.yaml
  sed \
  -i -e "s|V_MODEL_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  -i -e "s|V_IMAGE_NAME|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
  manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment.

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/model-deployment-${ACCELERATOR}.yaml
  ```

  ```
  deployment.apps/vllm-openai-gcs-l4 created
  service/vllm-openai-gcs-l4 created
  ```

- Watch the deployment until it is ready and available.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/vllm-openai-gcs-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 5+ minutes for the deployment to be ready and available.

  ```
  NAME                 READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-openai-gcs-l4   1/1     1            1           XXXXX
  ```