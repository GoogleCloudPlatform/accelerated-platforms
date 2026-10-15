# Online inference using vLLM with speculative decoding and GPUs on Google Kubernetes Engine (GKE)

This document implements online inference using GPUs on Google Kubernetes Engine
(GKE) using vLLM with Speculative Decoding enabled, and demonstrates how to
benchmark Speculative Decoding side-by-side against a standard vLLM baseline
deployment using `inference-perf`.

Speculative decoding is a powerful optimization technique that enhances LLM
inference speed without compromising output quality. It utilizes a smaller,
faster "draft" model or method to generate candidate tokens, which are then
validated by the main, larger "target" model in a single, efficient forward
pass. This reduces memory-bandwidth overhead during auto-regressive decoding and
improves both output throughput and Time Per Output Token (TPOT). However,
because speculative decoding trades additional compute per step for fewer
memory-bound target passes, its net gain depends on the draft token acceptance
rate ($\alpha$) and workload concurrency. See the
[Speculative Decoding guide](https://docs.vllm.ai/en/stable/features/spec_decode/#speculative-decoding)
in the official vLLM documentation for in-depth concepts and examples.

This guide walks you through three distinct Speculative Decoding paradigms with
vLLM on GKE:

- [N-gram Based Speculative Decoding (`method="ngram"`)](https://docs.vllm.ai/en/stable/features/spec_decode/#speculating-by-matching-n-grams-in-the-prompt)

  Matches n-gram sequences directly from the input prompt and generated prefix
  to propose candidate tokens with zero additional model weights or GPU memory
  overhead. This method is particularly effective for grounded tasks where the
  output frequently copies or paraphrases spans from the input context, such as
  document summarization (`cnn_dailymail`), RAG, or code editing.

- [EAGLE3 Based Draft Models (`method="eagle3"`)](https://docs.vllm.ai/en/stable/features/spec_decode.html#speculating-using-eagle-based-draft-models)

  [EAGLE (Extrapolation Algorithm for Greater Language-model Efficiency)](https://arxiv.org/pdf/2401.15077)
  uses a lightweight (~1B parameter) neural draft head conditioned on the target
  model's internal hidden states to propose candidate token trees, achieving
  high acceptance rates across open-ended conversational and instruction-tuned
  workloads (`shareGPT`).

- [Multi-Token Prediction (`method="mtp"`)](https://docs.vllm.ai/en/stable/features/spec_decode.html#multi-token-prediction-mtp)

  Native Multi-Token Prediction uses prediction heads co-trained directly inside
  the foundation model checkpoint (such as `Qwen/Qwen3.6-35B-A3B`) to predict
  multiple future tokens per step. Because the MTP head is bundled inside the
  target checkpoint and shares the model's exact vocabulary and hidden states,
  it requires no separate draft model download and achieves very high acceptance
  rates.

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the models.

  - For Gemma:

    - Consented to the license on [Kaggle](https://www.kaggle.com/) or Hugging
      Face using a Hugging Face account.
      - [**google/gemma-3-27b-it**](https://huggingface.co/google/gemma-3-27b-it)
      - [**google/gemma-4-31b-it**](https://huggingface.co/google/gemma-4-31b-it)

  - For Llama:

    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-3.3-70B-Instruct**](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
      - [**nvidia/Llama-3.3-70B-Instruct-FP8**](https://huggingface.co/nvidia/Llama-3.3-70B-Instruct-FP8)
      - [**yuhuili/EAGLE3-LLaMA3.3-Instruct-70B**](https://huggingface.co/yuhuili/EAGLE3-LLaMA3.3-Instruct-70B)

  - For Qwen:
    - [**Qwen/Qwen3.6-35B-A3B**](https://huggingface.co/Qwen/Qwen3.6-35B-A3B)

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

- Choose the model for your speculative decoding path.

  - **Path 1 — N-Gram Lookup (Gemma 3 27B or Gemma 4 31B Instruction-Tuned)**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-27b-it"
    ```

    or:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

  - **Path 2 — EAGLE3 Draft Model (Llama 3.3 70B Instruct FP8 + EAGLE3 Draft
    Head)**:

    Target model (single-GPU FP8):

    ```shell
    export HF_MODEL_ID="nvidia/llama-3.3-70b-instruct-fp8"
    ```

    or standard BF16 target model (4-GPU TP=4):

    ```shell
    export HF_MODEL_ID="meta-llama/llama-3.3-70b-instruct"
    ```

    EAGLE3 draft model (must also be downloaded to Cloud Storage):

    ```shell
    export HF_MODEL_ID="yuhuili/eagle3-llama3.3-instruct-70b"
    ```

  - **Path 3 — Native Multi-Token Prediction (Qwen 3.6 35B-A3B Sparse MoE)**:

    ```shell
    export HF_MODEL_ID="qwen/qwen3.6-35b-a3b"
    ```

> [!TIP] When using **EAGLE3 Based Draft Models**, run the model download steps
> below twice: once for the target model (`nvidia/llama-3.3-70b-instruct-fp8` or
> `meta-llama/llama-3.3-70b-instruct`) and once for the draft model
> (`yuhuili/eagle3-llama3.3-instruct-70b`). For **N-Gram** and **MTP**, only a
> single model download is required because the MTP head is bundled inside the
> `qwen/qwen3.6-35b-a3b` checkpoint.

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

- Ensure `HF_MODEL_ID` is set to your target model (for EAGLE3, set
  `HF_MODEL_ID="nvidia/llama-3.3-70b-instruct-fp8"` or
  `HF_MODEL_ID="meta-llama/llama-3.3-70b-instruct"`) and source the environment
  configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the Speculative Decoding deployment.

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
    > source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
    > ```

  - Select an accelerator.

    | Model (`HF_MODEL_NAME`)      | Speculative Method (`METHOD`) | h100 | rtx-pro-6000 |
    | ---------------------------- | ----------------------------- | ---- | ------------ |
    | `gemma-3-27b-it`             | `ngram`                       | ✅   | ✅           |
    | `gemma-4-31b-it`             | `ngram`                       | ✅   | ✅           |
    | `llama-3-3-70b-instruct`     | `ngram`, `eagle`              | ✅   | ✅           |
    | `llama-3-3-70b-instruct-fp8` | `eagle`                       | ✅   | ✅           |
    | `qwen3-6-35b-a3b`            | `mtp`                         | ✅   | ✅           |

    - **NVIDIA H100 80GB**:

      ```shell
      export ACCELERATOR_TYPE="h100"
      ```

    - **NVIDIA RTX PRO 6000 96GB**:

      ```shell
      export ACCELERATOR_TYPE="rtx-pro-6000"
      ```

    Ensure that you have enough quota in your project to provision the selected
    accelerator type. For more information about viewing GPU quotas, see
    [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

    The Kubernetes manifests invoked below are aligned with the guidance
    provided in
    [Inference Quickstart recommendations](https://cloud.google.com/kubernetes-engine/docs/how-to/machine-learning/inference-quickstart).

### Speculative Decoding with N-gram (`ngram`)

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
  NAME                                         READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-rtx-pro-6000-gemma-3-27b-it-sd-ngram    1/1     1            1           ###
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

- Delete the workload (when finished testing and benchmarking).

  ```shell
  export METHOD=ngram && \
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

### Speculative Decoding with EAGLE3 (`eagle`)

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
  NAME                                                     READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-rtx-pro-6000-llama-3-3-70b-instruct-fp8-sd-eagle    1/1     1            1           ###
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

- Delete the workload (when finished testing and benchmarking).

  ```shell
  export METHOD=eagle && \
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

### Speculative Decoding with Multi-Token Prediction (`mtp`)

> [!NOTE] > `Qwen/Qwen3.6-35B-A3B` is a Hybrid Gated DeltaNet + Sparse
> Mixture-of-Experts (MoE) model with `35B` total parameters (`3B` active per
> token) and a native Multi-Token Prediction (`mtp`) head. The
> `qwen3-6-35b-a3b-sd-mtp` overlay configures
> `--speculative-config={"method": "mtp", "num_speculative_tokens": 2}`
> alongside `--no-async-scheduling` (required for vLLM V1 engine compatibility
> when running MTP speculative decoding on Qwen 3.6).

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
  NAME                                         READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-rtx-pro-6000-qwen3-6-35b-a3b-sd-mtp     1/1     1            1           ###
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

- Delete the workload (when finished testing and benchmarking).

  ```shell
  export METHOD=mtp && \
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-spec-decoding/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  ```

### Performance Optimization: FP8 with TP=1 vs. BF16/FP16 with TP=4

When deploying Llama 3.3 70B on RTX PRO 6000 (96GB) or H100 (80GB) GPUs, the
standard BF16/FP16 model (`meta-llama/llama-3.3-70b-instruct`) requires Tensor
Parallelism (`TP=4` on 80GB GPUs) to fit the ~140GB weights and KV cache. By
using the **FP8 quantized model** (`nvidia/llama-3.3-70b-instruct-fp8`, ~68GB
weights), both the 70B target model and the ~1.9GB EAGLE3 draft head
(`yuhuili/eagle3-llama3.3-instruct-70b`) fit comfortably on a **single GPU
(`TP=1`)** with zero inter-GPU AllReduce communication overhead.

This allows you to deploy **four independent `TP=1` replicas** using the same
4-GPU hardware footprint as a single `TP=4` BF16 deployment, achieving
significantly higher aggregate throughput behind a Kubernetes Service or GKE
Inference Gateway:

```shell
export METHOD=eagle && \
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} scale deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} --replicas=4
```

## Measuring speculative decoding (`ngram` / `eagle` / `mtp`) performance with `inference-perf`

[inference-perf](https://github.com/kubernetes-sigs/inference-perf) allows you
to run load sweeps and simulate production traffic from an external Kubernetes
Job against your vLLM service pods.

Optional — Install the `inference-perf` and `matplotlib` libraries locally to
generate throughput and latency curves from the exported JSON reports:

```shell
pip install inference-perf
pip install matplotlib
```

### Workflow

1. Apply the `inference_perf_bench` Terraform configuration, which provisions:
   - The Cloud Storage bucket for storing `inference-perf` JSON reports
   - The Cloud Storage bucket for custom benchmarking datasets
   - The Kubernetes ServiceAccount and Workload Identity IAM bindings for Google
     Managed Prometheus (GMP) and Cloud Storage
2. Deploy and benchmark the **Speculative Decoding** workload
   (`vllm-spec-decoding/sd-${METHOD}`).
3. Deploy and benchmark the **Baseline (regular vLLM)** workload
   (`online-inference-gpu/vllm`) using the same model, dataset, and API type for
   an apples-to-apples comparison.
4. Inspect vLLM's Prometheus speculative decoding metrics and compare the
   resulting latency/throughput reports.

#### 1. Run the `inference-perf` Terraform

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

#### 2. Benchmark the Speculative Decoding deployment

- Ensure your Speculative Decoding deployment is running and export `METHOD`
  (`ngram`, `eagle`, or `mtp`) and `APP_LABEL`:

  ```shell
  export ACCELERATOR="GPU"
  export APP_LABEL="vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD}"
  echo "APP_LABEL=${APP_LABEL}"
  ```

- Configure the Speculative Decoding benchmarking job:

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-${METHOD}/configure_benchmark.sh"
  ```

  > [!IMPORTANT] > **Choosing the Dataset (`data.type`) and API Endpoint
  > (`api.type`)**:
  >
  > - **N-Gram (`sd-ngram`)**: Defaults to `data.type: cnn_dailymail` and
  >   `api.type: completion` to benchmark grounded summarization where n-gram
  >   prompt lookup excels. To test N-Gram on open-ended conversational prompts
  >   (`shareGPT`), update `configmap-benchmark.yaml` before applying:
  >   ```shell
  >   sed -i 's/type: cnn_dailymail/type: shareGPT/' "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-ngram/configmap-benchmark.yaml"
  >   ```
  > - **EAGLE3 (`sd-eagle`)**: Defaults to `data.type: shareGPT` and
  >   `api.type: chat` (`/v1/chat/completions`). Instruction-tuned EAGLE3 draft
  >   heads (such as `yuhuili/eagle3-llama3.3-instruct-70b`) are trained on
  >   chat-template-formatted hidden states
  >   (`<|begin_of_text|><|start_header_id|>...`). Using `api.type: chat`
  >   preserves the chat template and achieves **~60.8% draft acceptance**,
  >   whereas raw `api.type: completion` bypasses the chat template and reduces
  >   acceptance to **~35.8%**.
  > - **MTP (`sd-mtp`)**: Defaults to `data.type: shareGPT` and
  >   `api.type: completion`.

- Deploy the Speculative Decoding benchmarking job:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-${METHOD}"
  ```

- Watch the benchmarking job until it completes (approximately 8–15 minutes):

  ```shell
  export SHORT_HASH=$(echo -n "${APP_LABEL}" | sha256sum | cut -c1-10)
  watch --color --interval 5 --no-title "
    kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get job/${SHORT_HASH}-inference-perf | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete';
    echo '\nLogs(last 10 lines):';
    kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs job/${SHORT_HASH}-inference-perf --all-containers --tail 10
    "
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                       STATUS     COMPLETIONS   DURATION   AGE
  XXXXXX-inference-perf      Complete   1/1           10m        10m
  ```

- Inspect vLLM's live speculative decoding acceptance rate from Prometheus
  `/metrics`:

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}-sd-${METHOD} 8000:8000 >/dev/null &
  PF_PID=$!
  sleep 2
  curl -s http://127.0.0.1:8000/metrics | grep -E "vllm:spec_decode_num_(draft|accepted)_tokens_total|vllm:spec_decode_num_accepted_tokens_per_pos"
  kill -9 ${PF_PID}
  ```

- Delete the Speculative Decoding benchmarking job:

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-${METHOD}"
  ```

#### 3. Run a side-by-side Baseline (`vllm`) comparison

To compare Speculative Decoding against a standard auto-regressive vLLM
deployment on identical hardware and load stages:

- Deploy the matching baseline vLLM workload (either after deleting the
  Speculative Decoding workload or in parallel if your project has sufficient
  GPU quota):

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/configure_vllm.sh"
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Wait for `deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}` to become
  `1/1` Ready, then configure the baseline `inference-perf` job:

  ```shell
  export ACCELERATOR="GPU"
  export APP_LABEL="vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configure_benchmark.sh"
  ```

- Ensure the baseline `configmap-benchmark.yaml` uses the same `data.type`
  (`cnn_dailymail` or `shareGPT`) and `api.type` (`completion` or `chat`) as
  your Speculative Decoding run:

  - When comparing against **N-Gram on `cnn_dailymail`**:
    ```shell
    sed -i 's/type: shareGPT/type: cnn_dailymail/' "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configmap-benchmark.yaml"
    ```
  - When comparing against **EAGLE3 with `api.type: chat`**:
    ```shell
    sed -i 's/type: completion/type: chat/' "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configmap-benchmark.yaml"
    ```

- Deploy and watch the baseline benchmarking job:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm"
  export SHORT_HASH=$(echo -n "${APP_LABEL}" | sha256sum | cut -c1-10)
  watch --color --interval 5 --no-title "
    kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get job/${SHORT_HASH}-inference-perf | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete';
    echo '\nLogs(last 10 lines):';
    kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs job/${SHORT_HASH}-inference-perf --all-containers --tail 10
    "
  ```

- Delete the baseline benchmarking job and workload when complete:

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm"
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

#### 4. Analyze and Interpret Results

The output reports (`summary_lifecycle_metrics.json` and
`stage_N_lifecycle_metrics.json`) are uploaded to the benchmarking results Cloud
Storage bucket. Download the reports and run `inference-perf --analyze` to plot
throughput and latency curves:

```shell
gcloud storage cp -r gs://${hub_models_bucket_bench_results_name}/ .
inference-perf --analyze ${hub_models_bucket_bench_results_name}/*
```

### Reference Benchmark Results & Architecture Decision Guide

The table below summarizes reference benchmark measurements collected on GKE
using a single **NVIDIA RTX PRO 6000 Server Edition GPU (96GB VRAM, `TP=1`)**
comparing Speculative Decoding against a standard vLLM baseline across a 7-stage
load sweep (`QPS 1.0` to `2.0`):

| Speculative Paradigm                                 | Target Model (+ Draft)                                                       | Dataset & API Endpoint         | Draft Acceptance ($\alpha$)                | Mean Tokens / Step | Peak Output Throughput (SpecDec vs. Baseline) | Mean TPOT at Low/Med Load (SpecDec vs. Baseline)             | Key Takeaway                                                                                                                                                                                                |
| :--------------------------------------------------- | :--------------------------------------------------------------------------- | :----------------------------- | :----------------------------------------- | :----------------- | :-------------------------------------------- | :----------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1. N-Gram Lookup** (`method="ngram"`, $k=5$)       | `google/gemma-3-27b-it`                                                      | `cnn_dailymail` (`completion`) | **13.8%**                                  | **1.69**           | **736 vs. 534 tok/s (+37.9%)**                | **15.8 vs. 19.6 ms (-19.4%)**                                | Zero extra VRAM; large gains when outputs reuse spans from the input prompt.                                                                                                                                |
| **1. N-Gram Lookup** (`method="ngram"`, $k=5$)       | `google/gemma-3-27b-it`                                                      | `shareGPT` (`completion`)      | **5.5%**                                   | **1.28**           | **304 vs. 308 tok/s (-1.2%)**                 | **16.5 vs. 15.4 ms (+7.1%)**                                 | Open-ended chat rarely repeats prompt 4-grams; verification cost slightly exceeds draft hits.                                                                                                               |
| **2. EAGLE3 Draft Head** (`method="eagle3"`, $k=3$)  | `nvidia/llama-3.3-70b-instruct-fp8` + `yuhuili/eagle3-llama3.3-instruct-70b` | `shareGPT` (`chat`)            | **60.8%** (Pos 0: `82.6%`)                 | **2.82**           | **237 vs. 180 tok/s (+31.7%)**                | **25.9 vs. 33.4 ms (-22.6%)** (up to **-32%** at saturation) | Heavy 70B target model stays memory-bandwidth-bound across the sweep; EAGLE3 wins at every QPS stage.                                                                                                       |
| **2. EAGLE3 Draft Head** (`method="eagle3"`, $k=3$)  | `nvidia/llama-3.3-70b-instruct-fp8` + `yuhuili/eagle3-llama3.3-instruct-70b` | `shareGPT` (`completion`)      | **35.8%** (Pos 0: `58.9%`)                 | **2.07**           | **202 vs. 199 tok/s (+1.7%)**                 | **26.7 vs. 27.6 ms (-3.5%)**                                 | Raw completion prompts omit the Llama 3.3 Instruct chat template, lowering draft acceptance by 25 percentage points.                                                                                        |
| **3. Native Co-Trained MTP** (`method="mtp"`, $k=2$) | `qwen/qwen3.6-35b-a3b` (Sparse MoE: `35B` total, `3B` active)                | `shareGPT` (`completion`)      | **82.3%** (Pos 0: `89.3%`, Pos 1: `75.2%`) | **2.65**           | **308 vs. 243 tok/s (+26.4%)** at QPS 1.0–1.5 | **8.4 vs. 10.6 ms (-21.1%)** at QPS 1.0                      | Highest acceptance rate with zero external draft model; excels at low-to-medium concurrency before crossing over at high batch concurrency (`QPS >= 1.66`) where the `3B`-active MoE becomes compute-bound. |

#### Choosing the Right Speculative Decoding Method

- **Use N-Gram (`method="ngram"`)** for document summarization, RAG, information
  extraction, or code-editing pipelines where generated responses frequently
  copy entities or code spans from the prompt, or when GPU memory is near
  capacity and cannot fit an external draft model.
- **Use EAGLE3 (`method="eagle3"`)** for large dense models (such as 70B+
  models) serving open-ended chat or reasoning traffic. Always ensure requests
  use the model's instruction chat template (`/v1/chat/completions`) so hidden
  states align with the EAGLE3 draft head's training distribution.
- **Use Native MTP (`method="mtp"`)** when deploying foundation models with
  built-in co-trained MTP heads (such as `Qwen3.6-35B-A3B`) for interactive,
  low-latency serving (`TPOT < 15 ms`). For high-concurrency batch saturation on
  sparse MoE models (`3B` active parameters), monitor TPOT across load stages to
  determine the concurrency crossover point.

## Troubleshooting

If you experience any issue while deploying the workload, see the
[Online inference with GPUs Troubleshooting](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/troubleshooting.md)
guide.

## Clean up

- Destroy the `inference-perf` benchmarking resources (if deployed).

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform destroy -auto-approve
  ```

- Destroy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform destroy -auto-approve
  ```
