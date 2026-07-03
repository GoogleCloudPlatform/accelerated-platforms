# Single-host reinforcement learning with TPUs on Google Kubernetes Engine (GKE) using GRPO algorithm

This example implements reinforcement learning using Group Relative Policy
Optimization (GRPO) and MaxText on TPUs on Google Kubernetes Engine (GKE).

It integrates **MaxText** (for FSDP model training), **vLLM** (for
high-throughput rollout generation), and **Tunix** (the RL bridge) on a single
TPU v5e-8 slice (`v5e-2x4`) to fine-tune Llama-3.1-8B-Instruct.

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
  - **Hardware**: This configuration is tuned for a **TPU v5e-8** (`v5e-2x4`) or
    **TPU v6e-8** (`v6e-2x4`) slice topology.
  - **Storage**: Local ephemeral storage (or mounted SSD) at `/workspace` for
    handling model checkpoint conversions.

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

## Build the container images

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Build the container image for the TPU reinforcement learning trainer.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/images/tpu/reinforcement_learning_on_tpu && \
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
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-on-tpu/configure_job.sh"
  ```

- Deploy the reinforcement learning workload.

  For TPU v5e:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-on-tpu/v5e-2x4-llama-3-1-8b-instruct"
  ```

  For TPU v6e:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-on-tpu/v6e-2x4-llama-3-1-8b-instruct"
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

## Viewing Metrics (MLflow & TensorBoard)

MaxText logs step metrics directly to TensorBoard format during execution. The
`train.py` script automatically packages these logs and attaches them to
**MLflow** as artifacts upon run completion.

### Accessing the MLflow UI

Because MLflow runs inside the cluster, you can port-forward the service to view
the dashboard locally:

1. **Port-forward the MLflow Service:**

   ```shell
   kubectl port-forward --namespace=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name} svc/mlflow-service 5000:5000
   ```

2. **Open your Browser:** Navigate to `http://localhost:5000`

3. **View Experiment Runs:**
   - Select the `MaxText-RL-GRPO-v5e` experiment.
   - Click on your active run (e.g., `Llama3.1-8B-GRPO-...`).
   - Inspect logged metrics (policy loss, reward values, KL divergence) and
     access attached TensorBoard log archives in the **Artifacts** section.

### Live Tracking (During Training)

To view loss curves in real time while training is running, port-forward
TensorBoard directly from the pod:

```shell
kubectl exec -it --namespace=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name} job/reinforcement-learning-maxtext-grpo-v5e-2x4-llama-3-1-8b-instruct -- tensorboard --logdir /workspace/rl_llama3_output --host 0.0.0.0 --port 6006
kubectl port-forward --namespace=${rl_tpu_reinforcement_learning_on_tpu_kubernetes_namespace_name} job/reinforcement-learning-maxtext-grpo-v5e-2x4-llama-3-1-8b-instruct 6006:6006
```

## Critical Architecture Notes & Patches

Because this pipeline bridges MaxText, Tunix, and vLLM on TPUs, key technical
constraints and runtime patches are applied:

1. **Protobuf Multiprocessing Shield**: vLLM uses background workers
   (`os.fork()`) which can cause `SIGABRT` crashes with JAX's C++ Protobuf
   engine. The pipeline forces Python protobufs and `spawn` multiprocessing mode
   at startup.
2. **JAX Driver Compatibility**: The container image pins JAX TPU drivers
   (`jax[tpu]==0.4.25`) to prevent sharding constraint assertion failures during
   Tunix weight transfer to vLLM.
3. **Memory & Mesh Tuning**:
   - `rollout_tensor_parallelism=8`: Maps vLLM across all 8 TPU v5e chips.
   - `hbm_utilization_vllm=0.4`: Restricts vLLM HBM usage to 40% of TPU memory,
     preserving remaining memory for MaxText FSDP training and optimizer states.
