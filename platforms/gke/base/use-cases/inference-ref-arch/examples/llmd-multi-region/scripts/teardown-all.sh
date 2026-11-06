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

# Tears down the whole multi-region environment, in reverse order:
#   1. cross-region load balancer (global_lb.sh destroy, and optional
#      multi-cluster Gateway resources),
#   2. both experiment arms,
#   3. benchmark infrastructure and optional fleet features,
#   4. every regional platform (in parallel) and the shared VPC network via
#      terraform/multi-region/teardown.sh --parallel.
#
# Usage: teardown-all.sh [--dry-run]
#
# Set MR_TEARDOWN_FLEET_FEATURES=false to keep the fleet features enabled (for
# example, when other multi-cluster Gateways in the project still use them).

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

dry_run="false"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --dry-run) dry_run="true" && shift ;;
  -h | --help)
    echo "Usage: $(basename "$0") [--dry-run]"
    exit 0
    ;;
  *) mr_die "unknown argument: ${1} (usage: $(basename "$0") [--dry-run])" ;;
  esac
done

if [[ "${dry_run}" == "true" ]]; then
  targets=()
  for key in ${MR_REGION_KEYS}; do
    mr_validate_region_key "${key}"
    targets+=("$(mr_target_spec "${key}")")
  done
  exec "${MR_MULTI_REGION_DIR}/teardown.sh" --parallel --dry-run "${targets[@]}"
fi

MR_TEARDOWN_FLEET_FEATURES="${MR_TEARDOWN_FLEET_FEATURES:-true}"
cfg="${MR_CONFIG_CLUSTER_KEY}"
gateway="${MR_GATEWAY_NAME:-llm-mr-gateway}"

# Discover all deployed region keys by combining MR_REGION_KEYS with platforms
# registered in shared_network, existing local worktrees, and labeled GKE
# clusters for this environment, so temporarily narrowed MR_REGION_KEYS values
# don't strand clusters on teardown.
discover_region_keys() {
  local seen=" " k d cname env_label cluster_prefix
  local result=()
  add_key() {
    local candidate="${1}"
    if [[ -n "${MR_REGION[${candidate}]:-}" && -n "${MR_CIDR_INDEX[${candidate}]:-}" && "${seen}" != *" ${candidate} "* ]]; then
      seen+="${candidate} "
      result+=("${candidate}")
    fi
  }
  for k in ${MR_REGION_KEYS}; do
    add_key "${k}"
  done
  while IFS= read -r k; do
    [[ -n "${k}" ]] && add_key "${k}"
  done < <(mr_registry_json 2>/dev/null | jq -r 'keys[]' 2>/dev/null || true)
  if [[ -d "${MR_WORK_DIR}/worktrees" ]]; then
    for d in "${MR_WORK_DIR}/worktrees/"*; do
      [[ -d "${d}" ]] || continue
      add_key "${d##*/}"
    done
  fi
  env_label="${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}"
  cluster_prefix="${MR_RESOURCE_NAME_PREFIX}-"
  while IFS= read -r cname; do
    [[ -n "${cname}" && "${cname}" == "${cluster_prefix}"* ]] || continue
    add_key "${cname#"${cluster_prefix}"}"
  done < <(gcloud container clusters list --project "${MR_PROJECT_ID}" \
    --filter="resourceLabels.acp_environment=${env_label}" --format='value(name)' 2>/dev/null || true)
  echo "${result[*]}"
}

ALL_REGION_KEYS="$(discover_region_keys)"
[[ -n "${ALL_REGION_KEYS}" ]] && export MR_REGION_KEYS="${ALL_REGION_KEYS}"

ensure_kubeconfigs() {
  local key
  for key in ${MR_REGION_KEYS} "${cfg}"; do
    [[ -n "${MR_REGION[${key}]:-}" ]] || continue
    [[ -f "$(mr_kubeconfig "${key}")" ]] || mr_get_credentials "${key}" 2>/dev/null || true
  done
}

mc_gateway_lb_deleted() {
  [[ -z "$(gcloud compute forwarding-rules list --global --project "${MR_PROJECT_ID}" \
    --format='value(name)' --filter="name~^gkemcg AND network~/${MR_NETWORK_NAME}\$" 2>/dev/null)" ]] || return 1
  # Backend services aren't tied to a network: match this environment's
  # namespace (names are gkemcg<version>-<namespace>-<service>-<port>-<hash>).
  [[ -z "$(gcloud compute backend-services list --global --project "${MR_PROJECT_ID}" \
    --format='value(name)' --filter="name~^gkemcg[0-9]*-${MR_NAMESPACE}-" 2>/dev/null)" ]] || return 1
  [[ -z "$(gcloud compute firewall-rules list --project "${MR_PROJECT_ID}" \
    --format='value(name)' --filter="name~^gkemcg AND network~/${MR_NETWORK_NAME}\$" 2>/dev/null)" ]]
}

