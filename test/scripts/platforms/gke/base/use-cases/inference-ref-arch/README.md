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
- `hf_gpu_vllm_models`: A list of Hugging Face models that will be tested by the
  `online-inference-gpu/vllm` scripts.
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

  - The `online_gpu` terraservice must be deployed and configured.
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
