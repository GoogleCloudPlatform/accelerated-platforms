# RAG: Backend deployment

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
  cd use-cases/rag-pipeline/backend
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
  --substitutions _DESTINATION=${MLP_RAG_BACKEND_IMAGE}
  cd -
  ```

## Deploy the backend

- Configure the deployment.

  ```shell
  set -o nounset
  export CATALOG_DB="product_catalog"
  export CATALOG_TABLE_NAME="clothes"
  export CONTAINER_IMAGE_URL="${MLP_RAG_BACKEND_IMAGE}"
  export DB_INSTANCE_URI="${MLP_DB_INSTANCE_URI}"
  export EMBEDDING_COLUMN_IMAGE="image_embeddings"
  export EMBEDDING_COLUMN_MULTIMODAL="multimodal_embeddings"
  export EMBEDDING_COLUMN_TEXT="text_embeddings"
  export EMBEDDING_ENDPOINT_IMAGE="http://multimodal-embedding-model.ml-team:80/image_embeddings"
  export EMBEDDING_ENDPOINT_MULTIMODAL="http://multimodal-embedding-model.ml-team:80/multimodal_embeddings"
  export EMBEDDING_ENDPOINT_TEXT="http://multimodal-embedding-model.ml-team:80/text_embeddings"
  export GEMMA_IT_ENDPOINT="http://rag-it-model.ml-team:8000/v1/chat/completions"
  export KUBERNETES_SERVICE_ACCOUNT="${MLP_DB_USER_KSA}"
  export OTEL_KUBERNETES_SERVICE_ACCOUNT="${MLP_RAG_CLOUD_TRACE_KSA}"
  export ROW_COUNT="5"
  set +o nounset
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
  "kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get deployment/rag-backend | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs deployment/rag-backend --tail 10"
  ```

  ```
  NAME          READY   UP-TO-DATE   AVAILABLE   AGE
  rag-backend   1/1     1            1           XXXXX
  ```

## Verify the backend

- Create the curl job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/curl.yaml
  ```

- Get the logs for the curl job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs --follow job/rag-backend-curl
  ```

  The output should be similar to:

  ```
  "- London Fog Solid V-neck Casual Men's Sweater \n- Alpine Enterprises Solid V-neck Men's Sweater \n- Club York Solid V-neck Casual Men's Sweater \n"
  ```

## Tracing

For the RAG use case, tracing is enabled using
[Google Cloud Trace](https://cloud.google.com/trace/docs) and
[OpenTelemetry](https://opentelemetry.io/). The provided sample code imports the
necessary libraries and is instrumented. Additionally, an OpenTelemetry
collector (otel-collector) is installed and configured within the same namespace
as the RAG application.

With this setup, after sending a request, you can view the traces in the Cloud
Trace explorer, similar to the following:

![trace-explorer](/docs/use-cases/rag-pipeline/images/trace_explorer.png)

The left side allows you to filter trace spans based on various criteria. The
top right displays a heatmap of received traces, and you can change the chart
view via the dropdown menu. The bottom right panel shows all filtered spans. For
instance, clicking the span `POST /generate_product_recommendations/`, reveals
detailed information, such as:

![trace-example](/docs/use-cases/rag-pipeline/images/trace_example.png)

In the top panel of the page, the left side displays each span. Selecting a span
reveals its corresponding execution time on the right side. For instance,
connecting to the database requires approximately half a second. However, the
final `POST` call to the LLM model takes over seven seconds to return a
response.
