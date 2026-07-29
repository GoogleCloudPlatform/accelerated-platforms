# Online inference using vLLM with MTP Speculative Decoding and TPUs on Google Kubernetes Engine (GKE)

This document implements online inference using Trillium TPUs on Google
Kubernetes Engine (GKE) using vLLM with Multi-Token Prediction (MTP) Speculative
Decoding enabled for the Gemma-4 model.

Speculative decoding is a powerful optimization technique that enhances LLM
inference speed without compromising output quality. By drafting multiple future
tokens and verifying them in parallel, it significantly improves latency
compared to standard auto-regressive generation.

### How MTP Differs from Other Speculative Decoding Methods

There are several variations of speculative decoding. MTP (Multi-Token
Prediction) takes a unique approach compared to traditional methods:

| Method                            | Architecture                                                     | Training Approach                                                       | Alignment & Acceptance Rate                                                             | Key Characteristics                                                                                                     |
| :-------------------------------- | :--------------------------------------------------------------- | :---------------------------------------------------------------------- | :-------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- |
| **Standard Speculative Decoding** | Separate, smaller "draft" model and large "target" model.        | Models are trained completely independently.                            | **Lower:** Internal logic is separated, leading to frequent rejections.                 | Traditional approach. Simplest to implement but less efficient.                                                         |
| **Draft-Head (e.g., EAGLE)**      | Additional "draft heads" attached directly to the target model.  | Draft heads are trained separately _after_ base model pre-training.     | **Higher:** Shares the target model's hidden states.                                    | Avoids a separate model, but adds significant post-training complexity.                                                 |
| **MTP (Multi-Token Prediction)**  | Draft modules that share the main model's internal states.       | Draft modules are trained **jointly** with the base model from scratch. | **Highest:** Perfect alignment due to joint pre-training.                               | Gemma-4's architecture. Achieves superior efficiency without post-training add-ons. (Loaded as an "assistant" in vLLM). |
| **dSpark**                        | Draft-head based parallel verification architecture.             | Typically requires separate training or distillation.                   | **High:** Uses parallel speculative verification.                                       | _Note: Currently, dSpark is supported via the SGLang inference engine._                                                 |
| **N-gram (Prompt Lookup)**        | No extra model or head. Uses string matching against the prompt. | No training required.                                                   | **Variable:** High for repetitive/extractive tasks, very low for open-ended generation. | Completely training-free, but highly dependent on the prompt's content.                                                 |

### Ideal Benchmarking Datasets for Speculative Decoding

Because speculative decoding works by predicting future tokens, the achievable
speedup is directly proportional to how predictable the generated text is. For
this reason, speculative decoding architectures like MTP perform exceptionally
well on:

- **Extractive Summarization:** Where the model frequently quotes or restates
  long phrases from the source text (e.g., **CNN Daily Mail**).
- **Retrieval-Augmented Generation (RAG):** Where the context injected into the
  prompt contains the literal answers the model will output.
- **Code Generation & Formatting:** Where syntax, indentation, and variable
  names are highly structured and repetitive (e.g., **HumanEval** or
  **ShareGPT**).

When benchmarking MTP, using datasets like `cnn_dailymail` rather than
open-ended conversation datasets provides a much more accurate representation of
the latency improvements you can expect in enterprise use cases.

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

## Benchmark the inference workload

- Set the variables for the benchmark.

  ```shell
  export ACCELERATOR="TPU"
  export APP_LABEL="vllm-v6e-gemma-4-31b-it-mtp"
  export HF_MODEL_ID="google/gemma-4-31b-it"
  ```

- Configure the benchmark manifests.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-mtp/configure_benchmark.sh"
  ```

- Deploy the benchmark job.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-mtp"
  ```

- Watch the benchmark job until it completes.

  ```shell
  watch --color --interval 5 --no-title "kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} get job -l app=inference-perf | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${ira_online_tpu_kubernetes_namespace_name} logs -l app=inference-perf --tail 10"
  ```

- Delete the benchmark workload.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm-spec-decoding/sd-mtp"
  ```

## Clean up

- Destroy the online TPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_tpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
