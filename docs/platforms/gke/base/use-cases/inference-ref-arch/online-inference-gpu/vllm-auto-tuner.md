# Automated vLLM Server Parameter Tuning

This guide is aimed at finding the maximum throughput that we can get with the
single chips of nvidia-h100-80gb and nvidia-rtx-pro-6000 while running inference
of Qwen3/Qwen3-32B on Google Kubernetes Engine. We will use vLLM as the
inference server and try to find the parameters that provide us the best
performance. vLLM provides a script to automate the process of finding the
optimal server parameter combination (max-num-seqs and max-num-batched-tokens)
to maximize throughput for a vLLM server. It also supports additional
constraints such as E2E latency and prefix cache hit rate. More details are on
the
[official GitHub repository](https://github.com/vllm-project/vllm/tree/main/benchmarks/auto_tune)

## Before you begin

- Make sure that the
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

## Workflow

This example will run through the following steps:

1. Apply the terraform, which will:

   - Create a GCS bucket for storing optimization results.
   - Create a Kubernetes namespace where the vLLM auto-tune job will run.
   - Create the Kubernetes service account for the running vLLM auto-tune job.
   - Grant the required IAM permissions for workload identity KSA.

2. Create the custom kubernetes manifest for the vLLM auto-tune job
3. Run the vLLM auto-tune job based on a out-of-the box configuration provided
   with the reference architecture.
4. Store the results generated from the vLLM auto-tune job in the GCS bucket.

## Resources Created

- Cloud Storage Bucket
- Kubernetes namespace
- Kubernetes Service Account in the namespace
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
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/vllm-auto-tuning && \
rm -rf .terraform/ terraform.tfstate* && \
terraform init && \
terraform plan -input=false -out=tfplan && \
terraform apply -input=false tfplan && \
rm tfplan
```

### Configure the environment variables

The goal here is to find the most optimum vLLM parameters for serving
Qwen3/Qwen3-32B on a single chip of nvidia-h100-80gb(A3 High) and
nvidia-rtx-pro-6000(G4) in order to get the maximum throughput. This reference
architecture provides templated manifests to serve the following single
accelerator chip and model combination.

    | Model                          | h100 | RTX Pro 6000 |
    | ------------------------------ | ---- | ------------ |
    | qwen3-32b                      | ✅   | ✅           |

- Select an accelerator.

  - **NVIDIA H100 80GB**:

    ```shell
    export ACCELERATOR_TYPE="h100"
    ```

  - **NVIDIA RTX PRO 6000 96GB**:

    ```shell
    export ACCELERATOR_TYPE="rtx-pro-6000"
    ```

    Ensure that you have enough quota in your project to provision the selected
    accelerator type. For more information, see about viewing GPU quotas, see
    [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

- Set the model.

  - **Qwen3-32B**:

    ```shell
    export HF_MODEL_ID="qwen/qwen3-32b"
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

### Download the model from HuggingFace to GCS bucket

- [Generate a Hugging Face tokens](https://huggingface.co/docs/hub/security-tokens)
  with token type **Read**.
- Add the token to the secret manager

  ```
  HF_TOKEN_READ=<YOUR_HUGGINGFACE_READ_TOKEN>
  echo ${HF_TOKEN_READ} | gcloud secrets versions add ${huggingface_hub_access_token_read_secret_manager_secret_name} --data-file=- --project=${huggingface_secret_manager_project_id}
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

### Deploy the vLLM auto-tune job

- Configure the vLLM auto-tune job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-auto-tuning/configure_vllm.sh"
  ```

- Deploy the vLLM auto-tune job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-auto-tuning/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

### Check the status of the job

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

Download the results from the GCS bucket to your
[Cloud Shell](https://cloud.google.com/shell).

```
gcloud storage cp --recursive gs://${ira_auto_tuning_vllm_results_bucket}
```

View the files to see the result.

## Clean up

- Delete the vLLM auto-tune job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-auto-tuning/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Destroy the vLLM auto-tune resources created via Terraform.

  > Note: This will only destroy your benchmarking results GCS bucket only if
  > its empty

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/vllm-auto-tuning  && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
