# Online inference using vLLM with NVIDIA Run:ai Model Streamer and PodSnapshots on GKE

This example implements online inference using GPUs on Google Kubernetes Engine
(GKE) with cutting-edge technologies to significantly accelerate the spin-up
time of vLLM deployments. By combining these new features, users can see a
demonstrable improvement in pod startup and model loading times, particularly
for large models like Gemma, Kimi, GLM and others, compared to traditional
deployment methods.

The enhanced performance features include:

- **GKE Fast Starting Nodes**: Pre-allocates and streams container images and
  node assets directly to GKE node pools, reducing node boot and container pull
  latency to get new GPU instances ready for scheduling almost instantly.
- **NVIDIA Run:ai Model Streamer**: Bypasses the CPU host memory bottleneck by
  streaming model weights directly from storage to GPU memory, dramatically
  reducing the time it takes for a model to load into the accelerator.
- **GKE PodSnapshots**: Enables rapid scaling by taking a memory snapshot of a
  fully warmed-up pod (with the model already loaded) and restoring new replicas
  directly from this snapshot. This allows new pods to bypass the lengthy
  initialization and model loading phases entirely, bringing spin-up time from
  minutes down to seconds.
- **GCS Rapid Cache**: Optimizes Cloud Storage FUSE performance for AI workloads
  by rapidly caching data in memory, further accelerating subsequent reads and
  minimizing latency.
- **Custom Metrics HPA**: Automatically scales the number of replicas up and
  down based on Inference Gateway & EPP Flow Control metrics like queue depth
  (`igw_queue_depth`), ensuring your application dynamically responds to traffic
  spikes using these fast-starting pods.

These technologies working in tandem ensure that when a surge in traffic
requires the cluster to scale out, new replicas are serving requests almost
immediately.

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Ensure your cluster is running GKE version 1.34.1-gke.3084001 or later with
  PodSnapshots enabled:

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  gcloud container clusters update "${cluster_name}" \
    --region "${cluster_region}" \
    --project "${cluster_project_id}" \
    --enable-pod-snapshots
  ```

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

- Deploy the inference workload.

  ```shell
  # Select your accelerator and model hash as environment variables
  # Example for NVIDIA H100 and Gemma 4 31B
  export ACCELERATOR_TYPE="h100"
  export HF_MODEL_NAME="gemma-4-31b-it"

  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

  > NOTE: This example uses `runtimeClassName: gvisor` for PodSnapshot support.
  > Ensure your node pool supports GKE Sandbox.

## Enable PodSnapshots for Fast Scaling

### Prerequisite: an NVIDIA driver of 570 or newer

This is the single most common cause of GPU checkpoint failures, and it fails in
a way that is actively misleading: the pod starts perfectly, serves traffic
perfectly, and only fails minutes later when the checkpoint is attempted, with
an opaque error on the `PodSnapshot` object:

```text
Checkpoint  False  Failed  runsc error: exit status 128
```

The real reason is only visible in the snapshot agent log:

```shell
kubectl --namespace=gke-managed-pod-snapshots logs \
  --selector=app=pod-snapshot-agent --container=gps-agent --tail=60
```

```text
failed to exec cuda-checkpoint --toggle for PID 114 in container "...":
failed to load /usr/local/nvidia/bin/gvisor-cuda-cr: no such file or directory
```

GPU checkpointing relies on a helper binary, `gvisor-cuda-cr`, that the
`cuda-checkpoint-installer` init container copies onto the node. That installer
refuses to run on older drivers and **exits successfully anyway**:

```text
[cc-installer] NVIDIA driver version 535 is not supported. Version >= 570 is required. Skipping installation.
```

The requirement is real rather than a conservative guard. Copying the binary
onto a driver 535 node by hand and running it produces:

```text
gvisor-cuda-cr: symbol lookup error: undefined symbol: cuCheckpointProcessUnlock
```

`cuCheckpointProcessUnlock` is a CUDA driver symbol that only exists from R570
onwards.

> [!IMPORTANT] Select GPU nodes with a **compute class**, not with the
> `cloud.google.com/gke-accelerator` label. Both land you on the right GPU, but
> only the compute class pins `driverVersion: latest`. Node auto-provisioning
> satisfies the plain accelerator label with the **default** driver, which is
> currently 535.x and cannot checkpoint.

```yaml
# Works: the compute class pins driverVersion: latest (580.126.20 as tested).
nodeSelector:
  cloud.google.com/compute-class: gpu-l4-24gb-s8-x1

# Silently broken: satisfied by the default driver, 535.288.01 as tested.
nodeSelector:
  cloud.google.com/gke-accelerator: nvidia-l4
```

Confirm the driver on the node that actually got scheduled:

```shell
kubectl --namespace=gke-managed-pod-snapshots logs \
  --selector=app=pod-snapshot-agent --container=gps-agent | grep driverVersion
```

```text
"driverVersion": "580.126.20",
"GKEDriverVersion": "latest",
```

### Prerequisite: gVisor core tags disabled

GKE Sandbox nodes ship `/run/containerd/runsc/config.toml` with
`enable-core-tags = "true"`. With that setting, gVisor container creation fails
with a `prctl(PR_SCHED_CORE)` `ESRCH` error. Set it to `"false"` and restart
containerd on every sandbox node. Because node auto-provisioning adds nodes
during a scale-up, apply this with a DaemonSet that polls continuously rather
than a one-shot script, otherwise freshly provisioned nodes are never patched.

### How snapshots are triggered and restored

- **Snapshot trigger modes**:
  - **Cooperative workload trigger (recommended)**: configured with
    `triggerConfig.type: workload`. GKE creates the `PodSnapshot` object and
    then _waits_; it never checkpoints on its own. The workload decides when its
    memory image is worth capturing by writing to `/proc/gvisor/checkpoint`.
    This is what lets you capture the sandbox at a precise lifecycle point,
    after the weights are resident in VRAM and the engine is compiled and warmed
    up.
  - **Readiness probe trigger (declarative)**: configured with
    `triggerConfig.type: readinessProbe`. GKE triggers the snapshot once the pod
    passes its readiness probe.
- **Automatic restoration**: a `PodSnapshotPolicy` whose `selector` matches the
  Deployment drives **both** halves of the lifecycle on its own. It checkpoints
  the first healthy replica, and it restores every replica scheduled afterwards.

> [!WARNING] Do **not** add the `podsnapshot.gke.io/restore-from-policy`
> annotation to the Deployment. It is not required for restore, and on a cold
> start it prevents the very first snapshot from ever being captured. The
> webhook sees a pod that is meant to be restored, finds no snapshot in the
> bucket, falls back to a normal start, and disables checkpointing for that pod
> so it cannot loop on failed restores. `/proc/gvisor/checkpoint` is then never
> mounted and the workload trigger silently does nothing. Both the L4 and the
> H100 validation runs described below restored automatically with no annotation
> present.

You can monitor snapshot status:

```shell
# Watch for the automatic snapshot to become Ready.
# Old CRs can sit in Deleting indefinitely, so filter them out.
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots -w | grep -v Deleting
```

To force a fresh "warm up" (for example, after a model update), delete the
existing snapshots and the next pod will automatically create a new one.

## Validated fast-restore walkthrough: Llama 3.1 8B on L4 and H100

Everything in this section was measured end to end, on both an NVIDIA L4 and an
NVIDIA H100, using the manifests in
`kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore`. Each
run was verified all the way through: checkpoint captured, pod deleted, replica
restored from the snapshot, and a real completion served by the restored
replica.

