# Inference at scale

## Preparation

*   Ensure that your `MLP_ENVIRONMENT_FILE` is configured

    ```sh
    cat ${MLP_ENVIRONMENT_FILE} && \
    source ${MLP_ENVIRONMENT_FILE}
    ```

* Switch to inference directory

  ```sh
  cd ${INFERENCE_SCALE_DIR}
  ```

## Pre-requisites

*   GKE cluster running inference workload as shown in previous examples.
*   Export the metrics from the vLLM server to Cloud Monitoring as shown in [metric section](./../README.md#production-metrics).
  

## Metrics to scale the inference on

There are different metrics available that could be used to scale your inference workloads
on GKE:

*   Server metrics: LLM inference servers vLLM provides workload-specific
performance metrics. GKE simplifies scraping of those metrics and autoscaling
the workloads based on these server-level metrics. You can use these metrics to
gain visibility into performance indicators like batch size, queue size, and
decode latencies.
In case of vLLM, [production metrics class](https://docs.vllm.ai/en/latest/serving/metrics.html)
exposes a number of useful metrics which GKE can use to horizontally scale
inference workloads.

    ```sh
    vllm:num_requests_running - Number of requests currently running on GPU.
    vllm:num_requests_waiting - Number of requests waiting to be processed
    ```
    Here is an example of the metric `vllm:num_requests_running` in metrics explorer
    ![metrics graph](./cloud-monitoring-metrics-inference.png)

*   GPU metrics: Metrics related to the GPU.

    ```none
    GPU Utilization (DCGM_FI_DEV_GPU_UTIL) - Measures the duty cycle, which is the 
    amount of time that the GPU is active.

    GPU Memory Usage (DCGM_FI_DEV_FB_USED) - Measures how much GPU memory is being 
    used at a given point in time. This is useful for workloads that implement
    dynamic allocation of GPU memory.
    ```

*   CPU metrics: Since the inference workloads primarily rely on GPU resources,
we don't recommend CPU and memory utilization as the only indicators of the
amount of resources a job consumes. Therefore, using CPU metrics alone for
 autoscaling can lead to suboptimal performance and costs.

HPA is an efficient way to ensure that your model servers scale appropriately
with load. Fine-tuning the HPA settings is the primary way to align your 
provisioned hardware cost with traffic demands to achieve your inference server
performance goals.

We recommend setting these HPA configuration options:

*   Stabilization window: Use this HPA configuration option to prevent rapid
replica count changes due to fluctuating metrics. Defaults are 5 minutes for
scale-down (avoiding premature downscaling) and 0 for scale-up (ensuring responsiveness).
Adjust the value based on your workload's volatility and your preferred responsiveness.

*   Scaling policies: Use this HPA configuration option to fine-tune the scale-up
and scale-down behavior. You can set the "Pods" policy limit to specify the
absolute number of replicas changed per time unit, and the "Percent" policy
limit to specify by the percentage change.

For more details, see Horizontal pod autoscaling in the Google Cloud Managed 
Service for Prometheus [documentation](https://cloud.google.com/kubernetes-engine/docs/horizontal-pod-autoscaling).


### Autoscale with HPA metrics

*   Install the Custom Metrics Adapter. This adapter makes the custom metric that you 
    exported to Cloud Monitoring visible to the HPA. For more details, see HPA 
    in the [Google Cloud Managed Service for Prometheus documentation](https://cloud.google.com/stackdriver/docs/managed-prometheus/hpa).

    ```sh
     kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
    ```

*   Deploy an metric based HPA resource that based on your preferred custom metric.

    Choose one of the options below `Queue-depth` or `Batch-size` to configure
    the HPA resource in your manifest:

    *   Queue-depth

        ```sh
        sed -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|" hpa-vllm-openai-queue-size.yaml

        kubectl apply -f hpa-vllm-openai-queue-size.yaml
        ```

    *   Batch-size

        ```sh
        sed -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|" hpa-vllm-openai-batch-size.yaml

        kubectl apply -f hpa-vllm-openai-batch-size.yaml
        ```

    > NOTE: Adjust the appropriate target values for `vllm:num_requests_running`
      or `vllm:num_requests_waiting` in the yaml file.

    Once the HPA has been created on a given metric, GKE will autoscale the model
    deployment pods when the metric goes over the specified threshold.
    It will look something like the following:

    ```sh
    kubectl get hpa vllm-openai-hpa -n ${MLP_KUBERNETES_NAMESPACE} --watch
    NAME              REFERENCE                TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
    vllm-openai-hpa   Deployment/vllm-openai   1/1       1         5         1          27s
    vllm-openai-hpa   Deployment/vllm-openai   0/1       1         5         1          76s
    vllm-openai-hpa   Deployment/vllm-openai   1/1       1         5         1          95s
    ```

   You can also see the new pods coming online:

   ```sh
   kubectl get pods -n ${MLP_KUBERNETES_NAMESPACE} --watch
   NAME                           READY   STATUS      RESTARTS   AGE
   vllm-openai-767b477b77-2jm4v   1/1     Running     0          3d17h
   vllm-openai-767b477b77-82l8v   0/1     Pending     0          9s
   ```

   And evetually, the pods will be scaled up:

   ```sh
   kubectl get pods -n ml-serve --watch
   NAME                           READY   STATUS      RESTARTS   AGE
   vllm-openai-767b477b77-2jm4v   1/1     Running     0          3d17h
   vllm-openai-767b477b77-82l8v   1/1     Running     0          111s
   ```

If there are GPU resources available on the same node, the new pod may start on
it. Otherwise, a new node will be spun up by the autosclare with the required
resources and the new pod will be started on it.


[dashboard-readme]: ./dashboard/README.md