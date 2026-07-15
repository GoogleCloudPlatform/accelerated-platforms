# Online inference using vLLM with speculative decoding and GPUs on Google Kubernetes Engine (GKE)

This document implements online inference using GPUs on Google Kubernetes Engine
(GKE) using vLLM with Speculative Decoding enabled.

Speculative decoding is a powerful optimization technique that enhances LLM
inference speed without compromising output quality. It utilizes a smaller,
faster "draft" model or method to generate candidate tokens, which are then
validated by the main, larger "target" model in a single, efficient step. This
reduces the computational overhead and improves both throughput and inter-token
latency however, the technique potentially requires tuning for your specific use
case as a low draft acceptance rate reduces the overall throughput (tok/s). vLLM
supports several speculative decoding methods, each tailored to different use
cases and performance requirements. See the
[Speculative Decoding guide](https://docs.vllm.ai/en/stable/features/spec_decode/#speculative-decoding)
in the official vLLM docs for in depth concepts and examples. This guide will
walk you through the implementation of the following Speculative Decoding
methods with vLLM on GKE:

- [N-gram Based Speculative Decoding](https://docs.vllm.ai/en/stable/features/spec_decode/#speculating-by-matching-n-grams-in-the-prompt)

  This method is particularly effective for tasks where the output is likely to
  contain sequences from the input prompt, such as summarization or
  question-answering. Instead of a draft model, it uses n-grams from the prompt
  to generate token proposals.

- [EAGLE Based Draft Models](https://docs.vllm.ai/en/stable/features/spec_decode.html#speculating-using-eagle-based-draft-models)

  [EAGLE (Extrapolation Algorithm for Greater Language-model Efficiency)](https://arxiv.org/pdf/2401.15077)
  is a state-of-the-art speculative decoding method that uses a lightweight
  draft model to generate multiple candidate tokens in parallel.

- [Multi-Token Prediction (MTP)](https://docs.vllm.ai/en/stable/features/spec_decode.html#multi-token-prediction-mtp)

  MTP is an optimization that allows the model to predict multiple tokens
  simultaneously, which can significantly speed up inference for models like
  Qwen 3.6.

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the models.

  - For Gemma:

    - Consented to the license on [Kaggle](https://www.kaggle.com/) using a
      Hugging Face account.
      - [**google/gemma-4-31b-it**](https://huggingface.co/google/gemma-4-31b-it)
      - [**google/gemma-3-27b-it**](https://huggingface.co/google/gemma-3-27b-it)
      - [**thoughtworks/Gemma-4-31B-Eagle3**](https://huggingface.co/thoughtworks/Gemma-4-31B-Eagle3)
      - [**yuhuili/EAGLE3-Gemma-2-27B-Instruct**](https://huggingface.co/yuhuili/EAGLE3-Gemma-2-27B-Instruct)

  - For Llama:
    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-4-Scout-17B-16E-Instruct**](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct)
      - [**meta-llama/Llama-3.3-70B-Instruct**](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
      - [**nvidia/llama-3.3-70b-instruct-fp8**](https://huggingface.co/nvidia/llama-3.3-70b-instruct-fp8)
      - [**yuhuili/eagle3-llama3.3-instruct-70b**](https://huggingface.co/yuhuili/eagle3-llama3.3-instruct-70b)

  - For Qwen:
    - [**Qwen/Qwen3.6-35B-A3B**](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)
    - [**nvidia/Qwen3-35B-A3B-Eagle3**](https://huggingface.co/nvidia/Qwen3-35B-A3B-Eagle3)
    - [**Qwen/Qwen3.5-27B-Instruct**](https://huggingface.co/Qwen/Qwen3.5-27B-Instruct)
    - [**nvidia/Qwen3-27B-Eagle3**](https://huggingface.co/nvidia/Qwen3-27B-Eagle3)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the models to Cloud Storage

- Choose the model.

  - **Qwen 3.6 35B-A3B (MoE)**:

    ```shell
    export HF_MODEL_ID="Qwen/Qwen3.6-35B-A3B"
    ```

  - **Qwen 3.6 35B Draft Model (EAGLE3)**:

    ```shell
    export HF_MODEL_ID="nvidia/Qwen3-35B-A3B-Eagle3"
    ```

  - **Gemma 4 31B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

  - **Gemma 4 31B Draft Model (EAGLE3)**:

    ```shell
    export HF_MODEL_ID="thoughtworks/Gemma-4-31B-Eagle3"
    ```

  - **Gemma 3 27B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-27b-it"
    ```

  - **Llama 3.3 70B Instruction-Tuned (FP8)**:

    ```shell
    export HF_MODEL_ID="nvidia/llama-3.3-70b-instruct-fp8"
    ```

  - **EAGLE3 Llama 3.3 70B Draft Model**:

    ```shell
    export HF_MODEL_ID="yuhuili/eagle3-llama3.3-instruct-70b"
    ```

> [!TIP]
> If you plan to use **EAGLE Based Draft Models**, ensure you download both the
> target model (e.g., `llama-3.3-70b-instruct` or `qwen2.5-32b-instruct`)
> AND the draft model (e.g., `eagle3-llama3.3-instruct-70b` or `Qwen3-32B-speculator.eagle3`)
> by running the download job for each `HF_MODEL_ID`.

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

## Deploy the inference workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/configure_vllm_spec_decoding.sh"
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
    > source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"`
    > ```

  - Select an accelerator.

    | Model                        | h100 | rtx-pro-6000 |
    | ---------------------------- | ---- | ------------ |
    | qwen3-6-35b-a3b              | ✅   | ✅           |
    | gemma-4-31b-it               | ✅   | ✅           |
    | gemma-3-27b-it               | ✅   | ✅           |
    | llama-3.3-70b-instruct       | ✅   | ✅           |
    | llama-3.3-70b-instruct-fp8   | ✅   | ✅           |

    - **NVIDIA H100 80GB**:

      ```shell
      export ACCELERATOR_TYPE="h100"
      ```

    - **NVIDIA RTX Pro 6000 96GB**:

      ```shell
      export ACCELERATOR_TYPE="rtx-pro-6000"
      ```

    Ensure that you have enough quota in your project to provision the selected
    accelerator type. For more information, see about viewing GPU quotas, see
    [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

    The Kubernetes manifests invoked below are aligned with the guidance
    provided in
    [Inference Quickstart recommendations](https://cloud.google.com/kubernetes-engine/docs/how-to/machine-learning/inference-quickstart).

### Speculative Decoding with ngram

- Deploy the inference workload.

  ```shell
  export METHOD=ngram && \
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

- Watch the deployment until it is ready.

  ```shell
  export METHOD=ngram && \
  watch --color --interval 5 --no-title "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} --all-containers --tail 10"
  ```

- When the deployment is ready, you will see output similar to the following:

  ```text
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-h100-gemma-3-27b-it-sd-ngram         1/1     1            1           ###
  vllm-rtx-pro-6000-gemma-4-31b-it-sd-ngram  1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Send a test request to the model.

  Start a port forward to the model service.

  ```shell
  export METHOD=ngram && \
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} 8000:8000 >/dev/null & \
  PF_PID=$!
  ```

  Send a test request.

  ```shell
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "/gcs/'${HF_MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  ```

  Stop the port forward.

  ```shell
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  export METHOD=ngram && \
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

### Speculative Decoding with Eagle

- Deploy the inference workload.

  ```shell
  export METHOD=eagle && \
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

- Watch the deployment until it is ready.

  ```shell
  export METHOD=eagle && \
  watch --color --interval 5 --no-title "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see output similar to the following:

  ```text
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-h100-llama-3-3-70b-it-sd-eagle         1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Send a test request to the model.

  Start a port forward to the model service.

  ```shell
  export METHOD=eagle && \
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} 8000:8000 >/dev/null & \
  PF_PID=$!
  ```

  Send a test request.

  ```shell
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "/gcs/'${HF_MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  ```

  Stop the port forward.

  ```shell
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  export METHOD=eagle && \
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

### Speculative Decoding with Multi-Token Prediction (MTP)

- Deploy the inference workload.

  ```shell
  export METHOD=mtp && \
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

- Watch the deployment until it is ready.

  ```shell
  export METHOD=mtp && \
  watch --color --interval 5 --no-title "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see output similar to the following:

  ```text
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-rtx-pro-6000-qwen3-6-35b-a3b-sd-mtp  1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Send a test request to the model.

  Start a port forward to the model service.

  ```shell
  export METHOD=mtp && \
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} 8000:8000 >/dev/null & \
  PF_PID=$!
  ```

  Send a test request.

  ```shell
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "/gcs/'${HF_MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  ```

  Stop the port forward.

  ```shell
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  export METHOD=mtp && \
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

### Performance Optimization: FP8 with TP=1 vs. BF16/FP16 with TP=4

When deploying Llama 3.3 70B on RTX Pro 6000 GPUs, the standard BF16/FP16 model
requires a Tensor Parallel (TP) size of 4 to fit within the combined GPU memory.
However, by using the **FP8 quantized model** (`nvidia/llama-3.3-70b-instruct-fp8`),
a single replica can fit on a **single RTX Pro 6000 GPU (TP=1)**.

This allows you to deploy **four independent replicas** using the same amount of
hardware (4 GPUs) as a single TP=4 replica. By stitching these four replicas
together behind a GKE Inference Gateway (Service), you can achieve significantly
higher aggregate throughput compared to a single TP=4 replica of the non-quantized
model, especially when combined with EAGLE3 speculative decoding.

To scale the FP8 TP=1 deployment to 4 replicas:

```shell
export METHOD=eagle && \
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} scale deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} --replicas=4
```

## Measuring speculative decoding (ngram/eagle/mtp) performance with inference-perf

Inference-perf allows you to run your own benchmarks and simulate production
traffic and ensure the load generation is external to the model server pods.

This implementation deploys the inference-perf tool as a Kubernetes Job and can
be customized with different load scenarios and datasets.

Stay-up to date with the official
[inference-perf tool](https://github.com/kubernetes-sigs/inference-perf) to
learn more about all the supported features for metrics,load scenarios, and
datasets.

Optional - Install the inference-perf and matplot libraries to be able to create
throughput vs latency curves

```shell
pip install inference-perf
pip install matplotlib
```

### Workflow

This example will run through the following steps:

1. Apply the inference_perf_bench terraform, which will:

   - Create the GCS bucket for storing inference-perf results
   - Create the GCS bucket for storing a custom benchmarking dataset
   - Create the Kubernetes service account for the inference-perf workload
   - Grant the required IAM permissions for workload identity KSA

2. Create the custom kubernetes manifest for the benchmarking job
3. Run the benchmarking job for a load test on the vLLM service
4. Collect the google managed prometheus metrics to generate reports
5. Push the results from the benchmark run to the results GCS bucket

#### Run the Inference-perf terraform

```shell
export TF_VAR_enable_gpu=true
export ACCELERATOR="GPU"
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
rm -rf .terraform/ terraform.tfstate* && \
terraform init && \
terraform plan -input=false -out=tfplan && \
terraform apply -input=false tfplan && \
rm tfplan
```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Export the vLLM service endpoint

  ```shell
  export APP_LABEL="vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

  > > Verify the APP_LABEL
  > >
  > > ```shell
  > > echo $APP_LABEL
  > > ```

#### Run the benchmarking job.

- Configure the benchmarking job.

```shell
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-${METHOD}/configure_benchmark.sh"
```

- Deploy the benchmarking job.

```shell
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-${METHOD}"
```

- Check the status of the job

The job can take up an estimated 15 mins to run through all the stages

```shell
watch --color --interval 5 --no-title "
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get job/${SHORT_HASH}-inference-perf | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1';
  echo '\nLogs(last 10 lines):';
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs job/${SHORT_HASH}-inference-perf --all-containers --tail 10
  "
```

When the job is complete, you will see the following:

```text
NAME                       STATUS     COMPLETIONS   DURATION   AGE
XXXXXX-inference-perf      Complete    1/1           15m       25m
```

#### Analyze and Interpret Results

The output reports (JSON files) can be viewed in benchmarking results bucket
with metrics for each load stage

Download the report and run inference-perf to create the throughput and latency
curves

```shell
   gcloud storage cp -r gs://${hub_models_bucket_bench_results_name}/ .
   inference-perf --analyze ${hub_models_bucket_bench_results_name}/*

```

- Delete the benchmarking job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-${METHOD}"
  ```

## Troubleshooting

If you experience any issue while deploying the workload, see the
[Online inference with GPUs Troubleshooting](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/troubleshooting.md)
guide.

## Clean up

- Destroy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
