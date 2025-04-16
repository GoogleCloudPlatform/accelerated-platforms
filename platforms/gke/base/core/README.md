# Reference implementation for the Core GKE Accelerated Platform

## Pull the source code

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Clone the repository and change directory to the guide directory

   ```shell
   git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
   cd accelerated-platforms
   ```

1. Set environment variables

   ```shell
   ACP_REPO_DIR="$(pwd)" && \
   export ACP_REPO_DIR && \
   echo "export ACP_REPO_DIR=${ACP_REPO_DIR}" >> ${HOME}/.bashrc
   ```

   ```shell
   cd "${ACP_REPO_DIR}/platforms/gke/base" && \
   ACP_PLATFORM_BASE_DIR="$(pwd)" && \
   export ACP_PLATFORM_BASE_DIR && \
   echo "export ACP_PLATFORM_BASE_DIR=${ACP_PLATFORM_BASE_DIR}" >> ${HOME}/.bashrc
   ```

   ```shell
   cd "${ACP_REPO_DIR}/platforms/gke/base/core" && \
   ACP_PLATFORM_CORE_DIR="$(pwd)" && \
   export ACP_PLATFORM_CORE_DIR && \
   echo "export ACP_PLATFORM_CORE_DIR=${ACP_PLATFORM_CORE_DIR}" >> ${HOME}/.bashrc
   ```

## Configure the Core GKE Accelerated Platform

Terraform loads variables in the following order, with later sources taking
precedence over earlier ones:

- Environment variables (`TF_VAR_<variable_name>`)
- Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
- Any `-var` and `-var-file` options on the command line, in the order they are
  provided.

For more information about providing values for Terraform input variables, see
[Terraform input variables](https://developer.hashicorp.com/terraform/language/values/variables).

- Set the cluster project ID

```shell
export TF_VAR_cluster_project_id="<PROJECT_ID>"
```

**-- OR --**

```shell
vi ${ACP_PLATFORM_BASE_DIR}/_shared_config/cluster.auto.tfvars
```

```hcl
cluster_project_id = "<PROJECT_ID>"
```

- Set the Terraform project ID

```shell
export TF_VAR_terraform_project_id="<PROJECT_ID>"
```

**-- OR --**

```shell
vi ${ACP_PLATFORM_BASE_DIR}/_shared_config/terraform.auto.tfvars
```

```hcl
terraform_project_id = "<PROJECT_ID>"
```

## Deploy

To deploy this reference implementation, you need Terraform >= 1.8.0. For more
information about installing Terraform, see
[Install Terraform](https://developer.hashicorp.com/terraform/install).

```shell
${ACP_PLATFORM_CORE_DIR}/deploy.sh
```

## Teardown

```shell
${ACP_PLATFORM_CORE_DIR}/teardown.sh
```
