# Online inference using vLLM with NVIDIA Run:ai Model Streamer and PodSnapshots on GKE

This example implements online inference using GPUs on Google Kubernetes Engine
(GKE) with enhanced performance features:
- **NVIDIA Run:ai Model Streamer**: Accelerates model loading by streaming weights directly to GPU memory.
- **GKE PodSnapshots**: Enables rapid scaling by restoring replicas from pre-warmed snapshots.
- **GCS Rapid Cache**: Optimizes Cloud Storage FUSE performance for AI workloads.
- **Custom Metrics HPA**: Scales based on vLLM-specific metrics like queue depth.

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- Ensure your cluster is running GKE version 1.34.1-gke.3084001 or later for PodSnapshot support.

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the online GPU resources.

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

- Choose the model.

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

  - **gpt-oss-20b**

    ```shell
    export HF_MODEL_ID="openai/gpt-oss-20b"
    ```

  - **Llama 4 Scout 17B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="meta-llama/llama-4-scout-17b-16e-instruct"
    ```

  - **Llama 3.3 70B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="meta-llama/llama-3.3-70b-instruct"
    ```

  - **Qwen3-32B**:

    ```shell
    export HF_MODEL_ID="qwen/qwen3-32b"
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

## Deploy the inference workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh"
  ```

- Deploy the inference workload.

  ```shell
  # Select your accelerator and model hash as environment variables
  # Example for RTX Pro 6000 and Gemma 3 27B
  export ACCELERATOR_TYPE="rtx-pro-6000"
  export HF_MODEL_NAME="gemma-3-27b-it"

  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

  > NOTE: This example uses `runtimeClassName: gvisor` for PodSnapshot support. Ensure your node pool supports GKE Sandbox.

## Enable PodSnapshots for Fast Scaling

- The deployment is configured for **fully declarative PodSnapshots**:
  - **Automatic Snapshotting**: A `PodSnapshotPolicy` with `type: readinessProbe` automatically triggers a snapshot as soon as the first vLLM pod loads the model and becomes `Ready`.
  - **Automatic Restoration**: The Deployment includes the `podsnapshot.gke.io/restore-from-policy` annotation. This tells GKE to automatically restore all new replicas from the latest snapshot created by the policy.

- No manual annotations or triggers are required. Simply deploy the manifests, and the first pod will "warm up" the cluster by creating a snapshot that all subsequent replicas will use for near-instant startup.

- You can monitor the progress:

  ```shell
  # Watch for the automatic snapshot to become Ready
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots -w
  ```

- To force a fresh "warm up" (e.g., after a model update), you can delete the existing snapshots, and the next pod to become ready will automatically create a new one.

## Scaling with HPA

- The deployment includes an HPA resource that scales based on `vllm:num_requests_waiting` (Google Managed Prometheus).
- You can monitor the HPA status:

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get hpa vllm
  ```

## Send a test request

- Send a test request.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} port-forward service/vllm-${ACCELERATOR_TYPE}-${HF_MODEL_NAME} 8000:8000 >/dev/null &
  PF_PID=$!
  while ! echo -e '\x1dclose\x0d' | telnet localhost 8000 >/dev/null 2>&1; do
    sleep 0.1
  done
  echo "/v1/models:"
  curl --request GET --show-error --silent http:/127.0.0.1:8000/v1/models | jq
  sleep 1
  echo "/v1/chat/completions:"
  # Note: The model name should match the ID returned by the /v1/models endpoint.
  # For Run:ai streamer, it typically follows the gs://bucket/model-id format.
  MODEL_NAME=$(curl --request GET --show-error --silent http:/127.0.0.1:8000/v1/models | jq -r '.data[0].id')
  curl http://127.0.0.1:8000/v1/chat/completions \
  --data '{
    "model": "'${MODEL_NAME}'",
    "messages": [ { "role": "user", "content": "Why is the sky blue?" } ]
    }' \
  --header "Content-Type: application/json" \
  --request POST \
  --show-error \
  --silent | jq
  kill -9 ${PF_PID}
  ```

## Clean up

- Destroy the workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
  ```

- Destroy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
