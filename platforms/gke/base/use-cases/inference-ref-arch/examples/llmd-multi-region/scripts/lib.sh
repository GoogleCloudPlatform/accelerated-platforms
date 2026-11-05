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

# Shared helpers for the multi-region llm-d example. Sources mr.env, bridges
# its settings onto the shared multi-region foundation
# (platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh),
# and adds llm-d timing, rendering, and benchmark helpers. Source this file;
# don't execute it.

MR_SCRIPTS_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd -P
)"
export MR_SCRIPTS_DIR
MR_EXAMPLE_DIR="$(realpath "${MR_SCRIPTS_DIR}/..")"
export MR_EXAMPLE_DIR
MR_MULTI_REGION_DIR="$(realpath "${MR_EXAMPLE_DIR}/../../terraform/multi-region")"
export MR_MULTI_REGION_DIR

# shellcheck source=/dev/null
source "${MR_EXAMPLE_DIR}/mr.env"

# Bridge example settings onto terraform/multi-region/{helpers,provision,teardown,global_lb}.sh.
export PROJECT_ID="${MR_PROJECT_ID}"
export TF_VAR_resource_name_prefix="${MR_RESOURCE_NAME_PREFIX}"
export NETWORK_MODE="${NETWORK_MODE:-shared-vpc}"
export CLUSTER_MODE="${CLUSTER_MODE:-standard}"
export ENABLE_POD_SNAPSHOTS="${MR_POD_SNAPSHOTS_ENABLED}"
export TF_VAR_ira_online_gpu_kubernetes_namespace_name="${MR_NAMESPACE}"
export TF_VAR_ira_online_gpu_kubernetes_service_account_name="${MR_NAMESPACE}"
export TF_VAR_cluster_system_node_pool_machine_type="${MR_SYSTEM_MACHINE_TYPE_DEFAULT}"

# shellcheck source=/dev/null
source "${MR_MULTI_REGION_DIR}/helpers.sh"
mr_load_settings || exit 1

export MR_PYTHON="${MR_PYTHON:-python3}"

mkdir -p "${MR_WORK_DIR}" "${MR_RESULTS_DIR}/timings"

# Identifier for the current end-to-end run. Reuse it across scripts by
# exporting MR_RUN_ID; otherwise a new one is generated per invocation.
export MR_RUN_ID="${MR_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export MR_TIMINGS_FILE="${MR_TIMINGS_FILE:-${MR_RESULTS_DIR}/timings/${MR_RUN_ID}.jsonl}"

# mr_record_timing <stage> <scope> <start_epoch_s> <end_epoch_s> <status> [extra_json]
mr_record_timing() {
  local stage="${1}" scope="${2}" start="${3}" end="${4}" status="${5}" extra="${6:-{\}}"
  "${MR_PYTHON}" - "${MR_TIMINGS_FILE}" "${MR_RUN_ID}" "${stage}" "${scope}" "${start}" "${end}" "${status}" "${extra}" <<'EOF'
import json, sys
path, run_id, stage, scope, start, end, status, extra = sys.argv[1:9]
record = {
    "run_id": run_id,
    "stage": stage,
    "scope": scope,
    "start_epoch_s": float(start),
    "end_epoch_s": float(end),
    "duration_s": round(float(end) - float(start), 3),
    "status": status,
}
record.update(json.loads(extra))
with open(path, "a") as f:
    f.write(json.dumps(record) + "\n")
EOF
}

# mr_stage <stage> <scope> <command...>
# Runs a command, records its wall-clock duration and exit status in the
# timings file, and propagates the exit status.
mr_stage() {
  local stage="${1}" scope="${2}"
  shift 2
  local start end rc
  mr_log ">>> [${scope}] ${stage}: start"
  start="$(date +%s.%N)"
  set +o errexit
  "$@"
  rc=$?
  set -o errexit
  end="$(date +%s.%N)"
  if [[ ${rc} -eq 0 ]]; then
    mr_record_timing "${stage}" "${scope}" "${start}" "${end}" "ok"
    mr_log "<<< [${scope}] ${stage}: ok ($("${MR_PYTHON}" -c "print(round(${end}-${start},1))")s)"
  else
    mr_record_timing "${stage}" "${scope}" "${start}" "${end}" "failed" "{\"exit_code\": ${rc}}"
    mr_log "<<< [${scope}] ${stage}: FAILED with exit code ${rc}"
  fi
  return ${rc}
}

mr_require_example_tools() {
  mr_require_tools gcloud kubectl kustomize helm terraform jq "${MR_PYTHON}" git envsubst curl sponge flock
  if ! "${MR_PYTHON}" -c "import yaml" >/dev/null 2>&1; then
    mr_die "${MR_PYTHON} is missing PyYAML ('import yaml' failed). Install PyYAML or export MR_PYTHON=/path/to/venv/bin/python3."
  fi
}

