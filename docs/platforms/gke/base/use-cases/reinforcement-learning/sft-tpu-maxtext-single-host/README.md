# Single-host Supervised Fine-Tuning (SFT) with TPUs on Google Kubernetes Engine (GKE) using MaxText

This example implements Supervised Fine-Tuning (SFT) using MaxText and Tunix on Cloud TPUs on Google Kubernetes Engine (GKE).

It leverages **MaxText**'s scalable FSDP training loops and **Tunix** post-training libraries on a single TPU v5e-8 slice (`v5e-2x4`) or TPU v6e-8 slice (`v6e-2x4`) to fine-tune Llama-3.1-8B-Instruct on instruction-following datasets.

This use-case is built on top of the [GKE Reinforcement Learning reference implementation](/platforms/gke/base/use-cases/reinforcement-learning/terraform/README.md).

## Before you begin

- The [GKE Reinforcement Learning reference implementation](/platforms/gke/base/use-cases/reinforcement-learning/terraform/README.md) is deployed and configured.

- Get access to the model.
  - For Llama-3.1:
    - Accept the terms of the license on the Hugging Face model page:
      - [**meta-llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)

- Ensure your [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md) has been added to Secret Manager.

- Hardware & Storage Prerequisites:
  - **Hardware**: This configuration is tuned for a **TPU v5e-8** (`v5e-2x4`) or **TPU v6e-8** (`v6e-2x4`) slice topology.
  - **Storage**: GCS bucket configured for storing Hugging Face converted checkpoints and SFT checkpoint weights.

## Create and configure the Google Cloud resources

- Deploy the SFT cloud infrastructure resources (SFT dataset bucket, Kubernetes service accounts, IAM bindings, and namespaces).

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/sft-tpu-maxtext-single-host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Build the container images

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Build the SFT trainer container image using Google Cloud Build.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/images/tpu/sft-tpu-maxtext-single-host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  > The build usually takes 10 to 15 minutes.

## Deploy the SFT workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the SFT deployment manifests.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/sft-tpu-maxtext-single-host/configure_job.sh"
  ```

- Deploy the SFT workload.

  For TPU v5e:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/sft-tpu-maxtext-single-host/v5e-2x4-llama-3-1-8b-instruct"
  ```

  For TPU v6e:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/sft-tpu-maxtext-single-host/v6e-2x4-llama-3-1-8b-instruct"
  ```

- Watch the SFT training job until it is complete:

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${sft_tpu_maxtext_single_host_kubernetes_namespace_name} get job/sft-tpu-maxtext-single-host-v5e-2x4-llama-3-1-8b-instruct | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${sft_tpu_maxtext_single_host_kubernetes_namespace_name} logs job/sft-tpu-maxtext-single-host-v5e-2x4-llama-3-1-8b-instruct --all-containers --tail 10"
  ```

  When the job is complete, you will see the following status:

  ```text
  NAME                                                               STATUS     COMPLETIONS   DURATION   AGE
  sft-tpu-maxtext-single-host-v5e-2x4-llama-3-1-8b-instruct          Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

## Viewing Metrics (MLflow & TensorBoard)

MaxText logs step metrics directly to TensorBoard format during execution. The `train.py` script automatically intercepts metrics using monkey patching of JAX metric writers (`clu.metric_writers.MultiWriter.write_scalars`) and pipes real-time metrics to **MLflow**.

### Accessing the MLflow UI

Because MLflow runs inside the cluster, you can port-forward the service to view the dashboard locally:

1. **Port-forward the MLflow Service:**

   ```shell
    kubectl port-forward --namespace=${sft_tpu_maxtext_single_host_kubernetes_namespace_name} svc/mlflow-service 5000:5000
   ```

2. **Open your Browser:** Navigate to `http://localhost:5000`

3. **View SFT Experiment Runs:**
   - Select the `sft-tpu-maxtext-single-host` experiment.
   - Click on your active run (e.g., `Llama3.1-8B-SFT-...`).
   - Inspect logged loss curves, learning rates, and gradient norms.

## Critical Design Features

1. **Automated Conversion**: Checkpoint conversion from Hugging Face format to MaxText is built directly into Python execution. If converted parameters do not exist in GCS, `train.py` launches `maxtext.checkpoint_conversion.to_maxtext` before starting training.
2. **JAX-Level Metric Injection**: Real-time logging is handled via zero-code-change monkey patching of JAX's native `clu.metric_writers` API inside Python `runpy`, capturing loss scalars and streaming them instantly to the MLflow server.
3. **Optimized Resource Layout**: Configured with a dedicated GCS bucket and GKE Workload Identity bindings for clean security isolation.
