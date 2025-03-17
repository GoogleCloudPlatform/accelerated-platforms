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

export ACP_TEARDOWN_CORE_PLATFORM=${ACP_TEARDOWN_CORE_PLATFORM:-"true"}

export TF_VAR_initialize_backend_use_case_name="aiml/terraform"
export TF_VAR_resource_name_prefix="aiml"

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config ${ACP_PLATFORM_USE_CASE_DIR}/_shared_config

export MLP_ENVIRONMENT_FILE="${ACP_PLATFORM_USE_CASE_DIR}/terraform/pipelines/fine-tuning/${cluster_project_id}_${unique_identifier_prefix}.env"

cd ${ACP_PLATFORM_CORE_DIR}/initialize &&
    echo "Current directory: $(pwd)" &&
    sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" ${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket &&
    cp backend.tf.bucket backend.tf &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
rm tfplan

declare -a aiml_terraservices=(
    "pipelines/fine-tuning"
    "initialize"
)
for terraservice in $(echo "${aiml_terraservices[@]}" | tac -s " "); do
    cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
        echo "Current directory: $(pwd)" &&
        terraform init &&
        terraform destroy -auto-approve || exit 1
    rm -rf .terraform/
done

if [ "${ACP_TEARDOWN_CORE_PLATFORM}" = "true" ]; then
    ${ACP_PLATFORM_USE_CASE_DIR}/teardown.sh
else
    echo "Skipping core platform teardown."
fi

rm -rf \
    ${MLP_ENVIRONMENT_FILE}

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "fine-tuning-pipeline teardown total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
