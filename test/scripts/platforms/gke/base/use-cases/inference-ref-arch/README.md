# GKE Inference reference architecture test scripts

These test scripts can be used to test all of the permutations of the Hugging
Face model downloader, online GPU inference servers, and online TPU inference
servers that are configured in the repository.

## Files

### `config`

This directory contains configuration files that are used by the test scripts.

#### `huggingface.sh`

Contains environment variables to configure different Hugging Face settings.

- `hf_models`: A list of Hugging Face models that will be downloaded by the
  `model-download/huggingface` scripts.
- `hf_gpu_diffusers_models`: A list of Hugging Face models that will be tested
  by the `online-inference-gpu/diffusers` scripts.
- `hf_gpu_dynamo_trtllm_models`: A list of Hugging Face models that will be
  tested by the `online-inference-gpu/dynamo-trtllm` scripts.
- `hf_gpu_trtllm_models`: A list of Hugging Face models that will be tested by
  the `online-inference-gpu/trtllm` scripts.
- `hf_gpu_trtllm_podsnapshot_models`: A list of Hugging Face models that will be
  tested by the `online-inference-gpu/trtllm` scripts when
  `TRTLLM_VARIANT_SUFFIX` is set to `-podsnapshot`.
- `hf_gpu_vllm_models`: A list of Hugging Face models that will be tested by the
  `online-inference-gpu/vllm` scripts.
- `hf_gpu_vllm_podsnapshot_models`: A list of Hugging Face models that will be
  tested by the `online-inference-gpu/vllm-podsnapshot-fast-restore` scripts.
- `hf_gpu_vllm_runai_models`: A list of Hugging Face models that will be tested
  by the `online-inference-gpu/vllm-runai` scripts.
- `hf_tpu_max_diffusion_models`: A list of Hugging Face models that will be
  tested by the `online-inference-tpu/max-diffusion` scripts.
- `hf_tpu_vllm_models`: A list of Hugging Face models that will be tested by the
  `online-inference-tpu/vllm` scripts.

### `model-download/huggingface`

These scripts can be used to download the Hugging Face models and validate the
model download job.

#### `check_hf_models.sh`

Finds all of the `export HF_MODEL_ID=` lines in the repository and creates a
unique list of models. It then compares that list to the `hf_models` environment
variables and outputs and discrepancies.

#### `download_apply.sh`

Applies the manifests for the model download job for all of the models listed in
the `hf_models` environment variable.

#### `download_delete.sh`

Deletes the resources for the model download job for all of the models listed in
the `hf_models` environment variable.

#### `download_wait.sh`

Waits for all of the model download jobs to complete.

#### `model_file_size.sh`

Outputs the size of the models in the Google Cloud Storage bucket for each of
the `hf_models` models.

### `online-inference-gpu`

These scripts can be used to deploy and test the various online inference GPU
models.

#### `diffuser`

These scripts can be used to deploy and test the `hf_gpu_diffusers_models` that
use the Diffusers inference server.

##### `deployment_apply.sh`

Applies the manifests for the GPU Diffusers deployment for all of the models
listed in the `hf_gpu_diffusers_models` environment variable.

##### `deployment_delete.sh`

Applies the resources for the GPU Diffusers deployment for all of the models
listed in the `hf_gpu_diffusers_models` environment variable.

##### `deployment_test.sh`

Sends a test request to all of the GPU Diffusers deployments.

#### `common.sh` and `measure_restore.sh`

`common.sh` is the shared library sourced by the `trtllm` (and other engine)
`deployment_*.sh` scripts. It resolves the overlay for each model, runs the
engine's configure script, and reads Deployment, StatefulSet, Service, and
`PodSnapshotPolicy` names from the rendered overlay, so the scripts do not
hard-code `nameSuffix` values.

`measure_restore.sh` scales out a Deployment that includes the
`components/gke-pod-snapshot` Kustomize Component (`APP` is the Deployment name)
and reports, for each restored replica, the time to `Ready`, `PodRestored`, and
the first successful `/v1/chat/completions` response. If a
HorizontalPodAutoscaler targets the Deployment, it scales out by raising the
HPA's `minReplicas` and restores the original value when it exits.

#### `dynamo-trtllm`

