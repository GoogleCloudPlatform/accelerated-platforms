# Scalable and Distributed LLM Inference on GKE with vLLM

This guide assumes you possess a fine-tuned large language model (LLM) ready for production deployment. We'll focus on serving your model within the ML Platform on Google Kubernetes Engine (GKE), utilizing the vLLM framework and exploring various scaling strategies.

**Prerequisites**

- A deployed ML Platform Playground on GKE (refer to the repository for instructions).
- A prepared test dataset from the data preparation example.
- A fine-tuned or base model for serving.

## Serving LLMs

vLLM provides three core GPU strategies for model inference:

- **Single GPU:** Suited for models that fit comfortably within a single GPU's memory constraints.
- **Single-Node Multi-GPU (Tensor Parallelism):** Distributes a large model across multiple GPUs within a single node, enhancing inference speed for computationally intensive tasks.
- **Multi-Node Multi-GPU (Tensor & Pipeline Parallelism):** Combines both tensor and pipeline parallelism to scale exceptionally large models across multiple nodes, maximizing throughput and minimizing latency.

The examples primarily focus on the first two strategies, as they exploit the distributed computing capabilities of the ML Platform on GKE. The strategies may differ depending on business requirements and available resources within an organization.

The fine-tuned Gemma 2 9B IT model in the fine-tuning end-to-end example is too large to fit in a single GPU, but it can fit on a single node with multiple GPUs with [tensor parallelism](https://huggingface.co/docs/text-generation-inference/en/conceptual/tensor_parallelism). The tensor parallel size is the number of GPUs you want to use. For example, if you have 4 GPUs in a single node, you can set the tensor parallel size to 4\.

The model weight size, expected response latency and scale requirements impact the choice of accelerators to be used by the inference engine. The following examples showcase recommendations for loading model weights (i.e. Gemma 2 9B IT) and how to automatically scale the inference engine based on demand.

### Application start-up and Model loading Optimizations

To spin up a pod running an LLM related application, the start-up time consists of several portions:

- Container initialization (image pull)
- Application startup time

The container initialization time is primarily the container image pull time, while for a typical python LLM application using vLLM, the application startup time is mostly the time spent loading LLM model weights.

#### Accelerate the container image pull

The [Secondary Boot Disk](https://cloud.google.com/kubernetes-engine/docs/how-to/data-container-image-preloading) (SBD) capability for GKE, stores container images in an additional disk that is attached to the GKE node(s). This way, during the start-up of the pod, the container image download step is no longer required as it is available to the pod and the container image can start the container. This step would typically require automation to load container images into a [disk image](https://cloud.google.com/kubernetes-engine/docs/how-to/data-container-image-preloading#images) which will be mounted by the SBD feature.

[Image streaming](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming) is also an important capability to improve container image pulling by caching and use the cache for subsequent image pulls. It is also able to stream image data from the source, rather than waiting for the image to be completely pulled. There are a few [requirements](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming#requirements) and [limitations](https://cloud.google.com/kubernetes-engine/docs/how-to/image-streaming#limitations) to note, one being that the image must be hosted in Artifact Registry.

#### Accelerate the model weight loading

There are several ways to accelerate the model weight loading task. Each has its advantages and disadvantages depending on the desired performance, the amount of effort required to manage the workflow to make the model weights available, and costs for the services utilized.

We will cover advantages and disadvantages of loading weights from the following data stores:

- GCS Fuse ([example](/use-cases/inferencing/serving/vllm/gcsfuse))
- Persistent Disk ([example](/use-cases/inferencing/serving/vllm/persistent-disk))
- NFS backed by FileStore

The data stores above that are linked have examples.

#### Compare the model weight loading options

Each category depends on organization capabilities and desired outcome:

| Manageability                  |                   |                                                                                              |
| :----------------------------- | :---------------- | :------------------------------------------------------------------------------------------- |
| Convenience of use             | GCSFuse           | Tunables in the same manifest                                                                |
|                                | Persistent Volume | Tunables(`read_ahead_kb` etc) are in the PV's manifest                                       |
|                                | NFS Volume        | A privileged initContainer is needed to tune performance                                     |
| Model Update                   | GCSFuse           | just copy new model weights to GCS bucket                                                    |
|                                | Persistent Volume | an extra workflow is needed                                                                  |
|                                | NFS Volume        | just copy new model weights to NFS                                                           |
| Performance                    |                   |                                                                                              |
| :----------------------------- | :---------------- | :------------------------------------------------------------------------------------------- |
| Warm-up                        | GCSFuse           | Warm-up needed                                                                               |
|                                | Persistent Volume | No warm-up                                                                                   |
|                                | NFS Volume        | No warm-up                                                                                   |
| Max read throughput            | GCSFuse           | Depending on node disk type and size                                                         |
|                                | Persistent Volume | Depending on volume type and size                                                            |
|                                | NFS Volume        | Depending on FileStore volume                                                                |
| Price                          |                   |                                                                                              |
| :----------------------------- | :---------------- | :------------------------------------------------------------------------------------------- |
| Over provisioning requirements | GCSFuse           | Node disk over-provisioning needed. May require additional compute memory for larger models. |
|                                | Persistent Volume | Over-provisioning is shared by up to 100 nodes                                               |
|                                | NFS Volume        | Over-provisioning can be shared by other applications                                        |
| Cost summary\*                 | GCSFuse           | $$\*\*                                                                                       |
|                                | Persistent Volume | $                                                                                            |
|                                | NFS Volume        | $$$                                                                                          |

\* This will vary based on your implementation

\*\* for larger LLM's i.e. 70B+ parameter

Enabling [GCE Fuse parallel downloads](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/cloud-storage-fuse-csi-driver#parallel-download) can also improve model weight downloading time to the container image. To maximize the performance of this capability it is recommended to also provision [Local SSDs](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/local-ssd) for your nodes.

## LLM Inference
With your LLM efficiently deployed and optimized for startup and model loading, the next crucial step is performing inference. This involves using your model to generate predictions or responses based on input data.

### Types of inferencing

Inference can be executed in two distinct modes:
- Batch Inference
- Real-time inference

Batch inference and real-time inference are two distinct approaches to generating predictions from machine learning models. They differ primarily in how data is processed and how quickly predictions are delivered.

#### Batch Inference

- **Data Processing:** Processes data in batches or groups. Predictions are generated for multiple input samples at once.
- **Latency:** Higher latency (time taken to generate predictions) as it involves processing a batch of data.
- **Throughput:** Can handle high throughput (volume of data processed) efficiently
- **Sample Use cases:**
  - Pre-computing recommendations: Retailers might pre-compute product recommendations for all users overnight and display next day
  - Generating reports and analysis
  - Image Processing
  - Data enrichment
  - Training data set creation
- Two implementation examples of this are available:
  - Model evaluation prediction step [example](/use-cases/model-fine-tuning-pipeline/model-eval/README.md)
  - Inferencing [example](/use-cases/inferencing/batch-inference)

#### Real-time Inference

- **Data Processing:** Processes data individually as it arrives. Predictions are generated for each input sample immediately
- **Latency:** Low latency is critical, as predictions need to be generated quickly for real-time applications
- **Throughput:** Might have limitations on throughput, especially if the model is complex or resources are constrained
- **Sample Use cases:**
  - Online applications that require instant response:
    - Chatbots
    - Personalized recommendation
    - Fraud detection systems
    - Self-driving cars
    - Real-time language translation or speech recognition
- For an Implementation example, please check this document [Distributed Inferencing on vLLM](/use-cases/inferencing/serving/vllm)

## Production Monitoring and Scaling

The deployment of a machine learning model marks the beginning of a new phase: monitoring and maintenance. 

Production monitoring serves as a diagnostic tool, enabling us to track performance metrics, identify potential issues, and ensure the model remains accurate and reliable in a live environment.

- **Production Metrics:** Prometheus exposed metrics help provide crucial metrics to help provide inference engine details for observation and decision making.
  - Prometheus exposed metrics can automatically be captured once configured utilizing [Google Cloud Managed Service for Prometheus.](https://cloud.google.com/stackdriver/docs/managed-prometheus)
  - Utilize the `/metrics` endpoint exposed by vLLM to gain insights into crucial system health indicators, including request latency, throughput, and GPU memory consumption.
- **Custom Metrics and HPA:**  
  Define custom metrics relevant to your specific use case and configure the Horizontal Pod Autoscaler ([HPA](https://cloud.google.com/kubernetes-engine/docs/concepts/horizontalpodautoscaler)) to dynamically scale the number of model replicas in response to real-time demand, optimizing resource utilization.  
  There are different metrics available that can be used to scale your inference workload on GKE:

- **Server (inference engine) metrics**: vLLM provides workload-specific performance metrics. GKE simplifies scraping of those metrics and autoscaling the workloads based on these server-level metrics. You can use these metrics to gain visibility into performance indicators like batch size, queue size, and decode latencies.  
  In the case of vLLM, [production metrics class](https://docs.vllm.ai/en/latest/serving/metrics.html) exposes a number of useful metrics which GKE can use to horizontally scale inference workloads.

  - vllm:num_requests_running \- Number of requests currently running on GPU.
  - vllm:num_requests_waiting \- Number of requests waiting to be processed

- **GPU metrics**: Metrics related to the GPU utilization.

  - GPU Utilization (DCGM_FI_DEV_GPU_UTIL) \- Measures the duty cycle, which is the amount of time that the GPU is active.
  - GPU Memory Usage (DCGM_FI_DEV_FB_USED) \- Measures how much GPU memory is being used at a given point in time. This is useful for workloads that implement dynamic allocation of GPU memory.

- **CPU metrics**: Since the inference workloads primarily rely on GPU resources, we don't recommend CPU and memory utilization as the only indicators of the amount of resources a job consumes. Therefore, using CPU metrics alone for autoscaling can lead to suboptimal performance and costs.

  Horizontal Pod Autoscaling (HPA) is an efficient way to ensure that your model servers scale appropriately with load. Fine-tuning the HPA settings is the primary way to align your provisioned hardware cost with traffic demands to achieve your inference server performance goals.

We recommend setting these HPA configuration options:

- Stabilization window: Use this HPA configuration option to prevent rapid replica count changes due to fluctuating metrics. Defaults are 5 minutes for scale-down (avoiding premature scale-down) and 0 for scale-up (ensuring responsiveness). Adjust the value based on your workload's volatility and your preferred responsiveness.
- Scaling policies: Use this HPA configuration option to fine-tune the scale-up and scale-down behavior. You can set the "Pods" policy limit to specify the absolute number of replicas changed per time unit, and the "Percent" policy limit to specify the percentage change.
- Also, depending on the [inference engine](https://cloud.google.com/kubernetes-engine/docs/best-practices/machine-learning/inference/autoscaling), you can also determine appropriate metrics to help Kubernetes facilitate the scaling based on demand.

An example of collecting metrics and importing a dashboard are available [here](/use-cases/inferencing/serving/vllm/metrics). Once the metrics are available, they can be leveraged for autoscaling with this [example](/use-cases/inferencing/serving/vllm/autoscaling).

For the implementation examples, please [check out this document](/use-cases/inferencing/serving/vllm)
