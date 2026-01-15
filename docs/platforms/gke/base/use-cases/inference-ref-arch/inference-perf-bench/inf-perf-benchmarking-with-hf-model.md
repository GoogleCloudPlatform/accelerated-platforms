⚙️ GKE Inference Benchmarking with inference-perf (OSS)

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

📝 Prerequisites

Deploy one of the following reference architectures

- [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-hf-model.md)
- [Online inference using vLLM with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm-with-hf-model.md)

Cloud CLI (gcloud): Authenticated to your project. kubectl: Configured to access
your cluster inference-perf: pip install inference-perf in your terminal

## Run the Inference-perf Terraform

1. Creates the GCS bucket for storing inference-perf results
2. Create the Kubernetes service account for the inference-perf workload
3. Grants the required IAM workload identity permissions for KSA

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

Configure the environment variables

- Select an accelerator.

  | Model                          | l4  | h100 | h200 |
  | ------------------------------ | --- | ---- | ---- |
  | gemma-3-1b-it                  | ✅  | ❌   | ❌   |
  | gemma-3-4b-it                  | ✅  | ❌   | ❌   |
  | gemma-3-27b-it                 | ✅  | ✅   | ✅   |
  | gpt-oss-20b                    | ✅  | ✅   | ✅   |
  | llama-3.3-70b-instruct         | ❌  | ✅   | ✅   |
  | llama-4-scout-17b-16e-instruct | ❌  | ✅   | ✅   |
  | qwen3-32b                      | ✅  | ✅   | ✅   |

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

  ````shell
      export APP_LABEL="vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
      ```

  ````

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the benchmarking job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/configure_benchmark.sh"
  ```

  OPTIONAL: Customize the load scenario:

  This example is based on a Linear sweep load test of 7 stages \* 30s with a
  synthetic load. Update the following file with your custom load scenario and
  data set.

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/configmap-benchmark.yaml

  ```

## Deploy the benchmarking job.

```shell
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench"
```

## Analyze and Interpret Results

The output reports (JSON files) are stored in the <GCS Bucket> contain all the
measured metrics for each load stage

Download the report and run inference-perf to create the throughput and latency
curves

```shell
   gsutil -m cp -r gs://${RESULTS_BUCKET}/ .

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

Time-to-First-Token (TTFT) Latency from request start to the first output token.
Crucial for perceived responsiveness in chatbots.

Time-per-Output-Token (TPOT) Average time to generate subsequent tokens. Key
measure of generation speed and sustained throughput.

Total Latency (P95/P99) - End-to-end time for the entire response. Represents
the experience of users with the slowest responses.

Throughput (Tokens/s) Total tokens generated per second under load. Measure of
infrastructure efficiency and capacity.

Analysis Insights: High TTFT: Check your model server's configuration (e.g.,
prefill settings, batching), network connectivity, or KV cache utilization (if
using GKE Inference Gateway).

High TPOT / Low Throughput: You may be hitting hardware saturation. Consider a
more powerful accelerator or scaling up the number of replicas (which should be
handled by HPA).

📚 Resources Tool Description Official

Reference inference-perf GenAI inference performance benchmarking tool for K8s.
kubernetes-sigs/inference-perf (GitHub) GKE Inference Quickstart Provides
verified configurations and benchmarks for deploying models on GKE. GKE AI/ML
documentation
