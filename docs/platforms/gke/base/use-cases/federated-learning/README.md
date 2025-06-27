# Federated learning on Google Cloud

This repository contains a blueprint and a reference architecture to implement
and realize federated learning use cases on Google Cloud, such as:

- Cross-silo federated learning: where the participating members are
  organizations or companies, and the number of members is usually small such as
  within a hundred.
- Cross-device federated computation: is a type of federated computation where
  the participating members are end user devices such as mobile phones and
  vehicles. The number of members can reach up to a scale of millions or even
  tens of millions.

This reference architecture is based on Google Kubernetes Engine (GKE) and
follows security best practices that help you secure your Google Cloud
environment.

This reference architecture configures separated, isolated runtime environments.
Each runtime environment gets:

- A dedicated Kubernetes namespace
- A dedicated GKE node pool

You can run potentially untrusted federated learning workloads in these runtime
environments, granting these workloads only the minimum permissions that they
need.

This reference architecture assumes that you are familiar with GKE and
Kubernetes.

For more information about federated learning, see
[Cross-silo and cross-device federated learning on Google Cloud](https://cloud.google.com/architecture/cross-silo-cross-device-federated-learning-google-cloud).

## Get started

For more information about deploying this reference architecture in your Google
Cloud environment, see
[Deploy the Federated learning reference architecture on Google Cloud](/platforms/gke/base/use-cases/federated-learning/README.md)
