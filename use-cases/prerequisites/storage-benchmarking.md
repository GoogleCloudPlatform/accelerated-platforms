# Storage Benchmarking Prerequisites

These steps walk you through downloading Llama-3.3-70B-Instruct from Hugging Face
into the model GCS bucket for use within the guide for the
respective [use case](/use-cases). Please note that, we will be copying the model 
in two bucket, one of them is a flat bucket while the other is hierarchical.

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

- Set `HF_TOKEN` to your HuggingFace access token. Go to
  <https://huggingface.co/settings/tokens> , click `Create new token` , provide
  a token name, select `Read` in token type and click `Create token`.

  ```sh
  HF_TOKEN=
  ```

- Create a Kubernetes secret to hold the Hugging Face token
  
  ```sh
  kubectl create secret generic hf-secret \
    --from-literal=HF_TOKEN=${HF_TOKEN} \
    --dry-run=client -o yaml | \
    kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply  -f -
  ```

### Copy the model in the flat GCS bucket

  - Replace the respective variables required for the job

    ```sh
    MODEL_REPO=meta-llama/Meta-Llama-3-70B-Instruct

    sed \
      -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
      -i -e "s|V_BUCKET|${MLP_STORAGE_BENCHMARK_FLAT_BUCKET}|" \
      -i -e "s|V_MODEL_REPO|${MODEL_REPO}|" \
      manifests/transfer-llama-to-flat-gcs.yaml
    ```

  - Deploy the job

    ```sh
    kubectl apply --namespace ${MLP_KUBERNETES_NAMESPACE} \
      -f manifests/transfer-llama-to-flat-gcs.yaml
    ```

  - Trigger the wait for job completion (the job will take ~5 minutes to
    complete)

    ```sh
    kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait \
      --for=condition=complete --timeout=900s job/transfer-llama-to-flat-gcs
    ```

  - Example output of the job completion

    ```sh
    job.batch/transfer-llama-to-flat-gcs condition met
    ```



### Copy the model in the hierarchical GCS bucket

  - Replace the respective variables required for the job

    ```sh
    MODEL_REPO=meta-llama/Meta-Llama-3-70B-Instruct

    sed \
      -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
      -i -e "s|V_BUCKET|${MLP_STORAGE_BENCHMARK_HIERARCHICAL_BUCKET}|" \
      -i -e "s|V_MODEL_REPO|${MODEL_REPO}|" \
      manifests/transfer-llama-to-hierarchical-gcs.yaml
    ```

  - Deploy the job

    ```sh
    kubectl apply --namespace ${MLP_KUBERNETES_NAMESPACE} \
      -f manifests/transfer-llama-to-hierarchical-gcs.yaml
    ```

  - Trigger the wait for job completion (the job will take ~5 minutes to
    complete)

    ```sh
    kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait \
      --for=condition=complete --timeout=900s job/transfer-llama-to-hierarchical-gcs
    ```

  - Example output of the job completion

    ```sh
    job.batch/transfer-llama-to-hierarchical-gcs condition met
    ```


  > **NOTE:** Return to the respective use case instructions you were following.