These scripts can be used to deploy and test the `hf_gpu_dynamo_trtllm_models`
that use NVIDIA Dynamo with the TensorRT-LLM backend across `kv-routing`,
`kvbm-offloading`, and `disaggregated-pd` modes (controlled by `DYNAMO_MODE`,
defaulting to `kv-routing`, with optional `ENABLE_POOL_RELAY=true` or
`DYNAMO_VARIANT_SUFFIX` to select variant overlays such as `-pool-relay` or
`-topology-region`).

##### `deployment_apply.sh`

Applies the manifests for the GPU NVIDIA Dynamo + TensorRT-LLM deployment for
all matching models listed in `hf_gpu_dynamo_trtllm_models`.

##### `deployment_delete.sh`

Deletes the resources for the GPU NVIDIA Dynamo + TensorRT-LLM deployment for
all matching models listed in `hf_gpu_dynamo_trtllm_models`.

##### `deployment_test.sh`

Waits for the Dynamo `etcd` `StatefulSet`, worker(s), frontend, and optional
`pool-relay` deployments to become ready and sends OpenAI-compatible
`/v1/models` and `/v1/chat/completions` test requests.

#### `trtllm`

These scripts can be used to deploy and test the `hf_gpu_trtllm_models` that use
the NVIDIA TensorRT-LLM inference server with Cloud Storage FUSE streaming. Set
`TRTLLM_VARIANT_SUFFIX` to `-podsnapshot` to use the
`hf_gpu_trtllm_podsnapshot_models` overlays that add GKE Pod snapshots.

##### `deployment_apply.sh`

Applies the manifests for the GPU TensorRT-LLM deployment for all of the models
listed in the `hf_gpu_trtllm_models` environment variable.

##### `deployment_delete.sh`

Deletes the resources for the GPU TensorRT-LLM deployment for all of the models
listed in the `hf_gpu_trtllm_models` environment variable. For Pod snapshot
overlays, it deletes the Deployment first and then any `PodSnapshot` objects
created by the overlay's `PodSnapshotPolicy`.

##### `deployment_test.sh`

Waits for every Deployment in the overlay and sends test requests to the GPU
TensorRT-LLM deployments. For Pod snapshot overlays, it first waits for the
initial `PodSnapshot` to become available and scales out to two replicas with
`measure_restore.sh` (verifying `LOADING=0` on the restored replica).

#### `vllm`

These scripts can be used to deploy and test the `hf_gpu_vllm_models` that use
the vLLM inference server.

##### `deployment_apply.sh`

Applies the manifests for the GPU vLLM deployment for all of the models listed
in the `hf_gpu_vllm_models` environment variable.

##### `deployment_delete.sh`

Applies the resources for the GPU vLLM deployment for all of the models listed
in the `hf_gpu_vllm_models` environment variable.

##### `deployment_test.sh`

Sends a test request to all of the GPU vLLM deployments.

#### `vllm-podsnapshot-fast-restore`

These scripts can be used to deploy and test the
`hf_gpu_vllm_podsnapshot_models` that use the vLLM inference server with GKE Pod
snapshots.

##### `deployment_apply.sh`

Applies the manifests for the GPU vLLM Pod snapshot fast-restore deployment for
all of the models listed in the `hf_gpu_vllm_podsnapshot_models` environment
variable.

##### `deployment_delete.sh`

Deletes the resources (and any created `PodSnapshot` objects) for the GPU vLLM
Pod snapshot fast-restore deployment for all of the models listed in the
`hf_gpu_vllm_podsnapshot_models` environment variable.

##### `deployment_test.sh`

Waits for the initial `PodSnapshot` to become available, scales out to two
replicas with `measure_restore.sh` (verifying `LOADING=0` on the restored
replica), and sends test requests to the GPU vLLM Pod snapshot fast-restore
deployments.

#### `vllm-runai`

These scripts can be used to deploy and test the `hf_gpu_vllm_runai_models` that
use the vLLM inference server with the NVIDIA Run:ai Model Streamer.

##### `deployment_apply.sh`

Applies the manifests for the GPU vLLM Run:ai Model Streamer deployment for all
of the models listed in the `hf_gpu_vllm_runai_models` environment variable.

##### `deployment_delete.sh`

Deletes the resources for the GPU vLLM Run:ai Model Streamer deployment for all
of the models listed in the `hf_gpu_vllm_runai_models` environment variable.

##### `deployment_test.sh`

