# Inference reference implementation

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

To deploy this reference implementation, you need Terraform >= 1.8.0. For more
information about installing Terraform, see
[Install Terraform](https://developer.hashicorp.com/terraform/install).

```shell
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy.sh
```

## Teardown

```shell
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown.sh
```

## Workflow

The `deploy.sh` script will perform the following steps:

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
