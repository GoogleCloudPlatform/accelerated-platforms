# Multi-host reinforcement learning with TPUs on Google Kubernetes Engine (GKE) using Pathways and JobSet

This example implements distributed multi-host reinforcement learning using
Group Relative Policy Optimization (GRPO) and MaxText on TPUs on Google
Kubernetes Engine (GKE).

It integrates **MaxText** (for distributed FSDP model training), **vLLM** (for
high-throughput rollout generation), and **Tunix** (the RL bridge) on a
multi-host TPU v5e-16 slice (`v5e-4x4`) orchestrated via **Pathways** and
**JobSet** to fine-tune Llama-3.1-8B-Instruct.

This example is built on top of the
[GKE Reinforcement Learning reference architecture](/docs/platforms/gke/base/use-cases/reinforcement-learning/README.md).

## Before you begin

- The
  [GKE Reinforcement Learning reference implementation](/platforms/gke/base/use-cases/reinforcement-learning/terraform/README.md)
  is deployed and configured.

- Get access to the model.

  - For Llama-3.1:
    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

- Hardware & Storage Prerequisites:
  - **Hardware**: This configuration is tuned for a multi-host **TPU v5e-16**
    (`v5e-4x4`) slice topology.
  - **Storage**: GCS bucket (configured via the dataset bucket name) used as a
    synchronization directory (`pathwaysDir`) for inter-node communication.

## Create and configure the Google Cloud resources

- Deploy the multi-host reinforcement learning on TPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/rl_tpu_maxtext_grpo_multi_host && \
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

- Build the container image for the TPU reinforcement learning trainer.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/images/tpu/rl_tpu_maxtext_grpo_multi_host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  > The build usually takes 10 to 15 minutes.

## Deploy the reinforcement learning workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-tpu-maxtext-grpo-multi-host/configure_job.sh"
  ```

- Deploy the reinforcement learning workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-tpu-maxtext-grpo-multi-host/v5e-4x4-llama-3-1-8b-instruct"
  ```

- Watch the reinforcement learning job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${rl_tpu_maxtext_grpo_multi_host_kubernetes_namespace_name} get pathwaysjob/reinforcement-learning-maxtext-grpo-v5e-4x4-llama-3-1-8b-instruct
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${rl_tpu_maxtext_grpo_multi_host_kubernetes_namespace_name} logs pathwaysjob/reinforcement-learning-maxtext-grpo-v5e-4x4-llama-3-1-8b-instruct --tail 10"
  ```

## Viewing Metrics (MLflow & TensorBoard)

MaxText logs step metrics directly to TensorBoard format during execution. The
`train.py` script automatically packages these logs and attaches them to
**MLflow** as artifacts upon run completion.

### Accessing the MLflow UI

Because MLflow runs inside the cluster, you can port-forward the service to view
the dashboard locally:

1. **Port-forward the MLflow Service:**

   ```shell
   kubectl port-forward --namespace=${rl_tpu_maxtext_grpo_multi_host_kubernetes_namespace_name} svc/mlflow-service 5000:5000
   ```

2. **Open your Browser:** Navigate to `http://localhost:5000`

3. **View Experiment Runs:**
   - Select the `MaxText-RL-GRPO-v5e-multi` experiment.
   - Click on your active run (e.g., `Llama3.1-8B-GRPO-...`).
   - Inspect logged metrics (policy loss, reward values, KL divergence) and
     access attached TensorBoard log archives in the **Artifacts** section.

## Pathways & JobSet Architecture

Because this pipeline spans across multiple hosts, it leverages the
**PathwaysJob** Custom Resource:

1. **Pathways Orchestration**: The `PathwaysJob` operator creates a highly
   optimized Pathways cluster consisting of a resource manager (server), proxy
   server, and worker node pools.
2. **Underlying JobSet API**: Lifecycle synchronization and reliable process
   startup across distinct TPU hosts are managed under the hood by GKE's JobSet
   controller.
3. **Inter-Host GCS Synced Logging**: Multi-host coordination relies on a shared
   Google Cloud Storage subdirectory specified in `spec.pathwaysDir`. The
   workload's service account is granted `roles/storage.objectAdmin` on the
   dataset bucket to enable transparent file-based handshakes.
