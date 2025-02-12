# Process to set up AlloyDB

This kubernetes job helps you load the flipkart product catalog to the alloyDB
database named `product_catalog`.Also it creates separate columns to store the
embeddings(text, image and multimodal) in a table named `clothes` in the
`product_catalog` database.

## Prerequisites

<TODO> Write few lines about alloydb set up various users for IAM, workload
identity , different users in ML_ENV_FILE to use .

<TODO> Decide what how end users should get access to these buckets of the
image_uris and the associated datasets to load the product catalog?

MLP accounts MLP_DB_ADMIN_IAM and MLP_DB_USER_IAM need Storage object
permissions to retrieve, process and generate embeddings for image_uri stores in
Cloud Storage buckets.

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.
- Multimodal embedding model has been deployed as per instructions in the
  embedding models folder (../embedding-models/README.md)

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
  set -o allexport && \
  source ${MLP_ENVIRONMENT_FILE} && \
  set +o allexport
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
  --region ${MLP_REGION} \
  --substitutions _DESTINATION=${MLP_DB_SETUP_IMAGE}
  cd -
  ```

  It takes approximately 2 minutes for the build to complete.

## Run the job

**Steps to produce the `MASTER_CATALOG_FILE_NAME` need to be included
somewhere**

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
  set -o nounset
  export CATALOG_DB_NAME="product_catalog"
  export CATALOG_TABLE_NAME="clothes"
  export DB_READ_USERS="${MLP_DB_USER_IAM}"
  export DB_WRITE_USERS="${MLP_DB_USER_IAM}"
  export EMBEDDING_COLUMN_IMAGE="image_embeddings"
  export EMBEDDING_COLUMN_MULTIMODAL="multimodal_embeddings"
  export EMBEDDING_COLUMN_TEXT="text_embeddings"
  export EMBEDDING_DIMENSION="768"
  export EMBEDDING_ENDPOINT_IMAGE="http://multimodal-embedding-model.ml-team:80/image_embeddings"
  export EMBEDDING_ENDPOINT_MULTIMODAL="http://multimodal-embedding-model.ml-team:80/multimodal_embeddings"
  export EMBEDDING_ENDPOINT_TEXT="http://multimodal-embedding-model.ml-team:80/text_embeddings"
  export MASTER_CATALOG_FILE_NAME="master_product_catalog.csv"
  export NUM_LEAVES_VALUE="300"
  set +o nounset
  ```

  ```sh
  git restore manifests/job-initialize-database.yaml manifests/job-populate-table.yaml
  envsubst < manifests/job-initialize-database.yaml | sponge manifests/job-initialize-database.yaml
  envsubst < manifests/job-populate-table.yaml | sponge manifests/job-populate-table.yaml
  ```

- Create the initialize database job.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job-initialize-database.yaml
  ```

  It takes approximately 1 minute for the job to complete.

- Watch the job until it is complete.

  ```
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get job/initialize-database | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/initialize-database --tail 10"
  ```

- Check logs for any errors.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/initialize-database
  ```

- Create the populate table job.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job-populate-table.yaml
  ```

  It takes approximately 12 minutes for the job to complete.

- Watch the job until it is complete.

  ```
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get job/populate-table | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/populate-table --tail 10"
  ```

- Check logs for any errors.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/populate-table
  ```
