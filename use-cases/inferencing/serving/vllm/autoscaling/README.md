# vLLM autoscaling with horizontal pod autoscaling (HPA)

## Pre-requisites

- A model is deployed using one of the vLLM guides
  - [Distributed Inference and Serving with vLLM using GCSFuse](/use-cases/inferencing/serving/vllm/gcsfuse/README.md)
  - [Distributed Inference and Serving with vLLM using Hyperdisk ML](/use-cases/inferencing/serving/vllm/hyperdisk-ml/README.md)
  - [Distributed Inference and Serving with vLLM using Persistent Disk](/use-cases/inferencing/serving/vllm/persistent-disk/README.md)
- Metrics are being scraped from the vLLM server as shown in the [vLLM Metrics](/use-cases/inferencing/serving/vllm/metrics/README.md) guide.

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/inferencing/serving/vllm/autoscaling
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- Configure the environment

  > Set the environment variables based on the accelerator and model storage type used to serve the model.
  > The default values below are set for NVIDIA L4 GPUs and persistent disk.

  | Variable      | Description                                        | Example |
  | ------------- | -------------------------------------------------- | ------- |
  | ACCELERATOR   | Type of GPU accelerator used (a100, h100, l4)      | l4      |
  | MODEL_STORAGE | Type of storage used for the model (gcs, hdml, pd) | pd      |

  ```sh
  ACCELERATOR="l4"
  MODEL_STORAGE="pd"
  ```

## Scaling metrics

There are different metrics available that can be used to scale your inference workload on GKE:

