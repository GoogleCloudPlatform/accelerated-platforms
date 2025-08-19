# GKE Inference reference architecture

> [!IMPORTANT]  
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2025-07-01 (YYYY-MM-DD)

This document outlines the reference architecture for deploying and managing
inference workloads, particularly on Google Kubernetes Engine (GKE). It serves
as a foundational guide for building robust and scalable inference solutions.
This implementation is an extension of the
[GKE Base Platform](/docs/platforms/gke/base/README.md) tailored for inference
workloads.

<!-- Source: https://gcpdraw.googleplex.com/diagrams/7822a266-c831-4374-a1e8-a8f67a174d89 -->

![Reference Architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/images/reference_architecture_simple.svg)

Refer to the [Getting Started](#getting-started) section below for instructions
on setting up the infrastructure described in this document.

## Purpose

The primary goal of this reference architecture is to provide a best practices,
well-defined framework for serving models. It aims to:

- **Standardize Deployments**: Offer a consistent and repeatable methodology for
  deploying inference workloads, reducing operational complexity and promoting
  GitOps principles.
- **Optimize for Performance & Cost**: Leverage GKE's capabilities, including
  autoscaling and potential hardware acceleration (GPUs, TPUs), to ensure
  low-latency, high-throughput inference while managing costs effectively
  through efficient resource utilization.
- **Enable Scalability**: Design workloads that can automatically scale based on
  real-time demand, ensuring responsiveness and resource efficiency, and
  handling peak loads gracefully.
- **Promote \*Ops Best Practices**: Incorporate industry best practices for the
  model lifecycle, including model versioning, continuous integration/continuous
  deployment (CI/CD) for models and infrastructure, monitoring, logging, and
  robust security in an inference context.
- **Accelerate Implementation**: Provide a clear and actionable path to a
  working inference workload through well-defined components, examples, and
  integrated Google Cloud services.

## Features & Capabilities

This reference architecture provides a foundation for:

- Deploying various types of models for real-time (online) or batch (offline)
  inference.
- Utilizing hardware accelerators like GPUs and TPUs for computationally
  intensive models.
- Implementing robust monitoring and logging for inference workloads.
- Managing model versions and rollouts.
- Integrating with broader \*Ops pipelines.
- Ensuring secure and reliable model serving.

## Architectural Principles

- **Scalability (Horizontal and Vertical)**: The system must be able to scale
  out (add more instances) horizontally to handle increased request volume and
  vertically (use larger instances or more powerful accelerators) for more
  demanding models, ensuring consistent performance under varying loads.
- **High Availability & Resiliency**: Components should be designed for high
  availability across multiple zones or regions, with mechanisms for
  self-healing, fault tolerance, and disaster recovery to minimize downtime.
- **Cost Efficiency**: Optimize resource utilization through intelligent
  autoscaling, right-sizing of machine types, and leveraging preemptible VMs
  where appropriate, to reduce operational costs without sacrificing
  performance.
- **Low Latency (for real-time)**: For online inference, the architecture
  prioritizes minimizing the time between request and response, often leveraging
  optimized model serving frameworks and network configurations.
- **Security & Compliance**: Implement robust security measures at every layer,
  including network isolation, identity and access management (IAM), data
  encryption, vulnerability scanning, and adherence to relevant industry
  compliance standards.
- **Observability**: Provide comprehensive monitoring, logging, and tracing
  capabilities to gain deep insights into the health, performance, and resource
  consumption of inference workloads, enabling proactive issue detection and
  resolution.
- **Ease of Management**: Strive for automation of deployment, scaling, and
  operational tasks, reducing manual effort and potential for human error.

## Core Concepts and Technologies

### Inference Workloads

At scale, inference involves utilizing a trained or fine-tuned model to generate
outputs or make predictions from input data. This process demands efficient and
reliable handling of massive request volumes, all while maintaining low latency
and high throughput.

#### Real-time Inference (Online)

Real-time inference prioritizes low-latency, synchronous responses. It involves
using a model to make predictions on incoming data as soon as it arrives,
thereby minimizing the delay between input and the prediction itself.

- **Goal:** Have the model make predictions within a very short timeframe, often
  measured in milliseconds or low seconds.
- **Use Cases:** Fraud detection, personalized recommendations, real-time
  bidding, anomaly detection, interactive chatbots, and any application where
  immediate action based on new inputs is required.
- **Key Considerations:** High concurrency, strict latency SLAs, efficient load
  balancing, and rapid scaling.

#### Streaming Inference

Streaming inference involves processing a continuous flow of data as it arrives,
often involving complex transformations, aggregations, and filtering of the data
before making predictions. It emphasizes continuous data ingestion and
processing, rather than just low latency for single requests.

- **Goal:** Handle a constantly updating stream of data and make decisions based
  on that stream, often with slightly higher response time tolerances than pure
  real-time, but still aiming for near real-time processing.
- **Use Cases:** Monitoring sensor data for predictive maintenance, analyzing
  social media feeds for sentiment analysis, processing clickstream data for
  website personalization, continuous fraud detection on transaction streams.
- **Key Considerations:** Robust messaging queues (Pub/Sub, Kafka, etc.),
  stateful processing, and fault tolerance for continuous data streams.

#### Batch Inference (Offline)

Batch inference processes data in large groups at specific times such as hourly,
daily, or weekly. It's often used when predictions can be pre-computed and
stored, and the need for immediate results isn't critical.

- **Goal**: Efficiently process large volumes of data for predictions that can
  be consumed later.
- **Use Cases**: Generating daily reports, processing historical data for
  analytics, updating large datasets with new predictions (e.g., customer churn
  scores, product recommendations for email campaigns), retraining data
  preparation.
- **Key Considerations**: High throughput, cost-effectiveness, and efficient
  ingestion and output.

#### Infrastructure and Deployment

The underlying infrastructure planning and deployment strategies are essential
for building and managing inference workloads.

- **Accelerator Capacity**
  - **Verification**: Before deploying ensure you have sufficient quota for GPUs
    and TPUs in the target region.
  - **Requesting Increase:** If quota is insufficient, submit a quota increase
    request through the Google Cloud console or your sales team. Plan for this
    well in advance, as approval times can vary.
- **GKE Cluster Choice**
  - **Autopilot:** Recommended for most inference workloads due to its fully
    managed nature. It automatically provisions and scales nodes, including GPU
    or TPU capacity, based on your deployment manifests, provided you have the
    necessary quota. This simplifies cluster management, reduces operational
    overhead, and optimizes resource utilization. Best for standard workloads
    where control over node configuration is less critical.
  - **Standard:** Offers more granular control and customization over cluster
    and node configurations. Choose Standard if you require specific kernel
    versions, custom machine images, highly specialized node-level
    configurations, or need to manage underlying VM instances directly for
    advanced debugging or compliance reasons. Requires more operational effort.
- **Cluster and Node Pool Configuration**:
  - **Zonal or Regional Clusters:** Create regional clusters for higher
    availability and fault tolerance across multiple zones, which is crucial for
    production inference workloads. Zonal clusters can be used for development
    or cost-sensitive, less critical workloads.
  - **Custom Compute Classes (CCC):** Leverage CCC to define node pools with
    fallback priorities, specific hardware profiles, including custom machine
    types, GPU/TPU accelerators, local SSDs, etc. This ensures that your
    inference pods land on nodes with the precise resources they need for
    optimal performance and efficiency. CCC allows for fine-tuning resource
    allocation beyond standard machine types.
  - **Node Auto-provisioning (NAP):** Enable NAP in GKE Standard clusters to
    automatically create new node pools with appropriate machine types and
    accelerators when workloads require resources not available in existing node
    pools. This works seamlessly with CCC and Horizontal Pod Autoscaler (HPA) to
    provide robust scaling.
  - **Cluster Autoscaler:** Configure the Cluster Autoscaler to automatically
    adjust the number of nodes in your node pools based on the aggregate
    resource requests and limits of your pods, ensuring efficient resource
    utilization and scaling for both Autopilot and Standard modes.
- **Observability**:
  - **Comprehensive Monitoring:** Enable Cloud Monitoring for GKE, including
    metrics for nodes, pods, deployments, and HPA. Monitor key inference metrics
    like QPS (Queries Per Second), latency (p50, p90, p99), error rates, GPU/TPU
    utilization, and memory consumption.
  - **Logging:** Utilize Cloud Logging for system logs (kubelet, container
    runtime) and application logs from your model servers. Implement structured
    logging for easier parsing and analysis.
  - **Tracing:** Integrate with Cloud Trace or OpenTelemetry to trace requests
    through your inference pipeline, helping to identify performance
    bottlenecks.
  - **Managed Prometheus:** Deploy Google Cloud Managed Service for Prometheus
    to collect custom metrics from your model servers (e.g., prediction latency,
    model-specific errors).
  - **Custom Metrics Adapter for HPA:** Deploy the custom metrics adapter to
    allow HPA to scale deployments based on custom model server metrics (e.g.,
    `requests_per_second`, `model_latency_ms`). This allows for more intelligent
    autoscaling tailored to actual inference load.

#### Model Optimization

Optimizing your models for inference is critical, especially for Large Language
Models (LLMs), to achieve desired latency, throughput, and cost targets.

- **Quantization**: Reduce model size and accelerate inference by representing
  weights and activations in lower precision formats (e.g., 8-bit integers
  (INT8) or 4-bit integers (INT4)) instead of full 32-bit floating point (FP32).
  While it can significantly improve latency and throughput and reduce memory
  footprint, be mindful of potential accuracy trade-offs. Test thoroughly.
  - **Post-training Quantization (PTQ):** Quantize a pre-trained FP32 model
    without retraining. Simpler to implement but can lead to accuracy
    degradation.
  - **Quantization-Aware Training (QAT):** Quantize the model during training,
    allowing the model to adapt to the lower precision and minimize accuracy
    loss. More complex but generally yields better accuracy.
- **Tensor Parallelism**: Distribute a single large model's tensors (e.g.,
  weights) across multiple GPUs. Each GPU processes a portion of the tensor, and
  activations are exchanged between GPUs. Essential for very large models (e.g.,
  frontier models) that exceed the memory capacity of a single GPU. Enables
  serving models that would otherwise be impossible on a single accelerator.
