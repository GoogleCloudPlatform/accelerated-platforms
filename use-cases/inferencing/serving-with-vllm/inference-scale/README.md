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

We have couple of options to scale the inference workload on GKE using the HPA 
and custom metrics adapter.

*   Scale pod on the same node as the existing inference workload.
*   Scale pod on the other nodes in the same node pool as the existing inference workload.  

*   Install the Custom Metrics Adapter. This adapter makes the custom metric that you 
    exported to Cloud Monitoring visible to the HPA. For more details, see HPA 
    in the [Google Cloud Managed Service for Prometheus documentation](https://cloud.google.com/stackdriver/docs/managed-prometheus/hpa).

    ```sh
     kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
    ```

*   Deploy an metric based HPA resource that based on your preferred custom metric.

    Select **ONE** of the options below `Queue-depth` or `Batch-size` to configure
    the HPA resource in your manifest:

    *   Queue-depth

        ```sh
        sed -i -e "s/_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}" hpa-vllm-openai-queue-size.yaml

        kubectl apply -f manifests/inference-scale/hpa-vllm-openai-queue-size.yaml
        ```

    *   Batch-size

        ```sh
        sed -i -e "s/_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}" hpa-vllm-openai-batch-size.yaml

        kubectl apply -f manifests/inference-scale/hpa-vllm-openai-batch-size.yaml
        ```

    > NOTE: Adjust the appropriate target values for `vllm:num_requests_running`
      or `vllm:num_requests_waiting` in the yaml file.

    Below is an example of the batch size HPA scale test below:

    ```sh
    kubectl get hpa vllm-openai-hpa -n ${MLP_KUBERNETES_NAMESPACE} --watch
    NAME              REFERENCE                TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
    vllm-openai-hpa   Deployment/vllm-openai   0/10      1         5         1          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   13/10     1         5         1          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   17/10     1         5         2          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   12/10     1         5         2          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   17/10     1         5         2          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   14/10     1         5         2          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   17/10     1         5         2          XXXX
    vllm-openai-hpa   Deployment/vllm-openai   10/10     1         5         2          XXXX
    ```

```sh
kubectl get pods -n ${MLP_KUBERNETES_NAMESPACE} --watch
NAME                           READY   STATUS      RESTARTS   AGE
gradio-6b8698d7b4-88zm7        1/1     Running     0          10d
model-eval-2sxg2               0/1     Completed   0          8d
vllm-openai-767b477b77-2jm4v   1/1     Running     0          3d17h
vllm-openai-767b477b77-82l8v   0/1     Pending     0          9s
```

Pod scaled up
```sh
kubectl get pods -n ml-serve --watch
NAME                           READY   STATUS      RESTARTS   AGE
gradio-6b8698d7b4-88zm7        1/1     Running     0          10d
model-eval-2sxg2               0/1     Completed   0          8d
vllm-openai-767b477b77-2jm4v   1/1     Running     0          3d17h
vllm-openai-767b477b77-82l8v   1/1     Running     0          111s
```

The new pod is deployed on a node triggered by the cluster autoscaler.
> NOTE: The existing node where inference workload was deployed in this case had
only two GPUS. Hence a new node is required to deploy the copy pod of inference workload.

```sh
kubectl describe pods vllm-openai-767b477b77-82l8v -n ${MLP_KUBERNETES_NAMESPACE}

Events:
  Type     Reason                  Age    From                                   Message
  ----     ------                  ----   ----                                   -------
  Warning  FailedScheduling        4m15s  gke.io/optimize-utilization-scheduler  0/3 nodes are available: 1 Insufficient ephemeral-storage, 1 Insufficient nvidia.com/gpu, 2 node(s) didn't match Pod's node affinity/selector. preemption: 0/3 nodes are available: 1 No preemption victims found for incoming pod, 2 Preemption is not helpful for scheduling.
  Normal   TriggeredScaleUp        4m13s  cluster-autoscaler                     pod triggered scale-up: [{https://www.googleapis.com/compute/v1/projects/gkebatchexpce3c8dcb/zones/us-east4-a/instanceGroups/gke-kh-e2e-l4-2-c399c5c0-grp 1->2 (max: 20)}]
  Normal   Scheduled               2m40s  gke.io/optimize-utilization-scheduler  Successfully assigned ml-serve/vllm-openai-767b477b77-82l8v to gke-kh-e2e-l4-2-c399c5c0-vvm9
  Normal   SuccessfulAttachVolume  2m36s  attachdetach-controller                AttachVolume.Attach succeeded for volume "model-weights-disk-1024gb-zone-a"
  Normal   Pulling                 2m29s  kubelet                                Pulling image "vllm/vllm-openai:v0.5.3.post1"
  Normal   Pulled                  2m25s  kubelet                                Successfully pulled image "vllm/vllm-openai:v0.5.3.post1" in 4.546s (4.546s including waiting). Image size: 5586843591 bytes.
  Normal   Created                 2m25s  kubelet                                Created container inference-server
  Normal   Started                 2m25s  kubelet                                Started container inference-server
```

[dashboard-readme]: ./dashboard/README.md