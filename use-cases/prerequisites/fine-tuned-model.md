# Fine-tuned model

These steps walk you through downloading the fine-tuned model from Hugging Face
and uploads the data into the model GCS bucket for use within the guide for the
respective [use case](/use-cases).

These prereqs were developed to be run on the
[playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
are using a different environment the scripts and manifest will need to be
modified for that environment.

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```shell
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Download the fine-tuned model from Hugging Face and copy it into the GCS
  bucket.

  > NOTE: Due to the limitations of Cloud Shell's storage and the size of our
  > model we need to run this job to perform the transfer to GCS on the cluster.

  - Get credentials for the GKE cluster

    ```shell
    gcloud container clusters get-credentials ${MLP_CLUSTER_NAME} \
    --dns-endpoint \
    --location=${MLP_REGION} \
    --project=${MLP_PROJECT_ID}
    ```

  - Change directory to the prerequisites directory.

    ```shell
    cd use-cases/prerequisites
    ```

  - Replace the respective variables required for the job

    ```shell
    MODEL_REPO=gcp-acp/Llama-gemma-2-9b-it-ft

    git restore manifests/transfer-to-gcs.yaml && \
    sed \
    -i -e "s|V_KSA|${MLP_MODEL_EVALUATION_KSA}|" \
    -i -e "s|V_BUCKET|${MLP_MODEL_BUCKET}|" \
    -i -e "s|V_MODEL_REPO|${MODEL_REPO}|" \
    manifests/transfer-to-gcs.yaml
    ```

  - Deploy the job

    ```shell
    kubectl apply \
    --filename=manifests/transfer-to-gcs.yaml \
    --namespace=${MLP_KUBERNETES_NAMESPACE}
    ```

  - Trigger the wait for job completion (the job will take ~5 minutes to
    complete)

    ```shell
    kubectl wait job/transfer-to-gcs \
    --for=condition=complete \
    --namespace ${MLP_KUBERNETES_NAMESPACE} \
    --timeout=900s
    ```

  - Example output of the job completion

    ```shell
    job.batch/transfer-to-gcs condition met
    ```

  > **NOTE:** Return to the respective use case instructions you were following.