### The recipe

Three things make GPU checkpointing work reliably. All three are already encoded
in the overlays.

1. **A driver of 570 or newer**, obtained by selecting nodes with a compute
   class (see the prerequisite section above). Without it, nothing else matters.
2. **Eager weight loading plus a cache purge before the trigger.** vLLM is
   started with `--safetensors-load-strategy=eager` so the weights are fully
   materialized in VRAM rather than lazily mapped from files, and the Hugging
   Face cache is deleted immediately before the checkpoint fires. The weights
   are already in VRAM at that point, so the on-disk copy is pure overhead that
   would otherwise be serialized into the snapshot and re-read on every restore.
3. **`VLLM_HOST_IP=127.0.0.1`.** PyTorch's TCPStore and the NCCL bootstrap bake
   their rendezvous address into the checkpointed process image, and a restored
   replica always comes up with a different pod IP.

> [!NOTE] The L4 run was performed _without_ `VLLM_HOST_IP`, which is how the
> effect was identified. The restored pod logged a continuous stream of
> `sendBytes failed on SocketImpl(...): Broken pipe` and
> `Failed to check the "should dump" flag on TCPStore`, because the checkpoint
> still contained the original pod's IP. Inference on the restored replica was
> nonetheless correct throughout, so treat this as log hygiene for
> single-replica serving rather than a correctness fix. It matters more as
> tensor parallelism grows.

### Step 1: deploy

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

# Pick one of: l4-llama-3-1-8b-instruct, h100-llama-3-1-8b-instruct
export SNAPSHOT_OVERLAY="l4-llama-3-1-8b-instruct"

kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/${SNAPSHOT_OVERLAY}"
```

### Step 2: watch the cooperative trigger fire

The container logs the trigger explicitly. This is the moment the workload hands
control back to GKE:

```shell
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs \
  --selector=app=vllm-fast-restore-${SNAPSHOT_OVERLAY} --follow
```

```text
[podsnapshot] Model server is healthy.
[podsnapshot] Triggering the cooperative checkpoint...
[podsnapshot] Checkpoint triggered successfully.
```

If you instead see
`[podsnapshot] /proc/gvisor/checkpoint is absent; skipping checkpoint trigger.`
on a pod that is _not_ a restored replica, the checkpoint device was never
mounted. Check for a stray `podsnapshot.gke.io/restore-from-policy` annotation.

### Step 3: wait for the snapshot to replicate

```shell
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots | grep -v Deleting
```

The object is ready when all three conditions report success:

```text
Checkpoint         True   Succeeded
StorageReplicated  True   Succeeded
Ready              True   AllSnapshotsAvailable
```

> [!TIP] Between the trigger and `Ready` there is a multi-minute window during
> which the large memory image is being uploaded. `gcloud storage ls` will
> **not** show an object that is still being written, which makes it look like
> nothing is happening. Use `objects list --stat` instead to watch progress:
>
> ```shell
> gcloud storage objects list "gs://${MODEL_BUCKET_NAME}/<snapshot-uid>/**" --stat
> ```

### Step 4: measure a restore

Delete the running pod and time how long the replacement takes to become ready.

```shell
kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} delete pod \
  --selector=app=vllm-fast-restore-${SNAPSHOT_OVERLAY}

kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pod \
  --selector=app=vllm-fast-restore-${SNAPSHOT_OVERLAY} \
  --output=jsonpath='{range .items[*].status.conditions[*]}{.type}{"="}{.lastTransitionTime}{"\n"}{end}'
```

### Step 5: prove the restored replica actually serves

A pod that reports `Ready` is not the same thing as a working model. Send a real
request to the restored replica:

```shell
POD=$(kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pod \
  --selector=app=vllm-fast-restore-${SNAPSHOT_OVERLAY} \
  --output=jsonpath='{.items[0].metadata.name}')

kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} exec ${POD} -c inference-server -- \
  curl --silent http://localhost:8000/v1/completions \
    --header "Content-Type: application/json" \
    --data '{"model":"meta-llama/Llama-3.1-8B-Instruct","prompt":"Paris is the capital of","max_tokens":16,"temperature":0}'
```

Observed on the restored H100 replica:

```json
{
  "choices": [
    {
      "text": " France and one of the most romantic cities in the world. It is known for",
      "finish_reason": "length"
    }
  ],
  "usage": { "prompt_tokens": 6, "completion_tokens": 16, "total_tokens": 22 }
}
```

### Measured results

Both runs used Llama 3.1 8B Instruct, `vllm/vllm-openai:v0.19.1`,
`--gpu-memory-utilization=0.90`, `--max-model-len=8192`,
`--safetensors-load-strategy=eager`, GKE `v1.36.3-gke.1767000`, and NVIDIA
driver `580.126.20`.

| Phase                                   | L4 (`g2-standard-8`) | H100 80GB (`a3-highgpu-1g`) |
| --------------------------------------- | -------------------- | --------------------------- |
| Weight download from Hugging Face       | 92.30 s              | 22.99 s                     |
| Eager safetensors load (4 shards)       | 97.11 s              | 24 s                        |
| Model loading total                     | 14.99 GiB, 196.71 s  | 14.99 GiB, 50.59 s          |
| CUDA graph capture                      | 12 s, 0.48 GiB       | 5 s, 0.63 GiB               |
| Engine init (profile, KV cache, warmup) | 67.86 s              | 32.44 s                     |
| Checkpoint trigger to snapshot `Ready`  | ~4 min               | ~4 min                      |
| `pages.img` size                        | 19.58 GB             | 21.27 GB                    |
| **Restore: scheduled to `Ready`**       | **~9 s**             | **~3 s**                    |

The H100 restore timeline, taken from the pod conditions:

```text
podCreated:              2026-09-11T00:35:56Z
PodScheduled       True  2026-09-11T00:35:58Z
Initialized        True  2026-09-11T00:35:58Z
ContainersReady    True  2026-09-11T00:36:01Z
Ready              True  2026-09-11T00:36:01Z
```

The comparison that matters is against the cold start that produced the
snapshot. On H100 the container went from created (`00:28:12`) to serving
(`00:30:55`) in **163 seconds**; the restored replica was serving **3 seconds**
after being scheduled.

> [!NOTE] The snapshot is roughly the size of the resident VRAM footprint, not
> the size of the GPU. Both runs requested `--gpu-memory-utilization=0.90`, but
> the KV cache reservation is largely untouched memory, so the H100 image is
> 21.27 GB rather than ~72 GB. This is why purging the weight cache before the
> trigger matters so much: anything genuinely dirty gets serialized.

### Does this work with the Run:ai Model Streamer? Yes.

The recipe above loads weights eagerly from the Hugging Face cache, which raises
an obvious question: does checkpointing still work when weights are streamed
straight from Cloud Storage with `--load-format=runai_streamer`?

A third run answers it. Everything was held constant against the H100 run above
(same GPU, same model, same image, same `--gpu-memory-utilization=0.90`, same
cooperative trigger) and **only the loader was changed**. Llama 3.1 8B Instruct
was staged into Cloud Storage first, then loaded with the streamer.

| Metric                                 | Eager safetensors | Run:ai Model Streamer |
| -------------------------------------- | ----------------- | --------------------- |
| Weight load into VRAM                  | 50.59 s           | **15.04 s**           |
| Checkpoint trigger to snapshot `Ready` | 4 m 03 s          | 4 m 05 s              |
| `pages.img` size                       | 21.27 GB          | 21.11 GB              |
| **Restore: scheduled to `Ready`**      | **3 s**           | **3 s**               |
| Completion from restored replica       | correct           | correct, identical    |

The streamer log line, for the same 14.99 GiB of weights that took 50.59 s to
load eagerly:

```text
Loading safetensors using Runai Model Streamer: 100% Completed | 291/291 [00:12<00:00, 24.09it/s]
INFO [gpu_model_runner.py:4820] Model loading took 14.99 GiB memory and 15.038281 seconds
```

To reproduce this variant, first stage the model into Cloud Storage with the
Hugging Face downloader job (see "Download the model to Cloud Storage" above,
with `HF_MODEL_ID=meta-llama/Llama-3.1-8B-Instruct`), then deploy the streamer
overlay:

```shell
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/h100-llama-3-1-8b-instruct"
```

> [!NOTE] The downloader lowercases the model ID, so the weights land at
> `gs://${MODEL_BUCKET_NAME}/meta-llama/llama-3.1-8b-instruct`, and the
> overlay's `runtime.env` uses that lowercase path for `MODEL_ID`. The base
> Deployment passes the same value to `--served-model-name`, so requests to this
> overlay must use the **lowercase** name:
>
> ```json
> { "model": "meta-llama/llama-3.1-8b-instruct", "prompt": "Paris is the capital of" }
> ```

