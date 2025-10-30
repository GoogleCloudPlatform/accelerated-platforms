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

declare -a git_assume_unchanged_files=(
  "platforms/cws/_shared_config/initialize/backend.tf.bucket"
  "platforms/cws/_shared_config/profile/**/*.auto.tfvars"
  "platforms/gke/base/_shared_config/cloudbuild.auto.tfvars"
  "platforms/gke/base/_shared_config/cluster.auto.tfvars"
  "platforms/gke/base/_shared_config/configmanagement.auto.tfvars"
  "platforms/gke/base/_shared_config/huggingface.auto.tfvars"
  "platforms/gke/base/_shared_config/initialize.auto.tfvars"
  "platforms/gke/base/_shared_config/networking.auto.tfvars"
  "platforms/gke/base/_shared_config/nvidia.auto.tfvars"
  "platforms/gke/base/_shared_config/platform.auto.tfvars"
  "platforms/gke/base/_shared_config/policycontroller.auto.tfvars"
  "platforms/gke/base/_shared_config/terraform.auto.tfvars"
  "platforms/gke/base/_shared_config/workloads.auto.tfvars"
  "platforms/gke/base/core/initialize/backend.tf.bucket"
  "platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface/kustomization.yaml"
)
