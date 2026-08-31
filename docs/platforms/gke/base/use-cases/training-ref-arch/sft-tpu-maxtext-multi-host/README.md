# Multi-host Supervised Fine-Tuning (SFT) with TPUs on Google Kubernetes Engine (GKE) using MaxText

This example implements Supervised Fine-Tuning (SFT) using MaxText and Tunix on
Cloud TPUs on Google Kubernetes Engine (GKE).

It leverages **MaxText**'s scalable FSDP training loops and **Tunix**
post-training libraries across multi-host and multi-slice TPU v6e topologies to
fine-tune large language models on instruction-following datasets using
**PathwaysJob** orchestration.

This use-case is built on top of the
[GKE Training Reference Architecture](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md).

## Before you begin

- The
  [GKE Training Reference Architecture](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the model.

  - For Gemma:
    - Accept the terms of the license on the Hugging Face model page:
      - [**google/gemma-4-31b-it**](https://huggingface.co/google/gemma-4-31b-it)
      - [**google/gemma-3-4b-it**](https://huggingface.co/google/gemma-3-4b-it)

  - For Qwen:
    - Accept the terms of the license on the Hugging Face model page:
      - [**Qwen/Qwen3-14B-Instruct**](https://huggingface.co/Qwen/Qwen3-14B-Instruct)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

- Hardware & Storage Prerequisites:
  - **Hardware**: This configuration is tuned for multi-host and multi-slice
    **TPU v6e** topologies (e.g., `v6e-4x4`, `v6e-4x8`, or `2x4x4`
    multi-slice).
  - **Storage**: GCS bucket configured for storing Hugging Face converted
    checkpoints and SFT checkpoint weights.

## Create and configure the Google Cloud resources

- Deploy the SFT cloud infrastructure resources (SFT dataset bucket, Kubernetes
  service accounts, IAM bindings, and namespaces).

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/sft-tpu-maxtext-multi-host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Convert the Hugging Face weights to MaxText format

Before starting Supervised Fine-Tuning (SFT) training, you can run a one-time
CPU-based checkpoint conversion job to convert the base Hugging Face weights
into MaxText format. Running this on CPU nodes preserves valuable TPU resources.

- Choose the model to convert.

  - **Gemma 4 31B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="gemma4-31b"
    ```

  - **Qwen 3 14B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="qwen3-14b"
    ```

  - **Gemma 3 4B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="gemma3-4b"
    ```

- Source the environment configuration:

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the checkpoint converter deployment:

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/maxtext-checkpoint-converter/configure_checkpoint_converter.sh"
  ```

- Deploy the checkpoint converter job:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter"
  ```

- Watch the checkpoint converter job until it is complete:

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${sft_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-maxtext-checkpoint-converter | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${sft_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-maxtext-checkpoint-converter --all-containers --tail 10"
  ```

  Once complete, your model checkpoints will be stored under
  `gs://${huggingface_hub_models_bucket_name}/maxtext-checkpoint-converter-output/`.

- Clean up the CPU conversion job:

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter"
  ```

## Deploy the SFT workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the SFT deployment manifests.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/configure_job.sh"
  ```

- Deploy the SFT workload.

  For TPU v6e-16 (Gemma 4 31B):

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/v6e-4x4-gemma-4-31b-instruct"
  ```

  For TPU v6e-32 (Qwen 3 14B):

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/v6e-4x8-qwen-3-14b-instruct"
  ```

  For Multi-Slice TPU v6e (Gemma 3 4B):

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-multi-host/v6e-multislice-2x4x4-gemma-3-4b"
  ```

- Watch the SFT training job until it is complete:

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${sft_tpu_maxtext_multi_host_kubernetes_namespace_name} get pathwaysjob/sft-tpu-maxtext-multi-host-v6e-4x4-gemma-4-31b-instruct | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${sft_tpu_maxtext_multi_host_kubernetes_namespace_name} logs -l app=sft-trainer --all-containers --tail 10"
  ```

  When the job is complete, you will see the following status:

  ```text
  NAME                                                        STATUS      AGE
  sft-tpu-maxtext-multi-host-v6e-4x4-gemma-4-31b-instruct    Completed   ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

## Viewing Metrics (MLflow & TensorBoard)

MaxText logs step metrics directly to TensorBoard format in Cloud Storage during
execution.

### Accessing the MLflow UI

Because MLflow runs inside the cluster, you can port-forward the service to view
the dashboard locally:

1. **Port-forward the MLflow Service:**

   ```shell
   kubectl port-forward --namespace=${sft_cpu_mlflow_kubernetes_namespace_name} svc/mlflow-service-svc 5000:5000
   ```

2. **Open your Browser:** Navigate to `http://localhost:5000`

3. **View SFT Experiment Runs:**
   - Select the `sft-tpu-maxtext-multi-host` experiment.
   - Click on your active run (e.g., `gemma4-31b-sft-v6e`).
   - Inspect logged loss curves, learning rates, and gradient norms.

## Critical Design Features

1. **Decoupled Conversion**: Checkpoint conversion from Hugging Face format to
   MaxText is decoupled into a dedicated CPU-based conversion job, preserving
   valuable TPU resources for training.
2. **Official Post-Training Container Image**: Uses the official Google Cloud
   TPU MaxText post-training image (`tpu_post_training:0.2.4`) with execution
   scripts mounted declaratively via Kubernetes ConfigMaps, eliminating the need
   to build and maintain custom container images.
3. **Pathways Multi-Host Orchestration**: Employs `PathwaysJob` custom resources
   to natively coordinate distributed training across multi-host and multi-slice
   TPU topologies.
4. **Optimized Resource Layout**: Configured with a dedicated GCS bucket and GKE
   Workload Identity bindings for clean security isolation.
