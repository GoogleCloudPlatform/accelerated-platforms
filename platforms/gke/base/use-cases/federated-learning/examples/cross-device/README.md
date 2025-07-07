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

## Build the images needed

In order to completely deployed this infrastructure, you will need to build and
push on a registry the images to run the workloads. These images can be found in
the
[On-Device Personalization Federated Compute Server](https://github.com/privacysandbox/odp-federatedcompute).

1. Clone and update the repository

   ```bash
   git clone https://github.com/privacysandbox/odp-federatedcompute
   git submodule update --init --recursive
   ```

1. Create a worker-pool large enough to build the images

   ```bash
   gcloud builds worker-pools create odp-federatedcompute-privatepool --region us-central1 --worker-machine-type=e2-standard-32
   ```

1. Give the required permissions to the service account

   ```bash
   export PROJECT_NUMBER=$(gcloud projects list --filter="$(gcloud config get project)" --format="value(PROJECT_NUMBER)")
   export PROJECT_ID=$(gcloud config get project)
   gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:"${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" --role=roles/storage.objectUser
   gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:"${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" --role=roles/logging.logWriter
   gcloud projects add-iam-policy-binding ${PROJECT_ID} --member=serviceAccount:"${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" --role=roles/artifactregistry.writer
   ```

1. In the `cloudbuild.yaml` of the repository, uncomment lines 30,31 and replace
   `Registry` with the name of your registry

1. Submit the job

   ```bash
   gcloud builds submit --substitutions=_PROJECT_ID="${PROJECT_ID},_REGISTRY=europe-docker.pkg.dev/${PROJECT_ID}/container-image-repository" --region us-central1
   ```

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

## Destroy the example environment

To destroy an instance of this example, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Destroy the infrastructure

   1. Run the script to destroy an instance of this example:

   ```bash
   "platforms/gke/base/use-cases/federated-learning/examples/cross-device/teardown.sh"
   ```
