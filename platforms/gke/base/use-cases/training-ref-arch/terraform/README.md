# GKE Training reference implementation

### Requirements

This guide was designed to be run from
[Cloud Shell](https://cloud.google.com/shell) in the Google Cloud console. Cloud
Shell has the following tools installed:

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
- `curl`
- `envsubst`
- `jq`
- `kubectl`
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

- Deploy the training reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/deploy-ap.sh
  ```

  > The `deploy-ap.sh` script usually takes 15 to 20 minutes.

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/deploy-standard.sh
  ```

  > The `deploy-standard.sh` script usually takes 15 to 20 minutes.

## Example

This reference implementation is designed to support various training patterns.
Some example patterns provided are:

- [Model Fine Tuning](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/README.md)

## Clean up

- Teardown the training reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/teardown-ap.sh
  ```

  > The `teardown-ap.sh` script usually takes 10 to 15 minutes.

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/teardown-standard.sh
  ```

  > The `teardown-standard.sh` script usually takes 10 to 15 minutes.
