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
v0.26.0, GKE Autopilot, and a model bucket in the same region as the cluster
(`europe-west4`). Each load ran on a newly provisioned node.

- _Weight load time_ is the time that vLLM reports for loading the weights
  (`Model loading took`), as the median and range of `n` loads.
- _Scale-up to first response_ is the time from scaling the deployment from 0 to
  1 replica until the new replica answered its first request, as the range of
  `n` scale-ups. It includes GPU node provisioning, vLLM start-up, weight
  loading, `torch.compile`, CUDA graph capture, and warm-up.

| Model, GPU                                | Weights in GPU memory | Weight load time, median (range) | Scale-up to first response |
| ----------------------------------------- | --------------------- | -------------------------------- | -------------------------- |
| Gemma 4 31B, NVIDIA H100 80GB             | 58.99 GiB             | 20.1 s (19.0–27.8 s), n=5        | 6.9–7.4 min, n=2           |
| Gemma 4 31B, NVIDIA RTX PRO 6000 96GB     | 58.99 GiB             | 11.1 s (10.6–16.5 s), n=4        | 4.3 min, n=1               |
| Gemma 3 27B, NVIDIA RTX PRO 6000 96GB     | 51.54 GiB             | 9.1 s (8.2–16.2 s), n=3          | 4.6 min, n=1               |
| Qwen3.5 35B A3B, NVIDIA RTX PRO 6000 96GB | 65.53 GiB             | 15.2 s (12.6–22.2 s), n=6        | 5.5–6.4 min, n=4           |

Keep the following in mind when you compare your results:

- The weight load time varied by up to 2× between runs. Besides the downloaded
  model, we loaded copies of the model files that we wrote to new paths in the
  same bucket. For most of these sets of files, the first one or two loads after
  the files were written were the slowest, and later loads were faster, on new
  nodes as well as on reused nodes. One copy loaded quickly on its first load.
  Compare the median of several loads rather than a single load.
- Weight loading is a small part of the time to serve, about 4–6% of the
  scale-up to first response. Most of the time is spent provisioning the GPU
  node (1–3 minutes), starting vLLM before the weights load (1–1.5 minutes), and
  running `torch.compile`, CUDA graph capture, and warm-up after the weights
  load (1.3–2.7 minutes).
