# Online inference using vLLM Native KV Cache Offloading on GPUs on Google Kubernetes Engine (GKE)

This example implements online inference using vLLM's native KV Cache Offloading
(single-tier, CPU offloading) on GPUs on Google Kubernetes Engine (GKE).

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## About Native KV Cache Offloading

As LLM context windows expand and multi-turn conversations or agentic loops
scale, GPU High Bandwidth Memory (HBM) quickly becomes a primary bottleneck. KV
Cache Offloading solves this by seamlessly moving inactive or historical
Key-Value caches from GPU VRAM down to host CPU RAM (system memory) using
asynchronous CUDA DMA transfers on NVIDIA GPUs.

vLLM provides a built-in, lightweight Native Offloading Connector (v0.11.0+)
that requires zero external dependencies, making it simple to configure
out-of-the-box.

### Core Architecture & Prerequisites

- **Engine Compatibility**: Native offloading is built into vLLM v0.11.0+.
- **Hardware Support**: As per
  [vLLM official guide](https://docs.vllm.ai/en/stable/features/kv_offloading_usage/),
  the OffloadingConnector currently supports CUDA, ROCm, and XPU only.
- **Single-Tier Rule**: For single-tier (CPU-only) offloading, your CPU buffer
  must be substantially larger than the aggregate GPU/TPU KV cache pool. If the
  CPU buffer is smaller than or equal to what the accelerator holds, it simply
  mirrors active memory and provides a 0% cache hit rate.

### Mathematical Sizing Formula & Model Calculations

To compute the memory required to store the KV cache for a given sequence
length, use the fundamental attention tensor formula:

$$\text{Bytes per Token} = 2 \times \text{num layers} \times (\text{num KV heads} \times \text{head dim}) \times \text{bytes per element}$$

When serving standard, unquantized Hugging Face checkpoints, vLLM defaults to
native BF16 precision (`bytes_per_element = 2`).

#### Model Bytes per Token Calculations

- **Qwen3-32B (GQA)**: 64 layers, 8 KV heads × 128 head dim = 1,024 KV dim.
  $$2 \times 64 \times 1,024 \times 2 = 262,144 \text{ bytes / token} \approx 262.14 \text{ KB / token} \approx 24.414 \text{ GiB per 100k tokens}$$
- **Gemma 4-31B-IT (Method 1 Uniform Standard / Capacity Planning Upper
  Bound)**: 60 layers, 16 KV heads × 256 head dim = 4,096 KV dim.
  $$2 \times 60 \times 4,096 \times 2 = 983,040 \text{ bytes / token} \approx 983.04 \text{ KB / token} \approx 91.553 \text{ GiB per 100k tokens}$$
- **Gemma 4-31B-IT (Method 2 Hybrid Exact Sum across 50 Local + 10 Global
  Layers)**:
  - 50 Local Layers (16 KV heads × 256 head dim = 4,096 dim):
    $2 \times 50 \times 4,096 \times 2 = 819,200 \text{ bytes}$
  - 10 Global Layers (4 KV heads × 512 head dim = 2,048 dim):
    $2 \times 10 \times 2,048 \times 2 = 81,920 \text{ bytes}$
  - **Total Exact Bytes / Token** =
    $819,200 + 81,920 = 901,120 \text{ bytes / token} \approx 901.12 \text{ KB / token} \approx 83.923 \text{ GiB per 100k tokens}$

#### Required Offload Memory by Token Count

| Token Count                  | Qwen3-32B (BF16) | Gemma 4-31B-IT (BF16) [Method 1 - Standard] | Gemma 4-31B-IT (BF16) [Method 2 - Hybrid] |
| :--------------------------- | :--------------- | :------------------------------------------ | :---------------------------------------- |
| **100,000 Tokens (100k)**    | 24.414 GiB       | 91.553 GiB                                  | 83.923 GiB                                |
| **1,000,000 Tokens (1 Mil)** | 244.141 GiB      | 915.527 GiB                                 | 839.227 GiB                               |

### Safety Headroom Rule for CPU Offload Pools

When choosing the maximum value for `--kv-offloading-size`, never allocate 100%
of host CPU system DRAM. Pinned memory (`cudaHostAlloc`) cannot be paged to
disk. Allocating total physical DRAM will starve the Linux kernel and vLLM
worker threads, triggering the Linux Out-Of-Memory (OOM) Killer.

$$\text{Maximum Safe kv cache offloading-size} = \text{Total System RAM (GiB)} - \text{Mandatory Safety Headroom (GiB)}$$

**The following is just an estimate**:

- **Single-GPU CUDA Nodes (H100 / RTX 6000)**: Reserve at least **32 GiB** for
  OS operations, CUDA Graphs, and vLLM Python runtime.
- **Multi-Chip TPU Topologies (tpu-v6e-2x2)**: Reserve at least **48 GiB** due
  to host-side PyTorch-XLA compilation buffers and 4-worker thread management.

### Hardware & Offloading Reference Matrix

The following table is considering that the model inference will run on a single
accelerator chip.

| Model              | Machine Type                     | GPU / Accelerator Memory (per chip) | CPU System Memory (Host) | Model Weight Size (BF16) | Offload Space Needed (100k Tokens) [Method 1] | Absolute Max Safe Offload Size (`--kv-offloading-size`) | Maximum Offloading Token Capacity (Max Safe Pool)                 |
| :----------------- | :------------------------------- | :---------------------------------- | :----------------------- | :----------------------- | :-------------------------------------------- | :------------------------------------------------------ | :---------------------------------------------------------------- |
| **Qwen3-32B**      | g4-standard-48 (1x RTX PRO 6000) | 96 GB VRAM                          | 180 GiB DRAM             | ~60 GiB                  | 24.41 GiB                                     | **148 GiB** (180 GiB − 32 GiB Headroom)                 | **606,208 Tokens** (~606.2k tokens)                               |
| **Qwen3-32B**      | a3-highgpu-1g (1x NVIDIA H100)   | 80 GB VRAM                          | 234 GiB DRAM             | ~60 GiB                  | 24.41 GiB                                     | **202 GiB** (234 GiB − 32 GiB Headroom)                 | **827,392 Tokens** (~827.4k tokens)                               |
| **Gemma 4-31B-IT** | g4-standard-48 (1x RTX PRO 6000) | 96 GB VRAM                          | 180 GiB DRAM             | ~61 GiB                  | 91.55 GiB                                     | **148 GiB** (180 GiB − 32 GiB Headroom)                 | **161,655 Tokens (M1) / 176,351 Tokens (M2)** (~161.7k / ~176.4k) |
| **Gemma 4-31B-IT** | a3-highgpu-1g (1x NVIDIA H100)   | 80 GB VRAM                          | 234 GiB DRAM             | ~61 GiB                  | 91.55 GiB                                     | **202 GiB** (234 GiB − 32 GiB Headroom)                 | **220,637 Tokens (M1) / 240,695 Tokens (M2)** (~220.6k / ~240.7k) |

So theoretically , it means that :

- For Qwen3-32b we should be able to offload ~148 GiB on rtx-pro-6000 and ~202
  GiB on H100 that amounts to ~606K and ~827K tokens respectively given that the
  size of a token of Qwen3-32b is ~262 KB / token as calculated above.
- For Gemma-4-31-b, we should be able to offload ~148 GiB on rtx-pro-6000 and
  ~202 GiB on H100 that amounts to ~161/~176 and ~220/~240 tokens respectively
  given that the size of a token of Gemma-4-31-b is ~983 KB / token as
  calculated above.

However, when we try to offload these sizes to CPU memory on the respective
hosts, vLLM fails to start up due to memory issues. So, we started reducing the
offloading size in increments of 10GiB and found that the safest maximum safe
offloading size comes out to be:

Note: The Actual Maximum Offloading Token Capacity (Max Safe Pool) column shows
an estimate not the real numbers.

| Model              | Machine Type                     | Actual memory that can be offloaded | Actual Maximum Offloading Token Capacity (Max Safe Pool) |
| :----------------- | :------------------------------- | :---------------------------------- | :------------------------------------------------------- |
| **Qwen3-32B**      | g4-standard-48 (1x RTX PRO 6000) | 120 GiB                             | ~491K tokens                                             |
| **Qwen3-32B**      | a3-highgpu-1g (1x NVIDIA H100)   | 120 GiB                             | ~491K tokens                                             |
| **Gemma 4-31B-IT** | g4-standard-48 (1x RTX PRO 6000) | 80 GiB                              | ~87K/95K tokens                                          |
| **Gemma 4-31B-IT** | a3-highgpu-1g (1x NVIDIA H100)   | 160 GiB                             | ~174K/190K tokens                                        |

So, you will see that the KV Cache offloading configurations for
[qwen3 on rtx-pro-600](../../../../../../../platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/rtx-pro-6000-qwen3-32b/runtime.env)
,
[gemma-4 on rtx-pro-600](../../../../../../../platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/rtx-pro-6000-gemma-4-31b-it/runtime.env),
[qwen3 on h100](../../../../../../../platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/h100-qwen3-32b/runtime.env)
and
[gemma-4 on h100](../../../../../../../platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/h100-gemma-4-31b-it/runtime.env)
provided with this reference architecture have `cpu_bytes_to_use` set defined.
You can further tune these values if required and validate the results.

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the models.

  - For Gemma:
    - Consented to the license on [Kaggle](https://www.kaggle.com/) using a
      Hugging Face account.
      - [**google/gemma**](https://www.kaggle.com/models/google/gemma).

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the model to Cloud Storage

- Choose the model.

  - **Gemma 4 31B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

  - **Qwen3-32B**:

    ```shell
    export HF_MODEL_ID="qwen/qwen3-32b"
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

  When the job is complete, you will see the status as `Complete`.

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
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/configure_vllm.sh"
  ```

- Set the environment variables for the workload.

  - Check the model name.

    ```shell
    echo "HF_MODEL_NAME=${HF_MODEL_NAME}"
    ```

  - Select an accelerator.

    - **NVIDIA H100 80GB**:

      ```shell
      export ACCELERATOR_TYPE="h100"
      ```

    - **NVIDIA RTX PRO 6000 96GB**:

      ```shell
      export ACCELERATOR_TYPE="rtx-pro-6000"
      ```

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see the status as `1/1` ready.

- Send a test request.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null &
  PF_PID=$!
  while ! echo -e '\x1dclose\x0d' | telnet localhost 8000 >/dev/null 2>&1; do
    sleep 0.1
  done
  echo "/v1/models:"
  curl --request GET --show-error --silent http://127.0.0.1:8000/v1/models | jq
  sleep 1
  echo "/v1/chat/completions:"
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "'${HF_MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-native-cache-offloading/single-tier/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

## Troubleshooting

If you experience any issue while deploying the workload, see the
[Online inference with GPUs Troubleshooting](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/troubleshooting.md)
guide.

## Clean up

- Destroy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform destroy -auto-approve
  ```