mr_validate_region_key() {
  local key="${1}"
  [[ -n "${MR_REGION[${key}]:-}" ]] || mr_die "unknown region key '${key}'. Define it in MR_REGION in mr.env."
  [[ -n "${MR_CIDR_INDEX[${key}]:-}" ]] || mr_die "missing CIDR index for region key '${key}'. Define it in MR_CIDR_INDEX in mr.env."
  [[ "${key}" =~ ^[a-z][a-z0-9-]{0,8}$ ]] || mr_die "region key '${key}' must be 1-9 lowercase letters, digits, or hyphens, starting with a letter."
}

mr_validate_active_region_key() {
  local key="${1}"
  mr_validate_region_key "${key}"
  [[ " ${MR_REGION_KEYS} " == *" ${key} "* ]] ||
    mr_die "region key '${key}' is not in active MR_REGION_KEYS='${MR_REGION_KEYS}'"
}

# Per-region derived names. mr_cluster_name, mr_kubeconfig, mr_worktree_dir,
# mr_neg_name, mr_shared_network_name, mr_state_bucket, and mr_wait_for come
# directly from terraform/multi-region/helpers.sh (with <key> as <platform_name>).
mr_region() { echo "${MR_REGION[${1}]}"; }
mr_cidr_index() { echo "${MR_CIDR_INDEX[${1}]}"; }
mr_target_spec() { echo "${1}:$(mr_region "${1}"):$(mr_cidr_index "${1}")"; }
mr_node_cidr() { (mr_set_cidrs_for_index "$(mr_cidr_index "${1}")" && echo "${MR_NODE_CIDR}"); }
mr_models_bucket() { echo "${MR_PROJECT_ID}-$(mr_cluster_name "${1}")-hf-hub-models"; }
mr_pod_snapshots_bucket() { echo "${MR_PROJECT_ID}-$(mr_cluster_name "${1}")-pod-snapshots"; }
# GPU compute class of a region: MR_COMPUTE_CLASS_REGION[<key>] or MR_COMPUTE_CLASS.
mr_compute_class() { echo "${MR_COMPUTE_CLASS_REGION[${1}]:-${MR_COMPUTE_CLASS}}"; }

# mr_kubectl <region_key> <kubectl args...>
mr_kubectl() {
  local key="${1}"
  shift
  kubectl --kubeconfig "$(mr_kubeconfig "${key}")" "$@"
}

mr_helm() {
  local key="${1}"
  shift
  helm --kubeconfig "$(mr_kubeconfig "${key}")" "$@"
}

mr_get_credentials() {
  local key="${1}" kubeconfig
  kubeconfig="$(mr_kubeconfig "${key}")"
  mkdir -p "$(dirname "${kubeconfig}")"
  KUBECONFIG="${kubeconfig}" gcloud container clusters get-credentials \
    "$(mr_cluster_name "${key}")" \
    --dns-endpoint \
    --location "$(mr_region "${key}")" \
    --project "${MR_PROJECT_ID}" >/dev/null
}

# mr_gateway_vip <gateway_name> <region_key>
# Prints the internal VIP of the cross-region load balancer in a region. With
# MR_GLOBAL_LB=terraform, VIPs are recorded by scripts/set-route.sh (from
# terraform/multi-region/global_lb.sh vips). With MR_GLOBAL_LB=mc-gateway, the
# VIP is matched to the region's node subnet range.
mr_gateway_vip() {
  local gateway="${1}" key="${2}"
  if [[ "${MR_GLOBAL_LB}" != "mc-gateway" ]]; then
    local vips_file="${MR_RESULTS_DIR}/gateway/vips.json"
    [[ -f "${vips_file}" ]] || vips_file="${MR_WORK_DIR}/terraform/global_lb.vips.json"
    jq -er --arg k "${key}" '.[$k] // empty' "${vips_file}" 2>/dev/null
    return
  fi
  local addresses node_cidr
  addresses="$(mr_kubectl "${MR_CONFIG_CLUSTER_KEY}" get gateway "${gateway}" -n "${MR_NAMESPACE}" \
    -o jsonpath='{range .status.addresses[*]}{.value}{"\n"}{end}' 2>/dev/null)" || return 1
  node_cidr="$(mr_node_cidr "${key}")" || return 1
  "${MR_PYTHON}" - "${node_cidr}" <<EOF
import ipaddress, sys
net = ipaddress.ip_network(sys.argv[1])
for line in """${addresses}""".split():
    try:
        if ipaddress.ip_address(line) in net:
            print(line)
            sys.exit(0)
    except ValueError:
        pass
sys.exit(1)
EOF
}

# mr_probe_completion <client_region_key> <vip>
# Sends one small completion request from the in-VPC probe client in a region
# to a VIP. Succeeds on HTTP 200.
mr_probe_completion() {
  local key="${1}" vip="${2}"
  local body
  body="$(printf '{"model":"%s","prompt":"Say hello.","max_tokens":8}' "${MR_SERVED_MODEL_NAME}")"
  mr_kubectl "${key}" exec -n "${MR_NAMESPACE}" deploy/probe-client -- \
    curl -sS -o /dev/null -w '%{http_code}' --max-time 60 \
    -H 'Content-Type: application/json' -d "${body}" \
    "http://${vip}/v1/completions" 2>/dev/null | grep -q '^200$'
}
