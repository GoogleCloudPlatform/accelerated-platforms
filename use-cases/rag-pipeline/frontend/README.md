# Frontend application deployment

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/rag-pipeline/frontend
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
  --substitutions _DESTINATION=${MLP_RAG_FRONTEND_IMAGE}
  cd -
  ```

## Deploy the frontend application

- Configure the deployment.

  ```sh
  export BACKEND_SERVICE_ENDPOINT="http://rag-backend.ml-team:8000/generate_product_recommendations/"
  ```

  ```sh
  git restore manifests/deployment.yaml
  sed \
  -i -e "s|V_IMAGE|${MLP_RAG_FRONTEND_IMAGE}|" \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_BACKEND_SERVICE_ENDPOINT|${BACKEND_SERVICE_ENDPOINT}|" \
  manifests/deployment.yaml
  ```

- Create the deployment.

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/deployment.yaml
  ```

- Verify the deployment.

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get pods -l app=rag-frontend
```

- Verify the service.

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get service/frontend-rag-svc
```

## Test the frontend application

- Retrieve the frontend application URL

  ```sh
  echo -e "\n${MLP_KUBERNETES_NAMESPACE} RAG frontend URL: ${MLP_RAG_FRONTEND_NAMESPACE_ENDPOINT}\n"
  ```

- Open the Front end application in browser using URL value retrieved above.
