#!/bin/bash
#
# Copyright 2024 Google LLC
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

export TF_VAR_initialize_backend_use_case_name="aiml/platform"

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config ${ACP_PLATFORM_USE_CASE_DIR}/_shared_config

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
    echo "Current directory: $(pwd)" &&
    sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket &&
    cp backend.tf.bucket backend.tf &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
rm tfplan

cp ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf ${ACP_PLATFORM_USE_CASE_DIR}/platform/initialize/backend.tf
sed -i "s/^\([[:blank:]]*prefix[[:blank:]]*=\).*$/\1 \"terraform\/aiml\/platform\/initialize\"/" ${ACP_PLATFORM_USE_CASE_DIR}/platform/initialize/backend.tf

declare -a aiml_terraservices=("initialize")
for terraservice in $(echo "${aiml_terraservices[@]}" | tac -s " "); do
    cd "${ACP_PLATFORM_USE_CASE_DIR}/platform/${terraservice}" &&
        echo "Current directory: $(pwd)" &&
        terraform init &&
        terraform destroy -auto-approve || exit 1
    rm -rf .terraform/
done

declare -a CORE_TERRASERVICES_DESTROY=("workloads/kueue" "gke_enterprise/fleet_membership" "container_node_pool" "container_cluster" "networking")
${ACP_PLATFORM_CORE_DIR}/teardown.sh

rm -rf \
    ${ACP_PLATFORM_USE_CASE_DIR}/_shared_config/terraform.tfstate* \
    ${ACP_PLATFORM_USE_CASE_DIR}/platform/initialize/backend.tf

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
