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

# Shared library of the multi-region inference-ref-arch foundation. The scripts
# in this directory source it, and so can interactive sessions and runbooks:
#   source platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
#
# Functions read their settings from environment variables when they run. See
# README.md in this directory for the list.

MR_HELPERS_DIR="$(
  SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
  cd "$(dirname "${SCRIPT_SOURCE}")" >/dev/null 2>&1 || exit 1
  pwd -P
)"
ACP_REPO_DIR="$(realpath "${MR_HELPERS_DIR}/../../../../../../../")"
ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
ACP_PLATFORM_USE_CASE_DIR="${ACP_PLATFORM_BASE_DIR}/use-cases/inference-ref-arch"
export ACP_REPO_DIR ACP_PLATFORM_BASE_DIR ACP_PLATFORM_CORE_DIR ACP_PLATFORM_USE_CASE_DIR

# Digest-pinned crane v0.22.1 image used when mirroring upstream images into
# regional Artifact Registry repositories via Cloud Build.
export MR_CRANE_IMAGE="gcr.io/go-containerregistry/crane:v0.22.1@sha256:1f968817b95790bed063f71175aa6b8ff879fa17064020415f3e18bb6e6a36e1"

# Terraform variables that use_region sets for each region with TF_VAR_*
# environment variables. Terraform gives *.auto.tfvars files precedence over
# TF_VAR_* environment variables, so a value for one of these variables in a
# shared *.auto.tfvars file would silently apply to every region.
MR_OWNED_TF_VARIABLES=(
  cluster_autopilot_enabled
  cluster_custom_compute_class_active_migration_enabled
  cluster_region
  ira_online_gpu_pod_snapshots_enabled
  network_cluster_network_name
  network_cluster_pod_ipv4_cidr_block
  network_cluster_services_ipv4_cidr_block
  network_cluster_subnet_master_ipv4_cidr_block
  network_cluster_subnet_node_ip_cidr_range
  network_cluster_subnet_proxy_ip_cidr_range
  platform_default_project_id
  platform_default_region
  platform_name
  resource_name_prefix
  terraform_write_tfvars
)

mr_log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >&2
}

# Logs an error and exits. Scripts use it; interactive helpers return 1.
mr_die() {
  mr_log "ERROR: $*"
  exit 1
}

# Applies the defaults of the multi-region settings and validates them.
mr_load_settings() {
  NETWORK_MODE="${NETWORK_MODE:-island}"
  CLUSTER_MODE="${CLUSTER_MODE:-autopilot}"
  MR_ENVIRONMENT_NAME="${MR_ENVIRONMENT_NAME:-mr}"
  TF_VAR_resource_name_prefix="${TF_VAR_resource_name_prefix:-inf}"
  export NETWORK_MODE CLUSTER_MODE MR_ENVIRONMENT_NAME TF_VAR_resource_name_prefix

  if [[ "${NETWORK_MODE}" != "island" && "${NETWORK_MODE}" != "shared-vpc" ]]; then
    echo "ERROR: NETWORK_MODE='${NETWORK_MODE}' is not supported. Set it to 'island' (one VPC per region) or 'shared-vpc' (one VPC for every region)." >&2
    return 1
  fi
  if [[ "${CLUSTER_MODE}" != "autopilot" && "${CLUSTER_MODE}" != "standard" ]]; then
    echo "ERROR: CLUSTER_MODE='${CLUSTER_MODE}' is not supported. Set it to 'autopilot' or 'standard'." >&2
    return 1
  fi
  if [[ ! "${TF_VAR_resource_name_prefix}" =~ ^[a-z][a-z0-9]{0,2}$ ]]; then
    echo "ERROR: TF_VAR_resource_name_prefix='${TF_VAR_resource_name_prefix}' must be 1-3 lowercase letters or digits, starting with a letter." >&2
    return 1
  fi
  if [[ ! "${MR_ENVIRONMENT_NAME}" =~ ^[a-z][a-z0-9]{0,5}$ ]]; then
    echo "ERROR: MR_ENVIRONMENT_NAME='${MR_ENVIRONMENT_NAME}' must be 1-6 lowercase letters or digits, starting with a letter." >&2
    return 1
  fi
}

