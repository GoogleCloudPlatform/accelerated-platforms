# Process to set up AlloyDB

This kubernetes job helps you load the flipkart product catalog to the alloyDB database named `product_catalog`.Also it creates separate columns to store the embeddings(text, image and multimodal) in a table named `clothes` in the `product_catalog` database.

## Prerequisites

<TODO> Write few lines about alloydb set up various users for IAM, workload identity , different users in ML_ENV_FILE to use .

<TODO> Decide what how end users should get access to these buckets of the image_uris and the associated datasets to load the product catalog?

MLP accounts MLP_DB_ADMIN_IAM and MLP_DB_USER_IAM need Storage object permissions to retrieve, process and generate embeddings for image_uri stores in Cloud Storage buckets.

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- Multimodal embedding model has been deployed as per instructions in the embedding models folder (../embedding-models/README.md)

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/rag-pipeline/alloy-db-setup
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
  --substitutions _DESTINATION=${MLP_DB_SETUP_IMAGE}
  cd -
  ```

## Run the job

**Steps to produce the `MASTER_CATALOG_FILE_NAME` need to be included somewhere**

- Temporary steps to populate required data

  ```
  gcloud storage cp gs://temporary-rag-data/master_product_catalog.csv . && \
  sed -i s"/<MLP_DATA_BUCKET>/${MLP_DATA_BUCKET}/g" master_product_catalog.csv && \
  gcloud storage cp master_product_catalog.csv gs://${MLP_DATA_BUCKET}/ && \
  rm -f master_product_catalog.csv && \
  gcloud storage rsync gs://temporary-rag-data/flipkart_images gs://${MLP_DATA_BUCKET}/flipkart_images/
  ```

- Configure the job

  ```sh
  export CATALOG_DB="product_catalog"
  export CATALOG_TABLE_NAME="clothes"
  export EMBEDDING_COLUMN_IMAGE="image_embeddings"
  export EMBEDDING_COLUMN_MULTIMODAL="multimodal_embeddings"
  export EMBEDDING_COLUMN_TEXT="text_embeddings"
  export EMBEDDING_DIMENSION="\"768\""
  export IMAGE_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/image_embeddings"
  export MASTER_CATALOG_FILE_NAME="master_product_catalog.csv"
  export MULTIMODAL_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/multimodal_embeddings"
  export NUM_LEAVES_VALUE="\"300\""
  export TEXT_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/text_embeddings"
  ```

  ```sh
  git restore manifests/alloydb-setup-job.yaml
  sed \
  -i -e "s|V_CATALOG_DB|${CATALOG_DB}|" \
  -i -e "s|V_CATALOG_TABLE_NAME|${CATALOG_TABLE_NAME}|" \
  -i -e "s|V_IMAGE|${MLP_DB_SETUP_IMAGE}|" \
  -i -e "s|V_KSA|${MLP_DB_ADMIN_KSA}|" \
  -i -e "s|V_EMBEDDING_DIMENSION|${EMBEDDING_DIMENSION}|" \
  -i -e "s|V_EMBEDDING_ENDPOINT_IMAGE|${IMAGE_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_EMBEDDING_ENDPOINT_MULTIMODAL|${MULTIMODAL_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_EMBEDDING_ENDPOINT_TEXT|${TEXT_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_EMBEDDING_COLUMN_TEXT|${EMBEDDING_COLUMN_TEXT}|" \
  -i -e "s|V_EMBEDDING_COLUMN_IMAGE|${EMBEDDING_COLUMN_IMAGE}|" \
  -i -e "s|V_EMBEDDING_COLUMN_MULTIMODAL|${EMBEDDING_COLUMN_MULTIMODAL}|" \
  -i -e "s|V_MASTER_CATALOG_FILE_NAME|${MASTER_CATALOG_FILE_NAME}|" \
  -i -e "s|V_MLP_DB_ADMIN_IAM|${MLP_DB_ADMIN_IAM}|" \
  -i -e "s|V_MLP_DB_INSTANCE_URI|${MLP_DB_INSTANCE_URI}|" \
  -i -e "s|V_MLP_KUBERNETES_NAMESPACE|${MLP_KUBERNETES_NAMESPACE}|" \
  -i -e "s|V_NUM_LEAVES_VALUE|${NUM_LEAVES_VALUE}|" \
  -i -e "s|V_PROCESSED_DATA_BUCKET|${MLP_DATA_BUCKET}|" \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  manifests/alloydb-setup-job.yaml
  ```

- Create the job.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/alloydb-setup-job.yaml
  ```

  > The job runs for about two hours

- Check the status of the job.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get job/alloydb-setup
  ```

- Check logs for any errors.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/alloydb-setup
  ```