- Several replicas that load the same model at the same time can each load more
  slowly. On 2026-10-02, on reused nodes in one zone, each of 2 replicas that
  loaded Qwen3.5 35B A3B at the same time took 10.1–10.5 seconds, and each of 6
  replicas took 13.2–16.8 seconds (3 tests each). In an earlier single test, 2
  concurrent loads each took about twice as long as a single load. With
  [Rapid Cache](#optional-cache-the-model-with-rapid-cache), each of 6
  concurrent loads took 10.5–12.5 seconds.
- The first request to a new Qwen3.5 35B A3B replica took about 22 seconds, and
  the pod became `Ready` before that request finished. The same short request
  took less than a second after that.
- The results were measured on 2026-10-01. Every GPU node was a Spot
  `a3-highgpu-1g` or `g4-standard-48` node, because the compute classes fell
  back to their last priority rule, which uses Spot capacity. Results depend on
  the region, the machine type, the capacity type, and the location of the
  bucket.

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

CPU and memory utilization are poor scaling signals for inference, because they
don't show whether requests are waiting. GPU memory use doesn't show it either:
vLLM reserves most of the GPU memory for the KV cache when it starts, so GPU
memory use doesn't change with load. The deployment therefore includes a
`HorizontalPodAutoscaler` that scales on `vllm:num_requests_waiting`, the number
of requests that are waiting in the vLLM scheduler queue. GKE automatic
application monitoring collects the metric with Google Cloud Managed Service for
Prometheus, and the Custom Metrics Stackdriver Adapter makes it available to the
autoscaler.

> [!NOTE]
>
> The platform enables GKE automatic application monitoring by default
> (`cluster_auto_monitoring_config_scope = "ALL"`). If you set it to `NONE`, the
> metric isn't collected and the `HorizontalPodAutoscaler` can't scale the
> deployment.

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
    With `12,629` KV cache tokens on H100 (`18,348` on RTX PRO 6000 for Gemma 4
    31B; `99,070` for Gemma 3 27B), sending 24–32 concurrent requests with long
    outputs (`"max_tokens": 1500` and `"ignore_eos": true`) fills the first
    replica's KV cache so that requests wait in the scheduler queue and exceed
    the HPA target (`5`). With 24 concurrent requests to Gemma 4 31B on RTX PRO
    6000, the number of waiting requests fluctuated between 0 and 7.
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
- **Sustain load for at least 10 to 12 minutes**: In our tests, the
  `HorizontalPodAutoscaler` added a replica about 80 seconds after the load
  started. Scaling onto a new node then requires GKE to provision the GPU node
  (1–2 minutes for RTX PRO 6000 and 2–3 minutes for H100), start vLLM (the
  container image is pulled in seconds with image streaming, but vLLM takes
  another 1–1.5 minutes before it starts loading the weights), stream the model
  weights from Cloud Storage into GPU memory with the Run:ai Model Streamer, and
  complete `torch.compile`, CUDA graph capture, and warm-up (1.3–2.7 minutes). A
  new RTX PRO 6000 replica answered its first request about 6 minutes after the
  load started. Expect H100 replicas to take about 3 minutes longer.
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
  requests to the Service for 12 minutes.

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
                value: "720"
            command: ["/bin/sh", "-c"]
            args:
              - |
                URL="http://vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME}.${ira_online_gpu_kubernetes_namespace_name}.svc.cluster.local:8000/v1/completions"
                END=\$(( \$(date +%s) + \${DURATION_SECONDS} ))
                worker() {
                  while [ "\$(date +%s)" -lt "\${END}" ]; do
                    curl -s -o /dev/null "\${URL}" \
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

  After about 1–1.5 minutes, `TARGETS` rises above `5/5` and `REPLICAS`
  increases. The value fluctuates, because requests only wait while the running
  batch is full. New pods remain `Pending` while GKE provisions GPU nodes, then
  transition to `Running` and `1/1 Ready`. You can press `CTRL`+`c` to terminate
  the watch.

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

## Optional: Cache the model with Rapid Cache

[Rapid Cache](https://cloud.google.com/storage/docs/rapid/rapid-cache), formerly
Anywhere Cache, is an SSD-backed read cache for a Cloud Storage bucket. Each
cache serves only clients in its own zone. Rapid Cache can help when several
replicas load the same model in the same zone at the same time, for example when
a scale-out adds several replicas at once. In our tests, it didn't make a single
load faster.

The following weight load times were measured on 2026-10-02 with Qwen3.5 35B A3B
on Spot `g4-standard-48` nodes in one zone of `europe-west4`. The nodes were
reused between tests, and in each test all the replicas started loading within
1.2 seconds of each other. Each cell is the range for all the replicas in 3
tests.

| Replicas that load at the same time | Without Rapid Cache | With Rapid Cache |
| ----------------------------------- | ------------------- | ---------------- |
| 2                                   | 10.1–10.5 s         | 10.7–11.4 s      |
| 6                                   | 13.2–16.8 s         | 10.5–12.5 s      |

- With Rapid Cache, 97–100% of the bytes were read from the cache.
- Without Rapid Cache, the replicas read the same files from a second bucket in
  the same region, which we created about an hour before the tests. Part of the
  difference with 6 replicas might come from the bucket rather than the cache.
- A single replica loaded the model in 11.2–11.5 seconds with Rapid Cache, with
  78–91% of the bytes read from the cache, and in 11.0–15.4 seconds without it
  (4 loads each).

Keep the following in mind before you use Rapid Cache:

- **A new cache might not serve data for hours.** Creating a cache can take up
  to 48 hours. In our tests, Terraform finished creating each cache in 6–39
  minutes, but 3 of 5 caches reported `RUNNING` and still served no reads from
  the cache. One started to serve reads after 1 hour and 13 minutes, and the
  other two still served none about 18 hours later. The status of a cache
  doesn't show this, so
  [check that replicas read from the caches](#check-that-replicas-read-from-the-caches)
  before you rely on them. For more information, see
  [Troubleshooting temporary resource shortages](https://cloud.google.com/storage/docs/rapid/rapid-cache#temporary-resource-shortages).
- **A cache fills gradually.** A cache stores data after a read misses it. For a
  copy of Qwen3.5 35B A3B that hadn't been read in the zone before, 14% of the
  bytes came from the cache on the first load, 62% on the third load 20 minutes
  later, and 91% on the tenth load about an hour after the first.
- **Caches share a bandwidth limit.** Caches in the same project and zone share
  a cache bandwidth limit that starts at 100 Gbps and grows with the amount of
  data stored in them. Reads above the limit count toward the bandwidth quota of
  the project. In our tests, 6 concurrent loads read 33–39 GiB/s (about 290–340
  Gbps) from one cache for 10–12 seconds, and no requests failed. We didn't test
  more replicas or longer loads. For more information, see
  [Rapid Cache quotas and limits](https://cloud.google.com/storage/quotas#rapid-cache).
- **Ingest on write filled only the writer's zone.** If you set
  `ira_online_gpu_rapid_cache_ingest_on_write` to `true`, the caches also store
  objects when they are written. In our tests, only writes from a client in a
  cache's zone were stored, and only in that zone's cache. The model download
  job runs in one zone, so it can fill at most one cache.
- **Clean up takes longer.** When you destroy a cache, Cloud Storage deletes it
  after a grace period of 1 hour, and you can't delete the model bucket until
  then.
- **Caches have their own costs.** For more information, see
  [Rapid Cache pricing](https://cloud.google.com/storage/pricing#rapid-cache). A
  cache that isn't used doesn't incur additional cost.

### Create the caches

- List the zones in the cluster's region that offer your GPU type. A cache
  serves only clients in its own zone, so create a cache in each zone where your
  GPU nodes can run.

  - **NVIDIA RTX PRO 6000 96GB**:

    ```shell
    gcloud compute accelerator-types list \
    --filter="zone~/zones/${cluster_region}- AND name~^nvidia-rtx-pro-6000$" \
    --format="value(zone.basename())" \
    --sort-by=zone
    ```

  - **NVIDIA H100 80GB**:

    ```shell
    gcloud compute accelerator-types list \
    --filter="zone~/zones/${cluster_region}- AND name~^nvidia-h100-80gb$" \
    --format="value(zone.basename())" \
    --sort-by=zone
    ```

  Check that each zone is listed in the
  [supported locations](https://cloud.google.com/storage/docs/rapid/rapid-cache#supported-locations)
  for Rapid Cache.

- Set the zones for the caches, for example:

  ```shell
  export RAPID_CACHE_ZONES='["europe-west4-a", "europe-west4-b", "europe-west4-c"]'
  ```

- Add the zones to the Terraform configuration.

  ```shell
  sed -i "/^ira_online_gpu_rapid_cache_zones[[:blank:]]*=/{h;s|=.*|= ${RAPID_CACHE_ZONES}|};\${x;/^$/{s|.*|ira_online_gpu_rapid_cache_zones = ${RAPID_CACHE_ZONES}|;H};x}" "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/inference-ref-arch.auto.tfvars"
  ```

- Apply the online GPU resources again to create the caches.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  Terraform waits until each cache is `RUNNING`. In our tests, that took 6–39
  minutes for each cache.

### Check that replicas read from the caches

- After replicas have loaded the model, show how many GiB each zone read from
  its cache (`cache_hit=true`) and from the bucket (`cache_hit=false`) in the
  last hour.

  ```shell
  curl --silent \
  --header "Authorization: Bearer $(gcloud auth print-access-token)" \
  --data-urlencode "query=sum by (anywhere_cache_zone, anywhere_cache_hit) (increase(storage_googleapis_com:anywhere_cache_sent_bytes_count{monitored_resource=\"gcs_bucket\",bucket_name=\"${huggingface_hub_models_bucket_name}\",method=\"ReadObject\"}[1h])) / 2^30" \
  "https://monitoring.googleapis.com/v1/projects/${huggingface_hub_models_bucket_project_id}/location/global/prometheus/api/v1/query" | \
  jq --raw-output '.data.result[] | "\(.metric.anywhere_cache_zone) cache_hit=\(.metric.anywhere_cache_hit) \(.value[1] | tonumber | . * 10 | round / 10) GiB"'
  ```

  The output is similar to the following:

  ```text
  europe-west4-b cache_hit=false 0.1 GiB
  europe-west4-b cache_hit=true 401.9 GiB
  ```

  The metric can take a few minutes to appear. It lists every zone that read
  from the bucket, including zones without a cache. If a zone shows only
  `cache_hit=false` after the model was loaded there several times, its cache
  isn't serving the model yet.

## Considerations for production

- **GKE can evict a serving replica to move it to another node.** The compute
  classes that these manifests use prefer on-demand capacity, fall back to
  flex-start and then Spot capacity, and enable
  [active migration](https://cloud.google.com/kubernetes-engine/docs/concepts/about-custom-compute-classes#active-migration),
  which replaces nodes that use a lower-priority rule when nodes that use a
  higher-priority rule become available. During a migration, GKE creates a new
  node, then drains the old node, so the replica is evicted and starts again
  from the beginning. Spot nodes can also be reclaimed, and flex-start nodes
  have a maximum run duration. In our tests, while we added and removed GPU
  replicas, the cluster autoscaler drained nodes that were running vLLM replicas
  seven times in about 12 minutes. Each time, it had shortly before added a node
  with the same machine type and capacity type as the drained node, and the
  replacement replica started on the new node. Two of the evicted replicas were
  still starting, and each replacement took about 3–5 minutes to become `Ready`.
  The manifests in this guide run a single replica and don't set a
  `PodDisruptionBudget` or the
  `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` annotation, so each
  eviction interrupts serving. For production, run more than one replica, and
  consider a `PodDisruptionBudget` or the annotation. Active migration and
  cluster autoscaler scale-down both respect the annotation and
  `PodDisruptionBudget` objects.
- **The first request can be slow.** The first request to a new Qwen3.5 35B A3B
  replica took about 22 seconds, and the same short request took less than a
  second after that. The pod became `Ready` before that first request finished,
  so user requests can hit this delay. To avoid it, send a warm-up request to a
  new replica before it becomes `Ready`.
- **Concurrent loads can be slower.** In our tests in one zone, each of 6
  replicas that loaded the same model at the same time took 13.2–16.8 seconds,
  compared to 10.1–10.5 seconds for each of 2 replicas. A scale-out that adds
  several replicas at once can take longer than the single-replica results in
  this guide. With Rapid Cache, each of 6 concurrent loads took 10.5–12.5
  seconds. For more information, see
  [Optional: Cache the model with Rapid Cache](#optional-cache-the-model-with-rapid-cache).
- **Spot nodes don't use fast-starting nodes.** GKE Autopilot uses
  [fast-starting nodes](https://cloud.google.com/kubernetes-engine/docs/concepts/fast-starting-nodes)
  on a best-effort basis, at no extra charge, when a workload uses a compatible
  configuration. GKE pre-initializes the hardware for these nodes, and you don't
  need to configure anything. G4 machine types, which provide the RTX PRO 6000
  GPUs, are eligible in the Rapid channel on GKE 1.34.4-gke.1130000 or later,
  with a `hyperdisk-balanced` boot disk and no Local SSD. Spot VMs aren't
  eligible, and the A3 High machine types (`a3-highgpu-*`) that provide the H100
  GPUs aren't on the list of eligible machine types. The compute classes that
  these manifests use already prefer on-demand capacity to flex-start and Spot
  capacity. The G4 nodes in our tests met the requirements except that they were
  Spot nodes, so the results don't include fast-starting nodes. We couldn't
  measure their effect, because GKE couldn't create an on-demand GPU node in 6
  attempts in `us-central1` and `europe-west4` on 2026-10-02.

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

  If you created Rapid Cache caches, this step disables them, and Cloud Storage
  deletes them after a grace period of 1 hour. You can't delete the model bucket
  until the caches are deleted.
