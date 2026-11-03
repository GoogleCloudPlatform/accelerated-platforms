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

# Deploys one regional platform (GKE Standard cluster + inference-ref-arch
# online GPU resources) into the shared VPC, from a dedicated Git worktree.
#
# Usage: deploy-region.sh <region_key>
#
# Regions are independent, so you can run one instance of this script per
# region in parallel (see deploy-all.sh).

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

key="${1:?usage: deploy-region.sh <region_key>}"
mr_validate_region_key "${key}"
mr_require_tools

region="$(mr_region "${key}")"
platform_name="$(mr_platform_name "${key}")"
cluster_name="$(mr_cluster_name "${key}")"
wt="$(mr_worktree_dir "${key}")"
scope="region/${key}"

mr_log "Deploying ${cluster_name} in ${region} (worktree: ${wt})"

create_worktree() {
  if [[ -d "${wt}" ]]; then
    mr_log "Reusing existing worktree ${wt}"
    return 0
  fi
  mkdir -p "$(dirname "${wt}")"
  git -C "${ACP_REPO_DIR}" worktree add --detach "${wt}" HEAD
  # Carry over uncommitted changes to tracked files and untracked files, so
  # that the regional deployment uses exactly the code in this checkout.
  local diff_file="${MR_WORK_DIR}/worktree-${platform_name}.diff"
  git -C "${ACP_REPO_DIR}" diff HEAD --binary >"${diff_file}"
  if [[ -s "${diff_file}" ]]; then
    mr_log "Applying uncommitted changes from ${ACP_REPO_DIR} to the worktree"
    git -C "${wt}" apply --whitespace=nowarn "${diff_file}"
  fi
  (
    cd "${ACP_REPO_DIR}"
    git ls-files --others --exclude-standard -z | xargs -0 -r -I{} cp --parents "{}" "${wt}/"
  )
}

write_tfvars() {
  local shared="${wt}/platforms/gke/base/_shared_config"
  local uc_shared="${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config"

  # core/initialize generates platform_custom_role_unique_suffix on the first
  # run and writes it back to platform.auto.tfvars. Keep it when re-running,
  # otherwise later terraservices reference custom IAM roles that don't exist.
  local role_suffix=""
  if [[ -f "${shared}/platform.auto.tfvars" ]]; then
    role_suffix="$(sed -n 's/^[[:blank:]]*platform_custom_role_unique_suffix[[:blank:]]*=[[:blank:]]*"\(.*\)"/\1/p' "${shared}/platform.auto.tfvars")"
  fi

  cat >"${shared}/platform.auto.tfvars" <<EOF
platform_default_project_id = "${MR_PROJECT_ID}"
platform_default_region     = "${region}"
platform_name               = "${platform_name}"
resource_name_prefix        = "${MR_RESOURCE_NAME_PREFIX}"
EOF
  if [[ -n "${role_suffix}" && "${role_suffix}" != "null" ]]; then
    echo "platform_custom_role_unique_suffix = \"${role_suffix}\"" >>"${shared}/platform.auto.tfvars"
  fi

  cat >"${shared}/cluster.auto.tfvars" <<EOF
cluster_autopilot_enabled             = false
cluster_project_id                    = "${MR_PROJECT_ID}"
cluster_region                        = "${region}"
cluster_system_node_pool_machine_type = "${MR_SYSTEM_MACHINE_TYPE[${key}]:-${MR_SYSTEM_MACHINE_TYPE_DEFAULT}}"
EOF

  cat >"${shared}/networking.auto.tfvars" <<EOF
network_cluster_network_name                  = "${MR_NETWORK_NAME}"
network_cluster_subnet_master_ipv4_cidr_block = "${MR_MASTER_CIDR[${key}]}"
network_cluster_subnet_node_ip_cidr_range     = "${MR_NODE_CIDR[${key}]}"
network_cluster_subnet_proxy_ip_cidr_range    = "${MR_REGIONAL_PROXY_CIDR[${key}]}"
EOF

  # Identical namespace and Kubernetes service account in every region
  # (namespace sameness for multi-cluster Services and Gateways).
  cat >"${uc_shared}/inference-ref-arch.auto.tfvars" <<EOF
ira_online_gpu_kubernetes_namespace_name       = "${MR_NAMESPACE}"
ira_online_gpu_kubernetes_service_account_name = "${MR_NAMESPACE}"
ira_online_gpu_pod_snapshots_enabled           = ${MR_POD_SNAPSHOTS_ENABLED}
EOF
}

deploy_platform() {
  # Transient failures are common right after the cluster is created: for
  # example, gke_enterprise/fleet_membership waits only 60 seconds for running
  # cluster operations, and the cluster autoscaler often runs a RESIZE_CLUSTER
  # operation at that time. The core scripts are idempotent, so retry.
  local attempt max="${MR_CORE_PLATFORM_ATTEMPTS:-3}"
  for ((attempt = 1; attempt <= max; attempt++)); do
    if (
      unset TF_VAR_platform_name TF_VAR_cluster_region TF_VAR_platform_default_region || true
      export TF_VAR_resource_name_prefix="${MR_RESOURCE_NAME_PREFIX}"
      "${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-standard.sh"
    ); then
      return 0
    fi
    mr_log "core platform attempt ${attempt}/${max} failed"
    [[ ${attempt} -lt ${max} ]] && sleep 60
  done
  return 1
}

