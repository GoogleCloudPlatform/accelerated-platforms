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
  platform_default_project_id="<PROJECT_ID>"
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
  comfyui_accelerator_type="<ACCELERATOR>"
  sed -i '/^comfyui_accelerator_type[[:blank:]]*=/{h;s/=.*/= "'"${comfyui_accelerator_type}"'"/};${x;/^$/{s//comfyui_accelerator_type="'"${comfyui_accelerator_type}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/comfyui.auto.tfvars
  ```

  Valid values for `ACCELERATOR` are:

  - `nvidia-h100-80gb`
  - `nvidia-tesla-a100`
  - `nvidia-l4(default)`

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
  source ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
  ```

- Ensure that IAP is enabled.

  ```shell
  gcloud services enable iap.googleapis.com \
  --project="${comfyui_iap_oath_branding_project_id}"
  ```

- Check if the branding is already configured.

  ```shell
  gcloud iap oauth-brands list \
  --project="${comfyui_iap_oath_branding_project_id}"
  ```

  > If an entry is displayed, the branding is already configured.

- Configure the branding.

  ```shell
  gcloud iap oauth-brands create \
  --application_title="IAP Secured Application" \
  --project="${comfyui_iap_oath_branding_project_id}" \
  --support_email="<SUPPORT_EMAIL_ADDRESS>"
  ```

  Replace `<SUPPORT_EMAIL_ADDRESS>` with a group email address that you are a
  manger on or your personal email address.

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
  that the `comfyui_iap_oath_branding_project_id` project is in, you will need
  to manually set `IAP_DOMAIN` environment variable**

  ```
  IAP_DOMAIN="<project_id's organization domain>"
  ```

- Set the IAP domain in the configuration file

  ```
  sed -i '/^comfyui_iap_domain[[:blank:]]*=/{h;s/=.*/= "'"${IAP_DOMAIN}"'"/};${x;/^$/{s//comfyui_iap_domain="'"${IAP_DOMAIN}"'"/;H};x}' ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/comfyui.auto.tfvars
  ```

## Deploy

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-comfyui.sh
```

## Workflow

The `deploy-comfyui.sh` script will perform the following steps:

- Set up base GKE cluster platform.
- Create resources required to deploy ComfyUI on the GKE cluster and access it.
- Deploy ComfyUI on `nvidia-l4` accelerator and make the ComfyUI accessible
  through Identity-Aware Proxy.

## Verify ComfyUI deployment is up and running

- Set the environment variables

  ```
  source ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
  ```

- Source GKE cluster credentials

  ```
  gcloud container clusters get-credentials ${cluster_name} \
  --dns-endpoint \
  --location="${cluster_region}" \
  --project="${cluster_project_id}"
  ```

- Check the ComfyUI deployment

  ```
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${comfyui_kubernetes_namespace} get deployment/${comfyui_app_name}-${comfyui_accelerator_type} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

- When the deployment is ready, you will output similar to the following

  ```
  NAME                READY   UP-TO-DATE   AVAILABLE   AGE
  comfyui-nvidia-l4   1/1     1            1           XXXX
  ```

- Output the ComfyUI URL.

  ```
  echo -e "\nComfyUI URL: https://${comfyui_endpoints_hostname}\n"
  ```

- Open the ComfyUI URL in a web browser.

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
  checkpoint files for Stable diffusion base and refiner models, LTXV model and
  Flux text encoder from Hugging Face to the GCS bucket.

  - https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
  - https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0/resolve/main/sd_xl_refiner-1.0.safetensors
  - https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltx-video-2b-v0.9.1.safetensors
  - https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors

- Run the following command to trigger cloudbuild pipeline to copy checkpoint
  files:

  ```
  gcloud builds submit \
  --config="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/comfyui/copy-checkpoints/cloudbuild.yaml" \
  --gcs-source-staging-dir="gs://${comfyui_cloudbuild_source_bucket_name}/source" \
  --no-source \
  --project="${cluster_project_id}" \
  --service-account="${comfyui_cloudbuild_service_account_id}" \
  --substitutions="_BUCKET_NAME=${comfyui_cloud_storage_model_bucket_name}"
  ```

  It will take around 6 minutes to finish.

- When the copy is finished, you will see the output similar to the following:

  ```
  ID: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
  CREATE_TIME: YYYY-MM-DDTHH:MM:SS+ZZ:ZZ
  DURATION: #M##S
  SOURCE: -
  IMAGES: -
  STATUS: SUCCESS
  ```

- Refresh ComfyUI and click on `checkpoints` in MODEL LIBRARY, you will see
  three checkpoint files available to use. These files will be named
  `sd_xl_base_1.0.safetensors`, `sd_xl_refiner_1.0.safetensors` and
  `ltx-video-2b-v0.9`

- Click on `text_encoders` on ComfyUI in MODEL_LIBRARY, you will see a file
  named `t5xxl_fp16`

- You can download more models to use in your ComfyUI instance in a similar
  fashion.
- Get creative and storyboard your ideas on ComfyUI!

## ComfyUI workflows

This guide provides five workflows out of the box. On ComfyUI, click on
WORKFLOWS. You will five json workflow files.

- `imagen3-text-to-image` : This workflow shows text to image generation with
  Google's Imagen3 model.
