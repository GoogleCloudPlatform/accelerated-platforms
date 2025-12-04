# GKE Inference reference architecture test scripts

## `config`

This directory contains configuration files that are used by the test scripts.

### `huggingface.sh`

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

## `model-download`

## `online-inference-gpu`

### `diffuser`

### `vllm`

## `online-inference-tpu`

### `max-diffusion`

### `vllm`
