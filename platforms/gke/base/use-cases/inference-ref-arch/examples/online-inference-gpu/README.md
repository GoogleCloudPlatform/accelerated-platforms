# Online inference with GPUs on Google Kubernetes Engine (GKE)

This example implements online inference using GPUs on Google Kubernetes Engine
(GKE)

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

  - For Llama:

    - Accept the terms of the license on the Hugging Face model page.

      - [**meta-llama/Llama-4-Scout-17B-16E-Instruct**](https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct)
      - [**meta-llama/Llama-3.3-70B-Instruct**](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)

## Create and configure Google Cloud resources

- Deploy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
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

    - **Gemma 3 27B Instruction-Tuned**:

      ```shell
      export MODEL_ID="google/gemma-3-27b-it"
      ```

    - **Llama 4 Scout 17B Instruction-Tuned**:

      ```shell
      export MODEL_ID="meta-llama/llama-4-scout-17b-16e-instruct"
      ```

    - **Llama 3.3 70B Instruction-Tuned**:

      ```shell
      export MODEL_ID="meta-llama/llama-3.3-70b-instruct"
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
  transfer-model-to-gcs   Complete   1/1           33m        3h30m
  ```

- Delete the model downloader.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download"
  ```

## Deploy the online inference workload

- Set the environment variables for the model.

  - Set the model name.

    ```shell
    MODEL_NAME="${MODEL_ID##*/}" && export MODEL_NAME="${MODEL_NAME,,}"
    echo "MODEL_NAME=${MODEL_NAME}"
    ```

  - Select an accelerator.

    | Model                          | l4  | h100 | h200 |
    | ------------------------------ | --- | ---- | ---- |
    | gemma-3-27b-it                 | ✅  | ✅   | ✅   |
    | llama-3.3-70b-instruct         | ❌  | ✅   | ✅   |
    | llama-4-scout-17b-16e-instruct | ❌  | ✅   | ✅   |

    - **NVIDIA Tesla L4 24GB**:

      ```shell
      export ACCELERATOR_TYPE="l4"
      ```

    - **NVIDIA H100 80GB**:

      ```shell
      export ACCELERATOR_TYPE="h100"
      ```

    - **NVIDIA H200 141GB**:

      ```shell
      export ACCELERATOR_TYPE="h200"
      ```

    Ensure that you have enough quota in your project to provision the selected
    accelerator type. For more information, see about viewing GPU quotas, see
    [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

- Configure the Kustomize environment file.

  ```shell
  envsubst < ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-base/templates/deployment.tpl.env \
    | sponge ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-base/deployment.env
  ```

- Deploy the online inference workload in the GKE cluster.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/${ACCELERATOR_TYPE}-${MODEL_NAME}"
  ```

  The Kubernetes manifests in the
  `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/<ACCELERATOR_TYPE>-<MODEL_NAME>`
  directories include
  [Inference Quickstart recommendations](https://cloud.google.com/kubernetes-engine/docs/how-to/machine-learning/inference-quickstart).

- Wait for the Pod to be ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${MODEL_NAME} --tail 10"
  ```

- Send a test request.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${MODEL_NAME} 8000:8000 >/dev/null &
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
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${ACCELERATOR_TYPE}-${MODEL_NAME}"
  ```

## Troubleshooting

If you experience any issue while deploying the workload, see the
[Online inference with GPUs Troubleshooting](/platforms/gke/base/use-cases/inference-ref-arch/examples/online-inference-gpu/troubleshooting.md)
guide.

## Clean up

- Destroy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  terraform init &&
  terraform destroy -auto-approve
  ```
