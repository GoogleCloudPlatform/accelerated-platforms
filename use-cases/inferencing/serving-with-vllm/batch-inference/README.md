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
PREDICTIONS_FILE=<predictions.txt> # Look for sample example-prediction.text for expected results
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
