# Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on Google Kubernetes Engine (GKE)

This document implements online inference using GPUs on Google Kubernetes Engine
(GKE) with
[NVIDIA Run:ai Model Streamer](https://github.com/dsx-ai-factory/model-streamer),
which streams model weights directly from Cloud Storage into GPU memory.

In a conventional deployment, weights travel from object storage across the
network, onto the host filesystem, through the Linux page cache into CPU RAM,
and only then across PCIe into GPU memory. This serializes tensor reads,
allocates the model twice, and requires the node to carry enough local storage
or memory to stage the entire model. The Run:ai Model Streamer reads tensors
from Cloud Storage concurrently and streams them into GPU memory, so the weight
files are never staged on the node.

The following results were measured with the manifests in this guide, vLLM
v0.26.0, and a model bucket in the same region as the cluster (`europe-west4`).
_Weight load time_ is the time that vLLM reports for loading the weights.
_Container start to ready_ also includes vLLM start-up, `torch.compile`, CUDA
graph capture, and warm-up. Results depend on the region, the machine type, and
the location of the bucket.

| Model, GPU                                | Weights in GPU memory | Weight load time | Container start to ready |
| ----------------------------------------- | --------------------- | ---------------- | ------------------------ |
| Gemma 4 31B, NVIDIA H100 80GB             | 58.99 GiB             | 27.0 s           | 4 min 48 s               |
| Gemma 4 31B, NVIDIA RTX PRO 6000 96GB     | 58.99 GiB             | 19.2 s           | 2 min 46 s               |
| Gemma 3 27B, NVIDIA RTX PRO 6000 96GB     | 51.54 GiB             | 11.6 s           | 2 min 50 s               |
| Qwen3.5 35B A3B, NVIDIA RTX PRO 6000 96GB | 65.53 GiB             | 11.5 s           | 3 min 36 s               |

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).
For the architecture and design rationale, see the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the models.

  - For Gemma 3, accept the terms of the license on the Hugging Face model page.
    - [**google/gemma-3-27b-it**](https://huggingface.co/google/gemma-3-27b-it)

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
> enabled, which offers higher initial request rate limits for reading and
> writing objects than a bucket without hierarchical namespace. See
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
    export HF_MODEL_ID="qwen/qwen3.5-35b-a3b"
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

    | Model           | h100 | rtx-pro-6000 |
    | --------------- | ---- | ------------ |
    | gemma-3-27b-it  | ❌   | ✅           |
    | gemma-4-31b-it  | ✅   | ✅           |
    | qwen3-5-35b-a3b | ❌   | ✅           |
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

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see the following:

  ```text
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-<ACCELERATOR_TYPE>-<HF_MODEL_NAME>   1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Confirm that the weights were loaded with the Run:ai Model Streamer.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs \
  deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | \
  grep -e "Runai Model Streamer: 100%" -e "Model loading took"
  ```

  The output is similar to the following:

  ```text
  Loading safetensors using Runai Model Streamer: 100% Completed | 1188/1188 [00:24<00:00, 48.49it/s]
  (EngineCore pid=126) INFO 09-25 16:08:23 [model_runner.py:305] Model loading took 58.99 GiB and 27.027104 seconds
  ```

## Send a test request to the model

- Start a port forward to the model service.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward \
  service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null & \
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
that scales on `vllm:num_requests_waiting`, the number of requests that are
waiting in the vLLM scheduler queue. GKE automatic application monitoring
collects the metric with Google Cloud Managed Service for Prometheus, and the
Custom Metrics Stackdriver Adapter makes it available to the autoscaler.

- Review the autoscaling configuration.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get hpa/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} \
  --output=yaml | grep --after-context=7 "  metrics:"
  ```

  ```text
    metrics:
    - pods:
        metric:
          name: prometheus.googleapis.com|vllm:num_requests_waiting|gauge
        target:
          averageValue: "5"
          type: AverageValue
      type: Pods
  ```

  The deployment scales between 1 and 5 replicas. It adds replicas when more
  than 5 requests per replica are waiting on average, and it removes replicas
  only after the number of waiting requests has stayed below the target for 5
  minutes.

- Watch the autoscaler react to load.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get hpa/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

  You can press `CTRL`+`c` to terminate the watch.

  Until the first replica is serving and its metrics have been collected, the
  `TARGETS` column shows `<unknown>/5`.

For a full load-testing workflow, see
[Benchmarking with inference-perf](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/inf-perf-benchmarking-with-hf-model.md).

### What a scale-out benchmark requires

To trigger a scale-out onto a new GPU node and observe the Run:ai Model Streamer
speedup, a benchmark must account for how vLLM schedules requests and how GKE
provisions GPU capacity:

- **Saturate the replica's running batch so requests enter the waiting queue**:
  vLLM admits incoming requests immediately into the active batch
  (`vllm:num_requests_running`) until either GPU KV cache blocks are full or
  `--max-num-seqs` is reached. A request only increments
  `vllm:num_requests_waiting` when it cannot fit into the active batch:
  - **Gemma 4 31B (`h100` or `rtx-pro-6000`) and Gemma 3 27B (`rtx-pro-6000`)**:
    With `12,114` KV cache tokens on H100 (`18,348` on RTX PRO 6000 for Gemma 4
    31B; `99,070` for Gemma 3 27B), sending 24–32 concurrent requests with long
    outputs (`"max_tokens": 1500` and `"ignore_eos": true`) fills the first
    replica's KV cache so that 10 or more requests wait in the scheduler queue
    and exceed the HPA target (`5`).
  - **Qwen3.5 35B A3B (`rtx-pro-6000`)**: Because the hybrid linear-attention
    (Mamba) and sparse KV architecture allocates `220,013` KV cache tokens and
    sets `--max-num-seqs=256`, a single replica can hold up to 256 concurrent
    sequences in the running batch before queuing. To trigger scale-out, either
    drive more than 260 concurrent requests or lower `--max-num-seqs` (for
    example, to `--max-num-seqs=16`) in
    [`patch-vllm-args.yaml`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/rtx-pro-6000-qwen3-5-35b-a3b/patch-vllm-args.yaml).
- **Send traffic from inside the cluster to the Kubernetes `Service`**:
  `kubectl port-forward` binds to a single Pod when started and does not
  distribute requests to new replicas as they become ready. Run the load
  generator inside the cluster against
  `http://vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}.${ira_online_gpu_kubernetes_namespace_name}.svc.cluster.local:8000`
  so new requests are load-balanced across all `Ready` pods.
