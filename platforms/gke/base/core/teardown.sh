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
set -o pipefail

# shellcheck disable=SC1091
source "${ACP_PLATFORM_CORE_DIR}/functions.sh"

start_timestamp=$(date +%s)

declare -a terraservices
if [[ -v CORE_TERRASERVICES_DESTROY ]] &&
  [[ -n "${CORE_TERRASERVICES_DESTROY:-""}" ]]; then
  echo "Found customized core platform terraservices set to destroy: ${CORE_TERRASERVICES_DESTROY}"
  ParseSpaceSeparatedBashArray "${CORE_TERRASERVICES_DESTROY}" "terraservices"
else
  terraservices=(
    "workloads/kueue"
    # Disable gke_enterprise/servicemesh due to b/376312292
    # "gke_enterprise/servicemesh"
    "gke_enterprise/fleet_membership"
    "container_node_pool"
    "container_cluster"
    "networking"
    "initialize"
  )
fi
echo "Core platform terraservices to destroy: ${terraservices[*]}"

# shellcheck disable=SC1091
source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh" "${ACP_PLATFORM_BASE_DIR}/_shared_config"

# shellcheck disable=SC2154 # Variable is defined as a terraform output and sourced in other scripts
cd "${ACP_PLATFORM_CORE_DIR}/initialize" &&
  echo "Current directory: $(pwd)" &&
  sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket" &&
  cp backend.tf.bucket backend.tf &&
  terraform init &&
  terraform plan -input=false -out=tfplan &&
  terraform apply -input=false tfplan || exit 1
rm tfplan

for terraservice in "${terraservices[@]}"; do
  if [[ "${terraservice}" != "initialize" ]]; then
    cd "${ACP_PLATFORM_CORE_DIR}/${terraservice}" &&
      echo "Current directory: $(pwd)" &&
      terraform init &&
      terraform destroy -auto-approve || exit 1
    rm -rf .terraform/
  # Destroy the backend only if we're destroying the initialize service,
  # otherwise we wouldn't be able to support a tiered core platform provisioning
  # and teardown
  else
    cd "${ACP_PLATFORM_CORE_DIR}/${terraservice}" &&
      echo "Current directory: $(pwd)" &&
      rm -rf backend.tf &&
      terraform init -force-copy -lock=false -migrate-state || exit 1

    # Quote the globbing expression because we don't want to expand it with the
    # shell
    gcloud storage rm -r "gs://${terraform_bucket_name}/*" &&
      terraform destroy -auto-approve || exit 1

    rm -rf .terraform/
    rm -rf terraform.tfstate*

    rm -rf \
      "${ACP_PLATFORM_BASE_DIR}/_shared_config/.terraform/" \
      "${ACP_PLATFORM_BASE_DIR}/_shared_config"/terraform.tfstate* \
      "${ACP_PLATFORM_CORE_DIR}/kubernetes/kubeconfig" \
      "${ACP_PLATFORM_CORE_DIR}/kubernetes/manifests"

    git restore \
      "${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket" \
      "${ACP_PLATFORM_BASE_DIR}/kubernetes/kubeconfig/.gitkeep" \
      "${ACP_PLATFORM_BASE_DIR}/kubernetes/manifests/.gitkeep"
  fi
done

end_timestamp=$(date +%s)
total_runtime_value=$((end_timestamp - start_timestamp))
echo "Total runtime: $(date -d@${total_runtime_value} -u +%H:%M:%S)"
