# GKE Inference reference implementation

## Architecture

![Reference Architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/images/reference_architecture_simple.svg)

## Before you begin

### Permissions

You can choose between Project Owner access or granular access to implement a
principle of least privilege access.

#### Option 1: Project Owner role

Your account will have full administrative access to the project.

- `roles/owner`: Full access to all resources in the project.
  ([Project Owner role](https://cloud.google.com/iam/docs/roles-overview#legacy-basic))

#### Option 2: Granular Access

Your account needs to be assigned the following roles to access to the required
resources:

- `roles/artifactregistry.admin`: Grants full administrative access to Artifact
  Registry, allowing management of repositories and artifacts.
- `roles/browser`: Provides read-only access to browse resources in a project.
- `roles/compute.networkAdmin`: Grants full control over Compute Engine network
  resources.
- `roles/container.clusterAdmin`: Provides full control over Google Kubernetes
  Engine (GKE) clusters, including creating and managing clusters.
- `roles/iam.serviceAccountAdmin`: Grants full control over managing service
  accounts in the project.
- `roles/resourcemanager.projectIamAdmin`: Allows managing IAM policies and
  roles at the project level.
- `roles/servicenetworking.serviceAgent`: Allows managing service networking
  configurations.
- `roles/serviceusage.serviceUsageAdmin`: Grants permission to enable and manage
  services and APIs for a project.

### Requirements

This guide was designed to be run from
[Cloud Shell](https://cloud.google.com/shell) in the Google Cloud console. Cloud
Shell has the following tools installed:

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
- `curl`
- `envsubst`
- `jq`
- `kubectl`
- `nc`
- `sponge`
- `wget`

## Prepare the environment

### Pull the source code

- Open [Cloud Shell](https://cloud.google.com/shell).

- Clone the repository and set the repository directory environment variable.

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms && \
  export ACP_REPO_DIR="$(pwd)"
  ```

  To set the `ACP_REPO_DIR` value for new shell instances, write the value to
  your shell initialization file.

  `bash`

  ```shell
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.bashrc
  ```

  `zsh`

  ```shell
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.zshrc
  ```

### Configuration

Terraform loads variables in the following order, with later sources taking
precedence over earlier ones:

- Environment variables (`TF_VAR_<variable_name>`)
- Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
- Any `-var` and `-var-file` options on the command line, in the order they are
  provided.

For more information about providing values for Terraform input variables, see
[Terraform input variables](https://developer.hashicorp.com/terraform/language/values/variables).

- Set the platform default project ID

  ```shell
  export TF_VAR_platform_default_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```shell
  vi ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

  ```hcl
  platform_default_project_id = "<PROJECT_ID>"
  ```

### Install Terraform 1.8.0+

> [!IMPORTANT]  
> At the time this guide was written, Cloud Shell had Terraform v1.5.7 installed
> by default. Terraform version 1.8.0 or later is required for this guide.

- Run the `install_terraform.sh` script to install Terraform 1.8.0.

  ```shell
  "${ACP_REPO_DIR}/tools/bin/install_terraform.sh"
  ```

## Deploy and configure Google Cloud resources

- Deploy the inference reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh
  ```

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-standard.sh
  ```

- Configure the platform.

  - [Optional]
    [Hugging Face initialization](/platforms/gke/base/core/huggingface/initialize/README.md)
  - [Optional]
    [NVIDIA initialization](/platforms/gke/base/core/nvidia/initialize/README.md)

### Resources created

- Cloud Storage Buckets

  - Hugging Face Hub models
  - Terraform state

- VPC Network

  - Cloud Router
    - Google API direct connectivity routes
  - Regional Subnet
    - NAT Gateway
  - VPC firewall rules
    - Allow Google API direct connectivity rule

- Private GKE Cluster

  - Automatic application monitoring
  - Custom Compute Classes
    - [CPU](/platforms/gke/base/core/custom_compute_class/templates/manifests/cpu)
      - cpu-n4-s-8
    - [GPU](/platforms/gke/base/core/custom_compute_class/templates/manifests/gpu)
      - gpu-a100-40gb-x2
      - gpu-a100-80gb-x1
      - gpu-h100-80gb-high-x1
      - gpu-h100-80gb-high-x2
      - gpu-h100-80gb-high-x4
      - gpu-h100-80gb-high-x8
      - gpu-h100-80gb-mega-x8
      - gpu-h200-141gb-ultra-x8
      - gpu-l4-24gb-s4-x1
      - gpu-l4-24gb-s8-x1
      - gpu-l4-24gb-s12-x1
      - gpu-l4-24gb-s16-x1
      - gpu-l4-24gb-s32-x1
      - gpu-l4-24gb-x2
      - gpu-l4-24gb-x4
      - gpu-l4-24gb-x8
    - [TPU](/platforms/gke/base/core/custom_compute_class/templates/manifests/tpu)
      - tpu-v4-2x2x1
      - tpu-v4-2x2x2
      - tpu-v5e-2x2
      - tpu-v5e-2x4
      - tpu-v5p-2x2x1
      - tpu-v5p-2x2x2
      - tpu-v6e-2x2
      - tpu-v6e-2x4
  - Gateway API
    - Inference Gateway
  - `system` Node Pool
  - Workloads
    - Custom metrics adapter
    - Jobset
    - Kueue
    - LeaderWorkerSet (LWS)
    - [Priority Classes](/platforms/gke/base/core/workloads/priority_class/templates/manifests)
      - [critical](/docs/platforms/gke/base/core/workloads/priority_class/templates/manifests/priority-class-critical.yaml)
      - [high](/docs/platforms/gke/base/core/workloads/priority_class/templates/manifests/priority-class-high.yaml)
      - [standard](/docs/platforms/gke/base/core/workloads/priority_class/templates/manifests/priority-class-standard.yaml)
        (default)
      - [low](/docs/platforms/gke/base/core/workloads/priority_class/templates/manifests/priority-class-low.yaml)
      - [lowest](/docs/platforms/gke/base/core/workloads/priority_class/templates/manifests/priority-class-lowest.yaml)

- Secret Manager Secrets

  - Hugging Face Hub read token
  - Hugging Face Hub write token

## Clean up

- Teardown the inference reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-ap.sh
  ```

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-standard.sh
  ```
