# GKE Base Platform

The GKE Base Platform provides a "core", foundational, opinionated, and
streamlined setup for deploying accelerated workloads to Google Kubernetes
Engine (GKE). It serves as a starting point for building and managing robust,
scalable, and secure workloads on GKE, designed for rapid iteration and
deployment.

## Features & Capabilities

This platform provides a foundation for:

- **Infrastructure as Code (IaC):** Leverages Terraform extensively to define
  and manage all infrastructure resources. This ensures consistency,
  repeatability, version control (allowing rollbacks and audits), and reduces
  human error during provisioning and updates.
- **Terraservices Design:** The architecture is organized into modular
  components, referred to as Terraservices. Each Terraservice encapsulates a
  specific set of related resources (e.g., GKE cluster, networking components).
  This modularity, combined with shared configuration, simplifies management,
  promotes reusability across projects, and allows for easier customization
  without impacting the entire architecture.
- **Scalability and High Availability:** Configured to inherently support
  automatic scaling and high availability of your workloads. This means
  applications can seamlessly handle varying loads and remain resilient to
  component failures.
- **Accelerator Ready:** Streamlines the process obtaining, provisioning, and
  efficient utilization of hardware accelerators (GPUs, TPUs) within your
  cluster, enabling workloads to readily consume these powerful resources.
- **Observability:** Ensures easy integration with Google Cloud's monitoring,
  logging, and tracing tools. This provides comprehensive visibility into
  application and infrastructure performance, health, and behavior, critical for
  debugging, optimization, and operational excellence.
- **Security Best Practices:** Implements security best practices
  out-of-the-box, covering network segmentation, identity and access management
  (IAM), data encryption, and vulnerability management, reducing the attack
  surface and ensuring compliance.
- **Extensible:** Designed with extensibility in mind, allowing the architecture
  to be easily customized and extended to fit your specific organizational
  requirements, compliance needs, or unique application demands.
- **Rapid Development:** By providing a reliable, pre-configured, and secure
  base, this platform significantly accelerates the development and deployment
  cycles of new workloads, allowing teams to innovate faster.

## Architectural Principles

- **Standardize Deployments**: Enforce a consistent and repeatable methodology
  for deploying both infrastructure and applications. This consistency minimizes
  configuration drift, simplifies troubleshooting, and enables efficient GitOps
  workflows where infrastructure and application configurations are managed as
  code in a version-controlled repository.
- **Promote \*Ops Best Practices**: Incorporate industry best practices in
  automated CI/CD pipelines for infrastructure and application code,
  comprehensive monitoring and alerting, centralized logging for auditing and
  debugging, and robust security policies applied at every layer of the stack.
- **Accelerate Implementation**: Provide a clear, actionable, and automated path
  to a production-ready environment. This is achieved through well-defined,
  modular components, practical examples, and seamless integration with core
  Google Cloud services, significantly reducing the time-to-value for new
  projects.

## Core Concepts and Technologies

For an outline of Google Cloud products and features used in the platform, see
[Platform Products and Features](/docs/platforms/gke/base/products-and-features.md).

### Google Kubernetes Engine (GKE)

- **Cloud Storage FUSE**: Allows GKE pods to mount Google Cloud Storage buckets
  as local file systems. This is particularly useful for loading large amounts
  of data directly from Cloud Storage without needing to copy them into the
  container image or use Persistent Volumes, simplifying deployment and updates.
- **Cluster Autoscaler**: Automatically adjusts the number of nodes in your GKE
  cluster based on the demands of your workloads. This ensures applications have
  enough compute resources while minimizing costs during periods of low demand.
- **Confidential Nodes** (optional): Provides hardware-level isolation and
  memory encryption for highly sensitive workloads, protecting data in use from
  unauthorized access by the cloud provider or other tenants.
- **Control plane DNS endpoint**: Offers a DNS name that resolves to a frontend,
  enhancing flexibility in access methods and security controls. This endpoint
  is accessible from any network that can reach Google Cloud APIs, including
  VPC, on-premises, or other cloud networks.
