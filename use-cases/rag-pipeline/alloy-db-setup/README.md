# Process to set up AlloyDB

This kubernetes job helps you load the flipkart product catalog to the alloyDB database named `product_catalog`.Also it creates separate columns to store the embeddings(text, image and multimodal) in a  table named `clothes` in the `product_catalog` database.

## Prerequisites

<TODO> Write few lines about alloydb set up various users for IAM, workload identity , different users in ML_ENV_FILE to use .

MLP accounts MLP_DB_ADMIN_IAM and MLP_DB_USER_IAM need Storage object permissions to retrieve, process and generate embeddings for image_uri stores in Cloud Storage buckets. 

<TODO> Decide what how end users should get access to these buckets of the image_uris and the associated datasets to load the product catalog? 

- Use the existing  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

- AlloyDB instance has been created as part of the ML playground deployment.
- {MLP_ENVIRONMENT_FILE} has the Kubernetes Service Account and Google Cloud Service Account you need for this deployment with the following roles and permission.
```
Cloud AlloyDB Client
Cloud AlloyDB Database User
Service Usage Consumer
Storage Object User
```
- Multimodal embedding model has been deployed as per instructions in the embedding models folder (../embedding-models/README.md)

Steps : 

1. Source your playground environment file to export variables required for the set up.

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project $MLP_PROJECT_ID
```

2. Create the artifact repostiory(if it not already exists) to store the container images:

```
cd src
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="RAG artifacts repository"
```

```
gcloud builds submit . 
```

3. Update the manifest file with the values for deployment.

```
```sh
    export CATALOG_DB="product_catalog"
    export CATALOG_TABLE_NAME="clothes"
    export PROCESSED_DATA_BUCKET="flipkart-processed-data-bucket"
    export MASTER_CATALOG_FILE_NAME="RAG/master_product_catalog.csv"
    export TEXT_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/text_embeddings"
    export IMAGE_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/image_embeddings"
    export MULTIMODAL_EMBEDDING_ENDPOINT="http://multimodal-embedding-model.ml-team:80/multimodal_embeddings" 
    export EMBEDDING_COLUMN_TEXT="text_embeddings"
    export EMBEDDING_COLUMN_MULTIMODAL-"multimodal_embeddings"
    export EMBEDDING_COLUMN_IMAGE="image_embeddings"
    NUM_LEAVES_VALUE="\"300\""
    export EMBEDDING_DIMENSION="\"786\""
```

```sh
  sed \
  -i -e "s|V_MLP_DB_ADMIN_KSA|${MLP_DB_ADMIN_KSA}|" \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_PROCESSED_DATA_BUCKET|${PROCESSED_DATA_BUCKET}|" \
  -i -e "s|V_MASTER_CATALOG_FILE_NAME|${MASTER_CATALOG_FILE_NAME}|" \
  -i -e "s|V_CATALOG_DB|${CATALOG_DB}|" \
  -i -e "s|V_CATALOG_TABLE_NAME|${CATALOG_TABLE_NAME}|" \
  -i -e "s|V_MLP_DB_ADMIN_IAM|${MLP_DB_ADMIN_IAM}|" \
  -i -e "s|V_EMBEDDING_DIMENSION|${EMBEDDING_DIMENSION}|" \
  -i -e "s|V_EMBEDDING_COLUMN_TEXT|${EMBEDDING_COLUMN_TEXT}|" \
  -i -e "s|V_EMBEDDING_COLUMN_IMAGE|${EMBEDDING_COLUMN_IMAGE}|" \
  -i -e "s|V_EMBEDDING_COLUMN_MULTIMODAL|${EMBEDDING_COLUMN_MULTIMODAL}|" \
  -i -e "s|V_NUM_LEAVES_VALUE|${NUM_LEAVES_VALUE}|" \
  -i -e "s|V_MLP_DB_INSTANCE_URI|${MLP_DB_INSTANCE_URI}|" \
  -i -e "s|V_TEXT_EMBEDDING_ENDPOINT|${TEXT_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_IMAGE_EMBEDDING_ENDPOINT|${IMAGE_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_MULTIMODAL_EMBEDDING_ENDPOINT|${MULTIMODAL_EMBEDDING_ENDPOINT}|" \
  -i -e "s|V_MLP_KUBERNETES_NAMESPACE|${MLP_KUBERNETES_NAMESPACE}|" \
  manifests/alloydb-setup-job.yaml
  ```

4. Deploy the alloyDB set up job to ML Playground cluster.

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```
```
kubectl apply -f alloydb-setup-job.yaml -n {MLP_KUBERNETES_NAMESPACE}
```

  > The job runs for about two hours


5. Check the job completion status :
```
kubectl get pods -n {MLP_KUBERNETES_NAMESPACE}
```

6. Check logs for any errors:

```
kubectl logs -f alloydb-setup-xxxxx -n {MLP_KUBERNETES_NAMESPACE}
```

.