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
[Platform Products and Features](/docs/platforms/gke/base/products-and-features.md).

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

## Contributing

For for information about contributing to this repository, see
[CONTRIBUTING](/CONTRIBUTING.md).

For information about developing a new use case for the GKE Accelerated
Platform, see
[Base GKE Accelerated Platform developers guide](/platforms/gke/base/use-cases/DEVELOPER.md).
