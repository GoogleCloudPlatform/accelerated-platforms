# Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on Google Kubernetes Engine (GKE)

This document implements online inference using GPUs on Google Kubernetes Engine
(GKE) with
[NVIDIA Run:ai Model Streamer](https://github.com/run-ai/runai-model-streamer),
which streams model weights directly from Cloud Storage into GPU memory.

In a conventional deployment, weights travel from object storage across the
network, onto the host filesystem, through the Linux page cache into CPU RAM,
and only then across PCIe into GPU memory. This serializes tensor reads,
allocates the model twice, and requires the node to carry enough local storage
to stage the entire model. The Run:ai Model Streamer collapses that into a
single streaming operation, which both shortens the cold start and removes the
staging disk requirement.

| Model, GPU                            | Weights   | Load time  | Throughput  |
| ------------------------------------- | --------- | ---------- | ----------- |
| Gemma 4 31B, NVIDIA H100 80GB         | 58.99 GiB | **48.2 s** | ~1.22 GiB/s |
| Llama 3.1 8B, NVIDIA H100 80GB        | 14.99 GiB | **15.0 s** | ~1.00 GiB/s |
| Llama 3.1 8B, H100, default load path | 14.99 GiB | 50.6 s     | ~0.30 GiB/s |

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).
For the architecture and design rationale, see the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the model.

  - Accept the terms of the license on the Hugging Face model page.
    - [**google/gemma-4-31b-it**](https://huggingface.co/google/gemma-4-31b-it)
    - [**google/gemma-3-27b-it**](https://huggingface.co/google/gemma-3-27b-it)
    - [**Qwen/Qwen3.5-35B-A3B**](https://huggingface.co/Qwen/Qwen3.5-35B-A3B)

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

> [!NOTE]
>
> The model bucket is created with
> [hierarchical namespace](https://cloud.google.com/storage/docs/hns-overview)
> enabled. This gives the bucket a real directory structure rather than a flat
> keyspace, which makes the many-object listing and prefix reads that the
> streamer performs during load significantly faster. See
> [`storage.tf`](/platforms/gke/base/core/huggingface/initialize/storage.tf).

## Download the model to Cloud Storage

- Choose the model.

  - **Gemma 4 31B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

  - **Gemma 3 27B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-27b-it"
    ```

  - **Qwen3.5 35B A3B**:

    ```shell
    export HF_MODEL_ID="Qwen/Qwen3.5-35B-A3B"
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

## Deploy the inference workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh"
  ```

- Select a variant.

  | Model           | h100 | rtx-pro-6000 |
  | --------------- | ---- | ------------ |
  | gemma-3-27b-it  |      | ✅           |
  | gemma-4-31b-it  | ✅   | ✅           |
  | qwen3.5-35b-a3b |      | ✅           |

  - **Gemma 4 31B on NVIDIA H100 80GB**:

    ```shell
    export VLLM_VARIANT="h100-gemma-4-31b-it"
    ```

  - **Gemma 4 31B on NVIDIA RTX Pro 6000 96GB**:

    ```shell
    export VLLM_VARIANT="rtx-pro-6000-gemma-4-31b-it"
    ```

  - **Gemma 3 27B on NVIDIA RTX Pro 6000 96GB**:

    ```shell
    export VLLM_VARIANT="rtx-pro-6000-gemma-3-27b-it"
    ```

  - **Qwen3.5 35B A3B on NVIDIA RTX Pro 6000 96GB**:

    ```shell
    export VLLM_VARIANT="rtx-pro-6000-qwen3-5-35b-a3b"
    ```

  Ensure that you have enough quota in your project to provision the selected
  accelerator type. For more information about viewing GPU quotas, see
  [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${VLLM_VARIANT}"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${VLLM_VARIANT} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${VLLM_VARIANT} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see output similar to the following:

  ```text
  NAME                             READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-h100-gemma-4-31b-it         1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Confirm the streamer was used.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs \
  deployment/vllm-${VLLM_VARIANT} | grep "Model loading took"
  ```

  ```text
  Model loading took 58.9905 GiB and 48.164635 seconds
  ```

## Send a test request to the model

- Start a port forward to the model service.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward \
  service/vllm-${VLLM_VARIANT} 8000:8000 >/dev/null & \
  PF_PID=$!
  ```

- Send a test request.

  ```shell
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "'${HF_MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  ```

- Stop the port forward.

  ```shell
  kill -9 ${PF_PID}
  ```

## Autoscale on inference metrics

CPU and memory utilization are poor scaling signals for inference, because a
vLLM engine saturates both during normal continuous batching even when serving a
single request. The deployment therefore includes a `HorizontalPodAutoscaler`
that scales on queue depth reported by the GKE Inference Gateway Endpoint
Picker.

- Review the autoscaling configuration.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get hpa/vllm-${VLLM_VARIANT} \
  --output=yaml | grep --after-context=8 "metrics:"
  ```

  ```text
  metrics:
    - type: Pods
      pods:
        metric:
          name: prometheus.googleapis.com|igw_queue_depth|gauge
        target:
          type: AverageValue
          averageValue: 1
  ```

  `igw_queue_depth` counts requests buffered at the gateway before dispatch.
  Because it is observed at ingress rather than inside the engine, it rises the
  moment demand exceeds the capacity currently deployed. The deployment scales
  between 1 and 5 replicas.

- Watch the autoscaler react to load.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get hpa/vllm-${VLLM_VARIANT}"
  ```

  You can press `CTRL`+`c` to terminate the watch.

For a full load-testing workflow, see
[Benchmarking with inference-perf](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/inf-perf-benchmarking-with-hf-model.md).

## Troubleshooting

If you experience any issue while deploying the workload, see the
[Online inference with GPUs Troubleshooting](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/troubleshooting.md)
guide.

### The model loads slowly, or the node runs out of disk

Confirm the deployment is actually reading from Cloud Storage over `gs://`
rather than a mounted filesystem. The streamer path requires both a `gs://`
model argument and the `runai_streamer` load format:

```shell
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get \
deployment/vllm-${VLLM_VARIANT} \
--output=jsonpath='{.spec.template.spec.containers[0].args}' | tr ',' '\n' | grep -e model -e load-format
```

```text
--model=gs://<bucket>/<model-id>
--load-format=runai_streamer
```

If the model argument points at a local path, the pod is staging weights to disk
and none of the measurements above apply.

### Permission denied reading the model bucket

The deployment reads the bucket through Workload Identity Federation rather than
with a key. Confirm the Kubernetes service account is annotated and that the
bucket grants it object read access:

```shell
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get serviceaccount \
--output=jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.metadata.annotations}{"\n"}{end}'
```

## Clean up

- Delete the inference workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${VLLM_VARIANT}"
  ```

- Destroy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
