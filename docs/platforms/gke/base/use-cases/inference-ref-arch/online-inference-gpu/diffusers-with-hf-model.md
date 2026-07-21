# Online inference using Diffusers with GPUs on Google Kubernetes Engine (GKE)

This example implements online inference using GPUs on Google Kubernetes Engine
(GKE)

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

1. Deploy and configure the
   [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).

1. Get access to the models.

   - For FLUX.1-schnell:

     - Accept the conditions to access its files and content on the Hugging Face
       model page.
       - [**black-forest-labs/FLUX.1-schnell**](https://huggingface.co/black-forest-labs/FLUX.1-schnell)

   - For FLUX.2-klein-4B: The model is not gated, so there's no license check.

1. Ensure your
   [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
   has been added to Secret Manager.

## Create and configure the Google Cloud resources

1. Deploy the online GPU resources.

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
   rm -rf .terraform/ terraform.tfstate* && \
   terraform init && \
   terraform plan -input=false -out=tfplan && \
   terraform apply -input=false tfplan && \
   rm tfplan
   ```

## Download the model to Cloud Storage

1. Choose the model.

   - [**FLUX.1-schnell**](https://huggingface.co/black-forest-labs/FLUX.1-schnell):

     ```shell
     export HF_MODEL_ID="black-forest-labs/flux.1-schnell"
     ```

   - [**FLUX.2-klein-4B**](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B):

     ```shell
     export HF_MODEL_ID="black-forest-labs/flux.2-klein-4b"
     ```

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

1. Configure the model download job.

   ```shell
   "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
   ```

1. Deploy the model download job.

   ```shell
   kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
   ```

1. Watch the model download job until it is complete.

   ```shell
   watch --color --interval 5 --no-title \
   "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-hf-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
   echo '\nLogs(last 10 lines):'
   kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --all-containers --tail 10"
   ```

   When the job is complete, you will see the following:

   ```text
   NAME                       STATUS     COMPLETIONS   DURATION   AGE
   XXXXXXXX-hf-model-to-gcs   Complete   1/1           ###        ###
   ```

   You can press `CTRL`+`c` to terminate the watch.

1. Delete the model download job.

   ```shell
   kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
   ```

## Build the container image

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

1. Build the container image for the Diffusers inference server.

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   rm -rf ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/diffusers_flux/.terraform/ terraform.tfstate* && \
   terraform -chdir=${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/diffusers_flux init && \
   terraform -chdir=${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/diffusers_flux plan -input=false -out=tfplan && \
   terraform -chdir=${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/diffusers_flux apply -input=false tfplan && \
   rm ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/diffusers_flux/tfplan
   ```

   The build usually takes about 25 minutes.

## Deploy the inference workload

1. Source the environment configuration.

   ```shell
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   ```

1. Check the model name.

   ```shell
   echo "HF_MODEL_NAME=${HF_MODEL_NAME}"
   ```

   > If the `HF_MODEL_NAME` variable is not set, ensure that `HF_MODEL_ID` is
   > set and source the `set_environment_variables.sh` script:
   >
   > ```shell
   > source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   > ```

   > If the `HF_MODEL_NAME` variable is not set, ensure that `HF_MODEL_ID` is
   > set and source the `set_environment_variables.sh` script:
   >
   > ```shell
   > source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   > ```

   | Model           | NVIDIA L4 | 2x NVIDIA L4 | 4x NVIDIA L4 | NVIDIA H100 | NVIDIA RTX Pro 6000 | 1/2 NVIDIA RTX Pro 6000 | 1/4 NVIDIA RTX Pro 6000 | 1/8 NVIDIA RTX Pro 6000 |
   | --------------- | --------- | ------------ | ------------ | ----------- | ------------------- | ----------------------- | ----------------------- | ----------------------- |
   | flux.1-schnell  | ✅        | Not tested   | Not tested   | ✅          | Not tested          | Not tested              | Not tested              | Not tested              |
   | flux.2-klein-4B | ✅        | ✅           | ✅           | Not tested  | ✅                  | ✅                      | ✅                      | ❌                      |

   > When using fractional GPUs (1/2, 1/4, 1/8), you might see a warning in the
   > logs of the `inference-server` container:
   > `No CUDA runtime is found, using CUDA_HOME='/usr/local/cuda'`. You can
   > ignore this warning. It's due to the GPU virtualization layer masking
   > hardware probes from the PyTorch JIT compiler. It does not affect inference
   > performance or stability.

   - **NVIDIA Tesla L4 24GB**:

     - 1x **NVIDIA Tesla L4**:

       ```shell
       export ACCELERATOR_TYPE="l4"
       ```

     - 2x **NVIDIA Tesla L4**:

       ```shell
       export ACCELERATOR_TYPE="l4-x2"
       ```

     - 4x **NVIDIA Tesla L4**:

       ```shell
       export ACCELERATOR_TYPE="l4-x4"
       ```

   - 1x **NVIDIA H100 80GB**:

     ```shell
     export ACCELERATOR_TYPE="h100"
     ```

   - **NVIDIA RTX Pro 6000**:

     - 1x **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000"
       ```

     - 1/2x (half) of a **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000-1-2"
       ```

     - 1/4x (one fourth) of a **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000-1-4"
       ```

     - 1/8x (one eight) of a **NVIDIA RTX Pro 6000**:

       ```shell
       export ACCELERATOR_TYPE="rtx-pro-6000-1-8"
       ```

   Ensure that you have enough quota in your project to provision the selected
   accelerator type. For more information, see about viewing GPU quotas, see
   [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

1. Configure the deployment.

   ```shell
   "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/configure_diffusers.sh"
   ```

1. Deploy the inference workload.

   ```shell
   kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
   ```

1. Watch the deployment until it is ready.

   ```shell
   watch --color --interval 5 --no-title \
   "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
   echo '\nLogs(last 10 lines):'
   kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
   ```

   When the deployment is ready, you will see the following:

   ```text
   NAME                                           READY   UP-TO-DATE   AVAILABLE   AGE
   diffusers-<ACCELERATOR_TYPE>-<HF_MODEL_NAME>   1/1     1            1           ###
   ```

   You can press `CTRL`+`c` to terminate the watch.

1. Send a test request.

   ```shell
   kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/diffusers-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null &
   PF_PID=$!
   while ! echo -e '\x1dclose\x0d' | telnet localhost 8000 >/dev/null 2>&1; do
     sleep 0.1
   done
   curl http://localhost:8000/generate \
   --data '{
     "height": 512,
     "num_inference_steps": 4,
     "prompt": "A photo of a dog playing fetch in a park.",
     "width": 512
   }' \
   --header "Content-Type: application/json" \
   --output ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_${ACCELERATOR_TYPE}_image.png \
   --request POST \
   --show-error \
   --silent
   ls -alh ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_${ACCELERATOR_TYPE}_image.png
   kill -9 ${PF_PID}
   ```

1. Delete the workload.

   ```shell
   kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/diffusers/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
   ```

## Clean up

1. Destroy the container image.

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/diffusers_flux && \
   rm -rf .terraform/ terraform.tfstate* && \
   terraform init &&
   terraform destroy -auto-approve
   ```

1. Destroy the online GPU resources.

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
   rm -rf .terraform/ terraform.tfstate* && \
   terraform init &&
   terraform destroy -auto-approve
   ```
