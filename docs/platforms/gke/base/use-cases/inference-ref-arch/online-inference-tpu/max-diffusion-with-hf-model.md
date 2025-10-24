# Online inference using MaxDiffusion with TPUs on Google Kubernetes Engine (GKE)

This example implements online inference using TPUs on Google Kubernetes Engine
(GKE)

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the model to Cloud Storage

- Choose the model.

  - **SD-XL 1.0-base**:

    ```shell
    export HF_MODEL_ID="stabilityai/stable-diffusion-xl-base-1.0"
    ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the model download job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  ```

- Deploy the model download job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the model download job until it is complete.

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

- Delete the model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

## Build the container image

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Build the container image for the MaxDiffusion inference server.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/tpu/max_diffusion_sdxl && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  > The build usually takes 15 to 20 minutes.

## Deploy the inference workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Set the environment variables for the workload.

  - Check the model name.

    ```shell
    echo "HF_MODEL_NAME=${HF_MODEL_NAME}"
    ```

    > If the `HF_MODEL_NAME` variable is not set, ensure that `HF_MODEL_ID` is
    > set and source the `set_environment_variables.sh` script:
    >
    > ```shell
    > source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"`
    > ```

  - Select an accelerator.

    | Model                        | v5e | v6e |
    | ---------------------------- | --- | --- |
    | stable-diffusion-xl-base-1.0 | ✅  | ✅  |

    - **v5e**:

      ```shell
      export ACCELERATOR_TYPE="v5e"
      ```

    - **v56e**:

      ```shell
      export ACCELERATOR_TYPE="v6e"
      ```

    Ensure that you have enough quota in your project to provision the selected
    accelerator type. For more information, see about viewing TPU quotas, see
    [Ensure that you have TPU quota](https://cloud.google.com/kubernetes-engine/docs/how-to/tpus#ensure-quota).

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/configure_max_diffusion.sh"
  ```

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion//${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} get deployment/max-diffusion-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} logs deployment/max-diffusion-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see the following:

  ```text
  NAME                                               READY   UP-TO-DATE   AVAILABLE   AGE
  max-diffusion-<ACCELERATOR_TYPE>-<HF_MODEL_NAME>   1/1      1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Send a test request.

  ```shell
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} port-forward service/max-diffusion-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null &
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
  --output ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_image.png \
  --request POST \
  --show-error \
  --silent
  ls -alh ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/images/${HF_MODEL_NAME}_image.png
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/max-diffusion/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

## Clean up

- Destroy the container image.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/tpu/max_diffusion_sdxl && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```

- Destroy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