delete_gateway() {
  [[ -f "$(mr_kubeconfig "${cfg}")" ]] || return 0
  mr_kubectl "${cfg}" delete httproute "${gateway}" -n "${MR_NAMESPACE}" --ignore-not-found --wait=true || true
  mr_kubectl "${cfg}" delete gcpbackendpolicy,healthcheckpolicy -n "${MR_NAMESPACE}" --all --ignore-not-found --wait=true || true
  mr_kubectl "${cfg}" delete gateway "${gateway}" -n "${MR_NAMESPACE}" --ignore-not-found --wait=true || true
  # Give the multi-cluster Gateway controller time to delete the load balancer,
  # backend services, and firewall rules before the fleet feature is disabled,
  # otherwise those resources leak and block VPC deletion.
  mr_wait_for 900 15 "multi-cluster Gateway resources deleted" mc_gateway_lb_deleted
}

destroy_global_lb() {
  "${MR_MULTI_REGION_DIR}/global_lb.sh" destroy || return 1
  rm -f "${MR_RESULTS_DIR}/gateway/active.json" "${MR_RESULTS_DIR}/gateway/vips.json" \
    "${MR_WORK_DIR}/terraform/global_lb.state.json" "${MR_WORK_DIR}/terraform/global_lb.vips.json"
}

# Region keys whose cluster credentials are available (delete-arm.sh needs them).
live_region_keys() {
  local key
  for key in ${MR_REGION_KEYS}; do
    if [[ -f "$(mr_kubeconfig "${key}")" ]]; then
      printf '%s ' "${key}"
    fi
  done
}

delete_arms() {
  local key live
  live="$(live_region_keys)"
  for key in ${live}; do
    mr_kubectl "${key}" delete serviceexport --all -n "${MR_NAMESPACE}" --ignore-not-found || true
  done
  [[ -n "${live}" ]] || return 0
  MR_REGION_KEYS="${live}" "${MY_PATH}/delete-arm.sh" llmd || true
  MR_REGION_KEYS="${live}" "${MY_PATH}/delete-arm.sh" baseline || true
}

destroy_bench() {
  mr_tf_state_has_resources bench "terraform/llmd-multi-region/bench" || return 0
  if [[ -d "${MR_EXAMPLE_DIR}/terraform/bench" ]] && declare -F mr_write_bench_tfvars >/dev/null; then
    mr_write_bench_tfvars >/dev/null
    mr_tf bench destroy "${MR_EXAMPLE_DIR}/terraform/bench" "terraform/llmd-multi-region/bench"
  fi
}

destroy_fleet() {
  [[ "${MR_TEARDOWN_FLEET_FEATURES}" == "true" ]] || return 0
  mr_tf_state_has_resources fleet "terraform/llmd-multi-region/fleet" || return 0
  local stage
  stage="$(mr_tf_dir fleet)"
  mkdir -p "${stage}"
  jq -n \
    --arg project_id "${MR_PROJECT_ID}" \
    --arg config_membership_id "$(mr_cluster_name "${cfg}")" \
    '{project_id: $project_id, config_membership_id: $config_membership_id}' >"${stage}/terraform.tfvars.json"
  mr_tf fleet destroy "${MR_EXAMPLE_DIR}/terraform/fleet" "terraform/llmd-multi-region/fleet"
}

if [[ -f "${MY_PATH}/bench-lib.sh" ]]; then
  # shellcheck source=/dev/null
  source "${MY_PATH}/bench-lib.sh"
fi

ensure_kubeconfigs

mr_stage "teardown_global_lb" "global" destroy_global_lb
if [[ "${MR_GLOBAL_LB}" == "mc-gateway" ]] || mr_tf_state_has_resources fleet "terraform/llmd-multi-region/fleet"; then
  mr_stage "teardown_gateway" "global" delete_gateway
fi
mr_stage "teardown_arms" "global" delete_arms
mr_stage "teardown_bench" "global" destroy_bench || true
mr_stage "teardown_fleet" "global" destroy_fleet

targets=()
for key in ${MR_REGION_KEYS}; do
  mr_validate_region_key "${key}"
  targets+=("$(mr_target_spec "${key}")")
done
if ((${#targets[@]} > 0)); then
  mr_stage "teardown_foundation" "global" "${MR_MULTI_REGION_DIR}/teardown.sh" --parallel "${targets[@]}"
fi
mr_log "Teardown complete. Shared Terraform state bucket gs://$(mr_state_bucket) is kept; delete it manually if no longer needed."
