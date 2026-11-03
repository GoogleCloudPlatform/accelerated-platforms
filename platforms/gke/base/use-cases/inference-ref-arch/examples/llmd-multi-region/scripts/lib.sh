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

# Shared helpers for the multi-region llm-d example. Source this file; don't
# execute it.

MR_SCRIPTS_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd -P
)"
export MR_SCRIPTS_DIR
export MR_EXAMPLE_DIR="$(realpath "${MR_SCRIPTS_DIR}/..")"
export ACP_REPO_DIR="$(realpath "${MR_EXAMPLE_DIR}/../../../../../../..")"
export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
export ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch"

# shellcheck source=/dev/null
source "${MR_EXAMPLE_DIR}/mr.env"

mkdir -p "${MR_WORK_DIR}" "${MR_RESULTS_DIR}/timings"

# Identifier for the current end-to-end run. Reuse it across scripts by
# exporting MR_RUN_ID; otherwise a new one is generated per invocation.
export MR_RUN_ID="${MR_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export MR_TIMINGS_FILE="${MR_TIMINGS_FILE:-${MR_RESULTS_DIR}/timings/${MR_RUN_ID}.jsonl}"

mr_log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >&2
}

mr_die() {
  mr_log "ERROR: $*"
  exit 1
}

# mr_record_timing <stage> <scope> <start_epoch_s> <end_epoch_s> <status> [extra_json]
mr_record_timing() {
  local stage="${1}" scope="${2}" start="${3}" end="${4}" status="${5}" extra="${6:-{\}}"
  python3 - "${MR_TIMINGS_FILE}" "${MR_RUN_ID}" "${stage}" "${scope}" "${start}" "${end}" "${status}" "${extra}" <<'EOF'
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
    mr_log "<<< [${scope}] ${stage}: ok ($(python3 -c "print(round(${end}-${start},1))")s)"
  else
    mr_record_timing "${stage}" "${scope}" "${start}" "${end}" "failed" "{\"exit_code\": ${rc}}"
    mr_log "<<< [${scope}] ${stage}: FAILED with exit code ${rc}"
  fi
  return ${rc}
}

mr_require_tools() {
  local missing=()
  for tool in gcloud kubectl kustomize helm terraform jq python3 git envsubst; do
    command -v "${tool}" >/dev/null 2>&1 || missing+=("${tool}")
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    mr_die "missing required tools: ${missing[*]}"
  fi
}

mr_validate_region_key() {
  local key="${1}"
  [[ -n "${MR_REGION[${key}]:-}" ]] || mr_die "unknown region key '${key}'. Define it in mr.env."
  local platform_name="${MR_ENVIRONMENT_NAME}${key}"
  [[ ${#platform_name} -le 9 ]] || mr_die "platform_name '${platform_name}' is longer than 9 characters"
}

# Per-region derived names. These mirror the core platform naming:
#   unique_identifier_prefix = "${resource_name_prefix}-${platform_name}"
#   cluster_name             = unique_identifier_prefix
mr_platform_name() { echo "${MR_ENVIRONMENT_NAME}${1}"; }
mr_cluster_name() { echo "${MR_RESOURCE_NAME_PREFIX}-$(mr_platform_name "${1}")"; }
mr_region() { echo "${MR_REGION[${1}]}"; }
mr_worktree_dir() { echo "${MR_WORK_DIR}/worktrees/$(mr_platform_name "${1}")"; }
mr_kubeconfig() { echo "${MR_WORK_DIR}/kubeconfig/$(mr_cluster_name "${1}")"; }
mr_models_bucket() { echo "${MR_PROJECT_ID}-$(mr_cluster_name "${1}")-hf-hub-models"; }
mr_pod_snapshots_bucket() { echo "${MR_PROJECT_ID}-$(mr_cluster_name "${1}")-pod-snapshots"; }
# GPU compute class of a region: MR_COMPUTE_CLASS_REGION[<key>] or MR_COMPUTE_CLASS.
mr_compute_class() { echo "${MR_COMPUTE_CLASS_REGION[${1}]:-${MR_COMPUTE_CLASS}}"; }
# Prefix of the GKE standalone NEG names of a region:
#   <prefix>-<backend>, backend = baseline | ppcr | ob
mr_neg_prefix() { echo "${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-${1}"; }
mr_global_proxy_subnet_name() { echo "${MR_NETWORK_NAME}-$(mr_region "${1}")-gproxy"; }

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
  local key="${1}"
  mkdir -p "${MR_WORK_DIR}/kubeconfig"
  KUBECONFIG="$(mr_kubeconfig "${key}")" gcloud container clusters get-credentials \
    "$(mr_cluster_name "${key}")" \
    --dns-endpoint \
    --location "$(mr_region "${key}")" \
    --project "${MR_PROJECT_ID}" >/dev/null
}

# Wait until a command succeeds, or time out.
# mr_wait_for <timeout_s> <interval_s> <description> <command...>
mr_wait_for() {
  local timeout="${1}" interval="${2}" description="${3}"
  shift 3
  local deadline=$(($(date +%s) + timeout))
  until "$@" >/dev/null 2>&1; do
    if [[ $(date +%s) -ge ${deadline} ]]; then
      mr_log "timed out after ${timeout}s waiting for: ${description}"
      return 1
    fi
    sleep "${interval}"
  done
}

# mr_gateway_vip <gateway_name> <region_key>
# Prints the internal VIP of the multi-cluster Gateway in a region. The
# cross-region internal load balancer allocates one VIP per region listed in the
# Gateway addresses, from that region's subnet, so the VIP is matched to the
# region by subnet range.
mr_gateway_vip() {
  local gateway="${1}" key="${2}"
  if [[ "${MR_GLOBAL_LB}" != "mc-gateway" ]]; then
    # Terraform-managed load balancer: VIPs are recorded by deploy-global-lb.sh.
    jq -er --arg k "${key}" '.[$k] // empty' "${MR_RESULTS_DIR}/gateway/vips.json" 2>/dev/null
    return
  fi
  local addresses
  addresses="$(mr_kubectl "${MR_CONFIG_CLUSTER_KEY}" get gateway "${gateway}" -n "${MR_NAMESPACE}" \
    -o jsonpath='{range .status.addresses[*]}{.value}{"\n"}{end}' 2>/dev/null)" || return 1
  python3 - "${MR_NODE_CIDR[${key}]}" <<EOF
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
