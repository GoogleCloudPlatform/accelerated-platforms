# GKE Base Platform reference implementation

## Pull the source code

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

  ```
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.bashrc
  ```

  `zsh`

  ```
  sed -n -i -e '/^export ACP_REPO_DIR=/!p' -i -e '$aexport ACP_REPO_DIR="'"${ACP_REPO_DIR}"'"' ${HOME}/.zshrc
  ```

## Configure the platform

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

## Install Terraform 1.8.0+

> [!IMPORTANT]  
> At the time this guide was written, Cloud Shell had Terraform v1.5.7 installed
> by default. Terraform version 1.8.0 or later is required for this guide.

- Run the `install_terraform.sh` script to install Terraform 1.8.0.

  ```shell
  "${ACP_REPO_DIR}/tools/bin/install_terraform.sh"
  ```

## Deploy

- Deploy the reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/deploy-ap.sh
  ```

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/deploy-standard.sh
  ```

## Teardown

- Teardown the reference implementation.

  **GKE Autopilot**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/teardown-ap.sh
  ```

  **GKE Standard**

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/teardown-standard.sh
  ```
