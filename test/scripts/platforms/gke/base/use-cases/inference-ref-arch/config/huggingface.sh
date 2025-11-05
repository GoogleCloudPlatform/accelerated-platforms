#!/usr/bin/env bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

declare -a hf_models=(
  "black-forest-labs/flux.1-schnell"
  "google/gemma-3-1b-it"
  "google/gemma-3-4b-it"
  "google/gemma-3-27b-it"
  "meta-llama/llama-3.3-70b-instruct"
  "meta-llama/llama-4-scout-17b-16e-instruct"
  "openai/gpt-oss-20b"
  "qwen/qwen3-32b"
  "stabilityai/stable-diffusion-xl-base-1.0"
)

declare -a hf_gpu_diffusers_models=(
  "black-forest-labs/flux.1-schnell"
)

declare -a hf_gpu_vllm_models=(
  "google/gemma-3-1b-it"
  "google/gemma-3-4b-it"
  "google/gemma-3-27b-it"
  "meta-llama/llama-3.3-70b-instruct"
  "meta-llama/llama-4-scout-17b-16e-instruct"
  "openai/gpt-oss-20b"
  "qwen/qwen3-32b"
)

declare -a hf_tpu_max_diffusion_models=(
  "stabilityai/stable-diffusion-xl-base-1.0"
)

declare -a hf_tpu_vllm_models=(
  "google/gemma-3-1b-it"
  "google/gemma-3-4b-it"
  "google/gemma-3-27b-it"
)
