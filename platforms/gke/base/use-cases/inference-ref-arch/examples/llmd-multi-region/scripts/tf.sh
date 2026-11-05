#!/usr/bin/env bash
#
# Copyright 2026 Google LLC
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

# Terraform helpers for the example-specific shared terraservices under
# examples/llmd-multi-region/terraform/ (bench, fleet, front_door). Shared VPC
# and cross-region load balancer terraservices live in terraform/multi-region/.
# Source this file after lib.sh.

mr_ensure_example_state_bucket() {
  mr_ensure_state_bucket "$(mr_region "${MR_CONFIG_CLUSTER_KEY}")"
}

# mr_example_tf_state_has_resources <terraservice>
# Succeeds when the state of an example-local terraservice has resources.
mr_example_tf_state_has_resources() {
  local object err_file state err count
  object="gs://$(mr_state_bucket)/terraform/llmd-multi-region/${1}/default.tfstate"
  err_file="$(mktemp)"
  if ! state="$(gcloud storage cat "${object}" 2>"${err_file}")"; then
    err="$(<"${err_file}")"
    rm -f "${err_file}"
    if [[ "${err,,}" == *"matched no objects"* || "${err,,}" == *"not found"* || "${err,,}" == *"404"* ]]; then
      return 1
    fi
    mr_die "failed to read ${object}: ${err}"
  fi
  rm -f "${err_file}"
  count="$(jq '.resources | length' <<<"${state}")" || mr_die "${object} is not a Terraform state file."
  ((count > 0))
}

# mr_example_tf <terraservice> <action> <tfvars_json_file>
# action: apply | destroy
mr_example_tf() {
  local terraservice="${1}" action="${2}" tfvars_file="${3}"
  local dir="${MR_EXAMPLE_DIR}/terraform/${terraservice}"
  local data_dir="${MR_WORK_DIR}/terraform/example-${terraservice}"
  mkdir -p "${data_dir}"
  (
    cd "${dir}" || exit 1
    export TF_DATA_DIR="${data_dir}/.terraform"
    export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
    mkdir -p "${TF_PLUGIN_CACHE_DIR}"
    # Check every step explicitly: callers often run under mr_stage, where
    # errexit is off, and a failed plan must not look like a successful apply.
    terraform init -input=false -reconfigure \
      -backend-config="bucket=$(mr_state_bucket)" \
      -backend-config="prefix=terraform/llmd-multi-region/${terraservice}" >/dev/null || exit 1
    if [[ "${action}" == "destroy" ]]; then
      terraform destroy -input=false -auto-approve -var-file="${tfvars_file}" || exit 1
    else
      rm -f "${data_dir}/tfplan"
      terraform plan -input=false -var-file="${tfvars_file}" -out="${data_dir}/tfplan" || exit 1
      terraform apply -input=false "${data_dir}/tfplan" || exit 1
      rm -f "${data_dir}/tfplan"
    fi
  )
}

mr_write_fleet_tfvars() {
  local out="${MR_WORK_DIR}/terraform/fleet.tfvars.json"
  mkdir -p "$(dirname "${out}")"
  jq -n \
    --arg project_id "${MR_PROJECT_ID}" \
    --arg config_membership_id "$(mr_cluster_name "${MR_CONFIG_CLUSTER_KEY}")" \
    '{project_id: $project_id, config_membership_id: $config_membership_id}' >"${out}"
  echo "${out}"
}
