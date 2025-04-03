# Deploy NVIDIA FLARE on the Federated learning reference architecture

This example shows how to deploy NVIDIA FLARE on the
[Google Cloud Federated learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md).

[NVIDIA FLARE](https://nvflare.readthedocs.io/en/main/index.html) is a
domain-agnostic, open-source, extensible SDK that allows researchers and data
scientists to adapt existing ML/DL workflows to a federated paradigm. It enables
platform developers to build a secure, privacy-preserving offering for a
distributed multi-party collaboration.

For more information about nVidia FLARE, see
[NVIDIA FLARE overview](https://nvflare.readthedocs.io/en/main/flare_overview.html#high-level-system-architecture).

This example builds on top of the infrastructure that the
[Federated learning reference architecture provides](/platforms/gke/base/use-cases/federated-learning/README.md),
and follows the best practices the reference architecture establishes.

## Architecture

The following diagram shows one server and two clients that are connected to the
server:

![NVIDIA FLARE example architecture](/platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/assets/nvflare.svg "NVIDIA FLARE example architecture")

The previous diagram illustrates:

- A Cloud Storage bucket to store the NVIDIA FLARE workspace.
- A NVIDIA FLARE server running in Google Kubernetes Engine (GKE).
- Two NVIDIA FLARE clients that run in a runtime environment that is separated
  and independent from the NVIDIA FLARE server runtime environment. The NVIDIA
  FLARE clients connect to the NVIDIA FLARE server.

Cloud Service Mesh is configured to avoid intercepting traffic directed to the
NVIDIA FLARE server because NVIDIA FLARE handles mTLS authentication. If Cloud
Service Mesh intercepted the traffic directed at the NVIDIA FLARE server, the
Cloud Service Mesh proxy sidecar would present the service mesh certificate,
causing the NVIDIA FLARE clients to fail TLS certificate validation because they
receive a certificate that they don't recognize.

Note: due a bug in the Istio gateway implementation when exposing TCP services,
this reference architecture exposes the NVIDIA FLARE server using a LoadBalancer
service instead of exposing it using the service mesh ingress gateway. As soon
as the bug is resolved, the reference architecture will be refactored to use the
service mesh ingress gateway instead of exposing the NVIDIA FLARE server using a
LoadBalancer service.

### Modify the NVIDIA FLARE workspace and upload training code

If you need to modify the NVIDIA FLARE workspace, you interact with the `nvf-ws`
Cloud Storage bucket. For example, if you need to upload code to train your
model, you upload files in the `nvf-ws` bucket, respecting the
[NVIDIA FLARE workspace structure](https://nvflare.readthedocs.io/en/2.5/real_world_fl/workspace.html).

The NVIDIA FLARE server has access to the files you upload in the `nvf-ws`
bucket as soon as you upload it. For more information about uploading files from
a file system to Cloud Storage, see
[Upload objects from a file system](https://cloud.google.com/storage/docs/uploading-objects).

### Install dependencies in the NVIDIA FLARE containers

To install dependencies in the NVIDIA FLARE container image, edit the
`platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/container-image/requirements.txt`
file by adding listing the dependencies that you need.

Note: in a production environment, we recommend that you set up a workflow to
automatically build NVIDIA FLARE container images.

## Understand the repository structure

The NVIDIA FLARE example has the following directories and files.

In the `platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff`
directory:

- `assets`: contains documentation static assets.
- `deploy.sh`: convenience script to deploy an instance of the NVIDIA FLARE
  example on the reference architecture.
- `teardown.sh`: convenience script to destroy the NVIDIA FLARE example
  instance.
- `build-container-image.sh`: convenience script to build the NVIDIA FLARE
  container image.
- `push-container-image.sh`: convenience script to push the NVIDIA FLARE
  container image to a container image repository.
- `setup-environment.sh`: contains common shell variables and functions for the
  NVIDIA FLARE example.
- `README.md`: this document.

In the
`platforms/gke/base/use-cases/federated-learning/terraform/example_nvidia_flare_tff`:

- Terraform descriptors to deploy Google Cloud resources.
- NVIDIA FLARE workspace configuration file template.
- GKE and Cloud Service Mesh descriptors to deploy and expose the NVIDIA FLARE
  server.

## Deploy the reference architecture

This example builds on top of the infrastructure that the
[Federated Learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md)
provides, and follows the best practices that the reference architecture
establishes.

Before deploying the NVIDIA FLARE example described in this document, you deploy
one instance of the Federated learning reference architecture for each NVIDIA
FLARE workload. The reference architecture supports deploying multiple instances
of the reference architecture in the same project. To prepare the infrastructure
for the NVIDIA FLARE example, you do the following:

1. Deploy an instance of the reference architecture for the `server1` NVIDIA
   FLARE example workload. For more information about how to deploy an instance
   of the reference architecture, see
   [Federated Learning reference architecture](/platforms/gke/base/use-cases/federated-learning/README.md)

After you deploy the reference architecture instances, continue following this
document.

### Provision and configure Google Cloud infrastructure

For this example, you provision new Google Cloud resources in addition to the
ones that the Federated learning reference architecture provisions.

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Deploy `server1`:

   1. Change the working directory to the directory where you cloned the
      repository for the `server1` instance of the reference architecture.

   1. Run the script to configure the reference architecture and provision
      Google Cloud resources that this example needs:

   ```sh
   "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/deploy.sh" \
      --workload "server1"
   ```

For simplicity, the
`"platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/deploy.sh"`
convenience deployment script uploads the entire NVIDIA FLARE workspace to Cloud
Storage. In a production environment, we recommend that you upload only the
necessary part of the NVIDIA FLARE workspace.

### Check the status of the server

In this section, you check the status of the NVIDIA FLARE server:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Change the working directory to the directory where you cloned the repository
   for the `server1` instance of the reference architecture.

1. Set up the shell environment:

   ```bash
   source "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
   load_fl_terraform_outputs
   ```

1. Configure `kubectl` to access the cluster:

   ```bash
   gcloud container clusters get-credentials "${cluster_name}" --region "${cluster_region}" --project "${cluster_project_id}" --dns-endpoint
   ```

1. Get the list of NVIDIA FLARE pods running in the cluster:

   ```bash
   kubectl get pods --namespace "${NVFLARE_EXAMPLE_TENANT_NAME}"
   ```

   The output is similar to the following:

   ```bash
   NAME                               READY   STATUS             RESTARTS        AGE
   nvflare-server1-9f7cb8dfd-rzl27    3/3     Running            11 (42s ago)    66m
   ```

### Run clients

In this section, you run NVIDIA FLARE clients. You run NVIDIA FLARE clients as
containerized workloads in Cloud Shell to represent clients running in a runtime
environment that is different and completely separated from the NVIDIA FLARE
server runtime environment.

To run NVIDIA FLARE clients, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Change the working directory to the directory where you cloned the repository
   for the `server1` instance of the reference architecture.

1. Set up the shell environment:

   ```bash
   source "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
   load_fl_terraform_outputs
   load_kubernetes_outputs
   ```

1. Run `client1`:

   ```bash
   docker run --rm -it --entrypoint /usr/local/bin/python3 \
     --detach \
     --add-host=server1:${CLOUD_SERVICE_MESH_INGRESS_GATEWAY_IP_ADDRESS} \
     --name "nvflare-client1" \
     -v "$(pwd)/platforms/gke/base/use-cases/federated-learning/terraform/example_nvidia_flare_tff/nvflare-workspace":/workspace/nvfl/ \
     -u 10000:10000 \
     "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" \
     -u \
     -m nvflare.private.fed.app.client.client_train \
     -m /workspace/nvfl/workspace/example_project/prod_00/client1 \
     -s fed_client.json \
     --set secure_train=true \
     uid=client1 \
     config_folder=config \
     org=nvidia
   ```

1. Confirm that the `client1` is running:

   ```bash
   docker logs nvflare-client1
   ```

   The output is similar to the following:

   ```text
   Waiting for SP....
   2025-03-19 13:42:34,861 - CoreCell - INFO - client1: created backbone external connector to grpc://server1:8002
   2025-03-19 13:42:34,862 - ConnectorManager - INFO - 1: Try start_listener Listener resources: {'secure': False, 'host': 'localhost'}
   2025-03-19 13:42:34,863 - nvflare.fuel.f3.sfm.conn_manager - INFO - Connector [CH00002 PASSIVE tcp://0:40163] is starting
   2025-03-19 13:42:35,365 - CoreCell - INFO - client1: created backbone internal listener for tcp://localhost:40163
   2025-03-19 13:42:35,365 - nvflare.fuel.f3.sfm.conn_manager - INFO - Connector [CH00001 ACTIVE grpc://server1:8002] is starting
   2025-03-19 13:42:35,367 - FederatedClient - INFO - Wait for engine to be created.
   2025-03-19 13:42:35,376 - nvflare.fuel.f3.drivers.grpc_driver.GrpcDriver - INFO - created secure channel at server1:8002
   2025-03-19 13:42:35,377 - nvflare.fuel.f3.sfm.conn_manager - INFO - Connection [CN00002 N/A => server1:8002] is created: PID: 1
   2025-03-19 13:42:35,723 - FederatedClient - INFO - Successfully registered client:client1 for project example_project. Token:REDACTED SSID:REDACTED
   2025-03-19 13:42:35,727 - FederatedClient - INFO - Got engine after 0.36051297187805176 seconds
   2025-03-19 13:42:35,728 - FederatedClient - INFO - Got the new primary SP: grpc://server1:8002
   ```

1. Run `client2`:

   ```bash
   docker run --rm -it --entrypoint /usr/local/bin/python3 \
     --detach \
     --add-host=server1:${CLOUD_SERVICE_MESH_INGRESS_GATEWAY_IP_ADDRESS} \
     --name "nvflare-client2" \
     -v "$(pwd)/platforms/gke/base/use-cases/federated-learning/terraform/example_nvidia_flare_tff/nvflare-workspace":/workspace/nvfl/ \
     -u 10000:10000 \
     "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" \
     -u \
     -m nvflare.private.fed.app.client.client_train \
     -m /workspace/nvfl/workspace/example_project/prod_00/client2 \
     -s fed_client.json \
     --set secure_train=true \
     uid=client2 \
     config_folder=config \
     org=nvidia
   ```

1. Confirm that the `client2` is running:

   ```bash
   docker logs nvflare-client2
   ```

   The output is similar to the following:

   ```text
   Waiting for SP....
   2025-03-19 13:42:34,861 - CoreCell - INFO - client2: created backbone external connector to grpc://server1:8002
   2025-03-19 13:42:34,862 - ConnectorManager - INFO - 1: Try start_listener Listener resources: {'secure': False, 'host': 'localhost'}
   2025-03-19 13:42:34,863 - nvflare.fuel.f3.sfm.conn_manager - INFO - Connector [CH00002 PASSIVE tcp://0:40163] is starting
   2025-03-19 13:42:35,365 - CoreCell - INFO - client2: created backbone internal listener for tcp://localhost:40163
   2025-03-19 13:42:35,365 - nvflare.fuel.f3.sfm.conn_manager - INFO - Connector [CH00001 ACTIVE grpc://server1:8002] is starting
   2025-03-19 13:42:35,367 - FederatedClient - INFO - Wait for engine to be created.
   2025-03-19 13:42:35,376 - nvflare.fuel.f3.drivers.grpc_driver.GrpcDriver - INFO - created secure channel at server1:8002
   2025-03-19 13:42:35,377 - nvflare.fuel.f3.sfm.conn_manager - INFO - Connection [CN00002 N/A => server1:8002] is created: PID: 1
   2025-03-19 13:42:35,723 - FederatedClient - INFO - Successfully registered client:client2 for project example_project. Token:REDACTED SSID:REDACTED
   2025-03-19 13:42:35,727 - FederatedClient - INFO - Got engine after 0.36051297187805176 seconds
   2025-03-19 13:42:35,728 - FederatedClient - INFO - Got the new primary SP: grpc://server1:8002
   ```

For simplicity, in this example, NVIDIA FLARE clients have access to the entire
NVIDIA FLARE workspace. In a production environment, we recommend that you only
share the minimum amount of data from the NVIDIA FLARE workspace for the clients
to work correctly.

### Check the status of the registered clients

In this section, you check the status of the registered NVIDIA FLARE clients:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Change the working directory to the directory where you cloned the repository
   for the `server1` instance of the reference architecture.

1. Set up the shell environment:

   ```bash
   source "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
   load_fl_terraform_outputs
   load_kubernetes_outputs
   ```

1. Configure `kubectl` to access the cluster:

   ```bash
   gcloud container clusters get-credentials "${cluster_name}" --region "${cluster_region}" --project "${cluster_project_id}" --dns-endpoint
   ```

1. Open a shell in the NVIDIA FLARE server pod:

   ```bash
   kubectl exec --stdin --tty --namespace "${NVFLARE_EXAMPLE_TENANT_NAME}" "${NVFLARE_EXAMPLE_SERVER1_POD_NAME}" -- /bin/bash
   ```

1. Connect to NVIDIA FLARE:

   ```bash
   cd /workspace/nvfl/workspace/example_project/prod_00/admin@nvidia.com/startup
   mkdir -p ../local
   /bin/bash ./fl_admin.sh
   ```

   When prompted, input the username: `admin@nvidia.com`

   The output is similar to the following:

   ```bash
   User Name: admin@nvidia.com
   Trying to obtain server address
   Obtained server address: server1:8003
   Trying to login, please wait ...
   Logged into server at server1:8003 with SSID: ebc6125d-0a56-4688-9b08-355fe9e4d61a
   Type ? to list commands; type "? cmdName" to show usage of a command.
   >
   ```

1. Check that NVIDIA FLARE clients registered with the server:

   ```bash
   check_status server
   ```

   The output is similar to the following:

   ```bash
   Engine status: stopped
   ---------------------
   | JOB_ID | APP NAME |
   ---------------------
   ---------------------
   Registered clients: 2
   ------------------------------------------------
   | CLIENT | TOKEN    | LAST CONNECT TIME        |
   ------------------------------------------------
   | client2 | REDACTED | Mon Feb 10 13:45:09 2025 |
   | client1 | REDACTED | Mon Feb 10 13:45:08 2025 |
   ------------------------------------------------
   Done [282012 usecs] 2025-02-10 13:45:11.537354
   ```

1. Exit from NVIDIA FLARE by pressing the `CTRL+D` key combination.

   When prompted, input the username: `admin@nvidia.com`

1. Close the container shell:

   ```bash
   exit
   ```

## Next steps

After deploying NVIDIA FLARE on the reference architecture, you can deploy your
training workloads. For example, you can:

- [Deploy a NVIDIA FLARE example](#deploy-a-nvidia-flare-example)
- [Deploy a deep learning NVIDIA FLARE example](https://nvflare.readthedocs.io/en/2.4/example_applications_algorithms.html#deep-learning).

### Deploy a NVIDIA FLARE example

In this section, you deploy the
[Hello Scatter and Gather NVIDIA FLARE example](https://nvflare.readthedocs.io/en/2.4/examples/hello_scatter_and_gather.html)
in the reference architecture.

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Change the working directory to the directory where you cloned the repository
   for the `server1` instance of the reference architecture.

1. Run the script to configure the reference architecture:

   ```bash
   "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/deploy.sh" \
     --deploy-example \
     --workload "server1"
   ```

1. Connect to the NVIDIA FLARE server as described in the
   [Check the status of the registered clients](#check-the-status-of-the-registered-clients)
   section.

1. Submit the training job:

   ```bash
   submit_job hello-numpy-sag/jobs/hello-numpy-sag
   ```

   The output looks like the following:

   ```text
   Submitted job: c8973f05-8787-41c5-8568-ecc15c7683b2
   Done [262650 usecs] 2025-03-26 09:47:04.543903
   ```

1. Verify that the training job completed successfully:

   ```bash
   list_jobs
   ```

   The output looks like the following:

   ```markdown
   -----------------------------------------------------------------------------------------------------------------------------------
   | JOB ID                               | NAME            | STATUS             | SUBMIT TIME                      | RUN DURATION   |
   -----------------------------------------------------------------------------------------------------------------------------------
   | bbbbf80d-f313-4f6c-a8e5-043ea517a4a5 | hello-numpy-sag | FINISHED:COMPLETED | 2025-03-27T09:11:39.249673+00:00 | 0:00:12.168104 |
   -----------------------------------------------------------------------------------------------------------------------------------
   Done [41622 usecs] 2025-03-27 09:11:55.515199
   ```

1. Exit from NVIDIA FLARE by pressing the `CTRL+D` key combination.

   When prompted, input the username: `admin@nvidia.com`

1. Close the container shell:

   ```bash
   exit
   ```

## Destroy the example environment

To destroy an instance of this example, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Destroy `server1`:

   1. Change the working directory to the directory where you cloned the
      repository for the `server1` instance of the reference architecture.

   1. Run the script to destroy an instance of this example:

   ```sh
   "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/teardown.sh"
   ```

## Useful NVIDIA FLARE references

- [NVFLARE logging configuration](https://nvflare.readthedocs.io/en/2.4/user_guide/configurations/logging_configuration.html).