- `imagen3-veo2-text-to-image-to-video` : This workflow shows text to image
  generation with Google's Imagen3 model and image to video generation with
  Google's Veo2 model.
- `ltxv-text-to-video` : This workflow shows text to video generation with
  Lightricks' LTXV-Video model.
- `sdxl-text-to-image` : This workflow shows text to image generation with
  Stable Diffusion refiner model.
- `veo2-text-to-video` : This workflow shows text to video generation with
  Google's Veo2 model.

> Note: ComfyUI custom nodes to Imagen3 and Veo2 are in preview mode.

Click any of the workflow files to open the workflow and click `Run` to see the
results.

## [Optional] Setup a Workflow API for batch operation

In this section you can deploy a Workflow API to front the ComfyUI deployment
and use it in batch mode by submitting ComfyUI workflows exported as .json
objects to the Workflow API. ComfyUI will still output the generated media in
the output bucket.

Deploy Workflow API resources:

```
cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/workflow_api
terraform init
terraform apply
```

Verify that the Workflow API has been successfully deployed:

```
kubectl -n comfyui get deploy,svc
```

Response should look like this:

```
NAME                                READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/comfyui-nvidia-l4   1/1     1            1           10d
deployment.apps/workflow-api        1/1     1            1           15h

NAME                        TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/comfyui-nvidia-l4   ClusterIP   34.118.235.48    <none>        8188/TCP   10d
service/workflow-api        ClusterIP   34.118.228.170   <none>        8080/TCP   15h
```

Once the deployment is ready, we can run a Pod running curl which we can use to
send requests to the Workflow API.

```
kubectl run -n comfyui --image=curlimages/curl:8.13.0 shell-long-running -- sh -c 'while sleep 3600; do :; done'
```

We can then exec into this Pod:

```
kubectl -n comfyui exec -it shell-long-running -- sh
```

Create a .json file containing an example workflow:

```
cat <<'EOF' >> sdxl.json
{ "prompt": {
   "3": {
     "inputs": {
       "seed": 780438972461674,
       "steps": 20,
       "cfg": 8,
       "sampler_name": "euler",
       "scheduler": "normal",
       "denoise": 1,
       "model": [
         "4",
         0
       ],
       "positive": [
         "6",
         0
       ],
       "negative": [
         "7",
         0
       ],
       "latent_image": [
         "5",
         0
       ]
     },
     "class_type": "KSampler",
     "_meta": {
       "title": "KSampler"
     }
   },
   "4": {
     "inputs": {
       "ckpt_name": "sd_xl_base_1.0.safetensors"
     },
     "class_type": "CheckpointLoaderSimple",
     "_meta": {
       "title": "Load Checkpoint"
     }
   },
   "5": {
     "inputs": {
       "width": 512,
       "height": 512,
       "batch_size": 1
     },
     "class_type": "EmptyLatentImage",
     "_meta": {
       "title": "Empty Latent Image"
     }
   },
   "6": {
     "inputs": {
       "text": "Futuristic city with flying cars, highly detailed, award winning color photograph.",
       "clip": [
         "4",
         1
       ]
     },
     "class_type": "CLIPTextEncode",
     "_meta": {
       "title": "CLIP Text Encode (Prompt)"
     }
   },
   "7": {
     "inputs": {
       "text": "text, watermark",
       "clip": [
         "4",
         1
       ]
     },
     "class_type": "CLIPTextEncode",
     "_meta": {
       "title": "CLIP Text Encode (Prompt)"
     }
   },
   "8": {
     "inputs": {
       "samples": [
         "3",
         0
       ],
       "vae": [
         "4",
         2
       ]
     },
     "class_type": "VAEDecode",
     "_meta": {
       "title": "VAE Decode"
     }
   },
   "9": {
     "inputs": {
       "filename_prefix": "ComfyUI",
       "images": [
         "8",
         0
       ]
     },
     "class_type": "SaveImage",
     "_meta": {
       "title": "Save Image"
     }
   }
 }
}
EOF
```

And run curl to send the request to the Workflow API:

```
curl --header "Content-Type: application/json"   --request POST   http://workflow-api.comfyui.svc.cluster.local:8080/api/v1/queue_prompt --data "@sdxl.json"
```

The response should look like this:

```
{"prompt_id":"b2f1bdb0-1690-4d81-ac8b-b2f58685e81d","number":0}
```

### Gateway

As a part of the Workflow API setup, an internal Gateway was also deployed along
with supporting resources (e.g HTTPRoute, SSL Certificate, IP Address, DNS Zone,
DNS record). This allows for clients that have private access to the VPC (e.g.
GKE, GCE, Cloud Run with VPC access enabled) to be able to reach the Workflow
API privately.

We can use the same curl Pod we created earlier to test the Gateway
connectivity. Exec into this Pod:

```
kubectl -n comfyui exec -it shell-long-running -- sh
```

Then:

```
curl --header "Content-Type: application/json"   --request POST   https://workflow-api.internal.com/api/v1/queue_prompt --data "@sdxl.json"
```

Where `workflow-api.internal.com` is the domain indicated in the DNS Zone
created in the Workflow API setup.

## Teardown

```
${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-comfyui.sh
```
