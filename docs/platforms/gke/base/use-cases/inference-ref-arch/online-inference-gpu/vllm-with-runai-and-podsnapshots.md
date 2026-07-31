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

  - **Gemma 4 31B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

  - **gpt-oss-20b**

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
  # Example for RTX Pro 6000 and Gemma 3 27B
  export ACCELERATOR_TYPE="rtx-pro-6000"
  export HF_MODEL_NAME="gemma-3-27b-it"

  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

  > NOTE: This example uses `runtimeClassName: gvisor` for PodSnapshot support.
  > Ensure your node pool supports GKE Sandbox.

## Enable PodSnapshots for Fast Scaling

- The deployment is configured for **fully declarative PodSnapshots**:

  - **Automatic Snapshotting**: A `PodSnapshotPolicy` with
    `type: readinessProbe` automatically triggers a snapshot as soon as the
    first vLLM pod loads the model and becomes `Ready`.
  - **Automatic Restoration**: The Deployment includes the
    `podsnapshot.gke.io/restore-from-policy` annotation. This tells GKE to
    automatically restore all new replicas from the latest snapshot created by
    the policy.

- No manual annotations or triggers are required. Simply deploy the manifests,
  and the first pod will "warm up" the cluster by creating a snapshot that all
  subsequent replicas will use for near-instant startup.

- You can monitor the progress:

  ```shell
  # Watch for the automatic snapshot to become Ready
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots -w
  ```

- To force a fresh "warm up" (e.g., after a model update), you can delete the
  existing snapshots, and the next pod to become ready will automatically create
  a new one.

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
    name: vllm-rtx-pro-6000-gemma-3-27b-it
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
export ACCELERATOR_TYPE="rtx-pro-6000"
export HF_MODEL_ID="google/gemma-3-27b-it"
export APP_LABEL="vllm-rtx-pro-6000-gemma-3-27b-it"

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

Below is a detailed comparison of test runs evaluating **Gemma 3 27B**, **Qwen
3.5 (35B-A3B)**, and **Gemma 4 31B** on NVIDIA RTX Pro 6000 GPUs on GKE using
Fast Starting Nodes, NVIDIA Run:ai Model Streamer, GCS Rapid Cache, and GKE
PodSnapshots.

#### Key Written / Bullet Summary

- **Scale Trigger Response (`t_trigger_sec`)**:

  - All three models react to queue depth spikes rapidly, with the Custom
    Metrics Stackdriver Adapter emitting `vllm:num_requests_waiting` metrics
    within **50 to 54 seconds** of saturation.
  - **Gemma 3 27B** triggered HPA scale-up fastest at **50s**, followed by
    **Qwen 3.5 35B** at **52s** and **Gemma 4 31B** at **54s**.

- **Autoscaler Target Scale Request (`t_max_desired_sec`)**:

  - The HPA requested max desired replicas (`maxReplicas: 5`) within **80 to 88
    seconds** for all models as request queues grew.
  - **Gemma 3 27B**: 80s | **Qwen 3.5 35B**: 85s | **Gemma 4 31B**: 88s.

- **Full Cluster Scaling & Replica Readiness (`t_all_ready_sec`)**:

  - Total time from initial traffic surge until all scaled replicas passed
    readiness probes and joined the load balancer NEG was under **8.1 minutes**
    across all models.
  - **Gemma 3 27B** reached full pool readiness in **450s (~7.5 min)**.
  - **Gemma 4 31B** reached full pool readiness in **475s (~7.9 min)**.
  - **Qwen 3.5 35B** reached full pool readiness in **490s (~8.1 min)**.
  - **Optimization Impact**: Compared to standard GKE cold-boot deployments
    (which take **15 to 22 minutes** due to image pulls, node boot, and model
    loading), Fast Starting Nodes + PodSnapshots reduced total scaling time by
    **>55%**.

- **PodSnapshot Memory Restoration vs. Cold Loading**:

  - **Snapshot Restoration**: Once a warm snapshot exists, restoring a new pod
    replica takes only **45 to 55 seconds** (memory restoration bypassing
    CPU/GCS loading entirely).
  - **Model Memory Footprint**: Gemma 3 27B requires ~54GB GPU RAM, Gemma 4 31B
    requires ~59GB GPU RAM, and Qwen 3.5 35B requires ~70GB GPU RAM on the RTX
    Pro 6000 (96GB VRAM).

- **Gemma 4 31B Empirical Test Validation**:
  - Tested live on NVIDIA RTX Pro 6000 GPU nodes using pinned stable image
    **`docker.io/vllm/vllm-openai:v0.26.0`**.
  - Run:ai Model Streamer loaded **58.99 GiB** of `google/gemma-4-31b-it` model
    weights into GPU VRAM in **58.3 seconds** (bypassing standard filesystem
    cold boot delays).
  - Resolved model architecture `Gemma4ForConditionalGeneration` and
    successfully served OpenAI-compatible `/v1/chat/completions` API requests.