- **Sustain load for at least 6 to 8 minutes**: Scaling onto a new node requires
  GKE Node Auto-Provisioning to allocate and boot the GPU VM (~60–90 s), stream
  the container image (~30–60 s), stream the model weights from Cloud Storage
  into GPU memory with the Run:ai Model Streamer (`11.5–27.0 s`), and complete
  `torch.compile`, CUDA graph capture, and warm-up (`2 min 46 s` to `4 min 48 s`
  from container start to `Ready`).
  - When using
    [`inference-perf`](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/inf-perf-benchmarking-with-hf-model.md),
    edit `configmap-benchmark.yaml` after running `configure_benchmark.sh` to
    set `server.model_name` to `${HF_MODEL_ID}` (without the `/gcs/` prefix used
    by Cloud Storage FUSE deployments) and increase `load.sweep.stage_duration`
    from `30` to `180` or `300` seconds so the high-concurrency stages sustain
    load while the new node comes online.

### Replicate a scale-out onto a new GPU node

You can trigger and observe a scale-out onto a new GPU node directly without
deploying the full `inference-perf` stack:

- Start an in-cluster load generator `Job` that sends concurrent long-generation
  requests to the Service for 8 minutes.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} apply -f - <<EOF
  apiVersion: batch/v1
  kind: Job
  metadata:
    name: vllm-scaleout-load
  spec:
    backoffLimit: 4
    template:
      spec:
        restartPolicy: OnFailure
        containers:
          - name: load
            image: curlimages/curl:8.10.1
            resources:
              requests:
                cpu: "1"
                memory: "1Gi"
            env:
              - name: WORKERS
                value: "24"
              - name: DURATION_SECONDS
                value: "480"
            command: ["/bin/sh", "-c"]
            args:
              - |
                URL="http://vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}.${ira_online_gpu_kubernetes_namespace_name}.svc.cluster.local:8000/v1/completions"
                END=\$(( \$(date +%s) + \${DURATION_SECONDS} ))
                worker() {
                  while [ "\$(date +%s)" -lt "\${END}" ]; do
                    curl -s -o /dev/null "${URL}" \
                      -H "Content-Type: application/json" \
                      -d '{"model":"${HF_MODEL_ID}","prompt":"Write a detailed history of distributed computing.","max_tokens":1500,"ignore_eos":true}'
                  done
                }
                i=0
                while [ "\${i}" -lt "\${WORKERS}" ]; do
                  worker &
                  i=\$((i + 1))
                done
                wait
  EOF
  ```

- Watch the autoscaler and pods as GKE provisions new GPU nodes and starts
  additional replicas.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get hpa/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}
  echo ''
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pods -l app=vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} -o wide"
  ```

  Within 30–60 seconds, `TARGETS` rises above `5/5` (for example, `13/5`) and
  `REPLICAS` increases. New pods remain `Pending` while GKE provisions GPU
  nodes, then transition to `Running` and `1/1 Ready`. You can press `CTRL`+`c`
  to terminate the watch.

- Confirm that the scaled-out replica on the new node streamed the model weights
  from Cloud Storage with the Run:ai Model Streamer.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs \
  --selector=app=vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} \
  --prefix=true | \
  grep -e "Runai Model Streamer: 100%" -e "Model loading took"
  ```

  Each replica reports its own streaming throughput and weight load time (for
  example, `27.66 seconds` for 58.99 GiB on a newly provisioned H100 node):

  ```text
  [pod/vllm-h100-gemma-4-31b-it-595fcb9f4-hq6jp/inference-server] Loading safetensors using Runai Model Streamer: 100% Completed | 1188/1188 [00:24<00:00, 48.49it/s]
  [pod/vllm-h100-gemma-4-31b-it-595fcb9f4-hq6jp/inference-server] (EngineCore pid=126) INFO 09-25 16:08:23 [model_runner.py:305] Model loading took 58.99 GiB and 27.027104 seconds
  [pod/vllm-h100-gemma-4-31b-it-595fcb9f4-dw6vg/inference-server] Loading safetensors using Runai Model Streamer: 100% Completed | 1188/1188 [00:24<00:00, 47.65it/s]
  [pod/vllm-h100-gemma-4-31b-it-595fcb9f4-dw6vg/inference-server] (EngineCore pid=126) INFO 09-25 16:20:10 [model_runner.py:305] Model loading took 58.99 GiB and 27.655491 seconds
  ```

- Delete the load generator `Job`.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} delete job/vllm-scaleout-load --ignore-not-found
  ```

  After the waiting queue stays at `0` for the 5-minute stabilization window,
  the `HorizontalPodAutoscaler` scales the deployment back down to `1` replica.

## Clean up

- Delete the inference workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Destroy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
