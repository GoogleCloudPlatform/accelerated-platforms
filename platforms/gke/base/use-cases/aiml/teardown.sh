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
set -o errexit
set -o nounset

start_timestamp=$(date +%s)

export TF_VAR_initialize_backend_use_case_name="aiml/terraform"
export TF_VAR_resource_name_prefix="aiml"

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config ${ACP_PLATFORM_USE_CASE_DIR}/_shared_config

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
  echo "Current directory: $(pwd)" &&
  sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket &&
  cp backend.tf.bucket backend.tf &&
  terraform init &&
  terraform plan -input=false -out=tfplan &&
  terraform apply -input=false tfplan || exit 1
rm tfplan

declare -a CORE_TERRASERVICES_DESTROY=(
  "workloads/kueue"
  "workloads/kuberay"
  "workloads/cluster_credentials"
  "gke_enterprise/fleet_membership"
  "container_node_pool"
  "container_cluster"
  "networking"
  "initialize"
)
CORE_TERRASERVICES_DESTROY="${CORE_TERRASERVICES_DESTROY[*]}" ${ACP_PLATFORM_CORE_DIR}/teardown.sh

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "aiml teardown total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
