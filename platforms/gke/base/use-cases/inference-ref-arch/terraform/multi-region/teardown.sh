#!/usr/bin/env bash
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Tears down regional inference-ref-arch platforms created by provision.sh,
# reusing ACP's core/initialize backend generation and failing fast on IAM,
# authentication, or Terraform errors. With NETWORK_MODE=shared-vpc, it also
# destroys the global load balancer (when every platform is torn down), and
# removes the platforms from the shared network, which it destroys with the
# last platform.
#
# Usage:
#   teardown.sh [--parallel] [--dry-run] [<platform_name>:<region>[:<cidr_index>] ...]
#
# Use the targets, NETWORK_MODE, CLUSTER_MODE, TF_VAR_resource_name_prefix, and
# MR_ENVIRONMENT_NAME values that provisioned the platforms. Targets default to
# "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1".
#
#   --parallel  Tear down every region at the same time, each from its own Git
#               worktree, and remove the worktrees that were torn down.
#   --dry-run   Print the plan and exit without calling Google Cloud.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# shellcheck source=platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
source "${MY_PATH}/helpers.sh"

usage="Usage: teardown.sh [--parallel] [--dry-run] [<platform_name>:<region>[:<cidr_index>] ...]"
parallel="false"
dry_run="false"
targets=()
while (($# > 0)); do
  case "${1}" in
  --parallel) parallel="true" ;;
  --dry-run) dry_run="true" ;;
  -h | --help)
    echo "${usage}"
    exit 0
    ;;
  -*) mr_die "unknown option '${1}'. ${usage}" ;;
  *) targets+=("${1}") ;;
  esac
  shift
