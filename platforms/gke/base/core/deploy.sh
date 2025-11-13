#!/bin/bash
#
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
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# Set repository values
ACP_REPO_DIR="$(realpath ${MY_PATH}/../../../../)"
ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"

# Enable Terraform plugin caching and specifies location of the plugin cache directory
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_CORE_DIR}/functions.sh"

declare -a terraservices
if [[ -v CORE_TERRASERVICES_APPLY ]] && [[ -n "${CORE_TERRASERVICES_APPLY:-""}" ]]; then
  ParseSpaceSeparatedBashArray "${CORE_TERRASERVICES_APPLY}" "terraservices"
else
  echo "CORE_TERRASERVICES_APPLY was not set, exiting..."
  exit 1
fi
echo "Core platform Terraservices to provision: ${terraservices[*]}"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh"

declare -a projects=(
  "${cluster_node_pool_service_account_project_id}"
  "${cluster_project_id}"
  "${huggingface_hub_models_bucket_project_id}"
  "${huggingface_secret_manager_project_id}"
  "${nvidia_ncg_api_key_secret_manager_project_id}"
  "${nvidia_nim_model_store_bucket_project_id}"
  "${platform_default_project_id}"
  "${terraform_project_id}"
)
unique_projects=($(printf "%s\n" "${projects[@]}" | sort -u))

declare -a services=(
  "cloudresourcemanager.googleapis.com"
  "servicemanagement.googleapis.com"
  "serviceusage.googleapis.com"
)

for project in "${unique_projects[@]}"; do
  echo "Enabling services for project ${project}:"
  for service in "${services[@]}"; do
    echo " - ${service}"
    gcloud services enable ${service} \
      --project=${project} \
      --quiet
  done
  echo
done

# shellcheck disable=SC2154 # Variable is defined as a terraform output and sourced in other scripts
cd "${ACP_PLATFORM_CORE_DIR}/initialize" &&
  echo "Current directory: $(pwd)" &&
  sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket" &&
  export STATE_MIGRATED="false" &&
  if gcloud storage ls "gs://${terraform_bucket_name}/terraform/initialize/default.tfstate" &>/dev/null; then
    if [ ! -f "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf" ]; then
      cp backend.tf.bucket backend.tf
    fi
    export STATE_MIGRATED="true"
  fi

cd "${ACP_PLATFORM_CORE_DIR}/initialize" &&
  rm -rf .terraform/ &&
  terraform init &&
  terraform plan -input=false -out=tfplan &&
  terraform apply -input=false tfplan || exit 1
rm tfplan

if [ "${STATE_MIGRATED}" == "false" ]; then
  echo "Migrating the state backend"
  terraform init -force-copy -migrate-state || exit 1
  rm -rf terraform.tfstate*
fi

for terraservice in "${terraservices[@]}"; do
  cd "${ACP_PLATFORM_CORE_DIR}/${terraservice}" &&
    echo "Current directory: $(pwd)" &&
    rm -rf .terraform/ &&
    terraform init &&
    terraform plan -input=false -out=tfplan &&
    terraform apply -input=false tfplan || exit 1
  rm tfplan
done