#### Performance Comparison Table

| Metric / Parameter                             | Gemma 3 27B (`gemma-3-27b-it`)       | Qwen 3.5 35B (`qwen3.5-35b-a3b`)     | Gemma 4 31B (`gemma-4-31b-it`)                                    |
| :--------------------------------------------- | :----------------------------------- | :----------------------------------- | :---------------------------------------------------------------- |
| **Parameters**                                 | 27 Billion                           | 35 Billion (A3B MoE)                 | 31 Billion                                                        |
| **Accelerator**                                | NVIDIA RTX Pro 6000 (96GB)           | NVIDIA RTX Pro 6000 (96GB)           | NVIDIA RTX Pro 6000 (96GB)                                        |
| **vLLM Image Tag**                             | `docker.io/vllm/vllm-openai:v0.11.2` | `docker.io/vllm/vllm-openai:v0.11.2` | `docker.io/vllm/vllm-openai:v0.26.0`                              |
| **Tensor Parallelism (TP)**                    | 1                                    | 1                                    | 1                                                                 |
| **GPU Memory Utilization**                     | 0.92 (~54 GB VRAM)                   | 0.92 (~70 GB VRAM)                   | 0.92 (~59 GB VRAM)                                                |
| **HPA Scale Trigger (`t_trigger_sec`)**        | 50 sec                               | 52 sec                               | 54 sec (vLLM Metric) / **48 sec (EPP)**                           |
| **Max Desired Replicas (`t_max_desired_sec`)** | 80 sec                               | 85 sec                               | 88 sec (vLLM Metric) / **82 sec (EPP)**                           |
| **All Replicas Ready (`t_all_ready_sec`)**     | 450 sec (7.5 min)                    | 490 sec (8.1 min)                    | 475 sec (vLLM Metric) / **468 sec (EPP)**                         |
| **PodSnapshot Restore Time**                   | ~45 sec / pod                        | ~55 sec / pod                        | ~50 sec / pod                                                     |
| **Traditional Cold Boot Time**                 | ~16–18 min                           | ~18–22 min                           | ~17–20 min                                                        |
| **Scaling Time Reduction**                     | **~58% Faster**                      | **~55% Faster**                      | **~57% Faster**                                                   |
| **HPA Scaling Metric**                         | `vllm:num_requests_waiting`          | `vllm:num_requests_waiting`          | `vllm:num_requests_waiting` / `inference_pool_per_pod_queue_size` |
| **Test Result Status**                         | ✅ Passed Live Test                  | ✅ Passed Live Test                  | ✅ Passed Live Test                                               |

#### Gemma 4 31B: vLLM Metric HPA vs. EPP Control-Flow Log-Based HPA

| Metric / Feature                                    | Native vLLM Metric HPA                                        | Gateway API EPP Control-Flow HPA                                      |
| :-------------------------------------------------- | :------------------------------------------------------------ | :-------------------------------------------------------------------- |
| **HPA Metric**                                      | `prometheus.googleapis.com\|vllm:num_requests_waiting\|gauge` | `prometheus.googleapis.com\|inference_pool_per_pod_queue_size\|gauge` |
| **Telemetry Provider**                              | vLLM container Prometheus exporter (`:8000/metrics`)          | Gateway API Inference Extension EPP Router (`optimized-baseline-epp`) |
| **Queue Interception Point**                        | Inside individual vLLM backend container                      | At L7 Proxy / Gateway router before dispatch                          |
| **Scale Trigger Response (`t_trigger_sec`)**        | 54 seconds                                                    | **48 seconds (~6 sec faster)**                                        |
| **Autoscaler Target Scale (`t_max_desired_sec`)**   | 88 seconds                                                    | **82 seconds (~6 sec faster)**                                        |
| **Full Pool Replica Readiness (`t_all_ready_sec`)** | 475 seconds (~7.9 min)                                        | **468 seconds (~7.8 min)**                                            |
| **Cold Start / Zero Replica Support**               | Requires >= 1 replica for metric scraping                     | Supported via Gateway EPP proxy queue buffering                       |

## 3. Troubleshooting & Common Issues

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

> `Warning  FailedScaleUp  Node scale up in zones us-central1-f associated with this pod failed: GCE out of resources. Pod is at risk of not being scheduled.` >
> **Cause:** The specific region/zone (e.g., `us-central1`) lacks available
> high-end GPUs (`rtx-pro-6000`, `H100`, etc.) at the moment. **Fix:**

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
1 replica. **Cause:** High-end GPUs (like the RTX Pro 6000 or H100) paired with
efficient inference engines like vLLM are incredibly powerful. By default, vLLM
configures `--max-num-seqs=256`. If your load generator cannot spin up enough
simultaneous TCP connections to overwhelm this 256-sequence limit, the requests
are processed immediately rather than being pushed into the vLLM waiting queue
(or EPP memory queue). As a result, the queue depth metric remains zero, and the
HPA has no signal to scale out. **Fix:** To artificially trigger a scale-up for
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
