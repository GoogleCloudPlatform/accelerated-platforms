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

# Provisions the regional GKE inference-ref-arch platforms of a multi-region
# environment without mutating tracked *.auto.tfvars or ~/.kube/config.
#
# Usage:
#   provision.sh [--parallel] [--dry-run] [<platform_name>:<region>[:<cidr_index>] ...]
#
# Targets default to "americas:us-central1" "europe:europe-west2"
# "apac:asia-southeast1". The CIDR index (0-11) selects the platform's network
# ranges and defaults to the target's position in the list; keep it stable for
# the life of the platform.
#
#   --parallel  Provision every region at the same time, each from its own Git
#               worktree under ${MR_WORK_DIR}/worktrees, with one log file per
#               region under ${MR_WORK_DIR}/logs.
#   --dry-run   Print the plan of every region (checkout, CIDRs, KUBECONFIG,
#               TF_VAR_* values) and exit without calling Google Cloud.
#
# Environment variables (see README.md):
#   PROJECT_ID (required), TF_VAR_resource_name_prefix, NETWORK_MODE,
#   CLUSTER_MODE, MR_ENVIRONMENT_NAME, MR_WORK_DIR, MR_CORE_PLATFORM_ATTEMPTS,
#   HF_TOKEN, ENABLE_POD_SNAPSHOTS, ACTIVE_MIGRATION_ENABLED, MIRROR_IMAGES

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# shellcheck source=platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
source "${MY_PATH}/helpers.sh"

usage="Usage: provision.sh [--parallel] [--dry-run] [<platform_name>:<region>[:<cidr_index>] ...]"
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

ENABLE_POD_SNAPSHOTS="${ENABLE_POD_SNAPSHOTS:-false}"
ACTIVE_MIGRATION_ENABLED="${ACTIVE_MIGRATION_ENABLED:-false}"
MR_CORE_PLATFORM_ATTEMPTS="${MR_CORE_PLATFORM_ATTEMPTS:-3}"
for setting in ENABLE_POD_SNAPSHOTS ACTIVE_MIGRATION_ENABLED; do
  [[ "${!setting}" == "true" || "${!setting}" == "false" ]] ||
    mr_die "${setting}='${!setting}' must be 'true' or 'false'."
done
[[ "${MR_CORE_PLATFORM_ATTEMPTS}" =~ ^[1-9][0-9]*$ ]] ||
  mr_die "MR_CORE_PLATFORM_ATTEMPTS='${MR_CORE_PLATFORM_ATTEMPTS}' must be a positive integer."

mirror_sources=()
mirror_destinations=()
if [[ -n "${MIRROR_IMAGES:-}" ]]; then
  read -r -a mirror_specs <<<"${MIRROR_IMAGES}"
  for spec in "${mirror_specs[@]}"; do
    src_img="${spec%%=*}"
    dst_subpath="${spec#*=}"
    if [[ -z "${src_img}" || -z "${dst_subpath}" || "${src_img}" == "${spec}" ]]; then
      mr_die "invalid MIRROR_IMAGES entry '${spec}'. Use '<src_image>=<dst_subpath:tag>'."
    fi
    mirror_sources+=("${src_img}")
    mirror_destinations+=("${dst_subpath}")
  done
fi

# Exports the environment of one regional platform: use_region plus the
# provisioning-only TF_VAR_* values.
export_provision_env() {
  use_region "${1}" "${2}" "${3}" || exit 1
  export TF_VAR_cluster_custom_compute_class_active_migration_enabled="${ACTIVE_MIGRATION_ENABLED}"
  export TF_VAR_ira_online_gpu_pod_snapshots_enabled="${ENABLE_POD_SNAPSHOTS}"
}

region_checkout() {
  if [[ "${parallel}" == "true" ]]; then
    mr_worktree_dir "${1}"
  else
    echo "${ACP_REPO_DIR}"
  fi
}

# Prints the shared_network registry entries of the targets.
targets_registry_json() {
  local i json='{}'
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    mr_set_cidrs_for_index "${MR_TARGET_INDEXES[i]}" || return 1
    json="$(jq -c \
      --arg platform "${MR_TARGET_PLATFORMS[i]}" \
      --arg region "${MR_TARGET_REGIONS[i]}" \
      --arg node "${MR_NODE_CIDR}" \
      --arg pod "${MR_POD_CIDR}" \
      --arg proxy "${MR_PROXY_CIDR}" \
      --arg global_proxy "${MR_GLOBAL_PROXY_CIDR}" \
      '. + {($platform): {region: $region, node_cidr: $node, pod_cidr: $pod, regional_proxy_cidr: $proxy, global_proxy_cidr: $global_proxy}}' \
      <<<"${json}")" || return 1
  done
  echo "${json}"
}

