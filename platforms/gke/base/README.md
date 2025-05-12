# Base GKE Accelerated Platform

The base GKE Accelerated Platform provides a "core", foundational, opinionated,
and streamlined setup for deploying accelerated workloads to Google Kubernetes
Engine (GKE). It serves as a starting point for building and managing robust,
scalable, and secure workloads on GKE, designed for rapid iteration and
deployment.

## Key Features

- **Infrastructure as Code (IaC):** Leverages Terraform to define and manage all
  infrastructure resources, ensuring consistency, repeatability, and version
  control.
- **Terraservices Design:** Organized into modular components
  ([Terraservices](https://www.hashicorp.com/en/resources/evolving-infrastructure-terraform-opencredo))
  with shared configuration for easier management, customization, and reuse.
- **Scalability and High Availability:** Configured to support automatic scaling
  and high availability of your workloads.
- **Accelerator Ready:** Simplifies the process of obtaining and utilizing
  accelerators for your workloads.
- **Observability:** Easy integration with monitoring, logging, and tracing
  tools.
- **Security Best Practices:** Implements security best practices
  out-of-the-box.
- **Extensible:** Designed to be easily customized and extended to fit your
  specific requirements.
- **Rapid Development:** Provides a reliable base, enabling quicker development
  and deployment of workloads.

For an outline of Google Cloud products and features used in the platform, see
[Platform Products and Features](/docs/platforms/gke-aiml/products-and-features.md).

## Getting Started

1.  **Deploy the Core Platform:** Get up and running quickly with the
    [Reference Implementation for the Core GKE Accelerated Platform](/platforms/gke/base/core/README.md).
2.  **Explore Use Cases:** See how the platform can be applied to specific
    scenarios with our example
    [use case](/platforms/gke/base/use-cases/README.md) implementations.

## Additional Reading

- [Google Cloud Well-Architected Framework](https://cloud.google.com/architecture/framework)

  - [Well-Architected Framework: AI and ML perspective ](https://cloud.google.com/architecture/framework/perspectives/ai-ml)

- [Landing zone design in Google Cloud](https://cloud.google.com/architecture/landing-zones)
- [Google Cloud deployment archetypes](https://cloud.google.com/architecture/deployment-archetypes)
- [Google Cloud infrastructure reliability guide](https://cloud.google.com/architecture/infra-reliability-guide)

## Directory Structure

### **`_shared_config/`**

Contains the variables, `.tfvars` files, and other local configuration that can
be shared across Terraservices. These files enable efficient sharing of
configurations without relying on Terraform state files.

### **`core/`**

A flexible and customizable platform built on industry best practices, designed
to be adaptable and scalable to a wide range of use cases and requirements. Its
modular architecture allows for easy integration of additional components and
services, enabling the ability to tailor the platform to specific needs and
workloads.

### **`features/`**

A collection of optional Terraservices that can be incorporated to enhance the
platform's functionality.

### **`use-cases/`**

Illustrative examples demonstrating how to utilize the platform as the
foundation.
