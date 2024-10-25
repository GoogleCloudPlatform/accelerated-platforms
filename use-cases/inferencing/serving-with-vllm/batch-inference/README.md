### Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , its ready to run batch Inference pipeline.
In this example batch inference pipeline, we would first send prompts to the hosted fine-tuned model and then validate the results based on ground truth.

#### Prepare your environment


Set env variables.

```
PROJECT_ID=<your-project-id>
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
CLUSTER_NAME=<your-gke-cluster>
NAMESPACE=ml-serve
MODEL_PATH=<your-model-path>
BUCKET="<your dataset bucket name>"
DATASET_OUTPUT_PATH=""
ENDPOINT=<your-endpoint> # eg "http://vllm-openai:8000/v1/chat/completions"
KSA=<k8s-service-account> # Service account with work-load identity enabled
```

Create Service account.

```
NAMESPACE=ml-serve
kubectl create sa ${KSA} -n ${NAMESPACE}
```

Setup Workload Identity Federation access to read/write to the bucket for the inference batch data set

```
gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/${NAMESPACE}/sa/${KSA}" \
    --role "roles/storage.objectUser"
```

```
gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
    --member "principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/${NAMESPACE}/sa/${KSA}" \
    --role "roles/storage.legacyBucketWriter"
```

#### Build the image of the source and execute batch inference job

Create Artifact Registry repository for your docker image

```
gcloud artifacts repositories create llm-inference-repository \
    --repository-format=docker \
    --location=us \
    --project=${PROJECT_ID} \
    --async

```

Set Docker Image URL

```
DOCKER_IMAGE_URL=us-docker.pkg.dev/${PROJECT_ID}/llm-inference-repository/validate:v1.0.0
```

Enable the Cloud Build APIs

```
gcloud services enable cloudbuild.googleapis.com --project ${PROJECT_ID}
```

Build container image using Cloud Build and push the image to Artifact Registry Modify cloudbuild.yaml to specify the image url

sed -i "s|IMAGE_URL|${DOCKER_IMAGE_URL}|" cloudbuild.yaml && \
gcloud builds submit . --project ${PROJECT_ID}

Get credentials for the GKE cluster

```
gcloud container fleet memberships get-credentials ${CLUSTER_NAME} --project ${PROJECT_ID}
```

Set variables for the inference job in model-eval.yaml

```
sed -i -e "s|IMAGE_URL|${DOCKER_IMAGE_URL}|" \
    -i -e "s|KSA|${KSA}|" \
    -i -e "s|V_BUCKET|${BUCKET}|" \
    -i -e "s|V_MODEL_PATH|${MODEL_PATH}|" \
    -i -e "s|V_DATASET_OUTPUT_PATH|${DATASET_OUTPUT_PATH}|" \
    -i -e "s|V_ENDPOINT|${ENDPOINT}|" \
    model-eval.yaml
```

Create the Job in the ml-team namespace using kubectl command

```
kubectl apply -f model-eval.yaml -n ${NAMESPACE}
```

You can review predictions result in file named `predictions.txt` .Sample file has been added to the repository.
The job will take approx 45 mins to execute.