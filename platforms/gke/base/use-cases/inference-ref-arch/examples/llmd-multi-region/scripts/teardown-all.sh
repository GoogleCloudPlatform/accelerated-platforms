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
#   1. multi-cluster Gateway resources (deletes the load balancer),
#   2. both experiment arms,
#   3. benchmark infrastructure and fleet features,
#   4. every regional platform (in parallel),
#   5. the shared VPC network.
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
# shellcheck source=/dev/null
source "${MY_PATH}/tf.sh"

MR_TEARDOWN_FLEET_FEATURES="${MR_TEARDOWN_FLEET_FEATURES:-true}"
cfg="${MR_CONFIG_CLUSTER_KEY}"
gateway="${MR_GATEWAY_NAME:-llm-mr-gateway}"

# Discover all deployed region keys by combining MR_REGION_KEYS with any
# existing local worktrees and labeled GKE clusters for this environment, so
# temporarily narrowed MR_REGION_KEYS values don't strand clusters on teardown.
discover_region_keys() {
  local seen=" " k d cname prefix
  local result=()
  for k in ${MR_REGION_KEYS}; do
    if [[ -n "${MR_REGION[${k}]:-}" && "${seen}" != *" ${k} "* ]]; then
      seen+="${k} "
      result+=("${k}")
    fi
  done
  if [[ -d "${MR_WORK_DIR}/worktrees" ]]; then
    for d in "${MR_WORK_DIR}/worktrees/${MR_ENVIRONMENT_NAME}"*; do
      [[ -d "${d}" ]] || continue
      k="${d##*/"${MR_ENVIRONMENT_NAME}"}"
      if [[ -n "${MR_REGION[${k}]:-}" && "${seen}" != *" ${k} "* ]]; then
        seen+="${k} "
        result+=("${k}")
      fi
    done
  fi
  prefix="${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}"
  while IFS= read -r cname; do
    [[ -n "${cname}" && "${cname}" == "${prefix}"* ]] || continue
    k="${cname#"${prefix}"}"
    if [[ -n "${MR_REGION[${k}]:-}" && "${seen}" != *" ${k} "* ]]; then
      seen+="${k} "
      result+=("${k}")
    fi
  done < <(gcloud container clusters list --project "${MR_PROJECT_ID}" \
    --filter="resourceLabels.acp_environment=${prefix}" --format='value(name)' 2>/dev/null || true)
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

global_lb_state_has_resources() {
  local n
  n="$(gcloud storage cat "gs://$(mr_shared_state_bucket)/terraform/llmd-multi-region/global_lb/default.tfstate" 2>/dev/null |
    jq '.resources | length' 2>/dev/null)" || return 1
  [[ "${n:-0}" -gt 0 ]]
}

destroy_global_lb() {
  local tfvars="${MR_WORK_DIR}/terraform/global_lb.tfvars.json"
  if [[ ! -f "${tfvars}" ]]; then
    global_lb_state_has_resources || return 0
    mkdir -p "$(dirname "${tfvars}")"
    jq -n \
      --arg project_id "${MR_PROJECT_ID}" \
      --arg name "${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-llm" \
      --arg network "projects/${MR_PROJECT_ID}/global/networks/${MR_NETWORK_NAME}" \
      '{
        project_id: $project_id,
        name: $name,
        network: $network,
        regions: {},
        backends: {baseline: {health_check_path: "/health", health_check_port: 8000, negs: []}},
        active_backend: "baseline"
      }' >"${tfvars}"
  fi
  mr_tf global_lb destroy "${tfvars}" || return 1
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
  # Pod snapshots (if enabled): delete them through GKE, which removes their
  # objects, before Terraform destroys the snapshot bucket.
  for key in ${MR_REGION_KEYS}; do
    [[ -f "$(mr_kubeconfig "${key}")" ]] || continue
    if mr_kubectl "${key}" get crd podsnapshots.podsnapshot.gke.io >/dev/null 2>&1; then
      mr_kubectl "${key}" delete podsnapshotpolicies,podsnapshots --all -n "${MR_NAMESPACE}" --ignore-not-found --wait=true || true
      mr_kubectl "${key}" delete podsnapshotstorageconfigs --all --ignore-not-found || true
    fi
  done
  MR_REGION_KEYS="${live}" "${MY_PATH}/delete-arm.sh" baseline || true
}

