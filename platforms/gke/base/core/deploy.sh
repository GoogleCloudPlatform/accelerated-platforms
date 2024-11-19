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
set -e

start_timestamp=$(date +%s)

terraservices=("networking" "container_cluster" "container_node_pool" "gke_enterprise/fleet_membership" "workloads/kueue")
# Disable gke_enterprise/servicemesh due to b/376312292
#terraservices=("networking" "container_cluster" "container_node_pool" "gke_enterprise/fleet_membership" "gke_enterprise/servicemesh" "workloads/kueue")

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
    echo "Current directory: $(pwd)" &&
    export STATE_MIGRATED="false" &&
    if gcloud storage ls gs://${ACP_TERRAFORM_BUCKET_NAME}/terraform/initialize/default.tfstate &>/dev/null; then
        sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${ACP_TERRAFORM_BUCKET_NAME}\"/" ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket &&
            cp backend.tf.bucket backend.tf &&
            export STATE_MIGRATED="true"
    fi

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
rm tfplan

if [ ${STATE_MIGRATED} == "false" ]; then
    echo "Migrating the state backend"
    cp backend.tf.bucket backend.tf &&
        terraform init -force-copy -migrate-state || exit 1
    rm -rf state
fi

for terraservice in "${terraservices[@]}"; do
    cd "${ACP_PLATFORM_CORE_DIR}/${terraservice}" &&
        echo "Current directory: $(pwd)" &&
        terraform init &&
        terraform plan -input=false -out=tfplan &&
        terraform apply -input=false tfplan || exit 1
    rm tfplan
done

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
