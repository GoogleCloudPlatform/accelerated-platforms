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

# Terraform helpers for the shared (non-regional) terraservices of the
# multi-region example. Source this file after lib.sh.

mr_shared_state_bucket() {
  echo "${MR_PROJECT_ID}-${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-terraform"
}

mr_ensure_shared_state_bucket() {
  local bucket
  bucket="$(mr_shared_state_bucket)"
  if ! gcloud storage buckets describe "gs://${bucket}" --project "${MR_PROJECT_ID}" >/dev/null 2>&1; then
    mr_log "Creating shared Terraform state bucket gs://${bucket}"
    gcloud storage buckets create "gs://${bucket}" \
      --project "${MR_PROJECT_ID}" \
      --location "$(mr_region "${MR_CONFIG_CLUSTER_KEY}")" \
      --uniform-bucket-level-access \
      --public-access-prevention
    gcloud storage buckets update "gs://${bucket}" --versioning >/dev/null
  fi
}

# mr_tf <terraservice> <action> <tfvars_json_file>
# action: apply | destroy
mr_tf() {
  local terraservice="${1}" action="${2}" tfvars_file="${3}"
  local dir="${MR_EXAMPLE_DIR}/terraform/${terraservice}"
  local data_dir="${MR_WORK_DIR}/terraform/${terraservice}"
  mkdir -p "${data_dir}"
  (
    cd "${dir}" || exit 1
    export TF_DATA_DIR="${data_dir}/.terraform"
    export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
    mkdir -p "${TF_PLUGIN_CACHE_DIR}"
    # Check every step explicitly: callers often run under mr_stage, where
    # errexit is off, and a failed plan must not look like a successful apply.
    terraform init -input=false -reconfigure \
      -backend-config="bucket=$(mr_shared_state_bucket)" \
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

mr_write_shared_network_tfvars() {
  local out="${MR_WORK_DIR}/terraform/shared_network.tfvars.json"
  mkdir -p "$(dirname "${out}")"
  "${MR_PYTHON}" - "${out}" <<EOF
import json, sys
keys = "${MR_REGION_KEYS}".split()
region = dict(x.split("=", 1) for x in """$(for k in ${MR_REGION_KEYS}; do echo "${k}=${MR_REGION[${k}]}"; done)""".split())
node = dict(x.split("=", 1) for x in """$(for k in ${MR_REGION_KEYS}; do echo "${k}=${MR_NODE_CIDR[${k}]}"; done)""".split())
rproxy = dict(x.split("=", 1) for x in """$(for k in ${MR_REGION_KEYS}; do echo "${k}=${MR_REGIONAL_PROXY_CIDR[${k}]}"; done)""".split())
gproxy = dict(x.split("=", 1) for x in """$(for k in ${MR_REGION_KEYS}; do echo "${k}=${MR_GLOBAL_PROXY_CIDR[${k}]}"; done)""".split())
tfvars = {
    "project_id": "${MR_PROJECT_ID}",
    "network_name": "${MR_NETWORK_NAME}",
    "regions": {
        k: {
            "region": region[k],
            "node_cidr": node[k],
            "regional_proxy_cidr": rproxy[k],
            "global_proxy_cidr": gproxy[k],
        }
        for k in keys
    },
}
json.dump(tfvars, open(sys.argv[1], "w"), indent=2)
EOF
  echo "${out}"
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
