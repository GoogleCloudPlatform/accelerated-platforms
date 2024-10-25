### Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , its ready to run batch Inference pipeline.
In this example batch inference pipeline, we would first send prompts to the hosted fine-tuned model and then validate the results based on ground truth.

#### Prepare your environment


Set env variables.

```
  MLP_PROJECT_ID=<your-project-id>
  PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
  V_MODEL_BUCKET=<model-artifacts-bucket>
  MLP_CLUSTER_NAME=<your-gke-cluster>
  NAMESPACE=ml-serve
  KSA=<k8s-service-account>
  MODEL_PATH=<your-model-path>
  BUCKET="<your dataset bucket name>"
  DATASET_OUTPUT_PATH="your-predictions-data-set-path"
  ENDPOINT=<your-endpoint> # eg "http://vllm-openai:8000/v1/chat/completions"
  KSA=<k8s-service-account> # Service account with work-load identity enabled
```

Create Service account and namespace, if does not exist.

```
NAMESPACE=ml-serve
kubectl create sa ${KSA} -n ${NAMESPACE}
```

Setup Workload Identity Federation access to read/write to the bucket for the inference batch data set

```
gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${NAMESPACE}/sa/${KSA}" \
    --role "roles/storage.objectUser"
```

```
gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${NAMESPACE}/sa/${KSA}" \
    --role "roles/storage.legacyBucketWriter"
```

#### Build the image of the source and execute batch inference job

Create Artifact Registry repository for your docker image

```
gcloud artifacts repositories create batch-inference-repository \
    --repository-format=docker \
    --location=us \
    --project=${MLP_PROJECT_ID} \
    --async
```

Batch Inference Image location

```
BATCH_INFERENCE_IMAGE=us-docker.pkg.dev/${MLP_PROJECT_ID}/batch-inference-repository/batch_inference
```

Set Docker Image URL

```
DOCKER_IMAGE_URL=us-docker.pkg.dev/${MLP_PROJECT_ID}/llm-inference-repository/batch_inference:latest
```

Enable the Cloud Build APIs

```
gcloud services enable cloudbuild.googleapis.com --project ${MLP_PROJECT_ID}
```

Build container image using Cloud Build and push the image to Artifact Registry Modify cloudbuild.yaml to specify the image url

```
gcloud builds submit . --project ${MLP_PROJECT_ID} --substitutions _DESTINATION=${BATCH_INFERENCE_IMAGE}
```

Get credentials for the GKE cluster

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```

Set variables for the inference job in model-eval.yaml

```
sed -i -e "s|IMAGE_URL|${DOCKER_IMAGE_URL}|" \
    -i -e "s|KSA|${KSA}|" \
    -i -e "s|V_BUCKET|${BUCKET}|" \
    -i -e "s|V_MODEL_PATH|${MODEL_PATH}|" \
    -i -e "s|V_DATASET_OUTPUT_PATH|${DATASET_OUTPUT_PATH}|" \
    -i -e "s|V_ENDPOINT|${ENDPOINT}|" \
    -i -e "s|V_PREDICTIONS_FILE|${PREDICTIONS_FILE}|" \
    batch_inference.yaml
```

Create the Job in the ml-serve namespace using kubectl command

```
kubectl apply -f batch_inference.yaml -n ${NAMESPACE}
```

You can review predictions result in file named `predictions.txt` .Sample file has been added to the repository.
The job will take approx 45 mins to execute.