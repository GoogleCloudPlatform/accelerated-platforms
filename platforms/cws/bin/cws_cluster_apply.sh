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
set -o pipefail

MY_PATH="$(
  cd "$(dirname "${0}")" >/dev/null 2>&1
  pwd -P
)"
MY_NAME=$(basename "${0}" .sh)

declare -A start_timestamp["${MY_NAME}"]
start_timestamp["${MY_NAME}"]=$(date +%s)

ACP_REPO_DIR="$(realpath "${MY_PATH}/../../../")"
ACP_PLATFORM_DIR="${ACP_REPO_DIR}/platforms/cws"
ACP_PLATFORM_TF_DIR="${ACP_PLATFORM_DIR}/cluster/terraform"

# Enable Terraform plugin caching and specifies location of the plugin cache directory
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"

# shellcheck source=/dev/null
source "${ACP_PLATFORM_DIR}/cluster/_shared_config/scripts/set_environment_variables.sh"

declare -a terraservices=(
  "initialize"
  "network"
  "workstation_cluster"
)

apply_cluster_terraservices() {
  for terraservice in "${terraservices[@]}"; do
    cd "${ACP_PLATFORM_TF_DIR}/${terraservice}" &&
      echo "Current directory: $(pwd)" &&
      rm --force --recursive .terraform/ &&
      terraform init &&
      terraform plan -input=false -out=tfplan &&
      terraform apply -input=false tfplan || return 1
    rm tfplan
  done
}

if ! apply_cluster_terraservices; then
  fallback_location="${FALLBACK_LOCATION:-}"
  if [[ -n "${fallback_location}" && "${fallback_location}" != "${workstation_cluster_region:-}" ]]; then
    echo "WARNING: Cluster provisioning failed in '${workstation_cluster_region:-${platform_default_location}}'. Falling back to location '${fallback_location}'..."
    if [[ -n "${workstation_cluster_name:-}" && -n "${workstation_cluster_project_id:-}" && -n "${workstation_cluster_region:-}" ]]; then
      gcloud workstations clusters delete "${workstation_cluster_name}" \
        --project="${workstation_cluster_project_id}" \
        --region="${workstation_cluster_region}" \
        --quiet || true
    fi
    for terraservice in "workstation_cluster" "network"; do
      if [[ -d "${ACP_PLATFORM_TF_DIR}/${terraservice}" ]]; then
        cd "${ACP_PLATFORM_TF_DIR}/${terraservice}" &&
          rm --force --recursive .terraform/ &&
          terraform init &&
          terraform destroy -auto-approve -input=false || true
      fi
    done

    export TF_VAR_platform_default_location="${fallback_location}"
    export TF_VAR_workstation_cluster_region="${fallback_location}"
    if [[ -f "${ACP_PLATFORM_DIR}/_shared_config/platform.auto.tfvars" ]]; then
      sed -i "s|^\([[:blank:]]*platform_default_location[[:blank:]]*=\).*|\1 \"${fallback_location}\"|" "${ACP_PLATFORM_DIR}/_shared_config/platform.auto.tfvars"
    fi
    if [[ -f "${ACP_PLATFORM_DIR}/_shared_config/workstation_cluster.auto.tfvars" ]]; then
      sed -i "s|^\([[:blank:]]*workstation_cluster_region[[:blank:]]*=\).*|\1 \"${fallback_location}\"|" "${ACP_PLATFORM_DIR}/_shared_config/workstation_cluster.auto.tfvars"
    fi
    if [[ -f /workspace/build.env ]]; then
      sed -i "s|^\(export[[:blank:]]\+\)\?TF_VAR_platform_default_location=.*|export TF_VAR_platform_default_location=\"${fallback_location}\"|" /workspace/build.env
    fi

    "${ACP_PLATFORM_DIR}/bin/cws_initialize.sh"
    # shellcheck source=/dev/null
    source "${ACP_PLATFORM_DIR}/cluster/_shared_config/scripts/set_environment_variables.sh"

    apply_cluster_terraservices || exit 1
  else
    exit 1
  fi
fi

declare -A end_timestamp["${MY_NAME}"]
end_timestamp["${MY_NAME}"]=$(date +%s)
total_runtime_value=$((end_timestamp["${MY_NAME}"] - start_timestamp["${MY_NAME}"]))
echo
echo "Total runtime (${MY_NAME}): $(date -d@${total_runtime_value} -u +%H:%M:%S)"
