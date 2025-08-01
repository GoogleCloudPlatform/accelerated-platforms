# Online inference with TPUs on Google Kubernetes Engine (GKE)

This guide demonstrates how to deploy and serve Gemma large language models
(LLMs) for online inference on Google Kubernetes Engine (GKE), specifically
leveraging Cloud TPUs. It showcases high-performance and scalable LLM serving
using various Gemma model sizes and their corresponding TPU v5e and v6e
topologies.

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the models.

  - For Gemma:

    - Consented to the license on [Kaggle](https://www.kaggle.com/) using a
      Hugging Face account.

      - [**google/gemma**](https://www.kaggle.com/models/google/gemma).

## Create and configure Google Cloud resources

- Deploy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the Hugging Face `SecretProviderClass`es.

  ```shell
  envsubst < ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/templates/secretproviderclass-huggingface-tokens.tpl.yaml \
    | sponge ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/secretproviderclass-huggingface-tokens.yaml
  ```

## Download the model to Cloud Storage

- Set the environment variables for the model downloader.

  - Set the model ID.

    - **Gemma 3 1B Instruction-Tuned**:

      ```shell
      export MODEL_ID="google/gemma-3-1b-it"
      ```

    - **Gemma 3 4B Instruction-Tuned**:

      ```shell
      export MODEL_ID="google/gemma-3-4b-it"
      ```

    - **Gemma 3 27B Instruction-Tuned**:

      ```shell
      export MODEL_ID="google/gemma-3-27b-it"
      ```

  - Configure the Kustomize environment file

    ```shell
    envsubst < ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/templates/downloader.tpl.env \
      | sponge ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/downloader.env
    ```

- Deploy the model downloader in the GKE cluster.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download"
  ```

- Wait for the model downloader to download the model:

  Note: the model downloader job has `ttlSecondsAfterFinished` configured, so if
  you wait for more than `ttlSecondsAfterFinished` seconds after the job
  completes, GKE will have automatically deleted it to reclaim resources.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/transfer-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} logs job/transfer-model-to-gcs --tail 10"
  ```

  The output is similar to the following.

  ```text
  NAME                    STATUS     COMPLETIONS   DURATION   AGE
  transfer-model-to-gcs   Complete   1/1           ##m        ##m
  ```

- Delete the model downloader.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download"
  ```

## Deploy the online inference workload

- Configure the Kustomize environment file.

  ```shell
  envsubst < ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/base/templates/deployment.tpl.env \
    | sponge ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/base/deployment.env
  ```

- Set the environment variables for the model.

  - Set the model name.

    ```shell
    export MODEL_NAME="${MODEL_ID##*/}"
    echo "MODEL_NAME=${MODEL_NAME}"
    ```

  - Select an accelerator.

    | Model          | v5e | v6e |
    | -------------- | --- | --- |
    | gemma-3-1b-it  | ✅  | ❌  |
    | gemma-3-4b-it  | ✅  | ❌  |
    | gemma-3-27b-it | ✅  | ✅  |

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

- Deploy the online inference workload in the GKE cluster.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/${ACCELERATOR_TYPE}-${MODEL_NAME}"
  ```

- Wait for the Pod to be ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${MODEL_NAME} --tail 10"
  ```

- Send a test request.

  ```shell
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${MODEL_NAME} 8000:8000 >/dev/null &
  PF_PID=$!
  while ! nc -z localhost 8000; do
    sleep 0.1
  done
  echo "/v1/models:"
  curl --request GET --show-error --silent http:/127.0.0.1:8000/v1/models | jq
  sleep 1
  echo "/v1/chat/completions:"
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "/gcs/'${MODEL_ID}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  kill -9 ${PF_PID}
  ```

- Delete the workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/${ACCELERATOR_TYPE}-${MODEL_NAME}"
  ```

## Clean up

- Destroy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  terraform init &&
  terraform destroy -auto-approve
  ```
