# Inference reference implementation

## Pull the source code

- Clone the repository and change directory to the guide directory

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

- Set the cluster project ID

  ```
  export TF_VAR_cluster_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```
  vi ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars
  ```

  ```
  cluster_project_id = "<PROJECT_ID>"
  ```

- Set the Terraform project ID

  ```
  export TF_VAR_terraform_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```
  vi ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/terraform.auto.tfvars
  ```

  ```
  terraform_project_id = "<PROJECT_ID>"
  ```

## Deploy

To deploy this reference implementation, you need Terraform >= 1.8.0. For more
information about installing Terraform, see
[Install Terraform](https://developer.hashicorp.com/terraform/install).

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy.sh
```

## Teardown

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown.sh
```
