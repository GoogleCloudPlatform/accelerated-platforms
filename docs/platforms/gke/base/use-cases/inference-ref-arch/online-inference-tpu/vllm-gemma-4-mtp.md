# Online inference using vLLM with MTP Speculative Decoding and TPUs on Google Kubernetes Engine (GKE)

This document implements online inference using Trillium TPUs on Google
Kubernetes Engine (GKE) using vLLM with Multi-Token Prediction (MTP) Speculative
Decoding enabled for the Gemma-4 model.

Speculative decoding is a powerful optimization technique that enhances LLM
inference speed without compromising output quality. Specifically, Gemma-4's MTP
architecture uses an assistant (drafter) model to predict multiple tokens in
parallel, which the main model then verifies in a single step.

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

- Get access to the models.

  - For Gemma-4:
    - Consent to the license on [Kaggle](https://www.kaggle.com/) using a
      Hugging Face account.
      - **google/gemma-4-31b-it**
      - **google/gemma-4-31b-it-assistant**

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Create a standard GKE cluster

- Inject these values into the appropriate tfvars files
  (`${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars` and
  `cluster.auto.tfvars`) using sed.

  ```shell
  # Update platform variables
  sed -i 's/^platform_name.*/platform_name = "<platform_name>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
  grep -q "^platform_default_project_id" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars" || echo "platform_default_project_id = \"\"" >> "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
  sed -i 's/^platform_default_project_id.*/platform_default_project_id = "<project_id>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"

  # Update cluster variables
  sed -i 's/^cluster_region.*/cluster_region = "<cluster_region>"/g' "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
  ```

  For Standard Cluster:

  ```shell
  ${ACP_REPO_DIR}/platforms/gke/base/core/deploy-standard.sh
  ```

- Deploy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the models to Cloud Storage

- Choose the main model.

  - **Gemma 4 31B Instruction-Tuned (MTP)**:

    ```shell
    export HF_MODEL_ID="google/gemma-4-31b-it"
    ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure and deploy the main model download job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the main model download job until it is complete.

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

- Delete the main model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Choose the drafter model and run the download job again.

  ```shell
  export HF_MODEL_ID="google/gemma-4-31b-it-assistant"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the drafter model download job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-hf-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-hf-model-to-gcs --all-containers --tail 10"
  ```

- Delete the drafter model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

## Deploy the inference workload

- Set the environment variables for both models.

  ```shell
  export HF_MODEL_ID="google/gemma-4-31b-it"
  export DRAFTER_MODEL_ID="google/gemma-4-31b-it-assistant"
  ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/configure_vllm.sh"
  ```

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/v6e-gemma-4-31b-it-mtp"
  ```

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title "kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} get deployment/vllm-v6e-gemma-4-31b-it-mtp | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} logs deployment/vllm-v6e-gemma-4-31b-it-mtp --all-containers --tail 10"
  ```

- When the deployment is ready, you will see output similar to the following:

  ```text
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-v6e-gemma-4-31b-it-mtp                      1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Send a test request to the model.

  Start a port forward to the model service.

  ```shell
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} port-forward service/vllm-v6e-gemma-4-31b-it-mtp 8000:8000 >/dev/null & \
  PF_PID=$!
  ```

  Send a test request.

  ```shell
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "/gcs/'${HF_MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  ```

  Stop the port forward.

  ```shell
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/v6e-gemma-4-31b-it-mtp"
  ```

## Clean up

- Destroy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
