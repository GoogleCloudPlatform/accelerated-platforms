# ComfyUI reference implementation

## Pull the source code

- Open [Cloud Shell](https://cloud.google.com/shell).

  To deploy this reference implementation, you need Terraform >= 1.8.0. For more
  information about installing Terraform, see
  [Install Terraform](https://developer.hashicorp.com/terraform/install).

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

- Set the platform defaults project ID

  ```
  export TF_VAR_platform_default_project_id="<PROJECT_ID>"
  ```

  **-- OR --**

  ```
  platform_default_project_id = "<PROJECT_ID>"
  sed -i '/^platform_default_project_id[[:blank:]]*=/{h;s/=.*/= "'"${platform_default_project_id}"'"/};${x;/^$/{s//platform_default_project_id = "'"${platform_default_project_id}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

- Optional : By default, the platform name is set to `dev`. If you want to
  change it, set the platform name

  ```
  platform_name="<PLATFORM_NAME>"
  sed -i '/^platform_name[[:blank:]]*=/{h;s/=.*/= "'"${platform_name}"'"/};${x;/^$/{s//platform_name="'"${platform_name}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars
  ```

- Optional : Run the following step if you want to run ComfyUI on an accelerator
  other than L4 which is the default accelerator for this deployment.

  ```
  accelerator="<ACCELERATOR>"
  sed -i '/^accelerator[[:blank:]]*=/{h;s/=.*/= "'"${accelerator}"'"/};${x;/^$/{s//accelerator="'"${accelerator}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/comfyui.auto.tfvars

  Valid values for ACCELERATOR are nvidia-h100-80gb, nvidia-tesla-a100 and nvidia-l4(default)
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

**NOTE: These steps only need to be completed once for a project.**

- Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard?) >
  [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)
  configuration page.
- Select **Internal** for the **User Type**
- Click **CREATE**
- Enter **IAP Secured Application** for the the **App name**
- Enter an email address for the **User support email**
- Enter an email address for the **Developer contact information**
- Click **SAVE AND CONTINUE**
- Leave the default values for **Scopes**
- Click **SAVE AND CONTINUE**
- On the **Summary** page, click **BACK TO DASHBOARD**
- The **OAuth consent screen** should now look like this:
  ![oauth consent screen](/docs/platforms/gke-aiml/playground/images/oauth-consent-screen.png)

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
  that the `cluster_project_id` project is in, you will need to manually set
  `IAP_DOMAIN` environment variable**

  ```
  IAP_DOMAIN="<cluster_project_id organization domain>"
  ```

- Set the IAP domain in the configuration file

  ```
  sed -i '/^comfyui_iap_domain[[:blank:]]*=/{h;s/=.*/= "'"${IAP_DOMAIN}"'"/};${x;/^$/{s//comfyui_iap_domain="'"${IAP_DOMAIN}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/comfyui.auto.tfvars
  ```

## Deploy

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-comfyui.sh
```

## Teardown

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-comfyui.sh
```

## Workflow

The `deploy-comfyui.sh` script will perform the following steps:

- Set up base GKE cluster platform.
- Create resources required to deploy ComfyUI on the GKE cluster and access it.
- Deploy ComfyUI on `nvidia-l4` accelerator and make the ComfyUI accessible
  through Identity-Aware Proxy.

## Verify ComfyUI deployment is up and running

- Source output variables from Terraform run

  ```
  source ${ACP_REPO_DIR}/env_vars
  ```

- Source GKE cluster credentials

  ```
  gcloud container clusters get-credentials ${GKE_CLUSTER_NAME} \
  --dns-endpoint \
  --location="${GKE_CLUSTER_REGION}" \
  --project="${GKE_PROJECT_ID}"
  ```

- Check the ComfyUI deployment

  ```
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${COMFYUI_NAMESPACE} get deployment/${COMFYUI_APP_NAME}-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

- When the deployment is ready, you will output similar to the following

  ```
  NAME                READY   UP-TO-DATE   AVAILABLE   AGE
  comfyui-nvidia-l4   1/1     1            1           XXXX
  ```

- Fetch the DNS.

  ```
  echo $COMFYUI_URL
  ```

- Open the DNS in the web browser to access COmfyUI.

## Load models in ComfyUI

In ComfyUI, click the `Model Library(m)` menu shown with the box icon on the
left side. You will see empty folders including checkpoint folder. When ComfyUI
was deployed, there were three GCS buckets created with the suffixes
`comfyui-input`, `comfyui-output` and `comfyui-models` and these buckets are
mounted on the container that is running ComfyUI. The ComfyUI Model Library is
mounted on the bucket with the suffix `comfyui-models`. If you want to use a
model in ComfyUI, you can download its checkpoint file to that bucket and it
will show up in ComfyUI Model Library.

You can use different methods to download checkpoint files to the bucket. These
files can be large and the disk space where you are running this guide could be
limited. So, you can use perform the copy operation using a K8s job or
Cloudbuild pipeline or some thing else.

- In this guide, we will use Cloudbuild pipeline to copy the following
  checkpoint files for Stable diffusion base and refiner models from Huggingface
  to the GCS bucket.

  ```
  https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors?download=true"

  https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0/resolve/main/sd_xl_refiner-1.0.safetensors?download=true

  ```

- Run the following command to trigger cloudbuild pipeline to copy checkpoint
  files:

  ```
  gcloud builds submit --no-source --config="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/copy_checkpoints/cloudbuild.yaml" --service-account="${CUSTOM_SA}"  --gcs-source-staging-dir="gs://${STAGING_BUCKET}/source" --project="${GKE_PROJECT_ID}" --substitutions="_BUCKET_NAME=${COMFYUI_MODEL_BUCKET}"
  ```

- When the copy is finished, you will see the output similar to the following:

  ```
  ID: XXXXXXXXXXXXXXXXX
  CREATE_TIME: XXXXXXXXX
  DURATION: XXXX
  SOURCE: -
  IMAGES: -
  STATUS: SUCCESS
  ```

- Refresh ComfyUI and click on `checkpoints` , you will see two checkpoint files
  available to use.

- You can download more models to use in your ComfyUI instance in a similar
  fashion.
- Get creative and storyboard your ideas on ComfyUI!
