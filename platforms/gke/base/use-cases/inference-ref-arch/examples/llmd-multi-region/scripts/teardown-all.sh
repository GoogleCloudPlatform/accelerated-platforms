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

delete_gateway() {
  [[ -f "$(mr_kubeconfig "${cfg}")" ]] || return 0
  mr_kubectl "${cfg}" delete httproute "${gateway}" -n "${MR_NAMESPACE}" --ignore-not-found --wait=true || true
  mr_kubectl "${cfg}" delete gcpbackendpolicy,healthcheckpolicy -n "${MR_NAMESPACE}" --all --ignore-not-found --wait=true || true
  mr_kubectl "${cfg}" delete gateway "${gateway}" -n "${MR_NAMESPACE}" --ignore-not-found --wait=true || true
  # Give the multi-cluster Gateway controller time to delete the load balancer
  # before the fleet feature is disabled, otherwise the load balancer leaks.
  # (Multi-cluster Gateway forwarding rules are named gkemcg1-...)
  mr_wait_for 900 15 "multi-cluster Gateway forwarding rules deleted" bash -c \
    "! gcloud compute forwarding-rules list --global --project '${MR_PROJECT_ID}' --format='value(name)' --filter='name~^gkemcg AND network~${MR_NETWORK_NAME}' | grep -q ."
}

destroy_global_lb() {
  [[ -f "${MR_WORK_DIR}/terraform/global_lb.tfvars.json" ]] || return 0
  mr_tf global_lb destroy "${MR_WORK_DIR}/terraform/global_lb.tfvars.json" || return 1
  rm -f "${MR_RESULTS_DIR}/gateway/active.json" "${MR_RESULTS_DIR}/gateway/vips.json"
}

delete_arms() {
  local key
  for key in ${MR_REGION_KEYS}; do
    [[ -f "$(mr_kubeconfig "${key}")" ]] || continue
    mr_kubectl "${key}" delete serviceexport --all -n "${MR_NAMESPACE}" --ignore-not-found || true
  done
  "${MY_PATH}/delete-arm.sh" llmd || true
  # Pod snapshots (if enabled): delete them through GKE, which removes their
  # objects, before Terraform destroys the snapshot bucket.
  for key in ${MR_REGION_KEYS}; do
    [[ -f "$(mr_kubeconfig "${key}")" ]] || continue
    if mr_kubectl "${key}" get crd podsnapshots.podsnapshot.gke.io >/dev/null 2>&1; then
      mr_kubectl "${key}" delete podsnapshotpolicies,podsnapshots --all -n "${MR_NAMESPACE}" --ignore-not-found --wait=true || true
      mr_kubectl "${key}" delete podsnapshotstorageconfigs --all --ignore-not-found || true
    fi
  done
  "${MY_PATH}/delete-arm.sh" baseline || true
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
  [[ -d "${wt}" ]] || {
    mr_log "No worktree for ${key}, skipping"
    return 0
  }
  (
    cd "${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu"
    export TF_PLUGIN_CACHE_DIR="${wt}/.terraform.d/plugin-cache"
    if [[ -f backend.tf ]]; then
      rm -rf .terraform/
      terraform init -input=false
      terraform destroy -input=false -auto-approve
    fi
  )
  "${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-standard.sh"
  git -C "${ACP_REPO_DIR}" worktree remove --force "${wt}"
  rm -f "$(mr_kubeconfig "${key}")"
}

destroy_network() {
  mr_tf shared_network destroy "$(mr_write_shared_network_tfvars)"
}

if [[ -f "${MY_PATH}/bench-lib.sh" ]]; then
  # shellcheck source=/dev/null
  source "${MY_PATH}/bench-lib.sh"
fi

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
