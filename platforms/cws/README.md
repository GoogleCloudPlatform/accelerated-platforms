# Cloud Workstation

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

## Install Terraform 1.8.0+

> [!IMPORTANT]  
> At the time this guide was written, Cloud Shell had Terraform v1.5.7 installed
> by default. Terraform version 1.8.0 or later is required for this guide.

- Run the `install_terraform.sh` script to install Terraform 1.8.0.

  ```shell
  "${ACP_REPO_DIR}/tools/bin/install_terraform.sh"
  ```

## Configure the platform

- Set the platform default project ID.

  ```shell
  vi ${ACP_REPO_DIR}/platforms/cws/_shared_config/platform.auto.tfvars
  ```

  ```hcl
  platform_default_project_id = "<PROJECT_ID>"
  ```

- For additional platform configuration options see the Configuration
  Guide(WIP).

### Image Pipeline

- Set your Git token to the token file.

  ```shell
  vi ${ACP_REPO_DIR}/platforms/cws/_shared_config/secrets/cloudbuild_cws_image_git_token
  ```

  ```
  <git-provider-token>
  ```

- Set your Git namespace.

  ```shell
  vi ${ACP_REPO_DIR}/platforms/cws/_shared_config/build.auto.tfvars
  ```

  ```
  cloudbuild_cws_image_pipeline_git_namespace = "<namespace>"
  ```

- Set your Git repository.

  ```shell
  vi ${ACP_REPO_DIR}/platforms/cws/_shared_config/build.auto.tfvars
  ```

  ```
  cloudbuild_cws_image_pipeline_git_repository_name = "<repository name>"
  ```

