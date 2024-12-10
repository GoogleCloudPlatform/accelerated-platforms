# Multimodal blip2 model

To know more about the embedding model see original [blog](https://blog.salesforceairesearch.com/blip-2/) and [source](https://github.com/salesforce/LAVIS/tree/main/examples)

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
  cd use-cases/rag-pipeline/embedding-models/multimodal-embedding
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
  --substitutions _DESTINATION=${MLP_MULTIMODAL_EMBEDDING_IMAGE}
  cd -
  ```

## Deploy the embedding model

- Configure the deployment

  ```sh
  git restore manifests/embedding.yaml
  sed \
  -i -e "s|V_IMAGE|${MLP_MULTIMODAL_EMBEDDING_IMAGE}|" \
  -i -e "s|V_KSA|${MLP_DB_USER_KSA}|" \
  manifests/embedding.yaml
  ```

- Create the deployment

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/embedding.yaml
  ```

## Validate the embedding model deployment

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get pods
```

```sh
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get services
```

## Verify the embedding model

- Configure the curl job.

  ```
  export IMAGE_URI="$(gcloud storage ls gs://${MLP_DATA_BUCKET}/flipkart_images | head -1)"
  echo ${IMAGE_URI}
  ```

  ```
  git restore manifests/curl.yaml
  sed \
  -i -e "s|V_IMAGE_URI|${IMAGE_URI}|" \
  manifests/curl.yaml
  ```

- Create the curl job.

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/curl.yaml
  ```

- Get the logs for the curl job.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/multimodal-curl
  ```
