# Backend application deployment

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/rag-pipeline/backend
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

## Build the container image

- Build the container image using Cloud Build and push the image to Artifact
  Registry

  ```sh
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

## Deploy the backend application

- Configure the deployment.

  ```sh
  export CATALOG_DB="product_catalog"
  export CATALOG_TABLE_NAME="clothes"
  export TEXT_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/text_embeddings"
  export IMAGE_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/image_embeddings"
  export MULTIMODAL_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/multimodal_embeddings"
  export GEMMA_IT_ENDPOINT="http://rag-it-model.ml-team:8000/v1/chat/completions"
  export EMBEDDING_COLUMN_TEXT="text_embeddings"
  export EMBEDDING_COLUMN_IMAGE="image_embeddings"
  export EMBEDDING_COLUMN_MULTIMODAL="multimodal_embeddings"
  export ROW_COUNT="\"5\""
  ```

  ```sh
  git restore manifests/deployment.yaml
  sed \
  -i -e "s|V_CATALOG_DB|${CATALOG_DB}|" \
  -i -e "s|V_CATALOG_TABLE_NAME|${CATALOG_TABLE_NAME}|" \
  -i -e "s|V_EMBEDDING_COLUMN_IMAGE|${EMBEDDING_COLUMN_IMAGE}|" \
  -i -e "s|V_EMBEDDING_COLUMN_MULTIMODAL|${EMBEDDING_COLUMN_MULTIMODAL}|" \
  -i -e "s|V_EMBEDDING_COLUMN_TEXT|${EMBEDDING_COLUMN_TEXT}|" \
  -i -e "s|V_EMBEDDING_ENDPOINT_IMAGE|${IMAGE_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_EMBEDDING_ENDPOINT_MULTIMODAL|${MULTIMODAL_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_EMBEDDING_ENDPOINT_TEXT|${TEXT_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_GEMMA_IT_ENDPOINT|${GEMMA_IT_ENDPOINT}|" \
  -i -e "s|V_IMAGE|${MLP_RAG_BACKEND_IMAGE}|" \
  -i -e "s|V_MLP_DB_ADMIN_IAM|${MLP_DB_ADMIN_IAM}|" \
  -i -e "s|V_MLP_DB_USER_KSA|${MLP_DB_USER_KSA}|" \
  -i -e "s|V_MLP_DB_INSTANCE_URI|${MLP_DB_INSTANCE_URI}|" \
  -i -e "s|V_MLP_KUBERNETES_NAMESPACE|${MLP_KUBERNETES_NAMESPACE}|" \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_ROW_COUNT|${ROW_COUNT}|" \
  manifests/deployment.yaml
  ```

- Create the deployment.

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/deployment.yaml
  ```

## Test the backend application

Validations:

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get pods -l app=rag-backend
```

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get service/rag-backend
```

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/curl.yaml
```

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/rag-backend-curl
```
