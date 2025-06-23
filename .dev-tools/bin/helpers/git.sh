#!/usr/bin/env bash

declare -a git_assume_unchanged_files=(
  "platforms/gke/base/_shared_config/cluster.auto.tfvars"
  "platforms/gke/base/_shared_config/configmanagement.auto.tfvars"
  "platforms/gke/base/_shared_config/huggingface.auto.tfvars"
  "platforms/gke/base/_shared_config/initialize.auto.tfvars"
  "platforms/gke/base/_shared_config/networking.auto.tfvars"
  "platforms/gke/base/_shared_config/nvidia.auto.tfvars"
  "platforms/gke/base/_shared_config/platform.auto.tfvars"
  "platforms/gke/base/_shared_config/terraform.auto.tfvars"
  "platforms/gke/base/_shared_config/workloads.auto.tfvars"
)