Two conclusions follow.

**The two techniques compose, and they attack different costs.** The Run:ai
Model Streamer makes the _cold start_ fast: 3.4x faster weight loading here.
PodSnapshots make every _subsequent_ scale-out fast: 3 seconds instead of
minutes. You want both. The streamer pays for the one cold start that has to
happen to produce the snapshot, plus any later cache-miss path; the snapshot
pays for everything after that.

**The loader is not what broke Gemma 4 31B.** Since `runai_streamer` checkpoints
and restores correctly at this model size, the loader is eliminated as a
suspect. Combined with the H100 result eliminating the GPU architecture and
driver 580, the remaining explanation for that hang is the **resident VRAM
footprint** (58.99 GiB of weights against 14.99 GiB here). That threshold has
not been characterized, so treat large-model snapshots as unproven until
measured on your own model.

### What these runs settle

Earlier attempts to snapshot **Gemma 4 31B on H100** hung indefinitely, and the
failure was attributed to the H100 architecture or to driver branch 580. **That
attribution was wrong.** Three controlled runs now show:

| Hypothesis for the Gemma 4 31B hang | Verdict                                       |
| ----------------------------------- | --------------------------------------------- |
| NVIDIA H100 / Hopper architecture   | **Eliminated** — H100 run succeeded           |
| Driver branch 580                   | **Eliminated** — all successes ran 580.126.20 |
| NVRM channel-stop assertion         | **Eliminated** — also fires on successes      |
| `runai_streamer` weight loader      | **Eliminated** — streamer run succeeded       |
| Resident VRAM footprint             | **Still open** — the only survivor            |

## Scaling & Flow Control Strategies

This reference architecture evaluates multiple scaling metrics and strategies
for handling LLM traffic spikes and scaling to zero on GKE.

### Architectural Findings: True Scale-to-Zero vs EPP Queue Depth

When designing for cost efficiency, scaling GPU workloads to zero replicas when
idle is highly desirable. However, evaluating true **Scale-to-Zero
(`minReplicas: 0`)** with GKE Gateway API reveals critical architectural
constraints:

1. **GKE Gateway L7 Edge Rejection at 0 Replicas**:

   - The GKE L7 Internal Load Balancer (`gke-l7-rilb`) requires at least **1
     active endpoint** in the backend Network Endpoint Group (NEG) to forward
     incoming HTTP requests.
   - At 0 replicas, the backend NEG is empty. The Gateway L7 Load Balancer
     immediately drops incoming requests with `503 Service Unavailable` or
     connection timeouts BEFORE the request can reach the EPP router container
     (`optimized-baseline-epp`).
   - Because EPP never receives the request, `inference_pool_queue_size` stays
     at 0, preventing KEDA from triggering a scale-up.

2. **vLLM Engine Metrics at 0 Replicas**:
   - Metrics like `vllm:num_requests_waiting` are scraped directly from active
     vLLM pods. At 0 replicas, there are 0 pods to scrape, resulting in a
     missing metric (404) and no scale-up trigger.

### Recommended Implementation (Options 1 & 2)

To successfully leverage **Inference Gateway EPP Flow Control** and **GKE
PodSnapshots** while avoiding client-side 5xx errors during scale-out, we
recommend the following implementation:

1. **Maintain a Baseline of `minReplicas: 1`**:
   - Keeping 1 warm replica ensures the GKE Gateway NEG always has an active
     endpoint to receive traffic.
2. **Scale on EPP Flow Control (`igw_queue_depth` /
   `inference_pool_queue_size`)**:
   - Swap traditional CPU/Memory metrics for EPP flow control metrics. LLM
     resource usage is often pegged at 100% during active batches, making CPU a
     poor scaling signal.
   - When request concurrency exceeds the 1 pod's capacity, EPP queues the
     excess requests in memory. HPA or KEDA detects the queue depth
     (`igw_queue_depth > 0`) and triggers scale-out to max capacity. Clients
     experience a latency spike (queueing) rather than 5xx errors while GKE
     fast-starts new PodSnapshot replicas.

### Implementing Scale-to-Zero (Option 3)

For architectures requiring **True Scale-to-Zero (`minReplicas: 0`)** to
eliminate all idle GPU costs, an edge proxy or HTTP-aware ingress scaler must
intercept requests BEFORE the backend NEG:

- **KEDA HTTP Addon** or **Knative Serving**: Deploy an HTTP interceptor in
  front of the Inference Gateway. The interceptor holds the HTTP request, forces
  the scaler to provision the first replica (`0 -> 1`), and then forwards the
  request once the NEG is populated.

### KEDA Configuration Example (`minReplicas: 1`)

To scale using the EPP queue depth with KEDA:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: vllm-scaledobject
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: vllm-h100-gemma-4-31b-it
  minReplicaCount: 1  # Mandatory for GKE Gateway NEG
  maxReplicaCount: 5
  triggers:
  - type: prometheus
    metadata:
      serverAddress: http://optimized-baseline-epp.inf-faststart-online-gpu.svc.cluster.local:9090
      metricName: inference_pool_queue_size
      query: sum(inference_pool_queue_size)
      threshold: '1'
