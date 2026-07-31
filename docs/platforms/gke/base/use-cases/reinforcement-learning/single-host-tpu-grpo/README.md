# Single-host reinforcement learning with TPUs on Google Kubernetes Engine (GKE) using GRPO algorithm

This example implements reinforcement learning using Group Relative Policy
Optimization (GRPO) and MaxText on TPUs on Google Kubernetes Engine (GKE).

It integrates **MaxText** (for FSDP model training), **vLLM** (for
high-throughput rollout generation), and **Tunix** (the RL bridge) on a single
TPU v6e-8 slice (`v6e-2x4`) to fine-tune Llama-3.1-8B-Instruct.

This example is built on top of the
[GKE Reinforcement Learning reference architecture](/docs/platforms/gke/base/use-cases/reinforcement-learning/README.md).

## Before you begin

- Get access to the model.

  - For Llama-3.1:
    - Accept the terms of the license on the Hugging Face model page.
      - [**meta-llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

- Hardware & Storage Prerequisites:

  - **Hardware**: This configuration is tuned for a **TPU v6e-8** (`v6e-2x4`)
    slice topology.
  - **Storage**: Local ephemeral storage (or mounted SSD) at `/workspace` for
    handling model checkpoint conversions.

## Create and configure the Google Cloud resources

- Deploy all required core infrastructure and reinforcement learning cloud
  resources in a single step using the automated deployment script:

  ```shell
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform" && \
  ./deploy-standard.sh
  ```

## Convert the Hugging Face weights to MaxText format

Before starting reinforcement learning training, you can run a one-time
CPU-based checkpoint conversion job to convert the base Hugging Face weights
into MaxText format. Running this on CPU nodes preserves valuable TPU resources.

- Choose the model to convert.

  - **Llama 3.1 8B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="llama3.1-8b-Instruct"
    ```

  - **Gemma 2 9B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="gemma4-26b"
    ```

- Source the environment configuration:

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the checkpoint converter deployment:

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/configure_checkpoint_converter.sh"
  ```

- Deploy the checkpoint converter job:

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter"
  ```

- Watch the checkpoint converter job until it is complete:

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${rl_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-maxtext-checkpoint-converter | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${rl_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name} logs job/${HF_MODEL_ID_HASH}-maxtext-checkpoint-converter --all-containers --tail 10"
  ```

  Once complete, your model checkpoints will be stored under
  `gs://${rl_dataset_bucket_name}/maxtext-checkpoint-converter-output/`.

- Clean up the CPU conversion job:

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter"
  ```

## Deploy the reinforcement learning workload

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-tpu-maxtext-grpo-single-host/configure_job.sh"
  ```

- Deploy the reinforcement learning workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-tpu-maxtext-grpo-single-host/v6e-2x4-llama-3-1-8b-it"
  ```

- Watch the reinforcement learning job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name} get job/reinforcement-learning-maxtext-grpo-v6e-2x4-llama-3-1-8b-instruct | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name} logs job/reinforcement-learning-maxtext-grpo-v6e-2x4-llama-3-1-8b-instruct --all-containers --tail 10"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                                                              STATUS     COMPLETIONS   DURATION   AGE
  reinforcement-learning-maxtext-grpo-v6e-2x4-llama-3-1-8b-instruct Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

## Viewing Metrics

MaxText logs step metrics directly to TensorBoard format during execution. The
`train.sh` script automatically packages these logs and attaches them to
**MLflow** as artifacts upon run completion.

### Accessing the MLflow UI

Because MLflow runs inside the cluster, you can port-forward the service to view
the dashboard locally:

1. **Port-forward the MLflow Service:**

   ```shell
   kubectl port-forward --namespace=${rl_cpu_mlflow_kubernetes_namespace_name} svc/mlflow-service-svc 5000:5000
   ```

1. **Open your Browser:** Navigate to `http://localhost:5000`

1. **View Experiment Runs:**

   - Select the `MaxText-RL-GRPO-v6e` experiment.
   - Click on your active run (e.g., `Llama3.1-8B-GRPO-...`).
   - Inspect logged metrics (policy loss, reward values, KL divergence) and
     access attached TensorBoard log archives in the **Artifacts** section.

### Live Tracking (During Training)

To view loss curves in real time while training is running, port-forward
TensorBoard directly from the pod:

```shell
kubectl exec -it --namespace=${rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name} job/reinforcement-learning-maxtext-grpo-v6e-2x4-llama-3-1-8b-instruct -- tensorboard --logdir /workspace/rl_llama3_output --host 0.0.0.0 --port 6006
kubectl port-forward --namespace=${rl_tpu_maxtext_grpo_single_host_kubernetes_namespace_name} job/reinforcement-learning-maxtext-grpo-v6e-2x4-llama-3-1-8b-instruct 6006:6006
```

## Critical Architecture Notes & Patches

Because this pipeline bridges MaxText, Tunix, and vLLM on TPUs, key technical
constraints and runtime patches are applied:

1. **Protobuf Multiprocessing Shield**: vLLM uses background workers
   (`os.fork()`) which can cause `SIGABRT` crashes with JAX's C++ Protobuf
   engine. The pipeline forces Python protobufs and `spawn` multiprocessing mode
   at startup.
1. **JAX Driver Compatibility**: The container image pins JAX TPU drivers
   (`jax[tpu]==0.4.25`) to prevent sharding constraint assertion failures during
   Tunix weight transfer to vLLM.
1. **Memory & Mesh Tuning**:
   - `rollout_tensor_parallelism=8`: Maps vLLM across all 8 TPU v6e chips.
   - `hbm_utilization_vllm=0.4`: Restricts vLLM HBM usage to 40% of TPU memory,
     preserving remaining memory for MaxText FSDP training and optimizer states.
