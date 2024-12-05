## Backend application deployment

# Getting Started

## Prepare the environment

You have an existing [ML Playground cluster](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/platforms/gke-aiml/playground) in a Google Cloud Project.

## Set the default environment variables:
- Change directory to the backend source code directory

  ```sh
  cd use-cases/rag-pipeline/backend
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

## Build the backend container image container image

```sh
git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git
cd rag-on-gke/backend/src
```

Update the location where you would like to store the container images in the ```cloud build yaml`` and kick off the build: 

Create the artifact repostiory(if it not already exists) to store the container images:

```sh
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="RAG artifacts repository"
```

```sh
cd src
gcloud builds submit . 
```

## Deploy the embedding model

Update `manifests/backend_deployment.yaml` file with variables values as shown below:

```sh
    export CATALOG_DB_NAME="product_catalog"
    export CATALOG_TABLE_NAME="clothes"
    export TEXT_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/text_embeddings"
    export IMAGE_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/image_embeddings"
    export MULTIMODAL_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/multimodal_embeddings" 
    export GEMMA_IT_ENDPOINT="http://rag-it-model.ml-team:8000/v1/chat/completions"
    export EMBEDDING_COLUMN_TEXT="text_embeddings"
    export EMBEDDING_COLUMN_IMAGE="image_embeddings"
    export EMBEDDING_COLUMN_MULTIMODAL="multimodal_embeddings"
    export ROW_COUNT=5
```

```sh
  sed \
  -i -e "s|V_MLP_DB_ADMIN_KSA|${MLP_DB_ADMIN_KSA}|" \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_CATALOG_DB_NAME|${CATALOG_DB_NAME}|" \
  -i -e "s|V_CATALOG_TABLE_NAME|${CATALOG_TABLE_NAME}|" \
  -i -e "s|V_MLP_DB_ADMIN_IAM|${MLP_DB_ADMIN_IAM}|" \
  -i -e "s|V_MLP_DB_INSTANCE_URI|${MLP_DB_INSTANCE_URI}|" \
  -i -e "s|V_GEMMA_IT_ENDPOINT|${GEMMA_IT_ENDPOINT}|" \
  -i -e "s|V_MLP_KUBERNETES_NAMESPACE|${MLP_KUBERNETES_NAMESPACE}|" \
  -i -e "s|V_TEXT_EMBEDDING_ENDPOINT|${TEXT_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_IMAGE_EMBEDDING_ENDPOINT|${IMAGE_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_MULTIMODAL_EMBEDDING_ENDPOINT|${MULTIMODAL_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_EMBEDDING_COLUMN_TEXT|${EMBEDDING_COLUMN_TEXT}|" \
  -i -e "s|V_EMBEDDING_COLUMN_IMAGE|${EMBEDDING_COLUMN_IMAGE}|" \
  -i -e "s|V_EMBEDDING_COLUMN_MULTIMODAL|${EMBEDDING_COLUMN_MULTIMODAL}|" \
  -i -e "s|V_ROW_COUNT|${ROW_COUNT}|" \
  manifests/backend_deployment.yaml
  ```


```sh
kubectl apply -f manifests/backend_deployment.yaml -n ${MLP_KUBERNETES_NAMESPACE}
```

## Test the embedding model
Validations: 

```sh
kubectl get po -n ${MLP_KUBERNETES_NAMESPACE}
```


└─⪧ kubectl get svc -n ${MLP_KUBERNETES_NAMESPACE}
NAME              TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)          AGE


```sh
kubectl apply -f manifests/curl-job.yaml -n ${MLP_KUBERNETES_NAMESPACE}
```