> [!NOTE]  
> Terraform loads variables in the following order, with later sources taking
> precedence over earlier ones:
>
> - Environment variables (`TF_VAR_<variable_name>`)
> - Any `*.auto.tfvars` or files, processed in lexical order of their filenames.
> - Any `-var` and `-var-file` options on the command line, in the order they
>   are provided.
>
> For more information about providing values for Terraform input variables, see
> [Terraform input variables](https://developer.hashicorp.com/terraform/language/values/variables).

### Image Pipeline: Git provider host connection

- Source the platform environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/cws/_shared_config/scripts/set_environment_variables.sh"
  ```

#### GitHub

- Check if the
  [Google Cloud Build GitHub App](https://github.com/apps/google-cloud-build) is
  already configured for your organization or user namespace. Run the applicable
  command and go to the URL that is output.

  - For an organization:

    ```
    echo -e "\nOrganization installed GitHub Apps: https://github.com/organizations/${cloudbuild_cws_image_pipeline_git_namespace}/settings/installations\n"
    ```

  - For a user namespace:

    ```
    echo -e "\nUser namespace installed GitHub Apps: https://github.com/settings/installations\n"
    ```

  - If **Google Cloud Build** is listed under the **Installed GitHub Apps**,
    click **Configure**

  - Under **Repository access**, ensure that either **All repositories** is
    selected or your repository is selected under **Only select repositories**.

  - In the URL, the numeric installation ID will be displayed
    (https://github.com/organizations/<organization-name>/settings/installations/<installation-id>).
    Set the environment variable with the <installation-id>.

    ```
    vi ${ACP_REPO_DIR}/platforms/cws/_shared_config/build.auto.tfvars
    ```

    ```hcl
    cloudbuild_cws_image_pipeline_gh_app_installation_id = "<installation-id>"
    ```

    > If the Google Cloud Build GitHub App is already configured you can skip to
    > the to the next section

- Initiate a connection to your GitHub repository.

  ```shell
  gcloud builds connections create github ${cloudbuild_cws_image_pipeline_connection_name} \
  --project=${cloudbuild_project_id} \
  --region=${cloudbuild_location}
  ```

  After running the gcloud builds connections command, you will see a link to
  authorize the Cloud Build GitHub App.

- Follow the link to authorize the Cloud Build GitHub App.

- Install the Cloud Build GitHub App in your user namespace or in the
  organization for the repository. Permit the installation using the selected
  GitHub account.

- Verify the installation of your GitHub connection.

  ```shell
  gcloud builds connections describe ${cloudbuild_cws_image_pipeline_connection_name} \
  --project=${cloudbuild_project_id} \
  --region=${cloudbuild_location}
  ```

  The output should be similar to:

  ```
  createTime: 'YYYY-MM-DDTHH:MM:SS.ZZZZZZZZZZ'

  etag: XXXXXXXXXXXXXXXXXXXXXXXXXXXXX-XXXXXXXXXXXXX
  githubConfig:
    appInstallationId: '########'
    authorizerCredential:
      oauthTokenSecretVersion: projects/<cloudbuild_project_id>/secrets/<cloudbuild_cws_image_pipeline_connection_name>-github-oauthtoken-XXXXXX/versions/latest
      username: XXXXXXXXXX
  installationState:
    stage: COMPLETE
  name: projects/<cloudbuild_project_id>/locations/<cloudbuild_location>/connections/<cloudbuild_cws_image_pipeline_connection_name>
  reconciling: false
  updateTime: 'YYYY-MM-DDTHH:MM:SS.ZZZZZZZZZZ'
  ```

- Get the appInstallationId for the Cloud Build GitHub App.

  ```
  export TF_VAR_cloudbuild_cws_image_pipeline_gh_app_installation_id=$(gcloud builds connections describe ${cloudbuild_cws_image_pipeline_connection_name} \
  --project=${cloudbuild_project_id} \
  --region=${cloudbuild_location} \
  --format="value(githubConfig.appInstallationId)") && \
  echo -e "\nTF_VAR_cloudbuild_cws_image_pipeline_gh_app_installation_id=${TF_VAR_cloudbuild_cws_image_pipeline_gh_app_installation_id}"
  ```

For additional information see the
[Connecting a GitHub host](https://cloud.google.com/build/docs/automating-builds/github/connect-repo-github?generation=2nd-gen#connecting_a_github_host)
part of the
[Connect to a GitHub repository](https://cloud.google.com/build/docs/automating-builds/github/connect-repo-github?generation=2nd-gen)
document.

## Initialize the Cloud Workstation repository

> [!IMPORTANT]  
> Once the repository is initialized, to change Terraform variables you must
> edit the respective `.auto.tfvars` file in the `_shared_config` directory or
> pass them in via the command line. `TF_VAR_` environment variables will be
> ignored.

- Initialize the repository

  ```shell
  ${ACP_REPO_DIR}/platforms/cws/bin/cws_initialize.sh
  ```

## Apply the Cloud Workstation terrastacks

- Apply the `cluster` terrastack.

  ```shell
  ${ACP_REPO_DIR}/platforms/cws/bin/cws_cluster_apply.sh
  ```

> [!IMPORTANT]  
> Before applying the `image_pipeline` terrastack, ensure:
>
> - Your Git namespace is set:
>   `grep cloudbuild_cws_image_pipeline_git_namespace "${ACP_REPO_DIR}/platforms/cws/_shared_config/build_variables.tf"`
>
> - Your Git repository name is set:
>   `grep cloudbuild_cws_image_pipeline_git_repository_name "${ACP_REPO_DIR}/platforms/cws/_shared_config/build_variables.tf"`
>
> - Your Git token has been added to the token file.
>   `cat "${ACP_REPO_DIR}/platforms/cws/_shared_config/secrets/cloudbuild_cws_image_git_token"`

- Apply the `image_pipeline` terrastack.

  ```shell
  ${ACP_REPO_DIR}/platforms/cws/bin/cws_image_pipeline_apply.sh
  ```

## Destroy the Cloud Workstation terrastacks

- Destroy the `image_pipeline` terrastack.

  ```shell
  ${ACP_REPO_DIR}/platforms/cws/bin/cws_image_pipeline_destroy.sh
  ```

- Destroy the `cluster` terrastack.

  ```shell
  ${ACP_REPO_DIR}/platforms/cws/bin/cws_cluster_destroy.sh
  ```

## Reset the Cloud Workstation repository

- Reset the repository

  ```shell
  ${ACP_REPO_DIR}/platforms/cws/bin/cws_reset.sh
  ```
