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

# Set use-case specific values
export TF_VAR_initialize_backend_use_case_name="aiml/terraform"
export TF_VAR_resource_name_prefix="aiml"

${ACP_PLATFORM_USE_CASE_DIR}/deploy.sh

source ${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh ${ACP_PLATFORM_BASE_DIR}/_shared_config ${ACP_PLATFORM_USE_CASE_DIR}/_shared_config

declare -a aiml_terraservices=(
  "initialize"
  "pipelines/fine-tuning"
)
for terraservice in "${aiml_terraservices[@]}"; do
  cd "${ACP_PLATFORM_USE_CASE_DIR}/terraform/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  rm tfplan
done

echo -e "\n\nGenerating environment configuration file..."

export MLP_ENVIRONMENT_FILE="${ACP_PLATFORM_USE_CASE_DIR}/terraform/pipelines/fine-tuning/${cluster_project_id}_${unique_identifier_prefix}.env"
cd ${ACP_PLATFORM_USE_CASE_DIR}/terraform/pipelines/fine-tuning &&
  terraform output -raw environment_configuration >${MLP_ENVIRONMENT_FILE} &&
  source ${MLP_ENVIRONMENT_FILE} &&
  echo -e "The environment configuration file '${MLP_ENVIRONMENT_FILE}' has been generated.\n\n"

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "fine-tuning-pipeline deploy total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