- **Custom Compute Classes**: Allow you to select specific hardware
  configurations for your pods beyond standard CPU/memory profiles, providing
  fine-grained control over resource allocation for specialized workloads.
- **DataPlane V2 (eBPF-based)**: Enhances network performance, observability,
  and security within GKE. It leverages eBPF (extended Berkeley Packet Filter)
  to provide more efficient packet processing, fine-grained network policies,
  and deeper network visibility without traditional kube-proxy overhead.
- **Google Container File System (image streaming)**: Optimizes container image
  loading for faster pod startup times. Instead of downloading the entire image
  before starting the container, image streaming allows the container to start
  while the image layers are streamed on demand, significantly reducing cold
  start latency.
- **GKE Gateway API**: A modern, expressive, and extensible API for managing
  inbound and outbound traffic to your Kubernetes services. It offers more
  flexibility than Ingress for advanced routing, traffic splitting, and policy
  enforcement, especially for complex microservice architectures.
- **Horizontal Pod Autoscaler (HPA)**: Automatically scales the number of pod
  replicas up or down based on observed CPU utilization or custom metrics (e.g.,
  QPS, GPU utilization). This ensures applications can handle varying loads
  efficiently.
- **Node Auto-provisioning (NAP)**: An advanced feature of Cluster Autoscaler
  that automatically manages the creation and deletion of node pools based on
  pending pods' resource requests (e.g., CPU, memory, GPU type). This
  dynamically optimizes resource allocation and cost.
- **Node Pools (CPU, GPU, TPU)**: Pre-configured logical groupings of nodes
  within a GKE cluster, each optimized for specific compute requirements.
  - **CPU Node Pools:** General-purpose compute for control plane components,
    I/O bound tasks, or smaller model serving.
  - **GPU Node Pools:** Tailored for machine learning training and inference,
    equipped with NVIDIA GPUs and the necessary drivers.
  - **TPU Node Pools:** Specifically designed for large-scale, high-performance
    machine learning workloads, utilizing Google's Tensor Processing Units.
- **Private GKE Cluster**: A critical security feature where nodes have only
  internal IP addresses, and the cluster's control plane is also accessible only
  from within your VPC network or authorized networks. This significantly
  reduces the attack surface by preventing direct internet exposure.
- **Shielded Nodes**: Offer enhanced security for GKE nodes by using Google
  Cloud's advanced security features Secure Boot, Measured Boot, and vTPM
  (virtual Trusted Platform Module). They protect against rootkits and
  boot-level malware.
  - **Integrity Monitoring**: Continuously verifies the integrity of the node's
    boot and runtime components. If any unauthorized changes are detected, it
    can trigger alerts or automatically quarantine the node.
  - **Secure Boot**: Ensures that only authorized and cryptographically signed
    software loads at boot time, preventing the execution of malicious or
    unauthorized code during the boot process.
- **Vertical Pod Autoscaler (VPA)**: Automatically adjusts the CPU and memory
  requests and limits for individual containers in a pod. VPA learns resource
  usage over time, optimizing resource allocation and reducing waste or out of
  memory kills.

### Google Cloud Services

- **Artifact Registry**: A fully managed, universal package manager for storing,
  managing, and securing various build artifacts, including Docker container
  images, Maven artifacts, npm packages, etc. It integrates seamlessly with GKE
  for rapid and secure image pulls, supporting vulnerability scanning and access
  control.
- **Cloud Build**: A serverless CI/CD platform that executes your builds on
  Google Cloud. It can automatically pull code from source repositories, run
  tests, build container images, and push them to Artifact Registry. It is
  instrumental for automating infrastructure deployments via Terraform and
  application deployments to GKE.
- **Cloud Logging**: A centralized, fully managed logging service for
  collecting, storing, and analyzing logs from GKE clusters, application
  containers, model servers, and other Google Cloud services. It is essential
  for comprehensive debugging, performance monitoring, security auditing, and
  compliance.
