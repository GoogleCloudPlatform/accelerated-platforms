# Single-host Supervised Fine-Tuning (SFT) with TPUs on Google Kubernetes Engine (GKE) using MaxText

This example implements Supervised Fine-Tuning (SFT) using MaxText and Tunix on
Cloud TPUs on Google Kubernetes Engine (GKE).

It leverages **MaxText**'s scalable FSDP training loops and **Tunix** post-
training libraries on single-host TPU slice topologies (`v5e-2x4`, `v6e-2x4`,
`v6e-4x4`) to fine-tune supported models, including:

- **Gemma 3 4B** (`gemma3-4b` / `google/gemma-3-4b-it`) — Fits single-host
  `v6e-2x4` (8 chips) & `v5e-2x4` (8 chips).
- **Llama 3.1 8B** (`llama3.1-8b` / `meta-llama/Llama-3.1-8B-Instruct`) — Fits
  single-host `v6e-2x4` (8 chips) & `v5e-2x4` (8 chips).
- **Gemma 4 31B** (`gemma4-31b` / `google/gemma-4-31b-it`) — Dense 31B model
  (requires `v6e-4x4` 16-chip slice for full-parameter SFT due to 400GB+ HBM
  optimizer memory requirement, or `v6e-2x4` using LoRA/PEFT).

This use-case is built on top of the [GKE Training Reference
Architecture](/platforms/gke/base/use-cases/training-ref-
arch/terraform/README.md).

## Topology & Memory Sizing Guidelines

| Model            | Parameters | Full SFT Memory (Weights + AdamW States) | Recommended TPU Topology                                                            |
| :--------------- | :--------- | :--------------------------------------- | :---------------------------------------------------------------------------------- |
| **Gemma 3 4B**   | 4B         | ~56 GB HBM                               | TPU v6e-8 (`v6e-2x4`) or TPU v5e-8 (`v5e-2x4`)                                      |
| **Llama 3.1 8B** | 8B         | ~112 GB HBM                              | TPU v6e-8 (`v6e-2x4`) or TPU v5e-8 (`v5e-2x4`)                                      |
| **Gemma 4 31B**  | 31B        | ~434 GB HBM                              | TPU v6e-16 (`v6e-4x4` - 512GB HBM) for full SFT, or TPU v6e-8 (`v6e-2x4`) with LoRA |

## Objectives

- Set up Google Cloud infrastructure (GCS bucket, Kubernetes service account,
  IAM bindings).
- Build and push a custom MaxText container image to Artifact Registry.
- Deploy a GKE cluster with TPU support and Workload Identity.
- Convert Hugging Face checkpoints to MaxText format.
- Run Supervised Fine-Tuning (SFT) on Cloud TPUs using MaxText.
- Track SFT experiment metrics (loss, learning rate) using in-cluster MLflow.
- Export trained MaxText model weights back to Hugging Face format.

## Before you begin

