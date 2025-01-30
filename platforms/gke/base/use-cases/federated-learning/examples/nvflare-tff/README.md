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

![NVIDIA FLARE example architecture](/platforms/gke/base/use-cases/federated-learning/assets/nvflare.svg "NVIDIA FLARE example architecture")

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

All the models generated will be stored in a Cloud storage bucket mounted by
each pod.

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to configure the reference architecture and provision Google
   Cloud resources that this example needs:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/deploy.sh"
   ```

### Build and push the example container image

In this section, you run a script that:

- Builds a container image with TensorFlow and NVIDIA FLARE installed locally on
  your host. To build the container image you need about 8GB of persistent
  storage space and can take up to 20 minutes. For a production deployment,
  consider using Cloud Build.
- Pushes the container images to the Artifact Registry repository that the
  Federated learning reference architecture provides.

To run the script, do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to build the container image:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/build-container-image.sh"
   ```

### Create NVIDIA FLARE deployment descriptors

In this section, you create descriptors to deploy NVIDIA FLARE in the reference
architecture:

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

   When prompted, pick the non highly-available deployment option because
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

1. Copy the NVIDIA FLARE TensorFlow demo deployment descriptors in the
   workspace:

   ```bash
   cp -R NVFlare-${NVFLARE_RELEASE_TAG}/examples/hello-world/hello-tf2 workspace/example_project/prod_00/admin@nvidia.com/transfer
   ```

1. Exit the NVIDIA FLARE container:

   ```bash
   exit
   ```

1. Copy the workspace folder to Cloud Storage:

   ```bash
   gcloud storage -m cp -r "${HOME}/nvflare-workspace/workspace" "gs://${NVFLARE_WORKSPACE_BUCKET_NAME}"
   ```

### Verify that NVIDIA FLARE pods are running

In this section, you verify that you deployed NVIDIA FLARE in the reference
architecture:

1. Open the
   [GKE Workloads Dashboard](https://cloud.google.com/kubernetes-engine/docs/concepts/dashboards#workloads)
   and verify that NVIDIA FLARE pods are running in the `fl-1` namespace. The
   output to look for is similar to the following:

   ```bash
   NAME                               READY   STATUS    RESTARTS   AGE
   nvflare-client1-57d5b45d84-bmv58   1/1     Running   0          16h
   nvflare-client2-895b65d8f-p4fs9    1/1     Running   0          16h
   nvflare-server1-66c44ddb47-dhtqz   1/1     Running   0          16h
   ```

### Submit the training job

Everything is now ready to submit and run the job:

1. Start a NVIDIA FLARE container based on the container image you previously
   built:

   ```bash
   docker run --rm -v "${HOME}/nvflare-workspace:/opt/NVFlare/workspace" -it "${NVFLARE_EXAMPLE_CONTAINER_IMAGE_LOCALIZED_ID_WITH_TAG}" bash
   ```

1. Connect to NVIDIA FLARE:

   ```bash
   cd workspace/example_project/prod_00/admin@nvidia.com/startup
   ./fl_admin.sh
   ```

   When prompted, the username is `admin@nvidia.com`

   At this point, you should be connected to the NVIDIA FLARE workspace. The
   output is similar to the following:

   ```bash
   User Name: admin@nvidia.com
   Trying to obtain server address
   Obtained server address: server1:8003
   Trying to login, please wait ...
   Logged into server at server1:8003 with SSID: ebc6125d-0a56-4688-9b08-355fe9e4d61a
   Type ? to list commands; type "? cmdName" to show usage of a command.
   >
   ```

   When connected, you can list the jobs submitted to the cluster by using the
   `list_jobs` command.

1. Submit a training job:

   ```bash
   submit_job hello-tf2
   ```

   The output is similar to the following:

   ```bash
   Submitted job: c8973f05-8787-41c5-8568-ecc15c7683b2
   Done [262650 usecs] 2024-05-23 09:47:04.543903
   ```

1. Verify that the training job is running:

   ```bash
   list_jobs
   ```

   The output is similar to the following:

   ```bash
   -----------------------------------------------------------------------------------------------------------------------------
   | JOB ID                               | NAME      | STATUS             | SUBMIT TIME                      | RUN DURATION   |
   -----------------------------------------------------------------------------------------------------------------------------
   | c8973f05-8787-41c5-8568-ecc15c7683b2 | hello-tf2 | RUNNING            | 2024-05-23T09:47:04.488652+00:00 | 0:00:11.978134 |
   -----------------------------------------------------------------------------------------------------------------------------
   Done [136046 usecs] 2024-05-23 09:47:17.630953
   ```

1. Verify that the job completed successfully:

   ```bash
   list_jobs
   ```

   The output is similar to the following:

   ```bash
   -----------------------------------------------------------------------------------------------------------------------------
   | JOB ID                               | NAME      | STATUS             | SUBMIT TIME                      | RUN DURATION   |
   -----------------------------------------------------------------------------------------------------------------------------
   | c8973f05-8787-41c5-8568-ecc15c7683b2 | hello-tf2 | FINISHED:COMPLETED | 2024-05-23T09:47:04.488652+00:00 | 0:01:44.335456 |
   -----------------------------------------------------------------------------------------------------------------------------
   Done [56885 usecs] 2024-05-23 09:49:15.420097
   ```

## Destroy the example environment and the reference architecture

To destroy an instance of this example and the reference architecture, you do
the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to destroy the reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/examples/nvflare-tff/teardown.sh"
   ```
