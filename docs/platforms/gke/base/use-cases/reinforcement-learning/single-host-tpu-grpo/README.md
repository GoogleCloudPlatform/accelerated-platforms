# Reinforcement learning with TPUs on Google Kubernetes Engine (GKE)

This example implements reinforcement learning using Group Relative Policy Optimization (GRPO) and MaxText on TPUs on Google Kubernetes Engine (GKE).

This example is built on top of the
[GKE Reinforcement Learning reference architecture](/docs/platforms/gke/base/use-cases/reinforcement-learning/README.md).

## Before you begin

- The
  [GKE Reinforcement Learning reference implementation](/docs/platforms/gke/base/use-cases/reinforcement-learning/README.md)
  is deployed and configured.

- Get access to the model.

  - For Llama-3.1:
    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the reinforcement learning on TPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/rl_on_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Download the model to Cloud Storage

- Choose the model.

  - **Llama-3.1-8B-Instruct**:

    ```shell
    export HF_MODEL_ID="meta-llama/Llama-3.1-8B-Instruct"
    ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
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

## Deploy the reinforcement learning workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  Generate the configuration env file `runtime.env` for the kustomization overlays:

  ```shell
  cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-on-tpu/v5e-2x4-llama-3-1-8b-instruct/runtime.env"
  CONTAINER_IMAGE_URL=${rl_tpu_reinforcement_learning_on_tpu_image_url}
  INFERENCE_KUBERNETES_NAMESPACE=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name}
  INFERENCE_KUBERNETES_SERVICE_ACCOUNT=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_service_account_name}
  EOF
  ```

- Deploy the reinforcement learning workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-on-tpu/v5e-2x4-llama-3-1-8b-instruct"
  ```

- Watch the reinforcement learning job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name} get job/reinforcement-learning-maxtext-grpo-v5e-2x4-llama-3-1-8b-instruct | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name} logs job/reinforcement-learning-maxtext-grpo-v5e-2x4-llama-3-1-8b-instruct --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                                                              STATUS     COMPLETIONS   DURATION   AGE
  reinforcement-learning-maxtext-grpo-v5e-2x4-llama-3-1-8b-instruct Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.
