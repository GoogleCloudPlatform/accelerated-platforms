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

### Provision and configure Google Cloud infrastructure

For this example, you provision new Google Cloud resources in addition to the
ones that the Federated learning reference architecture provisions.

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Deploy the infrastructure

   1. Run the script to configure the reference architecture and provision
      Google Cloud resources that this example needs:

   ```bash
   "platforms/gke/base/use-cases/federated-learning/examples/cross-device/deploy.sh"
   ```

### Check the status of the server

In this section, you check the status of the cross-device example:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Set up the shell environment:

   ```bash
   source "platforms/gke/base/use-cases/federated-learning/examples/cross-device/setup-environment.sh"
   load_fl_terraform_outputs
   ```

1. Configure `kubectl` to access the cluster:

   ```bash
   gcloud container clusters get-credentials "${cluster_name}" --region "${cluster_region}" --project "${cluster_project_id}" --dns-endpoint
   ```

1. Get the list of cross-device pods running in the cluster:

   ```bash
   kubectl get pods --namespace "${CROSS_DEVICE_EXAMPLE_TENANT_NAME}"
   ```

   The output is similar to the following:

   ```text
   NAME                                        READY   STATUS    RESTARTS      AGE
   demo-dev-collector-6f465bcdf4-24lft         2/2     Running   0              1d
   demo-dev-task-assignment-84d65486c7-j5mvk   2/2     Running   0              1d
   demo-dev-task-assignment-84d65486c7-lm4hg   2/2     Running   0              1d
   demo-dev-task-assignment-84d65486c7-pqhk7   2/2     Running   0              1d
   demo-dev-task-assignment-84d65486c7-qk727   2/2     Running   0              1d
   demo-dev-task-builder-6b94dfb899-njgb9      2/2     Running   0              1d
   demo-dev-task-builder-6b94dfb899-z9czh      2/2     Running   0              1d
   demo-dev-task-management-666ddfcdd8-dkzkh   2/2     Running   0              1d
   demo-dev-task-management-666ddfcdd8-w7cq2   2/2     Running   0              1d
   demo-dev-task-scheduler-68bd758c46-759qr    2/2     Running   2 (1d ago)     1d
   demo-dev-task-scheduler-68bd758c46-lgtlq    2/2     Running   0              1d
   ```

## Run an end-to-end test

To validate that the deployment is working correctly, you can use the
[On-Device Personalization Federated Compute Server](https://github.com/privacysandbox/odp-federatedcompute)
to run an end-to-end test:

1. Get the ingress public IP:

   ```bash
   export LB_IP=$(kubectl get svc istio-ingressgateway-cross-device -n istio-ingress --template="{{range .status.loadBalancer.ingress}}{{.ip}}{{end}})"
   ```

1. Clone and update the FCP repo:

   ```bash
   git clone https://github.com/privacysandbox/odp-federatedcompute
   git submodule update --init --recursive
   ```

1. Once inside the `odp-federatedcompute` directory, run this command to go
   inside the Docker container:

   ```bash
   ./scripts/docker/docker_sh.sh
   ```

1. Once inside the container, create an evaluation task:

   ```bash
   bazel run //java/src/it/java/com/google/ondevicepersonalization/federatedcompute/endtoendtests:end_to_end_test -- --task_management_server http://$LB_IP:8082 --server http://$LB_IP:8083 --public_key_url https://publickeyservice-ca-staging.rb-odp-key-host-dev.com/v1alpha/publicKeys
   ```

1. Once inside the container, create and complete an evaluation task:

   ```bash
   bazel run //java/src/it/java/com/google/ondevicepersonalization/federatedcompute/endtoendtests:end_to_end_test -- --task_management_server http://$LB_IP:8082 --server http://$LB_IP:8083 --public_key_url https://publickeyservice-ca-staging.rb-odp-key-host-dev.com/v1alpha/publicKeys
   ```

## Destroy the example environment

To destroy an instance of this example, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Destroy the infrastructure

   1. Run the script to destroy an instance of this example:

   ```bash
   "platforms/gke/base/use-cases/federated-learning/examples/cross-device/teardown.sh"
   ```
