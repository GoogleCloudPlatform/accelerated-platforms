#!/usr/bin/env bash

# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

ACP_REPO_DIR=$(realpath "${MY_PATH}/../../../..")

rm --force --recursive \
  "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/.terraform/" \
  "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"/terraform.tfstate* \
  "${ACP_REPO_DIR}/platforms/gke/base/core/container_node_pool/"container_node_pool_* \
  "${ACP_REPO_DIR}/platforms/gke/base/core/initialize/.terraform/" \
  "${ACP_REPO_DIR}/platforms/gke/base/core/initialize"/terraform.tfstate* \
  "${ACP_REPO_DIR}/platforms/gke/base/kubernetes/kubeconfig" \
  "${ACP_REPO_DIR}/platforms/gke/base/kubernetes/manifests" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface/downloader.env" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface/secretproviderclass-huggingface-tokens.yaml" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/base/deployment.env" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/base/deployment.env" \

find "${ACP_REPO_DIR}/platforms/gke/base/" -name backend.tf -delete

git restore \
  "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"/*.auto.tfvars \
  "${ACP_REPO_DIR}/platforms/gke/base/core/initialize/backend.tf.bucket" \
  "${ACP_REPO_DIR}/platforms/gke/base/kubernetes/kubeconfig/.gitkeep" \
  "${ACP_REPO_DIR}/platforms/gke/base/kubernetes/manifests/.gitkeep"