- **Model Memory Optimization**: Techniques to reduce the memory footprint of
  LLMs, particularly concerning the Key-Value (KV) cache generated during
  auto-regressive decoding.
  - **Paged Attention:** Manages the KV cache by breaking it into fixed-size
    blocks (pages), similar to virtual memory in operating systems. This reduces
    fragmentation and allows for more efficient memory allocation, especially
    for variable-length sequences and large batch sizes.
  - **Flash Attention:** An optimized attention algorithm that reorders
    computations and leverages GPU on-chip memory more effectively,
    significantly reducing the memory bandwidth required and speeding up
    attention calculations.
- **KV Cache Quantization**: Utilize lower precision formats (e.g., FP8 E5M2,
  FP8 E4M3) for the KV cache itself. Decreases KV cache memory footprint, which
  can be a significant bottleneck for long sequences and large batch sizes,
  leading to improved latency and higher throughput. May introduce a slight
  reduction in inference accuracy, therefore requires careful evaluation.
- **Pruning:** Remove redundant connections (weights) in a neural network,
  leading to a smaller, faster model with minimal impact on accuracy.
- **Distillation:** Train a smaller "student" model to mimic the behavior of a
  larger "teacher" model, resulting in a more compact and faster model with
  comparable performance.
- **Model Serving Frameworks**: Utilize specialized frameworks (e.g., vLLM,
  Jetstream, NVIDIA Triton) suited to your requirements.