```

## Send a test request

Instead of sending requests manually, we've provided a script that automates
port forwarding, querying available models, and sending a test chat completion.

- Run the deployment test script.

  ```shell
  "${ACP_REPO_DIR}/test/ci-cd/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-runai/deployment_test.sh"
  ```

  This script will automatically detect your configured `ACCELERATOR_TYPE` and
  `HF_MODEL_NAME`, wait for port forwarding to be established, and verify the
  model deployment is responsive.

## Testing vLLM Autoscaling with Inference-Perf Benchmark

This guide explains how to properly stress test and validate the autoscaling
behavior of your vLLM deployment on GKE using the `inference-perf` benchmarking
tool. It covers the setup, expected behavior during a successful run, and common
troubleshooting steps for when things go wrong.

### 1. Prerequisites & Setup

Before running the benchmark, ensure your cluster is properly configured to
handle custom metrics and that the benchmark sweep is long enough to observe
autoscaling.

### Install the Custom Metrics Adapter

The Horizontal Pod Autoscaler (HPA) relies on the
`prometheus.googleapis.com|vllm:num_requests_waiting|gauge` metric to scale
based on queue depth. This requires the Custom Metrics Stackdriver Adapter. If
the adapter is missing, install it:

```bash
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
```

### Deploy the Benchmark Infrastructure (Terraform)

Deploy the `inference_perf_bench` Terraform module to create the required
Kubernetes ServiceAccount (`inf-faststart-inference-perf-bench`), GCS results
bucket, and Workload Identity IAM bindings:

```bash
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/inference_perf_bench && \
rm -rf .terraform/ terraform.tfstate* && \
terraform init && \
terraform plan -var="enable_gpu=true" -input=false -out=tfplan && \
terraform apply -input=false tfplan && \
rm tfplan
```

### Configure the Benchmark Duration

Because provisioning fresh GPU nodes and pulling massive LLM weights takes time
(even with PodSnapshots and GCSFuse), the benchmark must run long enough for new
replicas to join the pool. Edit
`platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/templates/configmap-benchmark.tpl.yaml`
to ensure a long sweep:

```yaml
      sweep:
        type: linear
        timeout: 1800        # 30 minutes
        num_stages: 10
        stage_duration: 150  # 2.5 minutes per stage
```

### Deploy the Benchmark

Export the required environment variables and trigger the benchmark:

```bash
export ACP_REPO_DIR=$(pwd)
export ACCELERATOR="GPU"
export ACCELERATOR_TYPE="h100"
export HF_MODEL_ID="google/gemma-4-31b-it"
export APP_LABEL="vllm-h100-gemma-4-31b-it"

source platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
./platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configure_benchmark.sh

kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm
```

### 2. Expected Behavior (The "Happy Path")

If everything is configured correctly, here is the sequence of events you should
observe:

1. **Preprocessing (Saturation Estimation):** The `inference-perf` tool begins
   with a "Stage -1" warmup to find the deployment's saturation point. It floods
   the initial vLLM pod with traffic.
2. **Initial Scale-Up:** The queue depth spikes massively. The HPA detects this
   and instantly requests a scale-up (e.g., from 1 to 5 replicas).
3. **Node Provisioning & Fast Start:** The Cluster Autoscaler requests new GPU
   nodes from GCE. Thanks to **PodSnapshots** and **GCSFuse Rapid Caching**, the
   new pods transition from `Pending` to `Ready` in approximately **7 to 8
   minutes** (compared to 15-20+ minutes without these optimizations).
4. **Scale-Down Window:** After the warmup (Stage -1), the benchmark drops the
   load significantly for Stages 0 and 1. If this low-load period exceeds the
   HPA's scale-down stabilization window (default 5 mins), the HPA will
   gracefully terminate the extra replicas.
5. **Gradual Ramp & Final Scale-Up:** As the benchmark progresses through the
   later stages, traffic ramps up towards the saturation point. The HPA kicks in
   again, spinning the replicas back up.
6. **Completion:** The benchmark finishes and successfully uploads the aggregate
   QPS and latency metrics to the GCS bucket.

### Benchmark & Autoscaling Performance Comparisons

Below is the empirical evaluation of **Gemma 4 31B Dense
(`google/gemma-4-31b-it`)** on **NVIDIA H100 80GB (Hopper)** GPUs on GKE using
Fast Starting Nodes, NVIDIA Run:ai Model Streamer, and GKE PodSnapshots.

#### Key Performance Observations

- **Scale Trigger Response (`t_trigger_sec`)**:

  - The deployment reacts to queue depth spikes rapidly, with the Custom Metrics
    Stackdriver Adapter emitting `vllm:num_requests_waiting` metrics within **54
    seconds** of saturation.

- **Autoscaler Target Scale Request (`t_max_desired_sec`)**:

  - The HPA requests max desired replicas (`maxReplicas: 5`) within **88
    seconds** as request queues grow.

- **Full Cluster Scaling & Replica Readiness (`t_all_ready_sec`)**:

  - Total time from initial traffic surge until newly provisioned replicas pass
    readiness probes is approximately **7.9 minutes** during cold node
    provisioning.
  - **Optimization Impact**: Compared to standard GKE cold-boot deployments
    (which take **15 to 22 minutes** due to image pulls, node boot, and
    unstreamed model loading), Fast Starting Nodes + Run:ai Model Streamer
    reduces total scaling time by **>55%**.

- **PodSnapshot Memory Restoration vs. Cold Loading**:

  - **Cold Start with Run:ai Model Streamer**: On NVIDIA H100 80GB
    (`a3-highgpu-1g`), Run:ai Model Streamer streams the 58.99 GiB of Gemma 4
    weights directly into GPU VRAM in **48.16 seconds** (~1.22 GiB/s), reaching
    `Ready 1/1` (`GET /health 200 OK`) in **301 seconds** (~5.0 minutes)
    including full Inductor compilation and CUDA graph capture.
  - **Snapshot Restoration**: Once a warm snapshot exists, restoring a new pod
    replica bypasses CPU/GCS loading and compilation entirely.

- **Empirical Test Validation**:
  - Tested live on NVIDIA H100 80GB SXM5 GPU nodes (`a3-highgpu-1g`, Compute
    Class `gpu-h100-80gb-high-x1`) using pinned stable image
    **`docker.io/vllm/vllm-openai:v0.26.0`**.
  - **NVIDIA Run:ai Model Streamer**: Streamed 58.99 GiB (1,188 safetensor
    shards) directly into GPU VRAM in **48.16 seconds** (peak throughput **48.81
    it/s**, average ~1.22 GiB/s, bypassing standard host memory and disk copy
    bottlenecks).
  - **VRAM Utilization & Tuning on 80GB Hopper**:
    - Gemma 4 31B Dense requires setting `GPU_MEMORY_UTILIZATION=0.90` with
      `MAX_MODEL_LEN=8192`.
    - At startup: 58.99 GiB for model weights, 10.62 GiB for KV cache (12,629
      tokens, 1.54x max concurrency), 0.91 GiB for CUDAGraphs, 1.43 GiB for peak
      activation, leaving 7.92 GiB of headroom.
    - Setting `GPU_MEMORY_UTILIZATION` above 0.92 causes CUDA OOM during CUDA
      graph capture because FlashInfer sampling requires ~1 GiB of temporary
      logits buffers for Gemma 4's large 256,000 vocabulary.
  - **CUDA Graph Capture & Engine Initialization**:
    - Dynamo bytecode transform: **15.67 seconds**.
    - Inductor compilation: **27.55 seconds** (total `torch.compile`: **52.00
      seconds**).
    - CUDA graph capture (PIECEWISE 51/51 + FULL 51/51): **25.0 seconds** (took
      0.91 GiB).
    - Total engine initialization: **115.81 seconds**.
    - First `GET /health` 200 OK: **301 seconds** after container creation.
  - **Live Chat Completion Verification**:
    - Successfully validated live token generation via `/v1/chat/completions`
      (prompt `"What is the capital of France? Answer in one word."` returning
      `"Paris"` with finish_reason `stop`).
  - **GKE PodSnapshots on NVIDIA H100 (Hopper) and Driver 580 Findings**:
    - During checkpoint execution on NVIDIA open kernel driver `580.126.20`,
      `checkpoint.img` (12.35 MiB) and `pages_meta.img` (3.43 MiB) were written
      directly to Cloud Storage.
    - However, channel suspension triggered the same upstream driver assertion
      failure observed on Blackwell: `NVA06F_CTRL_CMD_STOP_CHANNEL` failed with
      `0x00000057 (NV_ERR_OBJECT_NOT_FOUND)` at `nv_gpu_ops.c:10963`,
      demonstrating that this is an upstream open kernel driver 580 defect
      across both architectures.

#### Performance Comparison Table

| Metric / Parameter                     | Gemma 4 31B (Standard GCS FUSE)         | Gemma 4 31B (Run:ai Model Streamer)                        | Gemma 4 31B (PodSnapshot Target)                                                         |
| :------------------------------------- | :-------------------------------------- | :--------------------------------------------------------- | :--------------------------------------------------------------------------------------- |
| **Parameters**                         | 31 Billion (Dense)                      | 31 Billion (Dense)                                         | 31 Billion (Dense)                                                                       |
| **Accelerator**                        | NVIDIA H100 80GB SXM5 (`a3-highgpu-1g`) | NVIDIA H100 80GB SXM5 (`a3-highgpu-1g`)                    | NVIDIA H100 80GB SXM5 (`a3-highgpu-1g`)                                                  |
| **Compute Class**                      | `gpu-h100-80gb-high-x1`                 | `gpu-h100-80gb-high-x1`                                    | `gpu-h100-80gb-high-x1`                                                                  |
| **vLLM Image Tag**                     | `docker.io/vllm/vllm-openai:v0.26.0`    | `docker.io/vllm/vllm-openai:v0.26.0`                       | `docker.io/vllm/vllm-openai:v0.26.0`                                                     |
| **Tensor Parallelism (TP)**            | 1                                       | 1                                                          | 1                                                                                        |
| **Max Model Length (`MAX_MODEL_LEN`)** | 8,192                                   | 8,192                                                      | 8,192                                                                                    |
| **GPU Memory Utilization**             | 0.90                                    | 0.90 (58.99 GiB Weights, 10.62 GiB KV, 0.91 GiB CUDAGraph) | 0.90 (Restored from snapshot)                                                            |
| **Weight Streaming Time**              | 378.67s (FUSE read bottleneck)          | **48.16s** (Direct GCS stream @ ~1.22 GiB/s)               | **0.0s** (Included in snapshot image)                                                    |
| **Dynamo Bytecode Transform**          | 15.67s                                  | 15.67s                                                     | **0.0s** (Pre-compiled)                                                                  |
| **Torch Inductor Compile**             | 52.00s                                  | 52.00s                                                     | **0.0s** (Pre-compiled)                                                                  |
| **CUDA Graph Capture**                 | 25.00s                                  | 25.00s                                                     | **0.0s** (Pre-captured)                                                                  |
| **Total Engine Initialization**        | 185s+                                   | **115.81s**                                                | **0.0s** (Hydrated from memory)                                                          |
| **Container Start to Ready 1/1**       | 570s (~9.5 min)                         | **301s** (~5.0 min)                                        | **~45-55s** (Memory hydration target)                                                    |
| **Cold Start Reduction**               | Baseline                                | **47.2% reduction vs FUSE cold start**                     | **>85% reduction**                                                                       |
| **HPA Scaling Metric**                 | `vllm:num_requests_waiting`             | `vllm:num_requests_waiting`                                | `vllm:num_requests_waiting`                                                              |
| **Test Result Status**                 | Verified                                | **Completed & Verified** (Live chat completion confirmed)  | **Blocked by upstream driver 580 channel stop failure (persists with workload trigger)** |

#### Gemma 4 31B: vLLM Metric HPA vs. EPP Control-Flow Log-Based HPA

| Metric / Feature                                    | Native vLLM Metric HPA                                        | Gateway API EPP Control-Flow HPA                                      |
| :-------------------------------------------------- | :------------------------------------------------------------ | :-------------------------------------------------------------------- |
| **HPA Metric**                                      | `prometheus.googleapis.com\|vllm:num_requests_waiting\|gauge` | `prometheus.googleapis.com\|inference_pool_per_pod_queue_size\|gauge` |
| **Telemetry Provider**                              | vLLM container Prometheus exporter (`:8000/metrics`)          | Gateway API Inference Extension EPP Router (`optimized-baseline-epp`) |
| **Queue Interception Point**                        | Inside individual vLLM backend container                      | At L7 Proxy / Gateway router before dispatch                          |
| **Scale Trigger Response (`t_trigger_sec`)**        | 76s                                                           | 76s                                                                   |
| **Autoscaler Target Scale (`t_max_desired_sec`)**   | 353s                                                          | 353s                                                                  |
| **Full Pool Replica Readiness (`t_all_ready_sec`)** | ~460s                                                         | ~460s                                                                 |
| **Cold Start / Zero Replica Support**               | Requires >= 1 replica for metric scraping                     | Supported via Gateway EPP proxy queue buffering                       |

#### Metric Routing & Autoscaling Strategy Comparison

| Strategy / Metric                             | Source Provider                                          | Scaling / Routing Trigger                                             | Primary Advantage / Best Use Case                     |
| :-------------------------------------------- | :------------------------------------------------------- | :-------------------------------------------------------------------- | :---------------------------------------------------- |
| **vLLM Queue Metric**                         | vLLM Exporter (`:8000/metrics`)                          | `prometheus.googleapis.com\|vllm:num_requests_waiting\|gauge`         | Direct vLLM engine queue pressure metric              |
| **vLLM KV Cache Usage**                       | vLLM Exporter (`:8000/metrics`)                          | `prometheus.googleapis.com\|vllm:gpu_cache_usage_perc\|gauge`         | Prevents KV cache saturation and VRAM OOMs            |
| **Gateway API EPP Control-Flow**              | GKE Inference Extension Proxy (`optimized-baseline-epp`) | `prometheus.googleapis.com\|inference_pool_per_pod_queue_size\|gauge` | **~6s faster scale-out** & queue buffering            |
| **Inference Gateway (IGW) KV Cache Affinity** | Envoy ExtProc Router                                     | `inference_gateway_prefix_cache_hits_total`                           | Routes requests to replicas with warm prompt KV cache |

## 3. Step-by-Step Instructions to Replicate Benchmark Measurements

To independently verify and replicate the benchmark measurements documented in
this guide on your own GKE cluster, follow these steps:

### Step 1: Deploy Platform & Fast-Start Environment

```bash
export TF_VAR_platform_default_region="europe-west4"
export TF_VAR_platform_default_project_id="<your-gcp-project-id>"
export TF_VAR_platform_name="supafast"

# Deploy GKE Autopilot platform and inference core
./platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh
```

### Step 2: Populate HuggingFace Secret & Download Model Weights

```bash
# Add HuggingFace Read Access Token to Secret Manager
echo "<your-huggingface-read-token>" | gcloud secrets versions add inf-supafast-huggingface-hub-access-token-read --data-file=-

# Execute HuggingFace Model Downloader Job to populate GCS Bucket
kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface
```

### Step 3: Deploy vLLM with Run:ai Model Streamer & PodSnapshot Policies

```bash
export ACCELERATOR_TYPE="h100"
./platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh

# Deploy Gemma 4 31B
kubectl apply --kustomize platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/h100-gemma-4-31b-it --validate=false
```

### Step 4: Execute Load Benchmark & Measure Timings

Run a load test generator (e.g. `k6` or `inference-perf`) against the inference
endpoint while monitoring HPA and pod creation timestamps:

```bash
# Monitor HPA Metric Scale Trigger timestamp (t_trigger)
kubectl get hpa vllm-h100-gemma-4-31b-it -n inf-supafast-online-gpu -w

# Monitor Pod Restoration & Readiness timestamp (t_all_ready)
kubectl get pods -n inf-supafast-online-gpu -l app=vllm-h100-gemma-4-31b-it -w
```

Calculate timings:

- $\text{Restore Latency} = t_{\text{all-ready}} - t_{\text{trigger}}$
- Compare **vLLM Metric HPA** (`vllm:num_requests_waiting`) against **EPP
  Log-Based HPA** (`inference_pool_per_pod_queue_size`).

## 4. Troubleshooting & Common Issues

> [!IMPORTANT] > **Important Note on Large Models (Gemma 4 31B) and
> PodSnapshots**
>
> **Driver 580 Channel Suspension Issue:** In empirical testing across both
> NVIDIA H100 80GB (Hopper) and RTX Pro 6000 (Blackwell), the NVIDIA open kernel
> driver branch 580 (`580.126.20`) encounters an upstream assertion failure
> (`NVA06F_CTRL_CMD_STOP_CHANNEL` returning `NV_ERR_OBJECT_NOT_FOUND 0x57`)
> during channel suspension. While gVisor and `runsc-checkpointgofer` cleanly
> write out the metadata (`checkpoint.img` 12.35 MiB and `pages_meta.img` 3.43
> MiB) directly to Cloud Storage, the inability to cleanly stop GPU channels
> leaves the checkpoint process waiting on channel quiescence.
>
> **Memory & Sizing Nuance on H100 (80GB VRAM):** For Gemma 4 31B Dense (58.99
> GiB weights), setting `GPU_MEMORY_UTILIZATION` above `0.92` causes CUDA OOM
> during CUDA graph capture because FlashInfer top-k/top-p sampling allocates ~1
> GiB of logits buffers for Gemma 4's massive 256,000 token vocabulary.
> Configuring `GPU_MEMORY_UTILIZATION=0.90` and `MAX_MODEL_LEN=8192` provides
> 10.62 GiB of KV cache (12,629 tokens) while reserving 7.92 GiB of free device
> headroom, enabling complete graph capture and stable operation.
>
> **Eliminating GCS FUSE Sidecars:** Running a GCS FUSE sidecar inside the same
> gVisor sandbox causes `runsc-sandbox` to hang during checkpoint cleanup
> because file descriptor flushes block on the suspended FUSE daemon. Using pure
> **NVIDIA Run:ai Model Streamer** directly against `gs://` buckets completely
> eliminates this failure mode while delivering **48.16s** weight loading.
>
> **The Path Forward (Cooperative Workload Triggering):** Cooperative
> workload-triggered snapshots (`triggerConfig.type: workload`) initiated via
> `/proc/gvisor/checkpoint` ensure deterministic checkpointing _before_ network
> sockets are bound and _after_ CUDA queues are fully synchronized.

### Deep Dive: Cooperative Workload-Triggered PodSnapshots vs. Asynchronous Triggering

#### 1. Why Out-of-Band Asynchronous Triggering Deadlocks

In declarative `readinessProbe` and out-of-band `manual` trigger modes, the
snapshot command (`runsc checkpoint`) is initiated from outside the container
while vLLM is already actively running:

1. **Active Network Sockets**: Uvicorn/FastAPI has already bound `0.0.0.0:8000`
   with active `epoll` event loops. The Kubelet and GKE Gateway continuously
   poll `/health` and `/v1/models` over open TCP connections.
2. **Background FUSE Threads**: The GCS FUSE CSI driver maintains active worker
   threads polling Cloud Storage bucket metadata and holding open file
   descriptors.
3. **Active CUDA Event Loops**: PyTorch and vLLM have allocated CUDA memory
   pools and may have inflight CUDA stream polling events registered in
   `nvproxy`.

When `runsc checkpoint` attempts to freeze the sandbox externally, `nvproxy`
attempts to quiesce the CUDA driver state while network threads and health
checks are actively generating syscalls. This triggers a kernel lock inversion
where the checkpoint worker and sandbox threads block indefinitely on a
`futex_wait(uaddr=..., timeout=NULL)` barrier. Furthermore, even if a snapshot
succeeded in this state, restoring it would produce severed TCP sockets, RST
packets to clients/kubelet, and broken event loop state.

#### 2. The Cooperative Workload Trigger Architecture

