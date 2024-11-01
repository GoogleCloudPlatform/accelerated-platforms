### Run Batch inference on GKE

#### Prepare your environment

*   Ensure that your `MLP_ENVIRONMENT_FILE` is configured

    ```sh
    cat ${MLP_ENVIRONMENT_FILE} && \
    source ${MLP_ENVIRONMENT_FILE}
    ```

*   Switch to inference directory

    ```sh
    cd ${BATCH_INFERENCE_DIR}
    ```

*   Setup Workload Identity Federation access to read/write to the bucket for the inference batch data set


    ```sh
     gcloud storage buckets add-iam-policy-binding "gs://${MLP_MODEL_BUCKET}" \
    --member "principal://iam.googleapis.com/projects/"${MLP_PROJECT_NUMBER}"/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${MLP_KUBERNETES_NAMESPACE}/sa/${MLP_SERVE_KSA}" \
    --role "roles/storage.objectUser"
  
     gcloud storage buckets add-iam-policy-binding "gs://${MLP_MODEL_BUCKET}" \
    --member "principal://iam.googleapis.com/projects/"${MLP_PROJECT_NUMBER}"/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${MLP_KUBERNETES_NAMESPACE}/sa/${MLP_SERVE_KSA}" \
    --role "roles/storage.legacyBucketWriter"

    ```

#### Build the image of the source and execute batch inference job

*   Build container image using Cloud Build and push the image to Artifact Registry. 

    ```sh
    cd src
    sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
    gcloud beta builds submit \
    --config cloudbuild.yaml \
    --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
    --project ${MLP_PROJECT_ID} \
    --substitutions _DESTINATION=${MLP_SERVE_IMAGE}
    cd -
    ```

*   Set variables

    ```sh
    DATASET_OUTPUT_PATH=dataset/output
    EVAL_MODEL_PATH=/data/models/${MODEL_ID}/${MODEL_PATH}
    ENDPOINT="http://vllm-openai:8000/v1/chat/completions" # The model endpoint
    PREDICTION_FILE="prediction.txt" #output file for predictions
    ```

*   Replace variables in inference job manifest and deploy the job
    ```sh
    sed -i -e "s|_IMAGE_URL_|${MLP_SERVE_IMAGE}|" \
        -i -e "s|_KSA_|${MLP_SERVE_KSA}|" \
        -i -e "s|_MLP_PREDICTION_BUCKET_|${$MLP_DATA_BUCKET}|" \
        -i -e "s|_EVAL_MODEL_PATH_|${EVAL_MODEL_PATH}|" \
        -i -e "s|_DATASET_OUTPUT_PATH_|${DATASET_OUTPUT_PATH}|" \
        -i -e "s|_ENDPOINT_|${ENDPOINT}|" \
        -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|" \
        -i -e "s|_PREDICTION_FILE_|${PREDICTION_FILE}|" \
        prediction.yaml
    kubectl apply -f prediction.yaml
    ```

You can review predictions result in file named `predictions.txt` under /dataset/output folder in the bucket. Sample file has been added to the repository.
The job will take approx 45 mins to execute.

*   Go back to the infernece directory

    ```sh
    cd  ${INFERENCE_DIR}
    ```
  
  TODO: MLP_PREDICTION_BUCKET may not be needed. Check with kavitha to see if you cant point to the fine tuned date bucket