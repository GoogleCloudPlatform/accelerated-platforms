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


```

4. Deploy the alloyDB set up job to ML Playground cluster.

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```
```
kubectl apply -f alloydb-setup-job.yaml -n {MLP_KUBERNETES_NAMESPACE}
```

5. Check the job completion status :
```
kubectl get pods -n {MLP_KUBERNETES_NAMESPACE}
```

6. Check logs for any errors:

```
kubectl logs -f alloydb-setup-xxxxx -n {MLP_KUBERNETES_NAMESPACE}
```


#### Updates to file 

```sh
  INFERENCE_ENDPOINT="http://vllm-openai-${MODEL_STORAGE}-${ACCELERATOR}:8000/v1/chat/completions"
  INFERENCE_MODEL_PATH="/${MODEL_STORAGE}/${MODEL_NAME}/${MODEL_VERSION}"
  ```

  ```sh
  sed \
  -i -e "s|V_DATA_BUCKET|${MLP_DATA_BUCKET}|" \
  -i -e "s|V_DATASET_OUTPUT_PATH|${DATASET_OUTPUT_PATH}|" \
  -i -e "s|V_IMAGE_URL|${MLP_BATCH_INFERENCE_IMAGE}|" \
  -i -e "s|V_INFERENCE_ENDPOINT|${INFERENCE_ENDPOINT}|" \
  -i -e "s|V_INFERENCE_MODEL_PATH|${INFERENCE_MODEL_PATH}|" \
  -i -e "s|V_KSA|${MLP_BATCH_INFERENCE_KSA}|" \
  -i -e "s|V_PREDICTIONS_FILE|${PREDICTIONS_FILE}|" \
  manifests/job.yaml
  ```

- Create the job

  ```
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} apply -f manifests/job.yaml
  ```

  > The job runs for about an hour.