deploy_online_gpu() {
  (
    cd "${wt}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu"
    export TF_PLUGIN_CACHE_DIR="${wt}/.terraform.d/plugin-cache"
    rm -rf .terraform/
    terraform init -input=false
    terraform plan -input=false -out=tfplan
    terraform apply -input=false tfplan
    rm -f tfplan
  )
}

# The vLLM Run:ai Model Streamer loads gs:// models with the Cloud Storage
# client, which reads the bucket metadata (storage.buckets.get). The
# inference-ref-arch online_gpu terraservice only grants the Cloud Storage FUSE
# object role, so also grant the legacy bucket reader role to the namespace
# Kubernetes service account (Workload Identity principal).
grant_model_bucket_reader() {
  local project_number
  project_number="$(gcloud projects describe "${MR_PROJECT_ID}" --format='value(projectNumber)')"
  gcloud storage buckets add-iam-policy-binding "gs://$(mr_models_bucket "${key}")" \
    --member="principal://iam.googleapis.com/projects/${project_number}/locations/global/workloadIdentityPools/${MR_PROJECT_ID}.svc.id.goog/subject/ns/${MR_NAMESPACE}/sa/${MR_NAMESPACE}" \
    --role="roles/storage.legacyBucketReader" >/dev/null
}

add_hf_token() {
  [[ -s "${MR_HF_TOKEN_FILE}" ]] || mr_die "Hugging Face token file '${MR_HF_TOKEN_FILE}' is missing or empty"
  local secret="${cluster_name}-huggingface-hub-access-token-read"
  if gcloud secrets versions list "${secret}" --project "${MR_PROJECT_ID}" --filter="state=ENABLED" --format="value(name)" 2>/dev/null | grep -q .; then
    mr_log "Secret ${secret} already has an enabled version"
    return 0
  fi
  tr -d '\n' <"${MR_HF_TOKEN_FILE}" | gcloud secrets versions add "${secret}" \
    --data-file=- --project "${MR_PROJECT_ID}" >/dev/null
}

# GKE Pod snapshots (MR_POD_SNAPSHOTS_ENABLED): the online_gpu terraservice
# creates the snapshot bucket and its IAM grants; the cluster feature is enabled
# with gcloud, because the core platform's Terraform provider version predates
# the pod_snapshot_config addon.
enable_pod_snapshots() {
  local enabled
  enabled="$(gcloud beta container clusters describe "${cluster_name}" --location "${region}" \
    --project "${MR_PROJECT_ID}" --format='value(addonsConfig.podSnapshotConfig.enabled)')"
  if [[ "${enabled}" != "True" ]]; then
    # One cluster operation at a time: wait until the cluster is RUNNING.
    mr_wait_for 1800 20 "cluster ${cluster_name} RUNNING" bash -c \
      "[[ \"\$(gcloud container clusters describe '${cluster_name}' --location '${region}' --project '${MR_PROJECT_ID}' --format='value(status)')\" == RUNNING ]]" || return 1
    gcloud beta container clusters update "${cluster_name}" --location "${region}" \
      --project "${MR_PROJECT_ID}" --enable-pod-snapshots --quiet || return 1
  fi
  mr_wait_for 600 15 "Pod snapshot CRDs in ${cluster_name}" mr_kubectl "${key}" get crd \
    podsnapshots.podsnapshot.gke.io podsnapshotpolicies.podsnapshot.gke.io podsnapshotstorageconfigs.podsnapshot.gke.io
}

label_cluster() {
  gcloud container clusters update "${cluster_name}" \
    --location "${region}" \
    --project "${MR_PROJECT_ID}" \
    --update-labels "created_by=${MR_OWNER_LABEL},acp_environment=${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME},acp_example=llmd-multi-region" \
    --quiet >/dev/null
}

mr_stage "worktree" "${scope}" create_worktree
mr_stage "write_tfvars" "${scope}" write_tfvars
# Set MR_SKIP_CORE_PLATFORM=true to resume after the core platform step
# succeeded (re-running it is a no-op, but takes several minutes).
if [[ "${MR_SKIP_CORE_PLATFORM:-false}" != "true" ]]; then
  mr_stage "core_platform_and_cluster" "${scope}" deploy_platform
fi
mr_stage "online_gpu" "${scope}" deploy_online_gpu
mr_stage "model_bucket_reader_iam" "${scope}" grant_model_bucket_reader
mr_stage "hf_token_secret" "${scope}" add_hf_token
mr_stage "kubeconfig" "${scope}" mr_get_credentials "${key}"
mr_stage "label_cluster" "${scope}" label_cluster
if [[ "${MR_POD_SNAPSHOTS_ENABLED}" == "true" ]]; then
  mr_stage "pod_snapshots" "${scope}" enable_pod_snapshots
fi

mr_log "Region ${key} deployed: cluster ${cluster_name} (${region})"
