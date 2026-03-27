# Auto-Tune vLLM

[Auto-Tune vLLM](https://github.com/openshift-psap/auto-tuning-vllm) is a
distributed hyperparameter optimization framework for vLLM serving, built with
Ray and Optuna. It can be used to find the most optimum vLLm configuration for a
given model on a given accelerator. This example sets up a job on Google
Kubernetes Engine (GKE), that runs Auto-Tune vLLM for a given model and
accelerator and generating and visualizing the results.

## Before you begin

- The
  [GKE Inference reference implementation](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md)
  is deployed and configured.

- Get access to the models.

  - For Gemma:

    - Consented to the license on [Kaggle](https://www.kaggle.com/) using a
      Hugging Face account.
      - [**google/gemma**](https://www.kaggle.com/models/google/gemma).

  - For Llama:
    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-4-Scout-17B-16E-Instruct**](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct)
      - [**meta-llama/Llama-3.3-70B-Instruct**](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

- Deploy the following reference architecture for GPUs
  - [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)

## Workflow

This example will run through the following steps:

1. Apply the terraform, which will:

   - Create a GCS bucket for storing optimization results.
   - Create a Kubernetes namespace where the Auto-Tune vLLM job will run.
   - Create the Kubernetes service account for the running Auto-Tune vLLM
     workload.
   - Grant the required IAM permissions for workload identity KSA.

2. Create the custom kubernetes manifest for the Auto-Tune vLLM job
3. Run the Auto-Tune vLLM job based on a out-of-the box configuration provided
   with the reference architecture.
4. Store the results generated from the Auto-Tune vLLM job in the GCS bucket.
5. Visualize the results.

## Resources Created

- Cloud Storage Buckets
  - auto-tuning-vllm-results
- Kubernetes Service Account in the auto-tuning-vllm" namespace
- IAM Permissions for Kubernetes service account
  - roles/secretmanager.secretAccessor for Hugging Face token in Secret Manager
  - roles/storage.bucketViewer for results bucket
  - roles/storage.objectUser for results bucket

## Pull the source code

- Open [Cloud Shell](https://cloud.google.com/shell).

- Clone the repository and set the repository directory environment variable.

  ```shell
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms && \
  export ACP_REPO_DIR="$(pwd)"
  ```

To set the `ACP_REPO_DIR` value for new shell instances, write the value to your
shell initialization file.

`bash`

```shell
sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.bashrc
```

`zsh`

```shell
sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.zshrc
```

## Configuration

Terraform loads variables in the following order, with later sources taking
precedence over earlier ones:

- Environment variables (`TF_VAR_<variable_name>`)
- Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
- Any `-var` and `-var-file` options on the command line, in the order they are
  provided.

For more information about providing values for Terraform input variables, see
[Terraform input variables](https://developer.hashicorp.com/terraform/language/values/variables).

- Set the platform default project ID

  ```shell
  export TF_VAR_platform_default_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```shell
  vi ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

  ```hcl
  platform_default_project_id = "<PROJECT_ID>"
  ```

### Install Terraform 1.8.0+

> [!IMPORTANT]  
> At the time this guide was written, Cloud Shell had Terraform v1.5.7 installed
> by default. Terraform version 1.8.0 or later is required for this guide.

- Check the terraform version in your cloud shell

  ```shell
    'terraform version'
  ```

- Run the `install_terraform.sh` script to install Terraform 1.8.0.

  ```shell
  "${ACP_REPO_DIR}/tools/bin/install_terraform.sh"
  ```

## Deploy

### Run Terraform to create the resources

```shell
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/auto-tuning-vllm && \
rm -rf .terraform/ terraform.tfstate* && \
terraform init && \
terraform plan -input=false -out=tfplan && \
terraform apply -input=false tfplan && \
rm tfplan
```

### Configure the environment variables

The goal here is to find the most optimum vLLM settings for serving a model on a
single chip. This reference architecture provides templated manifests to serve
the following single accelerator chip and model.

| Model                          | l4  | h100 | h200 | RTX Pro 6000 |
| ------------------------------ | --- | ---- | ---- | ------------ |
| gemma-3-1b-it                  | ✅  | ❌   | ❌   | ❌           |
| gemma-3-4b-it                  | ✅  | ❌   | ❌   | ❌           |
| gemma-3-27b-it                 | ❌  | ✅   | ✅   | ✅           |
| gpt-oss-20b                    | ❌  | ✅   | ✅   | ✅           |
| llama-3.3-70b-instruct         | ❌  | ❌   | ✅   | ❌           |
| llama-4-scout-17b-16e-instruct | ❌  | ✅   | ✅   | ✅           |
| qwen3-32b                      | ❌  | ✅   | ✅   | ✅           |
| qwen3.5-35B (MoE)              | ❌  | ✅   | ✅   | ✅           |

- Select an accelerator.

  - **NVIDIA Tesla L4 24GB**:

    ```shell
    export ACCELERATOR_TYPE="l4"
    ```

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

- Choose the model.

  - **Gemma 3 1B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-1b-it"
    ```

  - **Gemma 3 4B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-4b-it"
    ```

  - **Gemma 3 27B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-27b-it"
    ```

  - **gpt-oss-120b**

    ```shell
    export HF_MODEL_ID="openai/gpt-oss-20b"
    ```

  - **Llama 4 Scout 17B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="meta-llama/llama-4-scout-17b-16e-instruct"
    ```

  - **Llama 3.3 70B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="meta-llama/llama-3.3-70b-instruct"
    ```

  - **Qwen3-32B**:

    ```shell
    export HF_MODEL_ID="qwen/qwen3-32b"
    ```

  - **Qwen3.5-35B-A3B**:

    ```shell
    export HF_MODEL_ID="qwen/qwen3.5-35b-a3b"
    ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Check the model name.

  ```shell
  echo "HF_MODEL_NAME=${HF_MODEL_NAME}"
  ```

- Export the vLLM service endpoint

  ```shell
  export APP_LABEL="vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
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

- Configure the Auto-Tune vLLM job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/auto-tuning-vllm/configure_vllm.sh"
  ```

## Deploy the Auto-Tune vLLM job.

```shell
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/auto-tuning-vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
```

## Check the status of the job

```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_auto_tuning_vllm_kubernetes_namespace_name} get job/vllm-auto-tuning-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_auto_tuning_vllm_kubernetes_namespace_name} logs job/vllm-auto-tuning-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
```

When the job is complete, you will see the following:

```text
NAME                         STATUS     COMPLETIONS   DURATION   AGE
vllm-auto-tuning-XXXXXX      Complete    1/1           XXX       XXX
```

## Analyze and Interpret Results

The Job runs a container that provides Optuna dashboard that visualizes the
optimization results. While the job is running, you can directly port-forward to
the Optuna dashboard container and view the results.

```shell
   kubectl port-forward --namespace=${ira_auto_tuning_vllm_kubernetes_namespace_name}  pod/$(kubectl --namespace=${ira_auto_tuning_vllm_kubernetes_namespace_name} get pods --selector=job-name=vllm-auto-tuning-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} -o=jsonpath='{.items[0].metadata.name}') 8080:8080

```

Note: The Optuna dashboard container ends after the `autotuner` container in the
job finishes and the results are uploaded to the optimization results bucket.
So, if you want to access the results after the job is completed, those can be
fetched from the GCS bucket and can be visualized with a local installation of
Optuna dashboard.

## Clean up

- Delete the optimization job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/auto-tuning-vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Delete the inference workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Destroy the benchmarking resources.

  > Note: This will only destroy your benchmarking results GCS bucket only if
  > its empty

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```

- Destroy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```

- Destroy the online TPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