Sends a test request to all of the GPU vLLM Run:ai Model Streamer deployments.

### `online-inference-tpu`

These scripts can be used to deploy and test the various online inference TPU
models.

#### `max-diffusion`

These scripts can be used to deploy and test the `hf_tpu_max_diffusion_models`
that use the MaxDiffusion inference server.

##### `deployment_apply.sh`

Applies the manifests for the TPU Diffusers deployment for all of the models
listed in the `hf_tpu_max_diffusion_models` environment variable.

##### `deployment_delete.sh`

Applies the resources for the TPU Diffusers deployment for all of the models
listed in the `hf_tpu_max_diffusion_models` environment variable.

##### `deployment_test.sh`

Sends a test request to all of the TPU MaxDiffusion deployments.

#### `vllm`

These scripts can be used to deploy and test the `hf_tpu_vllm_models` that use
the vLLM inference server.

##### `deployment_apply.sh`

Applies the manifests for the TPU vLLM deployment for all of the models listed
in the `hf_tpu_vllm_models` environment variable.

##### `deployment_delete.sh`

Applies the resources for the TPU vLLM deployment for all of the models listed
in the `hf_tpu_vllm_models` environment variable.

##### `deployment_test.sh`

Sends a test request to all of the TPU vLLM deployments.

## Prerequisite

