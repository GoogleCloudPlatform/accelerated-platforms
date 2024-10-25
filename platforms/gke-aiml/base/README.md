# Reference implementation for regional GKE accelerator clusters

## Pull the source code

- Clone the repository and change directory to the guide directory

  ```
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Set environment variables

  ```
  export ACP_BASE_DIR=$(pwd) && \
  echo "export ACP_BASE_DIR=${ACP_BASE_DIR}" >> ${HOME}/.bashrc
  ```

  ```
  cd platforms/gke-aiml/base && \
  export ACP_PLATFORM_BASE_DIR=$(pwd) && \
  echo "export ACP_PLATFORM_BASE_DIR=${ACP_PLATFORM_BASE_DIR}" >> ${HOME}/.bashrc
  ```

## Configure

Terraform loads variables in the following order, with later sources taking precedence over earlier ones:

- Environment variables (`TF_VAR_<variable_name>`)
- Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
- Any `-var` and `-var-file` options on the command line, in the order they are provided.

- Set the cluster project ID

```
export TF_VAR_cluster_project_id="<PROJECT_ID>"
```

**-- OR --**

```
vi ${ACP_PLATFORM_BASE_DIR}/shared_config/cluster.auto.tfvars
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
vi ${ACP_PLATFORM_BASE_DIR}/shared_config/terraform.auto.tfvars
```

```
terraform_project_id = "<PROJECT_ID>"
```

## Deploy

```
${ACP_PLATFORM_BASE_DIR}/deploy.sh
```

## Teardown

```
${ACP_PLATFORM_BASE_DIR}/teardown.sh
```