- **Cloud Monitoring**: Provides powerful metrics collection, customizable
  dashboards, proactive alerting, and uptime checks for your entire Google Cloud
  environment, including GKE clusters, node pools, individual pods, and
  applications. It enables real-time visibility into resource utilization and
  application health.
- **Cloud Storage**: A highly scalable and durable object storage service. It
  serves as the primary repository for raw data, processed datasets, model
  checkpoints, and trained models. Its global accessibility and high
  availability make it ideal for serving data to GKE workloads.
- **Cloud Trace**: A distributed tracing system that helps you understand how
  requests propagate through your application, identifying performance
  bottlenecks.
- **Endpoints**: a complement to Cloud DNS, it provides an API management system
  that helps you secure, monitor, analyze, and set quotas on your APIs using the
  same infrastructure Google uses for its own APIs.
- **Networking Services**
  - **Cloud DNS**: A high-performance, globally available DNS service that
    manages DNS records for your GKE cluster services, enabling service
    discovery and efficient traffic routing within your VPC and to external
    services.
  - **Cloud Load Balancing**: Provides scalable and highly available load
    balancing for applications running on GKE.
  - **Cloud NAT Gateway**: Enables instances in a private subnet (like GKE nodes
    in a private cluster) to connect to the internet for pulling container
    images, downloading software updates, or accessing external APIs, without
    requiring each instance to have a public IP address.
- **Network Connectivity**
  - **Cloud Router**: Facilitates dynamic routing and connectivity between your
    Google Cloud VPC network and other networks, such as on-premises data
    centers (via Cloud VPN or Cloud Interconnect) or other cloud providers.
    Essential for hybrid cloud scenarios.
- **Security**
  - **Certificate Manager**: A service for provisioning and managing SSL/TLS
    certificates for your applications. It integrates with Google Cloud load
    balancers and GKE Gateway to secure communication.
  - **Secret Manager**: Securely stores and manages sensitive data such as API
    keys, database credentials, and certificates. It provides versioning,
    auditing, and fine-grained access control, preventing sensitive information
    from being hardcoded in applications or configurations.

## Getting Started

A practical guide to setting up the infrastructure as described can be found in
the
[GKE Base Platform reference implementation](/platforms/gke/base/core/README.md).
This guide includes detailed Terraform configurations and deployment steps to
deploy your GKE Base Platform.

This architecture is designed to be the foundation for other use cases. Some
example use cases are:

- [ComfyUI reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/examples/comfyui/README.md)
- [Federated learning](/docs/platforms/gke/base/use-cases/federated-learning/README.md)
- [Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md)
  - [Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
    - [Online inference with GPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/README.md)
      - [Online inference using Diffusers with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/diffusers-with-hf-model.md)
      - [Online inference using vLLM with GPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu//vllm-with-hf-model.md)
    - [Online inference with TPUs](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/README.md)
      - [Online inference using MaxDiffusion with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu//max-diffusion-with-hf-model.md)
      - [Online inference using vLLM with TPUs on Google Kubernetes Engine (GKE)](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu//vllm-with-hf-model.md)

## Additional Reading

- [Google Cloud Well-Architected Framework](https://cloud.google.com/architecture/framework)
  - [Well-Architected Framework: AI and ML perspective](https://cloud.google.com/architecture/framework/perspectives/ai-ml)
- [Landing zone design in Google Cloud](https://cloud.google.com/architecture/landing-zones)
- [Google Cloud deployment archetypes](https://cloud.google.com/architecture/deployment-archetypes)
- [Google Cloud infrastructure reliability guide](https://cloud.google.com/architecture/infra-reliability-guide)

## Contributing

For more information about contributing to this repository, see
[CONTRIBUTING](/CONTRIBUTING.md).

For information about developing a new use case for the GKE Accelerated
Platform, see
[GKE Base Platform developers guide](/platforms/gke/base/use-cases/DEVELOPER.md).
