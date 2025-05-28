# Deploy cross-device on the Federated learning reference architecture

This example shows how to deploy the cross-device example on the
[Google Cloud Federated learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md).

This example builds on top of the infrastructure that the
[Federated learning reference architecture provides](/platforms/gke/base/use-cases/federated-learning/README.md),
and follows the best practices the reference architecture establishes.

## Architecture

//TODO architecture diagram

## Understand the repository structure

The cross-device example has the following directories and files.

In the `platforms/gke/base/use-cases/federated-learning/examples/cross-device`
directory:

- `assets`: contains documentation static assets.
- `deploy.sh`: convenience script to deploy an instance of the NVIDIA FLARE
  example on the reference architecture.
- `teardown.sh`: convenience script to destroy the NVIDIA FLARE example
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


### Check the status of the server

In this section, you check the status of the NVIDIA FLARE server:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Set up the shell environment:

   ```bash
   source "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
   load_fl_terraform_outputs
   ```

1. Configure `kubectl` to access the cluster:

   ```bash
   gcloud container clusters get-credentials "${cluster_name}" --region "${cluster_region}" --project "${cluster_project_id}" --dns-endpoint
   ```

1. Get the list of cross-device pods running in the cluster:

   ```bash
   kubectl get pods --namespace "${NVFLARE_EXAMPLE_TENANT_NAME}"
   ```

   The output is similar to the following:

   ```bash
   // TODO
   ```

### Run clients


### Check the status of the registered clients


## Next steps


### Deploy a NVIDIA FLARE example


## Destroy the example environment

To destroy an instance of this example, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

## Useful cross-device references

- [NVFLARE logging configuration](https://nvflare.readthedocs.io/en/2.4/user_guide/configurations/logging_configuration.html).