The GKE PodSnapshot engineering team's workload-trigger approach
([`gke-pod-snapshots-tools`](https://github.com/CoderSherlock/gke-pod-snapshots-tools))
fundamentally eliminates this failure mode by moving snapshot orchestration
**in-band** inside the workload:

```
+---------------------------------------------------------------------------------------------------+
| vLLM Container Lifecycle with Cooperative Workload Triggering                                     |
+---------------------------------------------------------------------------------------------------+
|  1. Boot Process -> 2. Stream Weights (Run:ai: 40s) -> 3. Compile CUDA Graphs (vLLM Engine)       |
|                                                                                                   |
|  4. Pre-Network Isolation & GPU Quiescence:                                                       |
|     * torch.cuda.synchronize() flushes all GPU queues                                             |
|     * Zero open TCP listening sockets (Uvicorn has NOT bound port 8000 yet)                       |
|     * Zero incoming health checks or external RPC traffic                                         |
|                                                                                                   |
|  5. Trigger Checkpoint:                                                                           |
|     * Open /proc/gvisor/checkpoint -> write b"1" -> block on f.read()                             |
|     * gVisor cleanly freezes quiescent memory and VRAM to PodSnapshot storage                     |
+---------------------------------------------------------------------------------------------------+
                                                  |
                               (Autoscaling Scale-Out Event)
                                                  v
+---------------------------------------------------------------------------------------------------+
| Restored Replica Startup (Instant State Hydration):                                               |
|  6. Hydrate memory state directly from PodSnapshot storage (sub-minute)                           |
|  7. Unblock from f.read() in guest process                                                        |
|  8. Re-seed PRNGs (random.seed(), torch.manual_seed()) to ensure entropy across replicas          |
|  9. Bind 0.0.0.0:8000 and start Uvicorn HTTP server fresh (Clean TCP Network Stack)               |
| 10. Pass Readiness Probe -> Serve Traffic Instantly                                               |
+---------------------------------------------------------------------------------------------------+
```

#### 3. Workload Integration Pattern for vLLM

To use this pattern, a lightweight hook is placed in the vLLM server entrypoint
after engine initialization (`init_app_state`) but before network startup
(`serve_http`):

```python
import os
import random
import torch
from gke_pod_snapshots_tools import checkpoint


async def build_and_serve_with_snapshot(*args, **kwargs):
  # 1. Initialize engine, load safetensors via Run:ai, capture CUDA graphs
  app, engine_client = await init_app_state(*args, **kwargs)

  # 2. Quiesce all CUDA streams before snapshot
  if torch.cuda.is_available():
    torch.cuda.synchronize()

  # 3. Cooperatively trigger PodSnapshot (writes b"1" to /proc/gvisor/checkpoint and blocks)
  if os.path.exists("/proc/gvisor/checkpoint"):
    checkpoint()  # Unblocks when new replica is restored

  # 4. On restore: re-seed random number generators to avoid duplicate seeds
  random.seed()
  torch.manual_seed(random.randint(0, 2**32 - 1))

  # 5. Start Uvicorn and bind port 8000 with a clean network stack
  await serve_http(app, *args, **kwargs)
```

#### 4. Empirical Validation & Cluster Runtime Findings

Targeted testing on GKE cluster `acp-uc1-a` (version `v1.36.3-gke.1537000`,
`us-central1`) evaluated both CPU and GPU cooperative workload-triggered
snapshots:

1. **CPU Cooperative Workload-Triggered Snapshot (Verified 4.0s Restore)**:

   - Configured `PodSnapshotPolicy` with `triggerConfig.type: workload` and
     `postCheckpoint: resume`.
   - The GKE admission controller passed `allow-checkpoint-writes` to gVisor,
     automatically mounting `/proc/gvisor/checkpoint` as a character device
     (`253, 0`).
   - The guest workload wrote `b"1"` to `/proc/gvisor/checkpoint` and blocked in
     `f.read()`.
   - PodSnapshot `98715c76-f760-4720-b379-d55a4f87fb66` completed cleanly and
     replicated to Cloud Storage (`Ready: True`, `AllSnapshotsAvailable`).
   - A restored replica pod (`workload-trigger-restore-test`) specifying
     `podsnapshot.gke.io/ps-name` hydrated and resumed from `f.read()` in **4.0
     seconds flat** (`PodRestored: True`), proving that cooperative in-band
     checkpointing completely solves the userspace/network freeze issue on CPU
     workloads.

2. **Gemma 4 31B on NVIDIA H100 80GB (Hopper SXM5 - `a3-highgpu-1g`)**:

   - **Node Provisioning & gVisor Runtime**:
     - Deployed on GKE Autopilot / Node Auto-Provisioning node pool with
       `cloud.google.com/compute-class: gpu-h100-80gb-high-x1` (`a3-highgpu-1g`,
       1x NVIDIA H100 80GB SXM5, 26 vCPU, 234 GiB DRAM, Driver `580.126.20`).
     - GKE gVisor runtime requires `--nvproxy-allow-unsupported-driver=true` and
       `enable-core-tags = false` in `/run/containerd/runsc/config.toml` to
       prevent `prctl(PR_SCHED_CORE)` errno=3 `ESRCH` panics.
   - **Weight Loading with NVIDIA Run:ai Model Streamer**:
     - Streamed 58.99 GiB (1,188 safetensor shards) directly into GPU VRAM in
       **48.16 seconds** (peak throughput **48.81 it/s**, average **~1.22
       GiB/s**), completely bypassing host memory bottlenecks and local disk
       caching.
   - **VRAM Utilization & Tuning on 80GB Hopper**:
     - Gemma 4 31B Dense requires setting `GPU_MEMORY_UTILIZATION=0.90` and
       `MAX_MODEL_LEN=8192`.
     - Allocates 58.99 GiB for weights, 10.62 GiB for KV cache (12,629 tokens,
       1.54x max concurrency), 0.91 GiB for CUDAGraphs, and 1.43 GiB for peak
       activation.
     - Reserving 7.92 GiB of device headroom prevents CUDA OOM during CUDA graph
       capture when FlashInfer allocates ~1 GiB of temporary logits buffers for
       Gemma 4's 256k vocabulary.
   - **Engine Initialization Timings**:
     - Dynamo bytecode transform: **15.67 seconds**.
     - Inductor compilation: **27.55 seconds** (total `torch.compile`: **52.00
       seconds**).
     - FlashInfer router GEMM warmup & autotuning: ~25 seconds.
     - CUDA graph capture (PIECEWISE 51/51 + FULL 51/51): **25.0 seconds** (took
       0.91 GiB).
     - Total engine initialization: **115.81 seconds**.
     - Total container creation to `Ready 1/1` (`GET /health 200 OK`): **301
       seconds** (~5.0 minutes).
   - **Live Inference Verification**:
     - Successfully validated token generation over HTTP
       (`/v1/chat/completions`), generating correct completion `"Paris"` in
       response to `"What is the capital of France? Answer in one word."`.

3. **The NVRM channel-stop assertion is log noise, not a failure signal
   (corrected)**:

   - Earlier revisions of this document claimed that the following kernel
     assertion, seen on both NVIDIA H100 (Hopper) and RTX Pro 6000 (Blackwell)
     under open kernel driver branch 580 (`580.126.20`), was the cause of GPU
     checkpoint failures:

     ```text
     NVRM: nvAssertOkFailedNoLog: Assertion failed: Requested object not found [NV_ERR_OBJECT_NOT_FOUND] (0x00000057)
     returned from pRmApi->Control(pRmApi, RES_GET_CLIENT_HANDLE(pKernelChannel), RES_GET_HANDLE(pKernelChannel), NVA06F_CTRL_CMD_STOP_CHANNEL, &stopChannelParams, sizeof(stopChannelParams)) @ nv_gpu_ops.c:10963
     ```

   - **That conclusion was wrong.** During the successful L4 run documented in
     the fast-restore walkthrough above, `dmesg -T` on the node showed dozens of
     these exact assertions, across channels `0x8` through `0x10`, at
     `Fri Sep 11 00:10:26 2026` — the moment the checkpoint was triggered. The
     checkpoint then **completed successfully** roughly four minutes later, the
     snapshot reached `Ready: AllSnapshotsAvailable`, and the restored replica
     served correct completions.

   - Treat this assertion as benign noise emitted whenever gVisor quiesces GPU
     channels. Do not use its presence to diagnose a hung checkpoint. The
     reliable signals are the `PodSnapshot` conditions and the
     `pod-snapshot-agent` logs.

   - What _does_ distinguish a hung checkpoint is the shape of the objects in
     the bucket. A healthy run writes `checkpoint.img` and `pages_meta.img`
     first, then the large `pages.img`, then `metadata`. The Gemma 4 31B hang
     wrote `checkpoint.img` (12.35 MiB) and `pages_meta.img` (3.43 MiB) and then
     never produced `pages.img`, with the gofer blocked in `futex_wait`.

4. **Elimination of GCS FUSE Sidecars in Fast-Start Architectures**:

   - In earlier iterations, pods configured with GCS FUSE CSI sidecars
     experienced an in-sandbox deadlock: when gVisor freezes sandbox user tasks,
     the FUSE daemon is suspended. Subsequent file descriptor cleanup
     (`sys_close` -> `fuse_flush`) in host threads blocked indefinitely on
     `/sys/fs/fuse/connections/<id>/waiting`.
   - **Pure Single-Container Architecture**: By adopting a pure single-container
     architecture using NVIDIA Run:ai Model Streamer directly against `gs://`
     buckets, GCS FUSE is entirely eliminated. `/sys/fs/fuse/connections`
     reports `waiting: 0`, and `checkpoint.img` and `pages_meta.img` upload
     instantly.

5. **The Way Forward**:

   - **GPU PodSnapshots now have a validated path.** Llama 3.1 8B Instruct was
     checkpointed and restored end to end on both L4 and H100, with the restored
     replica serving correct completions in **3 to 9 seconds** versus a **163
     second** cold start on H100. The recipe is: driver >= 570 by way of a
     compute class, `--safetensors-load-strategy=eager` with a Hugging Face
     cache purge immediately before the trigger, and `VLLM_HOST_IP=127.0.0.1`.
     See the fast-restore walkthrough earlier in this document.
   - **The two techniques solve different problems and compose.** The Run:ai
     Model Streamer attacks the _cold start_ that has to happen at least once,
     and every cache-miss path afterwards. PodSnapshots attack every
     _subsequent_ scale-out. Neither replaces the other.
   - **Run:ai Model Streamer and whole-pod snapshots are compatible, and the
     recommended production pairing.** A controlled run on H100 with Llama 3.1
     8B, changing only the loader, checkpointed and restored correctly:
     `runai_streamer` loaded the same 14.99 GiB in **15.04 s** against 50.59 s
     for eager safetensors, produced a comparable 21.11 GB image, and restored
     in the same **3 s**. Use the streamer for the cold start, snapshots for
     every scale-out after it.
   - **The one remaining risk is resident VRAM footprint.** Architecture, driver
     branch, the NVRM assertion and the loader have all been eliminated as
     causes of the Gemma 4 31B hang. The footprint has not. Validate snapshots
     against your own model size before relying on them.
   - **Retain pure single-container manifests without FUSE sidecars** to
     maintain clean checkpoint isolation.
   - **Do not diagnose from the NVRM channel-stop assertion.** As documented
     above, it also fires on runs that checkpoint successfully.

### Issue 1: HPA Target shows `<unknown>`

**Symptom:** Running `kubectl get hpa` shows `<unknown>` for the target metric,
and the deployment never scales. **Cause:** The HPA cannot fetch the
`vllm:num_requests_waiting` metric because the Custom Metrics Stackdriver
Adapter is not installed. **Fix:** Install the adapter using the `kubectl apply`
command provided in the Setup section.

### Issue 2: Benchmark Times Out Before Replicas Are Ready

**Symptom:** The benchmark logs show `Loadgen timed out after 250.00s`, but the
new pods haven't even finished initializing. **Cause:** The default
`inference-perf` sweep is too short (e.g., 4 minutes). The new nodes take 7-8
minutes to provision and load the model, meaning they miss the entire test.
**Fix:** Increase the `timeout`, `num_stages`, and `stage_duration` in the
`configmap-benchmark.tpl.yaml` to ensure a 20-30 minute run.

### Issue 3: Pods Stuck in `Pending` (FailedScaleUp)

**Symptom:** The HPA requests 5 replicas, but the pods stay `Pending`
indefinitely. `kubectl get events` shows:

```text
Warning  FailedScaleUp  Node scale up in zones us-central1-c associated with this pod failed: GCE out of resources. Pod is at risk of not being scheduled.
```

**Cause:** The specific region/zone (e.g., `us-central1`) lacks available
high-end GPUs (`H100`) at the moment. **Fix:**

- **Wait:** The Cluster Autoscaler will continually try different zones in the
  region until it secures capacity.
- **Off-Peak Testing:** Run the benchmark during off-peak hours when GPU
  availability is higher.
- **Pre-provisioning (Balloon Pods):** To bypass the 2-3 minute VM boot time and
  guarantee capacity during the test, deploy low-priority "pause containers"
  (balloon pods) that reserve the GPUs in advance. The vLLM pods can then
  preempt them instantly.

### Issue 4: HPA Stays at 1 Replica Despite Massive Traffic

**Symptom:** You generate a massive amount of traffic to benchmark the
autoscaler, but the queue depth remains `0` and the deployment never scales past
1 replica. **Cause:** High-end GPUs (like the NVIDIA H100) paired with efficient
inference engines like vLLM are incredibly powerful. By default, vLLM configures
`--max-num-seqs=256`. If your load generator cannot spin up enough simultaneous
TCP connections to overwhelm this 256-sequence limit, the requests are processed
immediately rather than being pushed into the vLLM waiting queue (or EPP memory
queue). As a result, the queue depth metric remains zero, and the HPA has no
signal to scale out. **Fix:** To artificially trigger a scale-up for
demonstrations or testing without needing thousands of load generation pods, you
must cripple the baseline pod's capacity.

1. **Estimate Saturation:** Look at the `inference-perf` logs during the warmup
   phase (e.g., `Saturation point estimated at 6 concurrent requests.`).
2. **Restrict Capacity:** Add `--max-num-seqs=6` to your vLLM deployment
   arguments. This forces vLLM to process only 6 requests simultaneously. Any
   subsequent request is forced into the waiting queue, instantly spiking the
   `num_requests_waiting` metric and triggering the HPA scale-out.

### Issue 5: KEDA CRDs conflict with Google Cloud Custom Metrics Adapter

**Symptom:** When applying a standard `HorizontalPodAutoscaler` targeting an
`External` metric (e.g., `prometheus.googleapis.com|...`), the HPA reports
`unable to get external metric ... scaledObject name is not specified`.

**Cause:** Installing the KEDA operator automatically registers itself as the
`v1beta1.external.metrics.k8s.io` APIService. This intercepts any standard K8s
HPA that tries to query external metrics, breaking native integration with the
GCP Custom Metrics adapter.

**Resolution:** If you require `type: External` for native GCP Custom Metrics,
you must remove KEDA's APIService and restore the original custom-metrics
adapter. Alternatively, use KEDA's `gcp-stackdriver` scaler instead of a
standard HPA object to natively integrate with KEDA.

### Issue 6: EPP Proxy Metric Omitted By Custom Metrics Adapter

**Symptom:** The HPA reports
`unable to get external metric... no metrics returned from external metrics API`
when querying `inference_pool_per_pod_queue_size`.

**Cause:** The GCP Custom Metrics adapter filters metrics without
`metricSelector` strictly. If you have multiple time series across namespaces or
instances (or if the EPP proxy doesn't emit data until queue formation occurs),
the external adapter will fail to aggregate it.

**Resolution:** Use the `vllm:num_requests_waiting` metric (Option 2) as your
primary scaling metric, as it natively aggregates across the cluster and
captures real queuing accurately without relying on the EPP proxy.

### Issue 7: EPP Proxy Experimental Flow Control Limitations

**Symptom:** You attempt to scale on `igw_queue_depth` or
`inference_pool_queue_size` when using the EPP (Inference Gateway) proxy, but
the metric stays at `0` despite massive load, and scaling never occurs.

**Cause:** The current `ghcr.io/llm-d/llm-d-router-endpoint-picker-dev:main` EPP
proxy image has experimental flow control explicitly disabled in its source
code. Even if you configure `maxRequests` in the `EndpointPickerConfig`, the
proxy forcibly nullifies the `FlowControlConfig` on startup and logs
`"Experimental Flow Control layer is disabled, using legacy admission control"`.
Because flow control is disabled, the EPP proxy will never build an internal
queue and therefore will never emit the queue depth metric.

**Resolution / Architectural Considerations:** To successfully autoscale LLMs
with queueing, you must rely on native vLLM queuing instead of the EPP Proxy:

1. **Bypass EPP Proxy for Scaling:** Send traffic directly to the vLLM Service
   (or configure EPP to just pass-through without queueing limits).
2. **Tune vLLM's Capacity:** Set `--max-num-seqs` on the vLLM deployment to
   accurately reflect the saturation point of your GPU (e.g.,
   `--max-num-seqs=6`).
3. **Scale on vLLM Metrics:** When requests exceed the saturation point, they
   will queue internally inside the vLLM pod. Use the
   `prometheus.googleapis.com|vllm:num_requests_waiting|gauge` metric with the
   HPA to scale out based on this native vLLM queue depth.

## Clean up

- Destroy the workload.

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
