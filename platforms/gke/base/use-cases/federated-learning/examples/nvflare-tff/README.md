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

Before deploying the NVIDIA FLARE example described in this document, you need
to deploy the Federated learning reference architecture first. Then, you can
deploy the NVIDIA FLARE example.

### Provision and configure Google Cloud infrastructure

For this example, you provision new Google Cloud resources in addition to the
ones that the Federated learning reference architecture provisions.

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to configure the reference architecture and provision Google
   Cloud resources that this example needs:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/deploy.sh"
   ```

### Build and push the example container image

In this section, you run a script that builds a container image with TensorFlow
and NVIDIA FLARE installed locally on your host. To build the container image
you need about 8GB of persistent storage space and can take up to 20 minutes.
For a production deployment, consider using Cloud Build.

To run the script, do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to build the container image:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/build-container-image.sh"
   ```

### Create NVIDIA FLARE deployment descriptors

In this section, you create descriptors to deploy NVIDIA FLARE in the reference
architecture:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Create a directory to store the NVIDIA FLARE workspace:

   ```bash
   mkdir "${HOME}/nvflare-workspace"
   ```

1. Grant the NVIDIA FLARE user ownership on the NVIDIA FLARE workspace:

   ```bash
   sudo chown -R 10000:10000 "${HOME}/nvflare-workspace"
   ```

1. Load NVIDIA FLARE example environment configuration:

   ```bash
   source "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/setup-environment.sh" && load_fl_terraform_outputs
   ```

1. Run an NVIDIA FLARE container based on the container image you built in the
   preceding section:

   ```bash
   docker run --rm -v "${HOME}/nvflare-workspace:/opt/NVFlare/workspace" -it "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" bash
   ```

1. Run the NVIDIA FLARE provisioning tool to create a NVIDIA FLARE project
   configuration file (`project.yml`) that you can customize to your needs:

   ```bash
   nvflare provision
   ```

   When prompted, choose the non highly-available deployment option because
   highly-available NVIDIA FLARE deployments are not yet supported on
   Kubernetes.

1. Run the provisioning tool again to generate deployment descriptors:

   ```bash
   nvflare provision
   ```

   The provisioning tool generates deployment descriptors:

   - `server1` is the server that will aggregate all the results from the
     computation
   - `site-1` and `site-2` are the clients that will be connected to the server
   - `admin@nvidia.com` is the administration client to start and list jobs

1. Exit the NVIDIA FLARE container:

   ```bash
   exit
   ```

1. Copy the workspace folder to Cloud Storage:

   ```bash
   gcloud storage cp --recursive "${HOME}/nvflare-workspace/workspace" "gs://${NVFLARE_EXAMPLE_WORKSPACE_BUCKET_NAME}"
   ```

### Push the example container image

In this section, you run a script that pushes the container images to the
Artifact Registry repository that the Federated learning reference architecture
provides.

To run the script, do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to build the container image:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/push-container-image.sh"
   ```

### Verify that NVIDIA FLARE pods are running

In this section, you verify that you deployed NVIDIA FLARE in the reference
architecture:

1. Open the
   [GKE Workloads Dashboard](https://cloud.google.com/kubernetes-engine/docs/concepts/dashboards#workloads)
   and verify that NVIDIA FLARE pods are running in the `fl-1` namespace. The
   output to look for is similar to the following:

   ```bash
   Name                               Status Pods
   nvflare-client1-57d5b45d84-bmv58   OK     1/1
   nvflare-client2-895b65d8f-p4fs9    OK     1/1
   nvflare-server1-66c44ddb47-dhtqz   OK     1/1
   ```

### Submit the training job

In this section, you submit and run a training job:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Configure `kubectl` to access the cluster:

   ```bash
   gcloud container clusters get-credentials <CLUSTER_NAME> --region <CLUSTER_REGION> --project <CLUSTER_PROJECT> --dns-endpoint
   ```

   Where:

   - `<CLUSTER_NAME>` is the name of the GKE cluster.
   - `<CLUSTER_REGION>` is the region of the GKE cluster.
   - `<CLUSTER_PROJECT>` is the project of the GKE cluster.

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

   When prompted, the username is `admin@nvidia.com`

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

## Destroy the example environment and the reference architecture

To destroy an instance of this example and the reference architecture, you do
the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to destroy the reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/teardown.sh"
   ```