done
if ((${#targets[@]} == 0)); then
  targets=("americas:us-central1" "europe:europe-west2" "apac:asia-southeast1")
fi

mr_init || exit 1
mr_parse_targets "${targets[@]}"

region_checkout() {
  if [[ "${parallel}" == "true" ]]; then
    mr_worktree_dir "${1}"
  else
    echo "${ACP_REPO_DIR}"
  fi
}

export_teardown_env() {
  use_region "${1}" "${2}" "${3}" || exit 1
  # core/initialize generates the backend.tf files of the use case's
  # terraservices, such as online_gpu.
  export TF_VAR_initialize_backend_use_case_name="inference-ref-arch/terraform"
  # Keep the files that other platforms deployed from this checkout still use.
  export ACP_TEARDOWN_RESET_CHECKOUT="false"
}

print_plan() {
  local i platform
  echo "Multi-region teardown plan (dry run, nothing is deleted)"
  echo "  project=${PROJECT_ID} prefix=${TF_VAR_resource_name_prefix} NETWORK_MODE=${NETWORK_MODE} CLUSTER_MODE=${CLUSTER_MODE} parallel=${parallel}"
  if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
    echo "  first: destroy global_lb (only if these targets are the last registered platforms)"
    echo "  last:  remove the targets from the shared network $(mr_shared_network_name); destroy it with the last platform"
  fi
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    platform="${MR_TARGET_PLATFORMS[i]}"
    echo
    echo "[${platform}] region=${MR_TARGET_REGIONS[i]} cidr_index=${MR_TARGET_INDEXES[i]} cluster=$(mr_cluster_name "${platform}")"
    echo "  checkout: $(region_checkout "${platform}")"
    echo "  steps:    delete Pod snapshot resources and standalone NEGs, empty the model and Pod snapshot buckets, core/initialize apply, terraform/online_gpu destroy, terraform/teardown-$(mr_deploy_suffix).sh"
    (
      export_teardown_env "${platform}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}"
      mr_print_region_env
      echo "  ACP_TEARDOWN_RESET_CHECKOUT=${ACP_TEARDOWN_RESET_CHECKOUT}"
    )
  done
}

empty_bucket_if_exists() {
  local bucket="${1}" entries
  if ! mr_bucket_exists "${bucket}"; then
    return 0
  fi
  entries="$(gcloud storage ls "gs://${bucket}/")"
  if [[ -n "${entries}" ]]; then
    mr_log "Emptying gs://${bucket}"
    gcloud storage rm --recursive "gs://${bucket}/**"
  fi
}

# Deleting the Pod snapshot resources through GKE removes their objects before
# Terraform destroys the snapshot bucket. Best effort: the bucket is emptied
# next in any case.
delete_pod_snapshot_resources() {
  local kubeconfig="${1}"
  if ! kubectl --kubeconfig "${kubeconfig}" get crd podsnapshots.podsnapshot.gke.io >/dev/null 2>&1; then
    return 0
  fi
  if ! kubectl --kubeconfig "${kubeconfig}" delete podsnapshotpolicies,podsnapshots --all --all-namespaces \
    --ignore-not-found --wait=true --timeout=600s ||
    ! kubectl --kubeconfig "${kubeconfig}" delete podsnapshotstorageconfigs --all --ignore-not-found --timeout=600s; then
    mr_log "WARNING: deleting the Pod snapshot resources failed; their objects are deleted with the bucket contents."
  fi
}

# Succeeds when none of the NEGs (names in the JSON array) exists in a region.
negs_deleted() {
  local names="${1}" region="${2}" negs
  negs="$(gcloud compute network-endpoint-groups list --project="${PROJECT_ID}" --format=json)" || return 1
  jq -e --argjson names "${names}" --arg region "${region}" \
    '[.[] | select((.name as $name | $names | index($name)) and (.zone | test("/zones/" + $region + "-[a-z]$")))] | length == 0' \
    <<<"${negs}" >/dev/null
}

# GKE doesn't delete standalone NEGs (expose_service_neg) with their cluster,
# and core/networking doesn't clean them up in a network that it doesn't own
# (NETWORK_MODE=shared-vpc), where they would block the deletion of the
# regional subnet. Removing the NEG annotation of the Services makes the NEG
# controller delete the NEGs while the cluster still runs; the global load
# balancer, which would keep them in use, is already gone.
delete_standalone_negs() {
  local kubeconfig="${1}" region="${2}" services names service
  services="$(kubectl --kubeconfig "${kubeconfig}" get services --all-namespaces -o json |
    jq -c '[.items[] | select((.metadata.annotations["cloud.google.com/neg"] // "") | contains("exposed_ports"))]')"
  names="$(jq -c '[.[].metadata.annotations["cloud.google.com/neg-status"] // empty
    | fromjson | (.network_endpoint_groups // {})[]] | unique' <<<"${services}")"
  while IFS= read -r service; do
    kubectl --kubeconfig "${kubeconfig}" annotate service "${service#*/}" --namespace "${service%%/*}" cloud.google.com/neg-
  done < <(jq -r '.[] | "\(.metadata.namespace)/\(.metadata.name)"' <<<"${services}")
  if [[ "${names}" != "[]" ]]; then
    mr_log "Waiting for GKE to delete the standalone NEGs ${names}"
    mr_wait_for 900 15 "deletion of the standalone NEGs ${names}" negs_deleted "${names}" "${region}" ||
      mr_die "the standalone NEGs ${names} still exist in ${region}. Detach them from any backend service (for example with 'global_lb.sh destroy') and re-run."
  fi
}

# teardown_region <checkout> <platform_name> <region> <cidr_index>
teardown_region() {
  local checkout="${1}" platform="${2}" region="${3}" index="${4}"
  local core_dir="${checkout}/platforms/gke/base/core"
  local terraform_dir="${checkout}/platforms/gke/base/use-cases/inference-ref-arch/terraform"
  local cluster state_bucket clusters checkout_kubeconfig pod_snapshots_bucket
  export_teardown_env "${platform}" "${region}" "${index}"
  cluster="$(mr_cluster_name "${platform}")"
  state_bucket="${PROJECT_ID}-${cluster}-terraform"

  if ! mr_bucket_exists "${state_bucket}"; then
    mr_log "[${platform}] State bucket gs://${state_bucket} doesn't exist; '${cluster}' is already torn down."
    rm -f "${KUBECONFIG}"
    return 0
  fi

  # The terraservices of this checkout read the kubeconfig that core generates
  # in it; refresh it, because the checkout might not be the one that
  # provisioned the platform (for example, a new worktree).
  checkout_kubeconfig="${checkout}/platforms/gke/base/kubernetes/kubeconfig/${PROJECT_ID}-${cluster}"
  clusters="$(gcloud container clusters list --project="${PROJECT_ID}" --filter="name=${cluster} AND location=${region}" --format="value(name)")"
  if [[ -n "${clusters}" ]]; then
    mkdir -p "$(dirname "${checkout_kubeconfig}")"
    KUBECONFIG="${checkout_kubeconfig}" gcloud container clusters get-credentials "${cluster}" \
      --dns-endpoint \
      --location="${region}" \
      --project="${PROJECT_ID}"
    delete_pod_snapshot_resources "${checkout_kubeconfig}"
    delete_standalone_negs "${checkout_kubeconfig}" "${region}"
  fi

  pod_snapshots_bucket="${PROJECT_ID}-${cluster}-pod-snapshots"
  if mr_bucket_exists "${pod_snapshots_bucket}"; then
    export TF_VAR_ira_online_gpu_pod_snapshots_enabled="true"
  else
    export TF_VAR_ira_online_gpu_pod_snapshots_enabled="false"
  fi
  empty_bucket_if_exists "${PROJECT_ID}-${cluster}-hf-hub-models"
  empty_bucket_if_exists "${pod_snapshots_bucket}"

  # Run core/initialize first, so that it generates the backend.tf files of
  # this platform (pointing at its state bucket) in the checkout.
  mr_log "[${platform}] Applying core/initialize against gs://${state_bucket}"
  (
    cd "${core_dir}/initialize" || exit 1
    cp backend.tf.bucket backend.tf || exit 1
    TF_PLUGIN_CACHE_DIR="${checkout}/.terraform.d/plugin-cache" terraform init -input=false -reconfigure \
      -backend-config="bucket=${state_bucket}" || exit 1
    terraform plan -input=false -out=tfplan || exit 1
    terraform apply -input=false tfplan || exit 1
    rm -f tfplan
  ) || mr_die "[${platform}] core/initialize failed."

  mr_log "[${platform}] Destroying terraform/online_gpu"
  mr_terraform_destroy "${terraform_dir}/online_gpu" "${checkout}" || mr_die "[${platform}] destroying terraform/online_gpu failed."

  "${terraform_dir}/teardown-$(mr_deploy_suffix).sh"
  rm -f "${KUBECONFIG}"
  mr_log "[${platform}] Torn down"
}

teardown_sequential() {
  local i restore_backend_template="false"
  local backend_template="${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket"
  if git -C "${ACP_REPO_DIR}" diff --quiet -- "${backend_template}"; then
    restore_backend_template="true"
  fi
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    echo "=================================================================="
    echo "[${MR_TARGET_INDEXES[i]}] Tearing down '$(mr_cluster_name "${MR_TARGET_PLATFORMS[i]}")' in ${MR_TARGET_REGIONS[i]}"
    echo "=================================================================="
    # An asynchronous subshell keeps errexit in effect (see provision.sh).
    (teardown_region "${ACP_REPO_DIR}" "${MR_TARGET_PLATFORMS[i]}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}") &
    wait "$!" || mr_die "tearing down '$(mr_cluster_name "${MR_TARGET_PLATFORMS[i]}")' failed; fix the error above and re-run."
    # A worktree left by a parallel run is stale now.
    mr_remove_worktree "${MR_TARGET_PLATFORMS[i]}"
  done
  if [[ "${restore_backend_template}" == "true" ]]; then
    git -C "${ACP_REPO_DIR}" checkout -- "${backend_template}"
  fi
}

teardown_parallel() {
  local logs i platform pids=() failed=()
  logs="${MR_WORK_DIR}/logs/teardown-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "${logs}"
  git -C "${ACP_REPO_DIR}" diff HEAD --binary >"${logs}/uncommitted.diff"
  git -C "${ACP_REPO_DIR}" worktree prune
  for platform in "${MR_TARGET_PLATFORMS[@]}"; do
    mr_sync_worktree "${platform}" "${logs}/uncommitted.diff"
    mr_require_clean_tfvars "$(mr_worktree_dir "${platform}")"
  done
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    platform="${MR_TARGET_PLATFORMS[i]}"
    (teardown_region "$(mr_worktree_dir "${platform}")" "${platform}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}") \
      >"${logs}/${platform}.log" 2>&1 &
    pids+=("$!")
    mr_log "[${platform}] Tearing down; log: ${logs}/${platform}.log"
  done
  for i in "${!pids[@]}"; do
    platform="${MR_TARGET_PLATFORMS[i]}"
    if wait "${pids[i]}"; then
      mr_remove_worktree "${platform}"
      mr_log "[${platform}] Done; removed its worktree"
    else
      failed+=("${platform}")
      mr_log "[${platform}] FAILED; log: ${logs}/${platform}.log"
    fi
  done
  ((${#failed[@]} == 0)) ||
    mr_die "teardown failed for: ${failed[*]}. Fix the cause (see ${logs}/<platform_name>.log) and re-run with the same targets."
}

# Prints the shared_network registry without the targets.
remaining_registry_json() {
  jq -c --args 'reduce $ARGS.positional[] as $platform (.; del(.[$platform]))' "${MR_TARGET_PLATFORMS[@]}" <<<"${1}"
}

if [[ "${dry_run}" == "true" ]]; then
  print_plan
  exit 0
fi

mr_require_tools gcloud git jq kubectl terraform
gcloud projects describe "${PROJECT_ID}" --format="value(projectId)" >/dev/null
for i in "${!MR_TARGET_PLATFORMS[@]}"; do
  mr_check_existing_platform "${MR_TARGET_PLATFORMS[i]}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}"
done

registry="{}"
remaining="{}"
if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
  registry="$(mr_registry_json)"
  remaining="$(remaining_registry_json "${registry}")"
  if mr_tf_state_has_resources global_lb; then
    [[ "${remaining}" == "{}" ]] ||
      mr_die "the global load balancer also serves $(jq -r 'keys | join(" ")' <<<"${remaining}"). Run 'global_lb.sh destroy' first, tear down these platforms, then re-run 'global_lb.sh apply' for the remaining ones."
    "${MY_PATH}/global_lb.sh" destroy
  fi
fi

if [[ "${parallel}" == "true" ]]; then
  teardown_parallel
else
  teardown_sequential
fi

if [[ "${NETWORK_MODE}" == "shared-vpc" && "${registry}" != "{}" ]]; then
  tfvars="$(mr_tf_dir shared_network)/terraform.tfvars.json"
  mkdir -p "$(dirname "${tfvars}")"
  if [[ "${remaining}" == "{}" ]]; then
    regions="${registry}"
    action="destroy"
  else
    regions="${remaining}"
    action="apply"
  fi
  jq -n \
    --arg project_id "${PROJECT_ID}" \
    --arg network_name "$(mr_shared_network_name)" \
    --argjson regions "${regions}" \
    '{project_id: $project_id, network_name: $network_name, regions: $regions}' >"${tfvars}"
  mr_log "Shared network $(mr_shared_network_name): ${action}"
  mr_tf shared_network "${action}"
  if [[ "${action}" == "destroy" ]]; then
    mr_log "The multi-region Terraform state bucket gs://$(mr_state_bucket) is kept; delete it when you no longer need it."
  fi
fi

echo "All ${#MR_TARGET_PLATFORMS[@]} regional platforms are torn down."
