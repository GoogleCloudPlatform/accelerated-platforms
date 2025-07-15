# Deploy cross-device on the Federated learning reference architecture

This example shows how to deploy the cross-device example on the
[Google Cloud Federated learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md).

This example builds on top of the infrastructure that the
[Federated learning reference architecture provides](/platforms/gke/base/use-cases/federated-learning/README.md),
and follows the best practices the reference architecture establishes.

## Architecture

The following diagram shows the deployment of the cross-device example with one
client connected to the server:

![Cross-device example architecture](/platforms/gke/base/use-cases/federated-learning/examples/cross-device/assets/cross-device.png "Cross-device example architecture")

The private GKE cluster uses confidential nodes as its primary pool to help
secure the data in use.

The cross-device architecture uses components from the open source
[Federated Compute Platform (FCP)](https://github.com/google-parfait/federated-compute)
project. This project includes the following:

- Client code for communicating with a server and executing tasks on the devices
- A protocol for client-server communication
- Connection points with TensorFlow Federated to make it easier to define your
  federated computations

The FCP components shown in the preceding diagram can be deployed as a set of
microservices. These components do the following:

- Collector: this job runs periodically to query active tasks and encrypted
  gradients. This information determines when aggregation starts
- Task-assignment: this front-end service distributes training tasks to devices
- Task-management: this job manages tasks
- Task-scheduler: this job either runs periodically or is triggered by specific
  events
- Task-builder: this job builds tasks to be sent to clients

Two of the FCP components have to be run in a confidential space virtual machine
that ensures the memory is encrypted during use. These components are:

- Aggregator: this job reads device gradients and calculates aggregated result
  with Differential Privacy
- Model updater: this job listens to events and publishes results so that device
  can download updated models

In addition to these components, the architecture also deploys:

- A GCS bucket to store the consolidated model and gradients
- A pubsub that enables communication between the different microservices
- A spanner table that register the tasks to be sent and the history of the
  training tasks

## Understand the repository structure

The cross-device example has the following directories and files.

In the `platforms/gke/base/use-cases/federated-learning/examples/cross-device`
directory:

- `assets`: contains documentation static assets.
- `prerequisites.sh`: convenient script to build and push workload images used
  in the cross-device example.
- `deploy.sh`: convenience script to deploy an instance of the cross-device
  example on the reference architecture.
- `teardown.sh`: convenience script to destroy the cross-device example
  instance.
- `setup-environment.sh`: contains common shell variables and functions for the
  cross-device example.
- `README.md`: this document.

In the
`platforms/gke/base/use-cases/federated-learning/terraform/example_cross_device`:

- Terraform descriptors to deploy Google Cloud resources.
- Cross-device configuration file template.
- GKE and Cloud Service Mesh descriptors to deploy and expose the cross-device
  workloads.

## Deploy the reference architecture

This example builds on top of the infrastructure that the
[Federated Learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md)
provides, and follows the best practices that the reference architecture
establishes.

After you deploy the reference architecture instances, continue following this
document.

## Provision and configure Google Cloud infrastructure

For this example, you provision new Google Cloud resources in addition to the
ones that the Federated learning reference architecture provisions.

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Deploy the infrastructure

   1. Run the script to configure the reference architecture and provision
      Google Cloud resources that this example needs:

   ```bash
   "platforms/gke/base/use-cases/federated-learning/examples/cross-device/deploy.sh"
   ```

## Open ports

This architecture requires certain ports to be open. For confidential computing,
workloads like `aggregator` and `modelupdater` listen to port `8082`. In
addition, SSH port is open for debugging purpose if you need to connect to the
VM to see logs. If you don't need it, you can comment the `ssh` block in the
`firewall.tf` of the confidential_space terraservice.

## Android specific variables

This architecture relies on another project maintained by the Android team at
Google. There are some variables that are specific to this project. By default,
theses variables are set to the staging environment.

These variables are:

- `federated_learning_cross_device_example_encryption_key_service_a_base_url = https://privatekeyservice-ca-staging.rb-odp-key-host-dev.com/v1alpha`
- `federated_learning_cross_device_example_encryption_key_service_b_base_url = https://privatekeyservice-cb-staging.rb-odp-key-host-dev.com/v1alpha`
- `federated_learning_cross_device_example_encryption_key_service_a_cloudfunction_url = https://ca-staging-us-central1-encryption-key-service-clo-2q6l4c4evq-uc.a.run.app`
- `federated_learning_cross_device_example_encryption_key_service_b_cloudfunction_url = https://cb-staging-us-central1-encryption-key-service-clo-2q6l4c4evq-uc.a.run.app`
- `federated_learning_cross_device_example_wip_provider_a = projects/586348853457/locations/global/workloadIdentityPools/ca-staging-opwip-1/providers/ca-staging-opwip-pvdr-1`
- `federated_learning_cross_device_example_wip_provider_b = projects/586348853457/locations/global/workloadIdentityPools/cb-staging-opwip-1/providers/cb-staging-opwip-pvdr-1`
- `federated_learning_cross_device_example_service_account_a = ca-staging-opverifiedusr@rb-odp-key-host.iam.gserviceaccount.com`
- `federated_learning_cross_device_example_service_account_b = cb-staging-opverifiedusr@rb-odp-key-host.iam.gserviceaccount.com`
- `federated_learning_cross_device_example_allowed_operator_service_accounts = ca-staging-opallowedusr@rb-odp-key-host.iam.gserviceaccount.com,cb-staging-opallowedusr@rb-odp-key-host.iam.gserviceaccount.com`

## Destroy the example environment

To destroy an instance of this example, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Destroy the infrastructure

   1. Run the script to destroy an instance of this example:

   ```bash
   "platforms/gke/base/use-cases/federated-learning/examples/cross-device/teardown.sh"
   ```