mr_load_project() {
  PROJECT_ID="${PROJECT_ID:-${TF_VAR_platform_default_project_id:-}}"
  if [[ -z "${PROJECT_ID}" ]]; then
    echo "ERROR: PROJECT_ID (or TF_VAR_platform_default_project_id) must be set." >&2
    return 1
  fi
  export PROJECT_ID
}

# Loads the settings, the project, and MR_WORK_DIR, the local directory (outside
# the checkout) for worktrees, logs, and the staged multi-region terraservices.
mr_init() {
  mr_load_settings || return 1
  mr_load_project || return 1
  MR_WORK_DIR="${MR_WORK_DIR:-${HOME}/.acp-multi-region/${PROJECT_ID}-${TF_VAR_resource_name_prefix}-${MR_ENVIRONMENT_NAME}}"
  export MR_WORK_DIR
}

mr_require_tools() {
  local tool missing=()
  for tool in "$@"; do
    command -v "${tool}" >/dev/null 2>&1 || missing+=("${tool}")
  done
  if ((${#missing[@]} > 0)); then
    mr_die "missing required tools: ${missing[*]}. Run bootstrap_tools.sh in this directory, or install them."
  fi
}

# Names derived from the core platform naming:
#   cluster_name = "<resource_name_prefix>-<platform_name>"
mr_cluster_name() { echo "${TF_VAR_resource_name_prefix:-inf}-${1}"; }
mr_kubeconfig() { echo "${ACP_PLATFORM_BASE_DIR}/kubernetes/kubeconfig/${PROJECT_ID}-$(mr_cluster_name "${1}")"; }
mr_shared_network_name() { echo "${TF_VAR_resource_name_prefix:-inf}-${MR_ENVIRONMENT_NAME:-mr}-vpc"; }
mr_state_bucket() { echo "${PROJECT_ID}-${TF_VAR_resource_name_prefix:-inf}-${MR_ENVIRONMENT_NAME:-mr}-terraform"; }
mr_worktree_dir() { echo "${MR_WORK_DIR}/worktrees/${1}"; }
mr_deploy_suffix() { if [[ "${CLUSTER_MODE}" == "autopilot" ]]; then echo "ap"; else echo "standard"; fi; }

# Name of the GKE standalone NEG of a backend in a regional platform, which
# global_lb.sh attaches to the cross-region internal Application Load Balancer.
mr_neg_name() {
  local platform_name="${1:?Usage: mr_neg_name <platform_name> <backend>}"
  local backend="${2:?Usage: mr_neg_name <platform_name> <backend>}"
  echo "$(mr_cluster_name "${platform_name}")-${backend}"
}

# Computes deterministic, non-overlapping RFC1918 CIDRs for CIDR index 0..11,
# staying outside Google Cloud's 10.128.0.0/9 auto-mode subnet space so that
# every platform can share one VPC (NETWORK_MODE=shared-vpc), or so that island
# VPCs can be connected later.
mr_set_cidrs_for_index() {
  local idx="${1:?Usage: mr_set_cidrs_for_index <0..11>}"
  if [[ ! "${idx}" =~ ^[0-9]+$ ]] || ((idx < 0 || idx >= 12)); then
    echo "ERROR: CIDR index '${idx}' must be an integer in 0..11." >&2
    return 1
  fi

  MR_NODE_CIDR="10.$((16 + idx * 4)).0.0/20"
  MR_PROXY_CIDR="10.$((16 + idx * 4)).16.0/23"
  MR_GLOBAL_PROXY_CIDR="10.$((16 + idx * 4)).18.0/23"
  MR_MASTER_CIDR="172.16.0.$((16 + idx * 16))/28"
  MR_POD_CIDR="10.$((64 + idx)).0.0/17"
  MR_SERVICES_CIDR="10.96.$((idx * 4)).0/22"
  export MR_NODE_CIDR MR_PROXY_CIDR MR_GLOBAL_PROXY_CIDR MR_MASTER_CIDR MR_POD_CIDR MR_SERVICES_CIDR
}

# Points ACP Terraform environment variables and KUBECONFIG at a regional
# platform without modifying tracked *.auto.tfvars or ~/.kube/config. Pass the
# platform's CIDR index to also export its network ranges, which provision.sh
# and teardown.sh do before they run Terraform.
use_region() {
  local platform_name="${1:?Usage: use_region <platform_name> <region> [<cidr_index>]}"
  local region="${2:?Usage: use_region <platform_name> <region> [<cidr_index>]}"
  local cidr_index="${3:-}"
  mr_load_settings || return 1
  mr_load_project || return 1

  export TF_VAR_platform_default_project_id="${PROJECT_ID}"
  export TF_VAR_platform_default_region="${region}"
  export TF_VAR_cluster_region="${region}"
  export TF_VAR_platform_name="${platform_name}"
  export TF_VAR_terraform_write_tfvars="false"
  if [[ "${CLUSTER_MODE}" == "autopilot" ]]; then
    export TF_VAR_cluster_autopilot_enabled="true"
  else
    export TF_VAR_cluster_autopilot_enabled="false"
  fi
  if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
    TF_VAR_network_cluster_network_name="$(mr_shared_network_name)"
    export TF_VAR_network_cluster_network_name
  else
    unset TF_VAR_network_cluster_network_name
  fi
  if [[ -n "${cidr_index}" ]]; then
    mr_set_cidrs_for_index "${cidr_index}" || return 1
    export TF_VAR_network_cluster_subnet_node_ip_cidr_range="${MR_NODE_CIDR}"
    export TF_VAR_network_cluster_subnet_proxy_ip_cidr_range="${MR_PROXY_CIDR}"
    export TF_VAR_network_cluster_subnet_master_ipv4_cidr_block="${MR_MASTER_CIDR}"
    export TF_VAR_network_cluster_pod_ipv4_cidr_block="${MR_POD_CIDR}"
    export TF_VAR_network_cluster_services_ipv4_cidr_block="${MR_SERVICES_CIDR}"
  fi
  KUBECONFIG="$(mr_kubeconfig "${platform_name}")"
  export KUBECONFIG
}

# Prints KUBECONFIG and the TF_VAR_* values that use_region and the scripts set
# (dry runs). Other TF_VAR_* variables are listed by name only.
mr_print_region_env() {
  local variable owned other
  echo "  KUBECONFIG=${KUBECONFIG}"
  owned="$(printf 'TF_VAR_%s\n' "${MR_OWNED_TF_VARIABLES[@]}" initialize_backend_use_case_name)"
  while IFS= read -r variable; do
    if [[ -v "${variable}" ]]; then
      echo "  ${variable}=${!variable}"
    fi
  done <<<"${owned}"
  other="$(compgen -e TF_VAR_ | grep -vxF -f <(echo "${owned}") | paste -sd' ' -)" || true
  if [[ -n "${other}" ]]; then
    echo "  other TF_VAR_* variables passed through (values not shown): ${other}"
  fi
}

# Parses "<platform_name>:<region>[:<cidr_index>]" targets into the
# MR_TARGET_PLATFORMS, MR_TARGET_REGIONS, and MR_TARGET_INDEXES arrays. The CIDR
# index defaults to the position of the target in the list.
mr_parse_targets() {
  MR_TARGET_PLATFORMS=()
  MR_TARGET_REGIONS=()
  MR_TARGET_INDEXES=()
  local position=0 target platform region index extra i
  for target in "$@"; do
    IFS=: read -r platform region index extra <<<"${target}"
    if [[ -z "${platform}" || -z "${region}" || -n "${extra}" ]]; then
      mr_die "invalid target '${target}'. Use '<platform_name>:<region>[:<cidr_index>]', for example 'americas:us-central1'."
    fi
    index="${index:-${position}}"
    [[ "${platform}" =~ ^[a-z][a-z0-9-]{0,8}$ ]] ||
      mr_die "platform name '${platform}' in '${target}' must be 1-9 lowercase letters, digits, or hyphens, starting with a letter."
    [[ "${region}" =~ ^[a-z]+-[a-z]+[0-9]+$ ]] ||
      mr_die "'${region}' in '${target}' is not a Google Cloud region name, for example 'us-central1'."
    [[ "${index}" =~ ^([0-9]|1[01])$ ]] ||
      mr_die "CIDR index '${index}' in '${target}' must be an integer in 0..11."
    for i in "${!MR_TARGET_PLATFORMS[@]}"; do
      [[ "${MR_TARGET_PLATFORMS[i]}" != "${platform}" ]] || mr_die "platform '${platform}' is listed more than once."
      [[ "${MR_TARGET_INDEXES[i]}" != "${index}" ]] ||
        mr_die "'${MR_TARGET_PLATFORMS[i]}' and '${platform}' both use CIDR index ${index}. Give each platform its own index with '<platform_name>:<region>:<cidr_index>'."
      # A VPC network can have only one active proxy-only subnet per purpose
      # in each region.
      [[ "${NETWORK_MODE}" != "shared-vpc" || "${MR_TARGET_REGIONS[i]}" != "${region}" ]] ||
        mr_die "'${MR_TARGET_PLATFORMS[i]}' and '${platform}' are both in ${region}. NETWORK_MODE=shared-vpc supports one platform per region, because each region of a VPC network has a single active proxy-only subnet per purpose."
    done
    [[ "${NETWORK_MODE}" != "shared-vpc" || "${platform}" != "${MR_ENVIRONMENT_NAME}" ]] ||
      mr_die "platform name '${platform}' equals MR_ENVIRONMENT_NAME, so its Terraform state bucket would collide with gs://$(mr_state_bucket). Use another platform name or MR_ENVIRONMENT_NAME."
    MR_TARGET_PLATFORMS+=("${platform}")
    MR_TARGET_REGIONS+=("${region}")
    MR_TARGET_INDEXES+=("${index}")
    position=$((position + 1))
  done
}

# Fails when an existing platform's node subnet doesn't match the CIDR index or
# the NETWORK_MODE of a target. The core scripts apply their plans without
# review, and another range or network would replace the subnet and the
# cluster.
mr_check_existing_platform() {
  local platform="${1}" region="${2}" index="${3}" subnet err_file out err cidr network expected_network
  subnet="$(mr_cluster_name "${platform}")"
  err_file="$(mktemp)"
  if ! out="$(gcloud compute networks subnets describe "${subnet}" --region="${region}" --project="${PROJECT_ID}" \
    --format="value(ipCidrRange,network.basename())" 2>"${err_file}")"; then
    err="$(<"${err_file}")"
    rm -f "${err_file}"
    if [[ "${err,,}" == *"not found"* || "${err,,}" == *"404"* ]]; then
      return 0
    fi
    mr_die "failed to inspect subnet ${subnet} in ${region}: ${err}"
  fi
  rm -f "${err_file}"
  read -r cidr network <<<"${out}"
  mr_set_cidrs_for_index "${index}" || exit 1
  [[ "${cidr}" == "${MR_NODE_CIDR}" ]] ||
    mr_die "[${platform}] subnet ${subnet} uses ${cidr}, but CIDR index ${index} maps to ${MR_NODE_CIDR}. Pass the CIDR index that created it ('${platform}:${region}:<cidr_index>')."
  if [[ "${NETWORK_MODE}" == "shared-vpc" ]]; then
    expected_network="$(mr_shared_network_name)"
  else
    expected_network="${subnet}"
  fi
  [[ "${network}" == "${expected_network}" ]] ||
    mr_die "[${platform}] subnet ${subnet} is in the network ${network}, but NETWORK_MODE=${NETWORK_MODE} uses ${expected_network}. Use the NETWORK_MODE and MR_ENVIRONMENT_NAME that provisioned the platform."
}

# Fails when a shared *.auto.tfvars file in a checkout sets a variable that
# use_region exports per region (see MR_OWNED_TF_VARIABLES).
mr_require_clean_tfvars() {
  local checkout="${1}" pattern file
  pattern="^[[:space:]]*($(
    IFS='|'
    echo "${MR_OWNED_TF_VARIABLES[*]}"
  ))[[:space:]]*="
  for file in \
    "${checkout}/platforms/gke/base/_shared_config/"*.auto.tfvars \
    "${checkout}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/"*.auto.tfvars; do
    if grep -Eq "${pattern}" "${file}"; then
      mr_die "'${file}' sets $(grep -Eo "${pattern}" "${file}" | tr -d ' =' | paste -sd, -), which would override the per-region TF_VAR_* values. Remove those lines (for example with 'git -C ${checkout} restore ${file#"${checkout}"/}') and re-run."
    fi
  done
}

# Creates the Git worktree of a regional platform, or resets an existing one,
# to the HEAD commit of this checkout plus its uncommitted changes to tracked
# files (diff_file, from 'git diff HEAD --binary'). Generated, git-ignored files
# in an existing worktree (backend.tf, .terraform/, local state) are kept.
mr_sync_worktree() {
  local platform="${1}" diff_file="${2}" wt head path
  wt="$(mr_worktree_dir "${platform}")"
  head="$(git -C "${ACP_REPO_DIR}" rev-parse HEAD)"
  if [[ -e "${wt}/.git" ]]; then
    git -C "${wt}" checkout --quiet --force --detach "${head}"
    # Files that the diff adds are untracked copies from a previous run.
    while IFS= read -r path; do
      rm -f "${wt:?}/${path}"
    done < <(git -C "${ACP_REPO_DIR}" diff HEAD --name-only --diff-filter=AR)
  elif [[ -e "${wt}" ]]; then
    mr_die "'${wt}' exists but is not a Git worktree. Move it out of the way and re-run."
  else
    mkdir -p "$(dirname "${wt}")"
    git -C "${ACP_REPO_DIR}" worktree add --quiet --detach "${wt}" "${head}"
  fi
  if [[ -s "${diff_file}" ]]; then
    git -C "${wt}" apply --whitespace=nowarn "${diff_file}"
  fi
}

mr_remove_worktree() {
  local wt
  wt="$(mr_worktree_dir "${1}")"
  if [[ -e "${wt}/.git" ]]; then
    git -C "${ACP_REPO_DIR}" worktree remove --force "${wt}"
  fi
}

# mr_terraform_apply <terraservice_dir> <checkout>
# Initializes, plans, and applies a per-platform terraservice in place, against
# the backend.tf that core/initialize generated for the current platform.
mr_terraform_apply() {
  local dir="${1}" checkout="${2}"
  (
    cd "${dir}" || exit 1
    TF_PLUGIN_CACHE_DIR="${checkout}/.terraform.d/plugin-cache" terraform init -input=false -reconfigure || exit 1
    terraform plan -input=false -out=tfplan || exit 1
    terraform apply -input=false tfplan || exit 1
    rm -f tfplan
  )
}

# mr_terraform_destroy <terraservice_dir> <checkout>
# Destroys a per-platform terraservice in place. Does nothing when its state
# has no resources, so that teardown.sh can be re-run.
mr_terraform_destroy() {
  local dir="${1}" checkout="${2}"
  (
    cd "${dir}" || exit 1
    TF_PLUGIN_CACHE_DIR="${checkout}/.terraform.d/plugin-cache" terraform init -input=false -reconfigure || exit 1
    resources="$(terraform state list)" || exit 1
    if [[ -z "${resources}" ]]; then
      mr_log "${dir}: no resources in the state, nothing to destroy."
      exit 0
    fi
    terraform destroy -input=false -auto-approve || exit 1
  )
}

mr_bucket_exists() {
  local bucket="${1}" out
  if out="$(gcloud storage buckets describe "gs://${bucket}" --project="${PROJECT_ID}" --format="value(name)" 2>&1)"; then
    return 0
  fi
  if [[ "${out,,}" == *"404"* || "${out,,}" == *"not found"* ]]; then
    return 1
  fi
  mr_die "failed to inspect bucket gs://${bucket}: ${out}"
}

# Creates the versioned bucket that holds the Terraform state of the
# multi-region terraservices of this directory. It outlives every regional
# platform; delete it manually when you no longer need it.
mr_ensure_state_bucket() {
  local location="${1}" bucket
  bucket="$(mr_state_bucket)"
  if mr_bucket_exists "${bucket}"; then
    return 0
  fi
  mr_log "Creating the multi-region Terraform state bucket gs://${bucket} in ${location}"
  gcloud storage buckets create "gs://${bucket}" \
    --project="${PROJECT_ID}" \
    --location="${location}" \
    --uniform-bucket-level-access \
    --public-access-prevention
  gcloud storage buckets update "gs://${bucket}" --versioning >/dev/null
}

mr_tf_dir() { echo "${MR_WORK_DIR}/terraform/${1}"; }

# mr_tf <terraservice> <apply|destroy|output>
# Runs a multi-region terraservice of this directory against the state bucket
# of the environment, with the variables in terraform.tfvars.json of
# "$(mr_tf_dir <terraservice>)". The module is copied there with its own
# backend.tf: core/initialize generates a backend.tf that points at a regional
# platform's state bucket in every directory with a versions.tf file under
# inference-ref-arch/terraform/, so that file is never copied.
mr_tf() {
  local terraservice="${1}" action="${2}" stage file
  stage="$(mr_tf_dir "${terraservice}")"
  mkdir -p "${stage}" || return 1
  rm -f "${stage}"/*.tf
  for file in "${MR_HELPERS_DIR}/${terraservice}"/*.tf "${MR_HELPERS_DIR}/${terraservice}/.terraform.lock.hcl"; do
    if [[ "$(basename "${file}")" != "backend.tf" ]]; then
      cp "${file}" "${stage}/" || return 1
    fi
  done
  # Partial configuration: terraform init gets the bucket and the prefix.
  printf 'terraform {\n  backend "gcs" {}\n}\n' >"${stage}/backend.tf" || return 1
  (
    cd "${stage}" || exit 1
    TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache" terraform init -input=false -reconfigure \
      -backend-config="bucket=$(mr_state_bucket)" \
      -backend-config="prefix=terraform/multi-region/${terraservice}" >&2 || exit 1
    case "${action}" in
    apply)
      terraform plan -input=false -out=tfplan || exit 1
      terraform apply -input=false tfplan || exit 1
      rm -f tfplan
      ;;
    destroy) terraform destroy -input=false -auto-approve || exit 1 ;;
    output) terraform output -json || exit 1 ;;
    *) mr_die "mr_tf: unknown action '${action}'" ;;
    esac
  )
}

# Succeeds when the state of a multi-region terraservice has resources.
mr_tf_state_has_resources() {
  local object err_file state err count
  object="gs://$(mr_state_bucket)/terraform/multi-region/${1}/default.tfstate"
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

# Prints the regional platforms of the shared-vpc environment, as registered in
# the shared_network state ({"<platform_name>": {"region": ..., "node_cidr": ...,
# ...}}), or {} when the shared network doesn't exist.
mr_registry_json() {
  local outputs
  if ! mr_tf_state_has_resources shared_network; then
    echo '{}'
    return 0
  fi
  outputs="$(mr_tf shared_network output)" || return 1
  jq -c '.regions.value // {}' <<<"${outputs}"
}

# mr_wait_for <timeout_s> <interval_s> <description> <command...>
mr_wait_for() {
  local timeout="${1}" interval="${2}" description="${3}"
  shift 3
  local deadline=$(($(date +%s) + timeout))
  until "$@" >/dev/null 2>&1; do
    if (($(date +%s) >= deadline)); then
      mr_log "timed out after ${timeout}s waiting for: ${description}"
      return 1
    fi
    sleep "${interval}"
  done
}

mr_service_neg_ready() {
  local kubeconfig="${1}" namespace="${2}" service="${3}" status
  status="$(kubectl --kubeconfig "${kubeconfig}" get service "${service}" -n "${namespace}" \
    -o jsonpath='{.metadata.annotations.cloud\.google\.com/neg-status}')" || return 1
  [[ -n "${status}" ]] && jq -e '.network_endpoint_groups | length > 0' <<<"${status}" >/dev/null
}

# Exposes a port of a regional frontend Service (for example dynamo-frontend,
# trtllm, or an llm-d router) as the GKE standalone NEG of a global load
# balancer backend, waits until GKE has created it, and prints its name.
expose_service_neg() {
  local usage="Usage: expose_service_neg <platform_name> <namespace> <service> <port> <backend>"
  local platform_name="${1:?${usage}}" namespace="${2:?${usage}}" service="${3:?${usage}}"
  local port="${4:?${usage}}" backend="${5:?${usage}}"
  (
    set -o errexit
    set -o nounset
    set -o pipefail

    mr_load_settings
    mr_load_project
    [[ "${backend}" =~ ^[a-z][a-z0-9-]{0,29}$ ]] ||
      mr_die "backend name '${backend}' must be 1-30 lowercase letters, digits, or hyphens, starting with a letter."
    local kubeconfig neg
    kubeconfig="$(mr_kubeconfig "${platform_name}")"
    neg="$(mr_neg_name "${platform_name}" "${backend}")"
    kubectl --kubeconfig "${kubeconfig}" annotate service "${service}" -n "${namespace}" --overwrite \
      cloud.google.com/neg="{\"exposed_ports\":{\"${port}\":{\"name\":\"${neg}\"}}}" >&2
    mr_wait_for 300 5 "standalone NEG ${neg} of Service ${namespace}/${service}" \
      mr_service_neg_ready "${kubeconfig}" "${namespace}" "${service}" ||
      mr_die "GKE didn't create the NEG ${neg}. Check the Service's events: kubectl --kubeconfig ${kubeconfig} describe service ${service} -n ${namespace}"
    echo "${neg}"
  )
}

# Stages a single Hugging Face model into the active region's GCS model bucket
# using the canonical inference-ref-arch model-download scripts.
stage_hf_model() {
  local model_id="${1:?Usage: stage_hf_model <hf_model_id>}"
  (
    set -o errexit
    set -o nounset
    set -o pipefail

    HF_MODEL_ID="$(echo "${model_id}" | tr '[:upper:]' '[:lower:]')"
    export HF_MODEL_ID
    local dl_dir="${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/model-download/huggingface"
    "${dl_dir}/download_apply.sh"
    "${dl_dir}/download_wait.sh"
    "${dl_dir}/download_delete.sh"
  )
}

# Server-side copies a staged model directory from one regional GCS
# hf-hub-models bucket to another, failing fast if the source directory is
# missing or empty. Note that hf-model-to-gcs writes under lowercase MODEL_ID.
replicate_hf_model() {
  local src_platform="${1:?Usage: replicate_hf_model <src_platform> <dst_platform> <hf_model_id>}"
  local dst_platform="${2:?Usage: replicate_hf_model <src_platform> <dst_platform> <hf_model_id>}"
  local model_id="${3:?Usage: replicate_hf_model <src_platform> <dst_platform> <hf_model_id>}"
  local project_id="${PROJECT_ID:-${TF_VAR_platform_default_project_id:-}}"
  local prefix="${TF_VAR_resource_name_prefix:-inf}"

  (
    set -o errexit
    set -o nounset
    set -o pipefail

    if [[ -z "${project_id}" ]]; then
      echo "ERROR: PROJECT_ID must be set before calling replicate_hf_model." >&2
      exit 1
    fi

    local model_subpath
    model_subpath="$(echo "${model_id}" | tr '[:upper:]' '[:lower:]')"
    local src_uri="gs://${project_id}-${prefix}-${src_platform}-hf-hub-models/${model_subpath}"
    local dst_uri="gs://${project_id}-${prefix}-${dst_platform}-hf-hub-models/${model_subpath}"

    if [[ -z "$(gcloud storage ls "${src_uri}/")" ]]; then
      echo "ERROR: Source model path '${src_uri}/' is empty or missing." >&2
      exit 1
    fi

    echo "Replicating '${model_subpath}' from ${src_uri} to ${dst_uri}..."
    gcloud storage rsync --recursive "${src_uri}" "${dst_uri}"
  )
}

# Mirrors an upstream image (ideally digest-pinned) into a regional Artifact
# Registry repository so GKE image streaming can lazy-load container layers.
mirror_image_to_ar() {
  local region="${1:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local platform_name="${2:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local src_image="${3:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local dst_subpath="${4:?Usage: mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath_and_tag>}"
  local project_id="${PROJECT_ID:-${TF_VAR_platform_default_project_id:-}}"
  local prefix="${TF_VAR_resource_name_prefix:-inf}"

  (
    set -o errexit
    set -o nounset
    set -o pipefail

    if [[ -z "${project_id}" ]]; then
      echo "ERROR: PROJECT_ID must be set before calling mirror_image_to_ar." >&2
      exit 1
    fi

    local dst_image="${region}-docker.pkg.dev/${project_id}/${prefix}-${platform_name}/${dst_subpath}"
    local cb_config
    cb_config="$(mktemp)"
    trap 'rm -f "${cb_config}"' EXIT

    cat >"${cb_config}" <<EOF
steps:
- name: '${MR_CRANE_IMAGE}'
  args: ['copy', '--platform', 'linux/amd64', '${src_image}', '${dst_image}']
options:
  machineType: 'E2_HIGHCPU_8'
timeout: '3600s'
EOF

    echo "Mirroring ${src_image} -> ${dst_image}..."
    gcloud builds submit \
      --no-source \
      --project="${project_id}" \
      --region="${region}" \
      --config="${cb_config}" \
      --quiet
  )
}