### Google Kubernetes Engine (GKE)

Google Kubernetes Engine (GKE) is a powerful platform for AI inference due to
its strong support for container orchestration, scalability, and specific
features designed to optimize AI workloads

- **Node Pools (CPU, GPU, TPU)**: Offer a powerful and flexible platform for
  deploying and scaling inference workloads by combining the benefits of
  Kubernetes orchestration, hardware acceleration with GPUs and TPUs, and
  specialized GKE features designed to optimize AI inference performance and
  cost-efficiency.
- **Custom Compute Classes**: Provide granular control over GKE's resource
  allocation, enabling you to optimize performance, cost, and availability for
  your AI inference workloads by leveraging specialized hardware and ensuring
  reliable access to the resources you need.
- **Performance Horizontal Pod Autoscaler (HPA)**: A powerful tool for
  optimizing inference workloads on GKE, providing significant benefits in terms
  of faster scaling, improved resource utilization, cost efficiency, and overall
  performance. By combining the Performance HPA with other GKE features, you can
  achieve highly efficient and performant inference workloads.
- **Inference Gateway**: Provides specialized features and optimizations that
  address the unique demands of serving generative AI workloads. Intelligent,
  model-aware load balancing and routing for enhanced performance and
  efficiency, potentially reducing serving costs, tail latency, and increasing
  throughput all while simplifying operations.
