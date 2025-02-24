# RAG: Frontend deployment

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.

## Preparation

- Clone the repository.

  ```shell
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```shell
  cd use-cases/rag-pipeline/frontend
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```shell
  cat ${MLP_ENVIRONMENT_FILE} && \
  set -o allexport && \
  source ${MLP_ENVIRONMENT_FILE} && \
  set +o allexport
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster.

  ```shell
  gcloud container clusters get-credentials ${MLP_CLUSTER_NAME} \
  --dns-endpoint \
  --project=${MLP_PROJECT_ID} \
  --region=${MLP_REGION}
  ```

## Build the container image

- Build the container image using Cloud Build and push the image to Artifact
  Registry.

  ```shell
  cd src
  git restore cloudbuild.yaml
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --substitutions _DESTINATION=${MLP_RAG_FRONTEND_IMAGE}
  cd -
  ```

## Deploy the frontend application

- Configure the deployment.

  ```shell
  set -o nounset
  export BACKEND_SERVICE_ENDPOINT="http://rag-backend.ml-team:8000/generate_product_recommendations/"
  export CONTAINER_IMAGE_URL="${MLP_RAG_FRONTEND_IMAGE}"
  set -o nounset
  ```

  > Ensure there are no `bash: <ENVIRONMENT_VARIABLE> unbound variable` error
  > messages.

  ```shell
  git restore manifests/deployment.yaml
  envsubst < manifests/deployment.yaml | sponge manifests/deployment.yaml
  ```

- Create the deployment.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/deployment.yaml
  ```

- Watch the deployment until it is ready and available.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get deployment/rag-frontend | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs deployment/rag-frontend --tail 10"
  ```

  ```
  NAME           READY   UP-TO-DATE   AVAILABLE   AGE
  rag-frontend   1/1     1            1           XXXXX
  ```

## Test the frontend application

- Run the following command to output the URL for the frontend application.

  ```shell
  echo -e "\n${MLP_KUBERNETES_NAMESPACE} RAG frontend URL: ${MLP_RAG_FRONTEND_NAMESPACE_ENDPOINT}\n"
  ```

- Open the frontend application in your browser.

  > It can take several minutes for the frontend application to be available via
  > the gateway.

  If you are seeing `fault filter abort`, wait a moment and retry.