- Server metrics: LLM inference servers vLLM provides workload-specific
  performance metrics. GKE simplifies scraping of those metrics and autoscaling
  the workloads based on these server-level metrics. You can use these metrics to
  gain visibility into performance indicators like batch size, queue size, and
  decode latencies.

  In the case of vLLM, [production metrics class](https://docs.vllm.ai/en/latest/serving/metrics.html)
  exposes a number of useful metrics which GKE can use to horizontally scale
  inference workloads.

  - `vllm:num_requests_running` - Number of requests currently running on GPU.
  - `vllm:num_requests_waiting `- Number of requests waiting to be processed

- GPU metrics: Metrics related to the GPU utilization.

  - GPU Utilization (`DCGM_FI_DEV_GPU_UTIL`) - Measures the duty cycle, which is the
    amount of time that the GPU is active.
  - GPU Memory Usage (`DCGM_FI_DEV_FB_USED`) - Measures how much GPU memory is being
    used at a given point in time. This is useful for workloads that implement
    dynamic allocation of GPU memory.=

- CPU metrics: Since the inference workloads primarily rely on GPU resources,
  we don't recommend CPU and memory utilization as the only indicators of the
  amount of resources a job consumes. Therefore, using CPU metrics alone for
  autoscaling can lead to suboptimal performance and costs.

Horizontal pod autoscaling (HPA) is an efficient way to ensure that your model servers scale appropriately
with load. Fine-tuning the HPA settings is the primary way to align your
provisioned hardware cost with traffic demands to achieve your inference server
performance goals.

We recommend setting these HPA configuration options:

- Stabilization window: Use this HPA configuration option to prevent rapid
  replica count changes due to fluctuating metrics. Defaults are 5 minutes for
  scale-down (avoiding premature scale-down) and 0 for scale-up (ensuring responsiveness).
  Adjust the value based on your workload's volatility and your preferred responsiveness.

- Scaling policies: Use this HPA configuration option to fine-tune the scale-up
  and scale-down behavior. You can set the "Pods" policy limit to specify the
  absolute number of replicas changed per time unit, and the "Percent" policy
  limit to specify by the percentage change.

For more details, see Horizontal pod autoscaling in the Google Cloud Managed
Service for Prometheus [documentation](https://cloud.google.com/kubernetes-engine/docs/horizontal-pod-autoscaling).

### Autoscale with HPA metrics

- Install the Custom Metrics Adapter. This adapter makes the custom metric that you
  exported to Cloud Monitoring visible to the HPA. For more details, see the [Horizontal pod autoscaling (HPA)](https://cloud.google.com/stackdriver/docs/managed-prometheus/hpa)
  document in the [Google Cloud Managed Service for Prometheus (GMP)](https://cloud.google.com/stackdriver/docs/managed-prometheus) documentation.

  ```sh
   kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
  ```

  ```
  namespace/custom-metrics created
  serviceaccount/custom-metrics-stackdriver-adapter created
  clusterrolebinding.rbac.authorization.k8s.io/custom-metrics:system:auth-delegator created
  rolebinding.rbac.authorization.k8s.io/custom-metrics-auth-reader created
  clusterrole.rbac.authorization.k8s.io/custom-metrics-resource-reader created
  clusterrolebinding.rbac.authorization.k8s.io/custom-metrics-resource-reader created
  deployment.apps/custom-metrics-stackdriver-adapter created
  service/custom-metrics-stackdriver-adapter created
  apiservice.apiregistration.k8s.io/v1beta1.custom.metrics.k8s.io created
  apiservice.apiregistration.k8s.io/v1beta2.custom.metrics.k8s.io created
  apiservice.apiregistration.k8s.io/v1beta1.external.metrics.k8s.io created
  clusterrole.rbac.authorization.k8s.io/external-metrics-reader configured
  clusterrolebinding.rbac.authorization.k8s.io/external-metrics-reader created
  ```

- Configure the resources

  ```sh
  git restore manifests/hpa-vllm-openai-batch-size.yaml manifests/hpa-vllm-openai-queue-size.yaml
  sed \
  -i -e "s|V_ACCELERATOR|${ACCELERATOR}|" \
  -i -e "s|V_MODEL_STORAGE|${MODEL_STORAGE}|" \
  manifests/hpa-vllm-openai-batch-size.yaml \
  manifests/hpa-vllm-openai-queue-size.yaml
  ```

- Deploy an metric based HPA resource that based on your preferred custom metric.

  Choose one of the options below `Queue-depth` or `Batch-size` to configure
  the HPA resource in your manifest:

  > Adjust the appropriate target values for `vllm:num_requests_running`
  > or `vllm:num_requests_waiting` in the yaml file.

  - Queue-depth

    ```sh
    kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/hpa-vllm-openai-queue-size.yaml
    ```

    ```
    horizontalpodautoscaler.autoscaling/vllm-openai-hpa created
    ```

  - Batch-size

    ```sh
    kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/hpa-vllm-openai-batch-size.yaml
    ```

    ```
    horizontalpodautoscaler.autoscaling/vllm-openai-hpa created
    ```

  Once the HPA has been created on a given metric, GKE will autoscale the model
  deployment pods when the metric goes over the specified threshold.

- Get the current state of the HPA

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get hpa/vllm-openai-hpa
  ```

  ```
  NAME              REFERENCE                        TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
  vllm-openai-hpa   Deployment/vllm-openai-XXX-XXX   0/10      1         5         1          ##m##s
  ```

- When the metrics threshold is crossed, new pods will be created.
  You can use the [Benchmarking with Locust](/use-cases/inferencing/benchmark/README.md) guide to generate load on the model.

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get pods --watch
  ```

  ```
  NAME                                   READY   STATUS      RESTARTS   AGE
  vllm-openai-XXX-XXX-##########-#####   1/1     Running     0          ##h##m
  vllm-openai-XXX-XXX-##########-#####   0/1     Pending     0          ##s
  ```

  And eventually, the pods will be scaled up:

  ```
  NAME                                   READY   STATUS      RESTARTS   AGE
  vllm-openai-XXX-XXX-##########-#####   1/1     Running     0          ##h##m
  vllm-openai-XXX-XXX-##########-#####   1/1     Running     0          ##m
  ```

  If there are GPU resources available available in the cluster, the new pod will start.
  Otherwise a new node, with the required GPU resources, will be created by the Cluster autoscaler and the pod will be scheduled.

## What's next

- [Benchmarking with Locust](/use-cases/inferencing/benchmark/README.md)
- [Batch inference on GKE](/use-cases/inferencing/batch-inference/README.md)
