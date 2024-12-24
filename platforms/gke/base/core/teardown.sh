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

start_timestamp=$(date +%s)

declare -a terraservices
if [[ -v CORE_TERRASERVICES_DESTROY ]]; then
    terraservices=("${CORE_TERRASERVICES_DESTROY[@]}")
else
    terraservices=(
        "workloads/kueue"
        # Disable gke_enterprise/servicemesh due to b/376312292
        # "gke_enterprise/servicemesh"
        "gke_enterprise/fleet_membership"
        "container_node_pool"
        "container_cluster"
        "networking"
    )
fi
echo "Core platform terraservices to destroy: ${terraservices[*]}"

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
    echo "Current directory: $(pwd)" &&
    sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket &&
    cp backend.tf.bucket backend.tf &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
rm tfplan

for terraservice in "${terraservices[@]}"; do
    cd "${ACP_PLATFORM_CORE_DIR}/${terraservice}" &&
        echo "Current directory: $(pwd)" &&
        terraform init &&
        terraform destroy -auto-approve || exit 1
    rm -rf .terraform/
done

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
    echo "Current directory: $(pwd)" &&
    rm -rf backend.tf &&
    terraform init -force-copy -lock=false -migrate-state || exit 1
gcloud storage rm -r gs://${terraform_bucket_name}/* &&
    terraform destroy -auto-approve || exit 1

rm -rf \
    ${ACP_PLATFORM_BASE_DIR}/_shared_config/.terraform/ \
    ${ACP_PLATFORM_BASE_DIR}/_shared_config/terraform.tfstate* \
    ${ACP_PLATFORM_CORE_DIR}/initialize/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/initialize/terraform.tfstate* \
    ${ACP_PLATFORM_CORE_DIR}/networking/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/container_cluster/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/container_node_pool/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/container_node_pool/container_node_pool_*.tf \
    ${ACP_PLATFORM_CORE_DIR}/gke_enterprise/configmanagement/git/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/gke_enterprise/configmanagement/oci/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/gke_enterprise/fleet_membership/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/gke_enterprise/servicemesh/.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/workloads/kueue.terraform/ \
    ${ACP_PLATFORM_CORE_DIR}/workloads/kubeconfig \
    ${ACP_PLATFORM_CORE_DIR}/workloads/manifests

git restore \
    ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket \
    ${ACP_PLATFORM_CORE_DIR}/container_node_pool/container_node_pool_*.tf

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
