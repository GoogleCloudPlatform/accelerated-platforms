# Train an image classifier using NVIDIA FLARE

This example uses nVidia FLARE to train an image classifier using federated
averaging and TensorFlow as the deep learning framework.

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

As shown in the preceding diagram, the reference architecture helps you to
create and configure the following components:

- A persistent volume to store the NVIDIA FLARE workspace
- Two pods that run NVIDIA FLARE clients that connect to the NVIDIA FLARE server
  in the `nvidia-client1` and `nvidia-client2` namespaces respectively.
- One pod that runs the NVIDIA FLARE server that aggregates the computation
  results in the `nvflare-infra` namespace.

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
   FLARE example workload.
1. Deploy an instance of the reference architecture for the `client1` NVIDIA
   FLARE example workload.
1. Deploy an instance of the reference architecture for the `client2` NVIDIA
   FLARE example workload.

For more information about how to deploy an instance of the reference
architecture, see
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

   1. Take note of the NVIDIA FLARE Cloud Storage bucket name from the output of
      the last command. The output is similar to the following:

   ```text
   NVFLARE workspace bucket name: bucket-name-xxxx
   ```

   1. Take note of the NVIDIA FLARE server IP address from the output of the
      last command. The output is similar to the following:

   ```text
   NVFLARE server IP address: 1.2.3.4
   ```

1. Deploy `client1`:

   1. Change the working directory to the directory where you cloned the
      repository for the `client1` instance of the reference architecture.

   1. Run the script to configure the reference architecture and provision
      Google Cloud resources that this example needs:

      ```sh
      "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/deploy.sh" \
          --server-ip "<SERVER_IP_ADDRESS>" \
          --workspace-bucket-name "<NVFLARE_WORKSPACE_BUCKET_NAME>" \
          --workload "client1"
      ```

      Where:

      - `<SERVER_IP_ADDRESS>` is the NVIDIA FLARE server IP address that you get
        from the output of the `server` deployment script.
      - `<NVFLARE_WORKSPACE_BUCKET_NAME>` is the NVIDIA FLARE Cloud Storage
        bucket name that you get from the output of the `server` deployment
        script.

1. Repeat the steps described to deploy `client1` to deploy `client2`.

### Check the status of the server and registered clients

In this section, you check the status of the NVIDIA FLARE server and clients:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Change the working directory to the directory where you cloned the repository
   for the `server1` instance of the reference architecture.

1. Set up the shell environment:

   ```bash
   source "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh"
   ```

1. Configure `kubectl` to access the cluster:

   ```bash
   gcloud container clusters get-credentials "${cluster_name}" --region "${cluster_region}" --project "${cluster_project_id}" --dns-endpoint
   ```

1. Get the list of NVIDIA FLARE pods running in the cluster:

   ```bash
   kubectl get pods --namespace fl-1
   ```

   The output is similar to the following:

   ```bash
   NAME                               READY   STATUS             RESTARTS        AGE
   nvflare-client1-7c5c469cdb-s4xn9   3/3     Running            9 (4m38s ago)   33m
   nvflare-client2-7b49bdd4d-h9xp5    3/3     Running            9 (4m56s ago)   66m
   nvflare-server1-9f7cb8dfd-rzl27    3/3     Running            11 (42s ago)    66m
   ```

1. Open a shell in the NVIDIA FLARE server pod:

   ```bash
   kubectl exec --stdin --tty --namespace fl-1 <NVIDIA_FLARE_SERVER_POD_NAME> -- /bin/bash
   ```

   Where:

   - `<NVIDIA_FLARE_SERVER_POD_NAME>` is the name of the NVIDIA FLARE server pod

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
   | site-2 | REDACTED | Mon Feb 10 13:45:09 2025 |
   | site-1 | REDACTED | Mon Feb 10 13:45:08 2025 |
   ------------------------------------------------
   Done [282012 usecs] 2025-02-10 13:45:11.537354
   ```

   If you don't see any registered client in the output, wait for a one minute
   and try again.

1. Exit from NVIDIA FLARE by pressing the `CTRL+D` key combination.

   When prompted, input the username: `admin@nvidia.com`

1. Close the container shell:

   ```bash
   exit
   ```

## Destroy the example environment

To destroy an instance of this example, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Destroy `client1`:

   1. Change the working directory to the directory where you cloned the
      repository for the `client1` instance of the reference architecture.

   1. Run the script to destroy an instance of this example:

   ```sh
   "platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/teardown.sh"
   ```

1. Repeat the steps described to destroy `client1` to deploy `client2`.

1. Repeat the steps described to destroy `client1` to deploy `server1`.
