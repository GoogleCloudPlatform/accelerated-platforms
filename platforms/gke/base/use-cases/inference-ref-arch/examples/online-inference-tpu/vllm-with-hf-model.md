# Online inference using vLLM with TPUs on Google Kubernetes Engine (GKE)

This example implements online inference using TPUs on Google Kubernetes Engine
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

- Choose the model ID.

  - **Gemma 3 1B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-1b-it"
    ```

  - **Gemma 3 4B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-4b-it"
    ```

  - **Gemma 3 27B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-27b-it"
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

## Deploy the online inference workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/configure_vllm.sh"
  ```

- Set the environment variables for the workload.

  - Check the model name.

    ```shell
    echo "HF_MODEL_NAME=${HF_MODEL_NAME}"
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

- Deploy the online inference workload.

```shell
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
```

The Kubernetes manifests are based on the
[Inference Quickstart recommendations](https://cloud.google.com/kubernetes-engine/docs/how-to/machine-learning/inference-quickstart).

- Watch the deployment until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} get deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} logs deployment/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} --all-containers --tail 10"
  ```

  When the deployment is ready, you will see the following:

  ```text
  NAME                                      READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-<ACCELERATOR_TYPE>-<HF_MODEL_NAME>   1/1     1            1           ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Send a test request.

  ```shell
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null &
  PF_PID=$!
  while ! echo -e '\x1dclose\x0d' | telnet localhost 8000 >/dev/null 2>&1; do
    sleep 0.1
  done
  echo "/v1/models:"
  curl --request GET --show-error --silent http:/127.0.0.1:8000/v1/models | jq
  sleep 1
  echo "/v1/chat/completions:"
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "/gcs/'${HF_MODEL_ID}'",
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
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

## Clean up

- Destroy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