- **Inference Quickstart**: Provides a streamlined and optimized approach to
  deploying inference workloads on GKE, making it a powerful tool for achieving
  high performance, scalability, and cost-efficiency with benchmarked
  performance profiles for various models. It offers pre-configured setups to
  accelerate deployment.
- **Cloud Storage FUSE**: Allows GKE pods to mount Google Cloud Storage buckets
  as local file systems. This is particularly useful for loading large models
  and datasets directly from Cloud Storage without needing to copy them into the
  container image or use Persistent Volumes, simplifying model deployment and
  updates.
- **Google Container File System (image streaming)**: Optimizes container image
  loading for faster pod startup times. Instead of downloading the entire image
  before starting the container, image streaming allows the container to start
  while the image layers are streamed on demand, significantly reducing cold
  start latency for large model images.

For additional information about GKE features used in the platform, see the
[Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/README.md#google-kubernetes-engine-gke)
section in the [GKE Base Platform](/docs/platforms/gke/base/README.md)
documentation.

### Google Cloud Services

Google Cloud Services with GKE, particularly with the new AI-focused mentioned
above, provide a robust, scalable, and cost-effective platform for deploying and
serving model inference at scale.

- **Cloud Storage**: Suitable for storing training data, models, and
  checkpoints. It offers quick data access using Cloud Storage FUSE with caching
  and parallel downloads. Cloud Storage FUSE can also pre-load model weights to
  improve load times while Anywhere Cache provides an SSD-backed zonal read
  cache for Cloud Storage buckets reducing the network costs associated with
  read-heavy workloads like loading model weights. Use regional buckets for
  performance and multi-regional buckets for higher availability/disaster
  recovery.
- **Cloud Load Balancing**: Provides a powerful and optimized solution for
  deploying and scaling AI inference workloads, particularly for demanding
  applications like Large Language Models (LLMs).
  - **External HTTP(S) Load Balancer**: Ideal for exposing public-facing
    inference endpoints with global reach, SSL termination, and advanced traffic
    management.
  - **Internal HTTP(S) Load Balancer**: Used for internal services or
    inter-service communication within your VPC, providing private IP access to
    inference endpoints.
  - **Integration with GKE Gateway API**: Modern GKE deployments can leverage
    the Gateway API and GKE Gateway Controller for advanced traffic management
    features, including multi-cluster routing, granular traffic splitting, and
    policy-based access control.
- **Cloud Networking**: Offers a comprehensive suite of networking solutions and
  integrations specifically designed to support and enhance inference workloads,
  providing high performance, low latency, scalability, and cost-efficiency.

For additional information about Google Cloud Services used in the platform, see
the
[Google Cloud Services](/docs/platforms/gke/base/README.md#google-cloud-services)
section in the [GKE Base Platform](/docs/platforms/gke/base/README.md)
documentation.

## Getting Started

A practical guide to setting up the infrastructure as described can be found in
the
[Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)

This reference architecture is designed to support various inference patterns.
Some example patterns provided are:

- [ComfyUI reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui/README.md)
- [Online inference with GPUs](/platforms/gke/base/use-cases/inference-ref-arch/examples/online-inference-gpu/README.md)
- [Online inference with TPUs](/platforms/gke/base/use-cases/inference-ref-arch/examples/online-inference-tpu/README.md)

Further use cases and patterns can be built upon this foundational architecture.

## Additional Reading

- [AI/ML orchestration on GKE documentation](https://cloud.google.com/kubernetes-engine/docs/integrations/ai-infra)
- [About AI/ML model inference on GKE](https://cloud.google.com/kubernetes-engine/docs/concepts/machine-learning/inference)
- [Best practices for running cost-optimized Kubernetes applications on GKE](https://cloud.google.com/architecture/best-practices-for-running-cost-effective-kubernetes-applications-on-gke)
