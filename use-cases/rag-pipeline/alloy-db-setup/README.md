# RAG: Database setup and initialization

This kubernetes job helps you load the flipkart product catalog to the alloyDB
database named `product_catalog`.Also it creates separate columns to store the
embeddings(text, image and multimodal) in a table named `clothes` in the
`product_catalog` database.

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.
- [RAG: Multimodal embedding model](/use-cases/rag-pipeline/embedding-models/multimodal-embedding/README.md)
  has been deployed as per the instructions.

## Preparation

- Clone the repository.

  ```shell
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```shell
  cd use-cases/rag-pipeline/alloy-db-setup
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
  Registry

  ```shell
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

- Configure the job

  ```shell
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
  export MASTER_CATALOG_FILE_NAME="RAG/master_product_catalog.csv"
  export NUM_LEAVES_VALUE="300"
  set +o nounset
  ```

  > Ensure there are no `bash: <ENVIRONMENT_VARIABLE> unbound variable` error
  > messages.

  ```shell
  git restore manifests/job-initialize-database.yaml manifests/job-populate-table.yaml
  envsubst < manifests/job-initialize-database.yaml | sponge manifests/job-initialize-database.yaml
  envsubst < manifests/job-populate-table.yaml | sponge manifests/job-populate-table.yaml
  ```

- Create the initialize database job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job-initialize-database.yaml
  ```

  It takes approximately 1 minute for the job to complete.

- Watch the job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get job/initialize-database | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/initialize-database --tail 10"
  ```

  ```
  NAME                  STATUS     COMPLETIONS   DURATION   AGE
  initialize-database   Complete   1/1           XXXXX      XXXXX
  ```

- Check logs for any errors.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/initialize-database
  ```

- Create the populate table job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job-populate-table.yaml
  ```

  It takes approximately 12 minutes for the job to complete.

- Watch the job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get job/populate-table | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/populate-table --tail 10"
  ```

  ```
  NAME             STATUS     COMPLETIONS   DURATION   AGE
  populate-table   Complete   1/1           XXXXX      XXXXX
  ```

- Check logs for any errors.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/populate-table
  ```