# GKE deletes the standalone and multi-cluster Service NEGs only while the
# clusters run; NEGs that are left behind block the VPC deletion.
vpc_negs_deleted() {
  [[ -z "$(gcloud compute network-endpoint-groups list --project "${MR_PROJECT_ID}" \
    --filter="network~/${MR_NETWORK_NAME}\$" --format='value(name)' 2>/dev/null)" ]]
}

destroy_bench() {
  if [[ -d "${MR_EXAMPLE_DIR}/terraform/bench" ]] && declare -F mr_write_bench_tfvars >/dev/null; then
    mr_tf bench destroy "$(mr_write_bench_tfvars)"
  fi
}

destroy_fleet() {
  [[ "${MR_TEARDOWN_FLEET_FEATURES}" == "true" ]] || return 0
  mr_tf fleet destroy "$(mr_write_fleet_tfvars)"
}

teardown_region() {
  local key="${1}" wt
  wt="$(mr_worktree_dir "${key}")"
  if [[ ! -d "${wt}" ]]; then
    if gcloud container clusters describe "$(mr_cluster_name "${key}")" --location "$(mr_region "${key}")" \
      --project "${MR_PROJECT_ID}" >/dev/null 2>&1; then
      mr_log "ERROR: cluster $(mr_cluster_name "${key}") exists but its worktree ${wt} doesn't;" \
        "recreate the worktree (scripts/deploy-region.sh ${key}) or delete the cluster, then re-run teardown-all.sh"
      return 1
    fi
    mr_log "No worktree or cluster for ${key}, skipping"
    return 0
  fi
  (
    cd "${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu" || exit 1
    export TF_PLUGIN_CACHE_DIR="${wt}/.terraform.d/plugin-cache"
    if [[ -f backend.tf ]]; then
      rm -rf .terraform/
      terraform init -input=false || exit 1
      terraform destroy -input=false -auto-approve || exit 1
    fi
  ) || return 1
  (
    KUBECONFIG="$(mr_kubeconfig "${key}")"
    export KUBECONFIG
    "${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-standard.sh"
  ) || return 1
  mkdir -p "${MR_WORK_DIR}/locks"
  (
    flock -x 9 || exit 1
    git -C "${ACP_REPO_DIR}" worktree remove --force "${wt}"
    git -C "${ACP_REPO_DIR}" worktree prune
  ) 9>"${MR_WORK_DIR}/locks/git-worktree.lock" || return 1
  rm -f "$(mr_kubeconfig "${key}")"
}

destroy_network() {
  mr_tf shared_network destroy "$(mr_write_shared_network_tfvars)"
}

if [[ -f "${MY_PATH}/bench-lib.sh" ]]; then
  # shellcheck source=/dev/null
  source "${MY_PATH}/bench-lib.sh"
fi

ensure_kubeconfigs

# Optional external front door (deploy-front-door.sh), only if it was deployed.
# It's removed first, because it forwards to the internal Gateway. A failure
# doesn't block the rest of the teardown (GPUs keep costing money), but the
# leftover external load balancer must be removed by re-running
# `deploy-front-door.sh destroy`.
if "${MY_PATH}/deploy-front-door.sh" exists; then
  mr_stage "teardown_front_door" "global" "${MY_PATH}/deploy-front-door.sh" destroy ||
    mr_log "WARNING: front door teardown failed; re-run scripts/deploy-front-door.sh destroy"
fi

mr_stage "teardown_global_lb" "global" destroy_global_lb
mr_stage "teardown_gateway" "global" delete_gateway
mr_stage "teardown_arms" "global" delete_arms
mr_stage "teardown_negs" "global" mr_wait_for 600 15 "NEGs in ${MR_NETWORK_NAME} deleted" vpc_negs_deleted ||
  mr_log "WARNING: NEGs are left in ${MR_NETWORK_NAME}; the VPC can't be deleted until they're gone (gcloud compute network-endpoint-groups list)"
mr_stage "teardown_bench" "global" destroy_bench || true
mr_stage "teardown_fleet" "global" destroy_fleet

pids=()
for key in ${MR_REGION_KEYS}; do
  (mr_stage "teardown_region" "region/${key}" teardown_region "${key}" >"${MR_WORK_DIR}/teardown-${key}.log" 2>&1) &
  pids+=($!)
done
rc=0
for pid in "${pids[@]}"; do wait "${pid}" || rc=1; done
[[ ${rc} -eq 0 ]] || mr_die "a regional teardown failed; see ${MR_WORK_DIR}/teardown-*.log"

mr_stage "teardown_shared_network" "global" destroy_network
mr_log "Teardown complete. Shared Terraform state bucket gs://$(mr_shared_state_bucket) is kept; delete it manually if no longer needed."
