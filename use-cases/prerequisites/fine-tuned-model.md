# Fine-tuned model

These steps walk you through downloading the fine-tuned model from Hugging Face
and uploads the data into the model GCS bucket for use within the guide for the
respective [use case](/use-cases).

These prereqs were developed to be run on the
[playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
are using a different environment the scripts and manifest will need to be
modified for that environment.

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Download the fine-tuned model from Hugging Face and copy it into the GCS
  bucket.

  > NOTE: Due to the limitations of Cloud Shell’s storage and the size of our
  > model we need to run this job to perform the transfer to GCS on the cluster.

  - Get credentials for the GKE cluster

    ```sh
    gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
    ```

  - Replace the respective variables required for the job

    ```sh
    MODEL_REPO=gcp-acp/Llama-gemma-2-9b-it-ft

    sed \
      -i -e "s|V_KSA|${MLP_MODEL_EVALUATION_KSA}|" \
      -i -e "s|V_BUCKET|${MLP_MODEL_BUCKET}|" \
      -i -e "s|V_MODEL_REPO|${MODEL_REPO}|" \
      manifests/transfer-to-gcs.yaml
    ```

  - Deploy the job

    ```sh
    kubectl apply --namespace ${MLP_KUBERNETES_NAMESPACE} \
      -f manifests/transfer-to-gcs.yaml
    ```

  - Trigger the wait for job completion (the job will take ~5 minutes to
    complete)

    ```sh
    kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait \
      --for=condition=complete --timeout=900s job/transfer-to-gcs
    ```

  - Example output of the job completion

    ```sh
    job.batch/transfer-to-gcs condition met
    ```

  > **NOTE:** Return to the respective use case instructions you were following.
