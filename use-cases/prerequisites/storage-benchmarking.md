# Storage Benchmarking Prerequisites

These steps walk you through downloading Llama-3.3-70B-Instruct from Hugging
Face into the two GCS buckets for use within the guide for the
[storage benchmarking](/use-cases/inferencing/cost-optimization/storage-benchmarking/gcsfuse/).
Please note that, you will be copying the model in two buckets, one of them is a
flat bucket while the other is hierarchical.

These prereqs were developed to be run on the
[playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
are using a different environment the scripts and manifest will need to be
modified for that environment.

> NOTE: Due to the limitations of Cloud Shell's storage and the size of llama
> 70B model we need to run this transfer via Kubernetes job.

- Get access to the model `meta-llama/Llama-3.3-70B-Instruct`

  Go to https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct . Sign In and
  accept the license agreement to get the access to the model.

- Change directory to the guide directory.

  ```sh
  cd use-cases/prerequisites
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  set -o allexport
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  set +o allexport
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster

  ```sh
  gcloud container clusters get-credentials ${MLP_CLUSTER_NAME} \
  --dns-endpoint \
  --location=${MLP_REGION} \
  --project=${MLP_PROJECT_ID}
  ```

- Set `HF_TOKEN` to your HuggingFace access token. Go to
  <https://huggingface.co/settings/tokens> , click `Create new token` , provide
  a token name, select `Read` in token type and click `Create token`.

  ```sh
  HF_TOKEN=
  ```

- Configure the environment

  ```sh
  export ACCELERATOR=a100
  export MODEL_REPO=meta-llama/Llama-3.3-70B-Instruct
  ```

- Create a Kubernetes secret to hold the Hugging Face token

  ```sh
  kubectl create secret generic hf-secret \
    --from-literal=HF_TOKEN=${HF_TOKEN} \
    --dry-run=client -o yaml | \
    kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply  -f -
  ```

- Configure the deployment.

  ```
  git restore manifests/transfer-llama-to-gcs-${ACCELERATOR}-dws.yaml
  envsubst < manifests/transfer-llama-to-gcs-${ACCELERATOR}-dws.yaml | sponge manifests/transfer-llama-to-gcs-${ACCELERATOR}-dws.yaml
  ```

  > Ensure there are no bash: <ENVIRONMENT_VARIABLE> unbound variable error
  > messages.

- Create the provisioning request and the job. The job copies llama 70B model to
  the flat and hierarchical GCS buckets.

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/provisioning-request-llama-transfer-${ACCELERATOR}.yaml
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/transfer-llama-to-gcs-${ACCELERATOR}-dws.yaml
  ```

  You will see output similar to the following:

  ```sh
  podtemplate/a100-gcs-transfer-job created
  provisioningrequest.autoscaling.x-k8s.io/a100-gcs-transfer-job created
  job.batch/transfer-llama-to-gcs created
  ```

  > Note : It may take a few minutes before the provisioning request is accepted
  > and the resources are provisioned. The job will be started as soon as the
  > resources are provisioned.

- Check the status of the provisioning request, once the `PROVISIONED` column
  shows `True`, the deployment will start.

  ```sh
  watch -n 5 kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get provisioningrequest ${ACCELERATOR}-gcs-transfer-job
  ```

- Once the job is started, trigger the wait for job completion(the job will take
  ~24 minutes to complete)

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait \
    --for=condition=complete --timeout=900s job/transfer-llama-to-gcs
  ```

- Example output of the job completion

  ```sh
  job.batch/transfer-llama-to-gcs condition met
  ```

- List the model files in the GCS buckets to verify the transfer.

  ```sh
  gcloud storage ls gs://${MLP_STORAGE_BENCHMARK_FLAT_BUCKET}/meta-llama/Llama-3.3-70B-Instruct

  gcloud storage ls gs://${MLP_STORAGE_BENCHMARK_HIERARCHICAL_BUCKET}/meta-llama/Llama-3.3-70B-Instruct
  ```

> **NOTE:** Return to the respective use case instructions you were following.
