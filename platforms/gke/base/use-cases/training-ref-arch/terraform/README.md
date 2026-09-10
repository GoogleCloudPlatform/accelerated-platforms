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
- `kustomize`

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

## Configure Identity-Aware Proxy (IAP)

Identity-Aware Proxy (IAP) lets you establish a central authorization layer for
applications accessed by HTTPS, so you can use an application-level access
control model instead of relying on network-level firewalls.

IAP policies scale across your organization. You can define access policies
centrally and apply them to all of your applications and resources. When you
assign a dedicated team to create and enforce policies, you protect your project
from incorrect policy definition or implementation in any application.

For more information on IAP, see the
[Identity-Aware Proxy documentation](https://cloud.google.com/iap/docs/concepts-overview#gke)

### Configure OAuth consent screen for IAP

For this guide we will configure a generic OAuth consent screen setup for
internal use. Internal use means that only users within your organization can be
granted IAM permissions to access the IAP secured applications and resource.

See the
[Configuring the OAuth consent screen documentation](https://developers.google.com/workspace/guides/configure-oauth-consent)
for additional information

- Set environment variables.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/_shared_config/scripts/set_environment_variables.sh"
  ```

- Ensure that IAP is enabled.

  ```shell
  gcloud services enable iap.googleapis.com \
  --project="${mft_project_id}"
  ```

- Check if the branding is already configured.

  ```shell
  gcloud iap oauth-brands list \
  --project="${mft_project_id}"
  ```

  > If an entry is displayed, the branding is already configured.

- If not already configured, configure the branding.

  ```shell
  gcloud iap oauth-brands create \
  --application_title="IAP Secured Application" \
  --project="${mft_project_id}" \
  --support_email="<SUPPORT_EMAIL_ADDRESS>"
  ```

  Replace `<SUPPORT_EMAIL_ADDRESS>` with a group email address that you are a
  manager on or your personal email address. The email address should be
  supplied without the domain.

### Default IAP access

For simplicity, in this guide access to the IAP secured applications will be
configure to allow all users in the organization. Access can be configured per
IAP application or resources.

- Set the IAP allow domain

  ```
  IAP_DOMAIN=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" | awk -F@ '{print $2}')
  echo "IAP_DOMAIN=${IAP_DOMAIN}"
  ```

  **If the domain of the active `gcloud` user is different from the organization
  that the `mft_project_id` project is in, you will need to manually set
  `IAP_DOMAIN` environment variable**

  ```
  IAP_DOMAIN="<project_id's organization domain>"
  ```

- Set the IAP domain in the configuration file

  ```
  sed -i '/^mft_iap_domain[[:blank:]]*=/{h;s/=.*/= "'"${IAP_DOMAIN}"'"/};${x;/^$/{s//mft_iap_domain="'"${IAP_DOMAIN}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/_shared_config/mft.auto.tfvars
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
