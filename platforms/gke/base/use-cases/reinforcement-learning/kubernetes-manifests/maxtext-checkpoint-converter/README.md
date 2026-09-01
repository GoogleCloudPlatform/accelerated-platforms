# Convert the Hugging Face weights to MaxText format

Before starting reinforcement learning training, you can run a one-time
CPU-based checkpoint conversion job to convert the base Hugging Face weights
into MaxText format. Running this on CPU nodes preserves valuable TPU resources.

- Choose the model to convert.

  - **Llama 3.1 8B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="llama3.1-8b-Instruct"
    ```

  - **Gemma 3 4B Instruction-Tuned**:

    ```shell
    export HF_MODEL_ID="google/gemma-3-4b-it"
    ```

  - **Gemma 4 26B Instruction-Tuned**:

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
  `gs://${huggingface_hub_models_bucket_name}/maxtext-checkpoint-converter-output/`.

- Clean up the CPU conversion job:

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter"
  ```