- The
  [Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  must be deployed and configured in your repository.

  - The `online_gpu` terraservice must be deployed and configured. For the
    `vllm-podsnapshot-fast-restore` and `trtllm/*-podsnapshot` overlays, enable
    GKE Pod snapshots (`ira_online_gpu_pod_snapshots_enabled = true`, GKE
    `1.35.3-gke.1234000` or later with Pod snapshots enabled, and on GKE
    Standard apply
    `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/node-setup/gvisor-disable-core-tags.yaml`).
  - The `online_tpu` terraservice must be deployed and configured.
  - The `images/gpu/diffusers_flux` terraservice must be deployed and
    configured.
  - The `images/tpu/max_diffusion_sdxl` terraservice must be deployed and
    configured.

- Your Hugging Face **Read** access token must be added to the latest version of
  the Secret Manager secret.

## How to use

### Download the models

- Check all of the Hugging Face models for the repository are configured in the
  environment variables.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface/check_hf_models.sh"
  ```

- Download all of the Hugging Face models.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface/download_apply.sh"
  ```

- Wait for all of the Hugging Face models to download.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface/download_wait.sh"
  ```

- Check the size of the downloaded Hugging Face models.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface/model_file_size.sh"
  ```

- Delete the Hugging Face model download resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface/model_file_size.sh"
  ```

### Test the GPU online inference Diffusers models

- Apply the GPU Diffusers manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/diffusers/deployment_apply.sh"
  ```

- Wait for all the deployments to be ready.

- Test the GPU Diffusers inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/diffusers/deployment_test.sh"
  ```

- Delete the GPU Diffusers resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/diffusers/deployment_delete.sh"
  ```

### Test the GPU online inference NVIDIA Dynamo + TensorRT-LLM models

- Select the accelerator type (`rtx-pro-6000`), Dynamo mode (`kv-routing`,
  `kvbm-offloading`, or `disaggregated-pd`), and optionally a single model from
  `hf_gpu_dynamo_trtllm_models` (for example `nvidia/qwen3-32b-nvfp4`,
  `qwen/qwen3-32b-fp8`, or `nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4`).

  ```shell
  export ACCELERATOR_TYPE="rtx-pro-6000"
  export DYNAMO_MODE="kv-routing"
  export HF_MODEL_ID="nvidia/qwen3-32b-nvfp4"
  ```

  To target the FP8 or hybrid Mamba-2 + Attention variants instead:

  ```shell
  export HF_MODEL_ID="qwen/qwen3-32b-fp8"
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4"
  ```

- Apply the GPU NVIDIA Dynamo + TensorRT-LLM manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/dynamo-trtllm/deployment_apply.sh"
  ```

- Test the GPU NVIDIA Dynamo + TensorRT-LLM inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/dynamo-trtllm/deployment_test.sh"
  ```

- Delete the GPU NVIDIA Dynamo + TensorRT-LLM resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/dynamo-trtllm/deployment_delete.sh"
  ```

### Test the GPU online inference TensorRT-LLM models

- Select the accelerator type (`rtx-pro-6000`), and optionally set `HF_MODEL_ID`
  to test a single model from `hf_gpu_trtllm_models` (unset `HF_MODEL_ID` to run
  all configured TensorRT-LLM models).

  ```shell
  export ACCELERATOR_TYPE="rtx-pro-6000"
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4"
  ```

  To target the FP8, BF16, or Super-120B NVFP4 variants instead:

  ```shell
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-fp8"
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-bf16"
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-super-120b-a12b-nvfp4"
  ```

- Apply the GPU TensorRT-LLM manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
  ```

- Test the GPU TensorRT-LLM inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_test.sh"
  ```

- Delete the GPU TensorRT-LLM resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_delete.sh"
  ```

### Test the GPU online inference TensorRT-LLM Pod snapshot fast-restore models

- Select the accelerator type (`rtx-pro-6000`), and optionally set `HF_MODEL_ID`
  to test a single model from `hf_gpu_trtllm_podsnapshot_models` (unset
  `HF_MODEL_ID` to run all configured Pod snapshot models).

  ```shell
  export ACCELERATOR_TYPE="rtx-pro-6000"
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4"
  ```

  To target the FP8 variant instead:

  ```shell
  export HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-fp8"
  ```

- Select the Pod snapshot overlays.

  ```shell
  export TRTLLM_VARIANT_SUFFIX="-podsnapshot"
  ```

- Apply the GPU TensorRT-LLM Pod snapshot fast-restore manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
  ```

- Test the GPU TensorRT-LLM Pod snapshot fast-restore inference servers (waits
  for the checkpoint upload, scales out and measures the restore, and sends test
  requests).

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_test.sh"
  ```

- Delete the GPU TensorRT-LLM Pod snapshot fast-restore resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_delete.sh"
  unset TRTLLM_VARIANT_SUFFIX
  ```

### Test the GPU online inference vLLM models

- Apply the GPU vLLM manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm/deployment_apply.sh"
  ```

- Wait for all the deployments to be ready.

- Test the GPU vLLM inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm/deployment_test.sh"
  ```

- Delete the GPU vLLM resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm/deployment_delete.sh"
  ```

### Test the GPU online inference vLLM Pod snapshot fast-restore models

- Select the accelerator type (`rtx-pro-6000`, `h100`, or `l4`).

  ```shell
  export ACCELERATOR_TYPE="rtx-pro-6000"
  ```

- Apply the GPU vLLM Pod snapshot fast-restore manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshot-fast-restore/deployment_apply.sh"
  ```

- Test the GPU vLLM Pod snapshot fast-restore inference servers (waits for the
  checkpoint upload, scales out and measures the restore, and sends test
  requests).

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshot-fast-restore/deployment_test.sh"
  ```

- Delete the GPU vLLM Pod snapshot fast-restore resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshot-fast-restore/deployment_delete.sh"
  ```

### Test the GPU online inference vLLM Run:ai Model Streamer models

- Select the accelerator type (`rtx-pro-6000` or `h100`).

  ```shell
  export ACCELERATOR_TYPE="rtx-pro-6000"
  ```

- Apply the GPU vLLM Run:ai Model Streamer manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-runai/deployment_apply.sh"
  ```

- Wait for all the deployments to be ready.

- Test the GPU vLLM Run:ai Model Streamer inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-runai/deployment_test.sh"
  ```

- Delete the GPU vLLM Run:ai Model Streamer resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-runai/deployment_delete.sh"
  ```

### Test the TPU online inference MaxDiffusion models

test/scripts/platforms/gke/base/use-cases/inference-ref-arch/

- Apply the TPU MaxDiffusion manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/max-diffusion/deployment_apply.sh"
  ```

- Wait for all the deployments to be ready.

- Test the TPU MaxDiffusion inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/max-diffusion/deployment_test.sh"
  ```

- Delete the TPU MaxDiffusion resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/max-diffusion/deployment_delete.sh"
  ```

### Test the TPU online inference vLLM models

- Apply the TPU vLLM manifests.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm/deployment_apply.sh"
  ```

- Wait for all the deployments to be ready.

- Test the TPU vLLM inference servers.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm/deployment_test.sh"
  ```

- Delete the TPU vLLM resources.

  ```shell
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-tpu/vllm/deployment_delete.sh"
  ```
