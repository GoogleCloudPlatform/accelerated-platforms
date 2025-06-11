# GKE Inference reference implementation

## Architecture

![Reference Architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/images/reference_architecture_simple.svg)

## Pull the source code

- Open [Cloud Shell](https://cloud.google.com/shell).

  To deploy this reference implementation, you need Terraform >= 1.8.0. For more
  information about installing Terraform, see
  [Install Terraform](https://developer.hashicorp.com/terraform/install).

- Clone the repository and set the repository directory environment variable.

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms && \
  export ACP_REPO_DIR="$(pwd)"
  ```

  To set the `ACP_REPO_DIR` value for new shell instances, write the value to
  your shell initialization file.

  `bash`

  ```
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.bashrc
  ```

  `zsh`

  ```
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.zshrc
  ```

## Configure

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

## Deploy

- Deploy the inference reference implementation.

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy.sh
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

- Private GKE Standard Cluster

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

## Teardown

- Teardown the inference reference implementation.

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown.sh
  ```
