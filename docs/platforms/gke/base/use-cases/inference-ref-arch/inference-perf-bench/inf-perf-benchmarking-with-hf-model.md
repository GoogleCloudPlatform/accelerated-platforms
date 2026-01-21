# GKE Inference Benchmarking with inference-perf

This example sets up a benchmarking job on Google Kubernetes Engine (GKE),
leveraging the Inference-reference-architecture for model deployment and the
inference-perf open-source tool for scalable benchmarking.

Inference-perf is built from the same framework as GKE Inference Quickstart
(GIQ), which provides validated, performance-tuned configurations, accelerating
the deployment of your model server.

Inference-perf allows you to run your own benchmarks and simulate production
traffic and ensure the load generation is external to the model server pods.

This implementation deploys the inference-perf tool as a Kubernetes Job and can
be alternatively deployed as a Helm Chart as well

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

- Deploy one of the following reference architectures for either GPUs or TPUs

  - [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)
  - [Online inference using vLLM with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm-with-hf-model.md)

### Requirements

This guide was designed to be run from
[Cloud Shell](https://cloud.google.com/shell) in the Google Cloud console. Cloud
Shell has the following tools installed:

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
- `curl`
- `envsubst`
- `jq`
- `kubectl`
- `sponge`
- `telnet`
- `wget`
- pip install inference-perf

## Workflow

This example will run through the following steps:

1. Apply the inference_perf_bench terraform, which will:

   - Create the GCS bucket for storing inference-perf results
   - Create the Kubernetes service account for the inference-perf workload
   - Grant the required IAM workload identity permissions for KSA

2. Create the custom kubernetes manifest for the benchmarking job
3. Run the benchmarking job for a load test on the vLLM service
4. Collect the google managed prometheus metrics to generate reports
5. Push the results from the benchmark run
6. Use the inference perf library to analyze the results and create performance
   curves

## Resources Created

- Cloud Storage Buckets
  - Inference-perf results bucket
  - Dataset bucket
- Kubernetes Service Account in the inf-dev-online-gpu / inf-dev-online-tpu
  namespace
- IAM Permissions for Kubernetes service account
  - roles/logging.Viewer
  - roles/monitoring.Viewer
  - roles/monitoring.metricsScopesViewer
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
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
rm -rf .terraform/ terraform.tfstate* && \
terraform init && \
terraform plan -input=false -out=tfplan && \
terraform apply -input=false tfplan && \
rm tfplan
```

## Define the Benchmarking Configuration

The inference-perf tool is configured entirely via the kubernetes manifest to
create a ConfigMap and job.yaml defining the model, dataset, and load pattern.

### Configure the environment variables

Choose between GPU or TPU accelerators:

```shell
export ACCELERATOR="GPU"

```

```shell
export ACCELERATOR="TPU"

```

#### For GPUs:

- Select an accelerator.

  | Model                          | l4  | h100 | h200 | RTX Pro 6000 |
  | ------------------------------ | --- | ---- | ---- | ------------ |
  | gemma-3-1b-it                  | ✅  | ❌   | ❌   | ❌           |
  | gemma-3-4b-it                  | ✅  | ❌   | ❌   | ❌           |
  | gemma-3-27b-it                 | ✅  | ✅   | ✅   | ✅           |
  | gpt-oss-20b                    | ✅  | ✅   | ✅   | ✅           |
  | llama-3.3-70b-instruct         | ❌  | ✅   | ✅   | ✅           |
  | llama-4-scout-17b-16e-instruct | ❌  | ✅   | ✅   | ✅           |
  | qwen3-32b                      | ✅  | ✅   | ✅   | ✅           |

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

#### For TPUs:

- Select an accelerator.

  | Model          | v5e | v6e |
  | -------------- | --- | --- |
  | gemma-3-1b-it  | ✅  | ❌  |
  | gemma-3-4b-it  | ✅  | ❌  |
  | gemma-3-27b-it | ✅  | ✅  |
  | qwen3-32b      | ✅  | ✅  |

  - **v5e**:

    ```shell
    export ACCELERATOR_TYPE="v5e"
    ```

  - **v56e**:

    ```shell
    export ACCELERATOR_TYPE="v6e"
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

- Export the vllm service endpoint

  ```shell
  export APP_LABEL="vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the benchmarking job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/configure_benchmark.sh"
  ```

  - OPTIONAL: Customize the load scenario:

  > This example is based on a Linear sweep load test of 7 stages \* 30s with a
  > synthetic load. Update the following file with your custom load scenario and
  > data set.

  > >

  ````shell
   cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/configmap-benchmark.yaml"
   ```
  ````

## Deploy the benchmarking job.

```shell
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench"
```

When the job is complete, you will see the following:

```text
NAME                       STATUS     COMPLETIONS   DURATION   AGE
inference-perf             Complete   1/1           ###        ###
```

## Analyze and Interpret Results

The output reports (JSON files) are stored in the
**_accelerated-platforms-dev-inf-dev-inf-perf-results_** contain all the
measured metrics for each load stage

Download the report and run inference-perf to create the throughput and latency
curves

```shell
   gsutil -m cp -r gs://accelerated-platforms-dev-inf-dev-inf-perf-results/ .

   inference-perf --analyze  .

```

## Clean up

- Delete the benchmarking workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench"
  ```

- Delete the inference workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Destroy the benchmarking resources.

  > Note: This will destroy your benchmarking results GCS bucket

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

## Key LLM Performance Metrics Metric Description Optimization Focus

- **_Time-to-First-Token (TTFT)_**: Latency from request start to the first
  output token. Crucial for perceived responsiveness in chatbots.

- **_Time-per-Output-Token (TPOT)_**: Average time to generate subsequent
  tokens. Key measure of generation speed and sustained throughput.

- **_Total Latency (P95/P99)_**: End-to-end time for the entire response.
  Represents the experience of users with the slowest responses.

- **_Throughput (Tokens/s)_**: Total tokens generated per second under load.
  Measure of infrastructure efficiency and capacity.

📚 References

- Stay-up to date with the official inference-perf tool to learn more about
  supported datasets and load scenarios:
  (https://github.com/kubernetes-sigs/inference-perf)
