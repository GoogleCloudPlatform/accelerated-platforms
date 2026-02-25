# Batch inference with GPUs on Google Kubernetes Engine (GKE)

This example implements batch inference using GPUs on Google Kubernetes Engine
(GKE)

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the model.

  - For Llama:
    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-3.3-70B-Instruct**](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the batch GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/offline_batch_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the model to Cloud Storage

- Choose the model.

  - **Llama-3.3-70B-Instruct**:

    ```shell
    export HF_MODEL_ID="meta-llama/Llama-3.3-70B-Instruct"
    ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the model download job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  ```

- Deploy the model download job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the model download job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-hf-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                       STATUS     COMPLETIONS   DURATION   AGE
  XXXXXXXX-hf-model-to-gcs   Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Delete the model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

## Build the container images

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Build the container image for the CPU batch dataset downloader.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/offline_batch_dataset_downloader && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  > The build usually takes 10 to 15 minutes.

- Build the container image for the CPU batch worker.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/cpu/offline_batch_worker && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  > The build usually takes 10 to 15 minutes.

## Run the dataset downloader job

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-dataset-downloader/configure_dataset_downloader.sh"
  ```

- Deploy the dataset downloader job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-dataset-downloader/base"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name} get job/$(cat job_random_hash.txt)-offline-batch-dataset-downloader | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_offline_batch_cpu_dataset_downloader_kubernetes_namespace_name} logs job/$(cat job_random_hash.txt)-offline-batch-dataset-downloader --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
  deployment/batch-pubsub-subscriber   1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

## Run the worker jobset

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the jobset.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-worker/configure_worker.sh"
  ```

- Set the environment variables for the workload.

  - Check the model name.

    ```shell
    echo "HF_MODEL_NAME=${HF_MODEL_NAME}"
    ```

    > If the `HF_MODEL_NAME` variable is not set, ensure that `HF_MODEL_ID` is
    > set and source the `set_environment_variables.sh` script:
    >
    > ```shell
    > source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
    > ```

  - Select an accelerator.

    | Model                  | l4  | h100 | h200 | RTX Pro 6000 |
    | ---------------------- | --- | ---- | ---- | ------------ |
    | llama-3.3-70b-instruct | ❌  | ✅   | ✅   | ✅           |

    - **NVIDIA H100 80GB**:

      ```shell
      export ACCELERATOR_TYPE="h100"
      ```

    - **NVIDIA H200 141GB**:

      ```shell
      export ACCELERATOR_TYPE="h200"
      ```

    - **NVIDIA RTX PRO 6000 96GB**:

      ```shell
      export ACCELERATOR_TYPE="rtx-pro-6000"
      ```

    Ensure that you have enough quota in your project to provision the selected
    accelerator type. For more information, see about viewing GPU quotas, see
    [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

- Deploy the subscriber workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/offline-batch-inference-gpu/offline-batch-worker/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_offline_batch_cpu_worker_kubernetes_namespace_name} get job/js-$(cat jobset_random_hash.txt)-offline-batch-worker | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_offline_batch_cpu_worker_kubernetes_namespace_name} logs job/js-$(cat jobset_random_hash.txt)-offline-batch-worker --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                                 READY   UP-TO-DATE   AVAILABLE   AGE
  deployment/offline-batch-worker   1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.