- The
  [GKE Training Reference Architecture](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
  is deployed and configured.

- Get access to the model on Hugging Face:

  - **Gemma 3 4B Instruction-Tuned**:
    [**google/gemma-3-4b-it**](https://huggingface.co/google/gemma-3-4b-it)
  - **Llama 3.1 8B Instruction-Tuned**: [**meta-
    llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-
    llama/Llama-3.1-8B-Instruct)
  - **Gemma 4 31B Instruction-Tuned**:
    [**google/gemma-4-31b-it**](https://huggingface.co/google/gemma-4-31b-it)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

- Hardware & Storage Prerequisites:
  - **Hardware**: Configured for **TPU v5e-8** (`v5e-2x4`), **TPU v6e-8**
    (`v6e-2x4`), or **TPU v6e-16** (`v6e-4x4`) slice topology.
  - **Storage**: GCS bucket configured for storing Hugging Face converted
    checkpoints and SFT checkpoint weights.

## Create and configure the Google Cloud resources

- Deploy the SFT cloud infrastructure resources (SFT dataset bucket, Kubernetes
  service accounts, IAM bindings, and namespaces):

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-
  arch/terraform/sft-tpu-maxtext-single-host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Build the container images

- Source the environment configuration:

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-
  arch/_shared_config/scripts/set_environment_variables.sh"
  ```

- Build the SFT trainer container image using Google Cloud Build:

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-
  arch/terraform/images/tpu/sft-tpu-maxtext-single-host && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

  > The build usually takes 10 to 15 minutes.

## Deploy the SFT workload

- Source the environment configuration:

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-
  arch/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the SFT deployment manifests:

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-
  manifests/sft-tpu-maxtext-single-host/configure_job.sh"
  ```

- Deploy the SFT workload for your selected model and accelerator topology:

  - **Gemma 3 4B on TPU v6e (2x4)**:

        ```shell
        kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-

    cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-single-
    host/v6e-2x4-gemma-3-4b-instruct" ```

  - **Gemma 4 31B on TPU v6e (4x4 16-chip slice)**:

        ```shell
        kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-

    cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-single-
    host/v6e-4x4-gemma-4-31b-instruct" ```

  - **Llama 3.1 8B on TPU v6e (2x4)**:

        ```shell
        kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-

    cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-single-
    host/v6e-2x4-llama-3-1-8b-instruct" ```

  - **Llama 3.1 8B on TPU v5e (2x4)**:

        ```shell
        kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-

    cases/training-ref-arch/kubernetes-manifests/sft-tpu-maxtext-single-
    host/v5e-2x4-llama-3-1-8b-instruct" ```

- Watch the SFT training job until it is complete:

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${sft_tpu_maxtext_single_host_kubernetes_namespace_name}
  get job -l app=sft-trainer | GREP_COLORS='mt=01;92' egrep --color=always -e '^'
  -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace=${sft_tpu_maxtext_single_host_kubernetes_namespace_name}
  logs -l app=sft-trainer --all-containers --tail 10"
  ```

  When the job is complete, you will see `Complete 1/1`. You can press
  `CTRL`+`c` to exit the watch.

## Viewing Metrics (MLflow & TensorBoard)

MaxText logs step metrics directly during execution. The `train.py` script
automatically intercepts metrics using monkey patching of JAX metric writers
(`clu.metric_writers.MultiWriter.write_scalars`) and pipes real-time metrics to
**MLflow**.

### Accessing the MLflow UI

Because MLflow runs inside the cluster, you can port-forward the service to view
the dashboard locally:

1. **Port-forward the MLflow Service:**

   ```shell
   kubectl port-forward
   --namespace=${sft_tpu_maxtext_single_host_kubernetes_namespace_name} svc/mlflow-
   service 5000:5000
   ```

2. **Open your Browser:** Navigate to `http://localhost:5000`

3. **View SFT Experiment Runs:**
   - Select the `sft-tpu-maxtext-single-host` experiment.
   - Click on your active run (e.g., `gemma3-4b-SFT-...`).
   - Inspect logged loss curves, learning rates, and gradient norms.

## Advanced: Standalone Step-by-Step Job Execution

If you prefer deploying individual Kubernetes batch Jobs for each stage
(Conversion -> Training -> Export), follow these steps:

### 1. Convert Hugging Face Checkpoint to MaxText Format

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: maxtext-checkpoint-conversion
  namespace: default
spec:
  template:
    spec:
      serviceAccountName: maxtext-tutorial-ksa
      nodeSelector:
        cloud.google.com/compute-class: Performance
      containers:
      - name: maxtext-converter
        image: "${REGION}-docker.pkg.dev/${PROJECT}/maxtext-images/maxtext_base"
        resources:
          requests:
            cpu: "16"
            memory: "64Gi"
            ephemeral-storage: "10Gi"
        env:
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token
              key: HF_TOKEN
        command: ["/bin/bash", "-c"]
        args:
        - |
          set -ex
          python3 -m maxtext.checkpoint_conversion.to_maxtext \
              model_name=${MODEL_NAME:-gemma3-4b} \
              hf_access_token=${HF_TOKEN?} \
              base_output_directory="gs://${GCS_BUCKET}/${MODEL_NAME}-mt" \
              scan_layers=True \
              use_multimodal=True \
              hardware=cpu \
              skip_jax_distributed_system=true \
              checkpoint_storage_use_zarr3=1 \
              checkpoint_storage_use_ocdbt=1 \
              --lazy_load_tensors=False
      restartPolicy: Never
  backoffLimit: 2
```

### 2. Run MaxText Supervised Fine-Tuning (SFT) Job

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: maxtext-sft
  namespace: default
spec:
  template:
    spec:
      serviceAccountName: maxtext-tutorial-ksa
      nodeSelector:
        cloud.google.com/gke-tpu-accelerator: tpu-v6e-slice
        cloud.google.com/gke-tpu-topology: 2x4
      containers:
      - name: maxtext-train
        image: ${REGION}-docker.pkg.dev/${PROJECT}/maxtext-images/maxtext_base
        resources:
          requests:
            google.com/tpu: "8"
          limits:
            google.com/tpu: "8"
        env:
        - name: MODEL_NAME
          value: "gemma3-4b"
        - name: HF_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token
              key: HF_TOKEN
        - name: RUN_NAME
          value: "sft"
        - name: BASE_OUTPUT_DIRECTORY
          value: "gs://${GCS_BUCKET}/gemma3-4b-mt-trained"
        - name: MAXTEXT_CKPT_PATH
          value: "gs://${GCS_BUCKET}/gemma3-4b-mt/0/items"
        - name: PER_DEVICE_BATCH_SIZE
          value: "1"
        - name: STEPS
          value: "1000"
        - name: DATASET_NAME
          value: "HuggingFaceH4/ultrachat_200k"
        - name: TRAIN_SPLIT
          value: "train_sft"
        - name: TRAIN_DATA_COLUMNS
          value: "['messages']"
        command: ["/bin/bash", "-c"]
        args:
        - |
          set -ex
          python3 -m maxtext.trainers.post_train.sft.train_sft \
              run_name=${RUN_NAME?} \
              base_output_directory=${BASE_OUTPUT_DIRECTORY?} \
              model_name=${MODEL_NAME?} \
              load_parameters_path=${MAXTEXT_CKPT_PATH?} \
              per_device_batch_size=${PER_DEVICE_BATCH_SIZE?} \
              steps=${STEPS?} \
              hf_path=${DATASET_NAME?} \
              train_split=${TRAIN_SPLIT?} \
              train_data_columns="${TRAIN_DATA_COLUMNS?}" \
              skip_jax_distributed_system=True \
              profiler=xplane
      restartPolicy: Never
  backoffLimit: 2
```

### 3. Convert Trained MaxText Checkpoint Back to Hugging Face Format

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: maxtext-checkpoint-to-hf
  namespace: default
spec:
  template:
    spec:
      serviceAccountName: maxtext-tutorial-ksa
      nodeSelector:
        cloud.google.com/compute-class: Performance
      containers:
      - name: maxtext-to-hf
        image: ${REGION}-docker.pkg.dev/${PROJECT}/maxtext-images/maxtext_base
        resources:
          requests:
            cpu: "16"
            memory: "64Gi"
            ephemeral-storage: "10Gi"
        env:
        - name: MODEL_NAME
          value: "gemma3-4b"
        - name: MAXTEXT_CKPT_PATH
          value: "gs://${GCS_BUCKET}/gemma3-4b-mt-trained/sft/checkpoints/1000/model_params"
        - name: HF_EXPORT
          value: "gs://${GCS_BUCKET}/gemma3-4b-trained"
        command: ["/bin/bash", "-c"]
        args:
        - |
          set -ex
          python3 -m maxtext.checkpoint_conversion.to_huggingface \
              model_name=${MODEL_NAME?} \
              load_parameters_path=${MAXTEXT_CKPT_PATH?} \
              base_output_directory=${HF_EXPORT?} \
              scan_layers=True \
              use_multimodal=True \
              skip_jax_distributed_system=True \
              weight_dtype=bfloat16
      restartPolicy: Never
  backoffLimit: 2
```

## Critical Design Features

1. **Automated Conversion**: Checkpoint conversion from Hugging Face format to
   MaxText is built directly into Python execution. If converted parameters do
   not exist in GCS, `train.py` launches
   `maxtext.checkpoint_conversion.to_maxtext` before starting training.
2. **JAX-Level Metric Injection**: Real-time logging is handled via
   zero-code-change monkey patching of JAX's native `clu.metric_writers` API
   inside Python `runpy`, capturing loss scalars and streaming them instantly to
   the MLflow server.
3. **Optimized Resource Layout**: Configured with a dedicated GCS bucket and GKE
   Workload Identity bindings for clean security isolation.