print_plan() {
  local i platform steps
  steps="terraform/deploy-$(mr_deploy_suffix).sh (up to ${MR_CORE_PLATFORM_ATTEMPTS} attempts), terraform/online_gpu apply"
  if [[ -n "${HF_TOKEN:-}" ]]; then
    steps+=", Hugging Face token secrets"
  fi
  if [[ "${ENABLE_POD_SNAPSHOTS}" == "true" ]]; then
    steps+=", GKE Pod snapshots"
  fi
  if ((${#mirror_sources[@]} > 0)); then
    steps+=", mirror ${mirror_sources[*]}"
  fi
  echo "Multi-region provisioning plan (dry run, nothing is created)"
  echo "  project=${PROJECT_ID} prefix=${TF_VAR_resource_name_prefix} NETWORK_MODE=${NETWORK_MODE} CLUSTER_MODE=${CLUSTER_MODE} parallel=${parallel}"
  echo "  MR_WORK_DIR=${MR_WORK_DIR}"
  if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
    echo "  shared network: $(mr_shared_network_name), Terraform state: gs://$(mr_state_bucket)/terraform/multi-region/shared_network"
    echo "  shared_network registry entries of these targets (merged with the platforms that are already registered):"
    targets_registry_json | jq . | sed 's/^/    /'
  fi
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    platform="${MR_TARGET_PLATFORMS[i]}"
    echo
    echo "[${platform}] region=${MR_TARGET_REGIONS[i]} cidr_index=${MR_TARGET_INDEXES[i]} cluster=$(mr_cluster_name "${platform}")"
    echo "  checkout: $(region_checkout "${platform}")"
    echo "  steps:    ${steps}"
    (
      export_provision_env "${platform}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}"
      if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
        echo "  GLOBAL_MANAGED_PROXY subnet (shared_network): ${MR_GLOBAL_PROXY_CIDR}"
      fi
      mr_print_region_env
    )
  done
}

apply_shared_network() {
  local registry targets_json conflicts merged duplicates tfvars
  registry="$(mr_registry_json)"
  targets_json="$(targets_registry_json)"
  conflicts="$(jq -rn --argjson registered "${registry}" --argjson new "${targets_json}" \
    '[$new | to_entries[] | select($registered[.key] != null and $registered[.key] != .value) | .key] | join(" ")')"
  [[ -z "${conflicts}" ]] ||
    mr_die "platform(s) ${conflicts} are registered in the shared network with another region or CIDR index. Pass the '<platform_name>:<region>:<cidr_index>' that provisioned them."
  merged="$(jq -cn --argjson registered "${registry}" --argjson new "${targets_json}" '$registered + $new')"
  duplicates="$(jq -r '[.[] | .region] | group_by(.) | map(select(length > 1) | .[0]) | join(" ")' <<<"${merged}")"
  [[ -z "${duplicates}" ]] ||
    mr_die "the shared network would have more than one platform in ${duplicates}. NETWORK_MODE=shared-vpc supports one platform per region."
  duplicates="$(jq -r '[.[] | .node_cidr] | group_by(.) | map(select(length > 1) | .[0]) | join(" ")' <<<"${merged}")"
  [[ -z "${duplicates}" ]] ||
    mr_die "more than one platform would use the node range ${duplicates}. Give each platform its own CIDR index."

  tfvars="$(mr_tf_dir shared_network)/terraform.tfvars.json"
  mkdir -p "$(dirname "${tfvars}")"
  jq -n \
    --arg project_id "${PROJECT_ID}" \
    --arg network_name "$(mr_shared_network_name)" \
    --argjson regions "${merged}" \
    '{project_id: $project_id, network_name: $network_name, regions: $regions}' >"${tfvars}"
  mr_log "Applying the shared network $(mr_shared_network_name) for platforms: $(jq -r 'keys | join(" ")' <<<"${merged}")"
  mr_tf shared_network apply
}

# Retries the core platform deployment: right after a cluster is created,
# transient failures are common (for example, fleet registration waits a short
# time for running cluster operations), and the core scripts are idempotent.
deploy_platform() {
  local script="${1}" attempt
  for ((attempt = 1; attempt <= MR_CORE_PLATFORM_ATTEMPTS; attempt++)); do
    if "${script}"; then
      return 0
    fi
    mr_log "[${TF_VAR_platform_name}] ${script##*/} attempt ${attempt}/${MR_CORE_PLATFORM_ATTEMPTS} failed"
    if ((attempt < MR_CORE_PLATFORM_ATTEMPTS)); then
      sleep 60
    fi
  done
  mr_die "[${TF_VAR_platform_name}] ${script} failed ${MR_CORE_PLATFORM_ATTEMPTS} time(s); fix the error above and re-run (completed steps are idempotent)."
}

add_hf_token() {
  local platform="${1}" suffix
  for suffix in huggingface-hub-access-token-read huggingface-hub-access-token-write; do
    printf '%s' "${HF_TOKEN}" | gcloud secrets versions add "$(mr_cluster_name "${platform}")-${suffix}" \
      --project="${PROJECT_ID}" \
      --data-file=- >/dev/null
  done
}

cluster_running() {
  [[ "$(gcloud container clusters describe "${1}" --location="${2}" --project="${PROJECT_ID}" --format='value(status)')" == "RUNNING" ]]
}

# The online_gpu terraservice creates the snapshot bucket and its IAM grants;
# the cluster feature is enabled with gcloud.
enable_pod_snapshots() {
  local platform="${1}" region="${2}" cluster enabled
  cluster="$(mr_cluster_name "${platform}")"
  enabled="$(gcloud --quiet beta container clusters describe "${cluster}" --location="${region}" --project="${PROJECT_ID}" \
    --format='value(addonsConfig.podSnapshotConfig.enabled)')"
  if [[ "${enabled}" != "True" ]]; then
    # A cluster runs one operation at a time.
    mr_wait_for 1800 20 "cluster ${cluster} RUNNING" cluster_running "${cluster}" "${region}" ||
      mr_die "[${platform}] cluster ${cluster} didn't return to RUNNING; check its operations and re-run."
    gcloud --quiet beta container clusters update "${cluster}" \
      --enable-pod-snapshots \
      --location="${region}" \
      --project="${PROJECT_ID}"
  fi
  mr_wait_for 600 15 "Pod snapshot CRDs in ${cluster}" kubectl --kubeconfig "$(mr_kubeconfig "${platform}")" get crd \
    podsnapshots.podsnapshot.gke.io podsnapshotpolicies.podsnapshot.gke.io podsnapshotstorageconfigs.podsnapshot.gke.io ||
    mr_die "[${platform}] the GKE Pod snapshot CRDs didn't appear in ${cluster}."
}

mirror_images() {
  local platform="${1}" region="${2}" i pids=() failed=0
  for i in "${!mirror_sources[@]}"; do
    mirror_image_to_ar "${region}" "${platform}" "${mirror_sources[i]}" "${mirror_destinations[i]}" &
    pids+=("$!")
  done
  for i in "${!pids[@]}"; do
    wait "${pids[i]}" || failed=1
  done
  ((failed == 0)) || mr_die "[${platform}] mirroring ${mirror_sources[*]} failed; see the output above."
}

# provision_region <checkout> <platform_name> <region> <cidr_index>
provision_region() {
  local checkout="${1}" platform="${2}" region="${3}" index="${4}"
  local terraform_dir="${checkout}/platforms/gke/base/use-cases/inference-ref-arch/terraform"
  export_provision_env "${platform}" "${region}" "${index}"
  mkdir -p "$(dirname "${KUBECONFIG}")"

  mr_log "[${platform}] Deploying the ${CLUSTER_MODE} platform $(mr_cluster_name "${platform}") in ${region} from ${checkout}"
  deploy_platform "${terraform_dir}/deploy-$(mr_deploy_suffix).sh"
  mr_log "[${platform}] Applying terraform/online_gpu"
  mr_terraform_apply "${terraform_dir}/online_gpu" "${checkout}" || mr_die "[${platform}] terraform/online_gpu failed."
  if [[ -n "${HF_TOKEN:-}" ]]; then
    add_hf_token "${platform}"
  fi
  if [[ "${ENABLE_POD_SNAPSHOTS}" == "true" ]]; then
    enable_pod_snapshots "${platform}" "${region}"
  fi
  mr_log "[${platform}] Provisioned; KUBECONFIG=${KUBECONFIG}"
}

provision_sequential() {
  local i pid pids=() failed=0 restore_backend_template="false" restore_lock_files="false"
  local backend_template="${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket"
  mr_require_clean_tfvars "${ACP_REPO_DIR}"
  # The core scripts write the platform's state bucket into backend.tf.bucket
  # and terraform init can touch .terraform.lock.hcl; restore them afterwards
  # unless they already had local changes.
  if git -C "${ACP_REPO_DIR}" diff --quiet -- "${backend_template}"; then
    restore_backend_template="true"
  fi
  if git -C "${ACP_REPO_DIR}" diff --quiet -- ':(glob)**/.terraform.lock.hcl'; then
    restore_lock_files="true"
  fi
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    echo "=================================================================="
    echo "[${MR_TARGET_INDEXES[i]}] Provisioning '$(mr_cluster_name "${MR_TARGET_PLATFORMS[i]}")' in ${MR_TARGET_REGIONS[i]}"
    echo "=================================================================="
    # Run in an asynchronous subshell and wait for it, like the parallel mode:
    # errexit stays in effect inside it, which an 'if ! (...)' would disable.
    (provision_region "${ACP_REPO_DIR}" "${MR_TARGET_PLATFORMS[i]}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}") &
    if ! wait "$!"; then
      for pid in "${pids[@]}"; do
        wait "${pid}" || true
      done
      mr_clean_checkout "${ACP_REPO_DIR}" "${restore_backend_template}" "${restore_lock_files}"
      mr_die "provisioning '$(mr_cluster_name "${MR_TARGET_PLATFORMS[i]}")' failed; fix the error above and re-run with the same targets (completed steps are idempotent)."
    fi
    if ((${#mirror_sources[@]} > 0)); then
      # Mirror into this region while the next region is provisioned.
      mirror_images "${MR_TARGET_PLATFORMS[i]}" "${MR_TARGET_REGIONS[i]}" &
      pids+=("$!")
    fi
  done
  for pid in "${pids[@]}"; do
    wait "${pid}" || failed=1
  done
  mr_clean_checkout "${ACP_REPO_DIR}" "${restore_backend_template}" "${restore_lock_files}"
  ((failed == 0)) || mr_die "mirroring images failed in at least one region; see the output above."
}

provision_parallel() {
  local logs i platform wt pids=() failed=() restore_backend_template="false" restore_lock_files="false"
  local backend_template="${ACP_PLATFORM_CORE_DIR}/initialize/backend.tf.bucket"
  logs="${MR_WORK_DIR}/logs/provision-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "${logs}"
  if git -C "${ACP_REPO_DIR}" diff --quiet -- "${backend_template}"; then
    restore_backend_template="true"
  fi
  if git -C "${ACP_REPO_DIR}" diff --quiet -- ':(glob)**/.terraform.lock.hcl'; then
    restore_lock_files="true"
  fi
  git -C "${ACP_REPO_DIR}" diff HEAD --binary >"${logs}/uncommitted.diff"
  git -C "${ACP_REPO_DIR}" worktree prune
  # Worktrees are created one at a time: git doesn't support concurrent
  # worktree operations on one repository.
  for platform in "${MR_TARGET_PLATFORMS[@]}"; do
    mr_sync_worktree "${platform}" "${logs}/uncommitted.diff"
    mr_require_clean_tfvars "$(mr_worktree_dir "${platform}")"
  done
  for i in "${!MR_TARGET_PLATFORMS[@]}"; do
    platform="${MR_TARGET_PLATFORMS[i]}"
    wt="$(mr_worktree_dir "${platform}")"
    (
      provision_region "${wt}" "${platform}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}"
      if ((${#mirror_sources[@]} > 0)); then
        mirror_images "${platform}" "${MR_TARGET_REGIONS[i]}"
      fi
    ) >"${logs}/${platform}.log" 2>&1 &
    pids+=("$!")
    mr_log "[${platform}] Provisioning in ${wt}; log: ${logs}/${platform}.log"
  done
  for i in "${!pids[@]}"; do
    platform="${MR_TARGET_PLATFORMS[i]}"
    wt="$(mr_worktree_dir "${platform}")"
    if wait "${pids[i]}"; then
      mr_clean_checkout "${wt}" "${restore_backend_template}" "${restore_lock_files}"
      mr_log "[${platform}] Done"
    else
      mr_clean_checkout "${wt}" "${restore_backend_template}" "${restore_lock_files}"
      failed+=("${platform}")
      mr_log "[${platform}] FAILED; log: ${logs}/${platform}.log"
    fi
  done
  ((${#failed[@]} == 0)) ||
    mr_die "provisioning failed for: ${failed[*]}. Fix the cause (see ${logs}/<platform_name>.log) and re-run with the same targets."
}

if [[ "${dry_run}" == "true" ]]; then
  mr_require_clean_tfvars "${ACP_REPO_DIR}"
  print_plan
  exit 0
fi

mr_require_tools gcloud git jq kubectl terraform
if [[ "${ENABLE_POD_SNAPSHOTS}" == "true" ]]; then
  mr_require_gcloud_beta
fi
gcloud projects describe "${PROJECT_ID}" --format="value(projectId)" >/dev/null
for i in "${!MR_TARGET_PLATFORMS[@]}"; do
  mr_check_existing_platform "${MR_TARGET_PLATFORMS[i]}" "${MR_TARGET_REGIONS[i]}" "${MR_TARGET_INDEXES[i]}"
done

if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
  mr_ensure_state_bucket "${MR_TARGET_REGIONS[0]}"
  apply_shared_network
fi

if [[ "${parallel}" == "true" ]]; then
  provision_parallel
else
  provision_sequential
fi

echo "All ${#MR_TARGET_PLATFORMS[@]} regional platforms are provisioned. To point kubectl and Terraform at one of them:"
echo "  source ${MY_PATH}/helpers.sh && use_region <platform_name> <region>"
