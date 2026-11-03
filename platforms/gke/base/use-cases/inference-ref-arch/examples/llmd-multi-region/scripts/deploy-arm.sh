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

# Deploys one experiment arm in every region, waits until it serves through
# the multi-cluster Gateway, and records the spin-up timeline.
#
# Usage: deploy-arm.sh <baseline|llmd> [--backend <ppcr|ob>] [--lb-mode <mode>] [--no-route]
#
#   baseline  plain vLLM Deployment + ServiceExport per region (arm A)
#   llmd      llm-d model servers + router InferencePools (precise prefix cache
#             routing and optimized baseline) per region (arm B)
#
# Unless --no-route is set, the multi-cluster Gateway is then pointed at the
# arm (deploy-gateway.sh) and the time to the first successful completion
# through each region's VIP is recorded.

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
source "${MY_PATH}/render.sh"

arm="${1:?usage: deploy-arm.sh <baseline|llmd> [--backend <ppcr|ob>] [--lb-mode <mode>] [--no-route]}"
shift
backend=""
lb_mode="locality"
route="true"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --backend) backend="${2}" && shift 2 ;;
  --lb-mode) lb_mode="${2}" && shift 2 ;;
  --no-route) route="false" && shift ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done
case "${arm}" in
baseline) backend="baseline" ;;
llmd) backend="${backend:-ppcr}" ;;
*) mr_die "arm must be one of: baseline, llmd" ;;
esac

mr_require_tools
startup_root="${MR_RESULTS_DIR}/startup/${MR_RUN_ID}/${arm}"
mkdir -p "${startup_root}"

apply_common() {
  local key="${1}" dst="${MR_WORK_DIR}/rendered/${1}/common"
  mr_render_dir "${MR_EXAMPLE_DIR}/manifests/common" "${dst}"
  mr_kubectl "${key}" apply -f "${dst}/compute-class-bench.yaml"
  mr_kubectl "${key}" apply -f "${dst}/compute-class-gpu-obtainable.yaml"
  # vLLM metrics come from GKE automatic application monitoring. A second
  # PodMonitoring for the same pods would create a duplicate series per pod,
  # which breaks the HPA's per-pod metric.
  mr_kubectl "${key}" delete podmonitoring vllm-model-servers -n "${MR_NAMESPACE}" --ignore-not-found
  mr_kubectl "${key}" apply -f "${dst}/probe-client.yaml"
  if mr_kubectl "${key}" get crd autoscalingmetrics.autoscaling.gke.io >/dev/null 2>&1; then
    mr_kubectl "${key}" apply -f "${dst}/autoscaling-metric.yaml"
  else
    mr_log "WARNING: AutoscalingMetric CRD not found in ${key}; CUSTOM_METRICS load balancing won't have data"
  fi
  mr_kubectl "${key}" rollout status deploy/probe-client -n "${MR_NAMESPACE}" --timeout=600s
}

podsnapshots_on() { [[ "${MR_POD_SNAPSHOTS_ENABLED}" == "true" && "${arm}" == "llmd" ]]; }

# Succeeds when a Pod snapshot of the llm-d model servers is available in the
# region (PodSnapshot Ready condition with reason AllSnapshotsAvailable).
snapshot_available() {
  mr_kubectl "${1}" get podsnapshots -n "${MR_NAMESPACE}" -o json 2>/dev/null | python3 -c '
import json, sys
items = json.load(sys.stdin)["items"]
ok = [i for i in items if i.get("spec", {}).get("policyName") == "llmd-model-servers"
      and any(c.get("type") == "Ready" and c.get("reason") == "AllSnapshotsAvailable"
              for c in i.get("status", {}).get("conditions", []))]
sys.exit(0 if ok else 1)'
}

apply_model_servers() {
  local key="${1}" dir bootstrap="false"
  dir="$(mr_render_model_server "${key}")"
  kustomize build "${dir}/${arm}" >"${dir}/${arm}.rendered.yaml" || return 1
  if podsnapshots_on; then
    local sha old_sha
    sha="$(python3 "${MY_PATH}/podsnapshot_patch.py" "${dir}/${arm}.rendered.yaml" "$(model_server_deployment)" \
      "${dir}/podsnapshot/checkpoint-wrapper.sh" "${MR_POD_SNAPSHOT_MEMORY_LIMIT}")" || return 1
    old_sha="$(mr_kubectl "${key}" get podsnapshotpolicy llmd-model-servers -n "${MR_NAMESPACE}" \
      -o jsonpath='{.metadata.annotations.acp-mr/pod-template-sha256}' 2>/dev/null || true)"
    if [[ -n "${old_sha}" && "${old_sha}" != "${sha}" ]]; then
      # The pod spec changed: the existing snapshots can't be restored into it.
      mr_log "Pod spec changed in ${key}; deleting its old Pod snapshots"
      mr_kubectl "${key}" delete podsnapshots --all -n "${MR_NAMESPACE}" --wait=true || return 1
    fi
    mr_kubectl "${key}" apply -f "${dir}/podsnapshot/storage-config.yaml" -f "${dir}/podsnapshot/policy.yaml" \
      -f "${dir}/podsnapshot/pdb.yaml" || return 1
    mr_kubectl "${key}" annotate podsnapshotpolicy llmd-model-servers -n "${MR_NAMESPACE}" --overwrite \
      "acp-mr/pod-template-sha256=${sha}" || return 1
    if ! snapshot_available "${key}"; then
      # Bootstrap: start from one cold pod, which is checkpointed; the HPA (and
      # so the other replicas, restored from the snapshot) comes afterwards.
      bootstrap="true"
      touch "${dir}/podsnapshot.bootstrap"
      mr_kubectl "${key}" delete hpa -l "acp-mr/arm=${arm}" -n "${MR_NAMESPACE}" --ignore-not-found
      mr_kubectl "${key}" delete deployment "$(model_server_deployment)" -n "${MR_NAMESPACE}" --ignore-not-found --wait=true
      python3 - "${dir}/${arm}.rendered.yaml" "$(model_server_deployment)" <<'EOF_PY' || return 1
import sys
import yaml

path, name = sys.argv[1], sys.argv[2]
with open(path) as f:
    docs = [d for d in yaml.safe_load_all(f) if d]
for d in docs:
    if d.get("kind") == "Deployment" and d["metadata"]["name"] == name:
        d["spec"]["replicas"] = 1
with open(path, "w") as f:
    yaml.safe_dump_all(docs, f, sort_keys=False)
EOF_PY
    fi
  fi
  if [[ "${MR_HPA_ENABLED}" == "true" ]]; then
    MR_HPA_DEPLOYMENT="$(model_server_deployment)" MR_HPA_ARM="${arm}" \
      envsubst '${MR_HPA_DEPLOYMENT} ${MR_HPA_ARM}' <"${dir}/hpa.yaml" >"${dir}/${arm}.hpa.yaml"
    # When the Deployment already exists, leave its replica count to the HPA:
    # re-applying spec.replicas would scale a scaled-out arm back down.
    if mr_kubectl "${key}" get deployment "$(model_server_deployment)" -n "${MR_NAMESPACE}" >/dev/null 2>&1; then
      python3 - "${dir}/${arm}.rendered.yaml" "$(model_server_deployment)" <<'EOF_PY'
import sys
import yaml

path, name = sys.argv[1], sys.argv[2]
with open(path) as f:
    docs = [d for d in yaml.safe_load_all(f) if d]
for d in docs:
    if d.get("kind") == "Deployment" and d["metadata"]["name"] == name:
        d["spec"].pop("replicas", None)
with open(path, "w") as f:
    yaml.safe_dump_all(docs, f, sort_keys=False)
EOF_PY
    fi
  fi
  # Release the GPU nodes held by delete-arm.sh --hold-gpus (if any) right
  # before the model servers are created, so that they land on those nodes.
  mr_kubectl "${key}" delete deployment gpu-hold -n "${MR_NAMESPACE}" --ignore-not-found --wait=true
  mr_kubectl "${key}" apply -f "${dir}/${arm}.rendered.yaml" || return 1
  if [[ "${MR_HPA_ENABLED}" == "true" && "${bootstrap}" != "true" ]]; then
    mr_kubectl "${key}" apply -f "${dir}/${arm}.hpa.yaml" || return 1
  fi
}

# After a Pod snapshot bootstrap: wait for the snapshot, then apply the HPA,
# whose minimum replicas are restored from the snapshot.
finish_snapshot_bootstrap() {
  local key="${1}" dir="${MR_WORK_DIR}/rendered/${1}/model-server"
  mr_stage "pod_snapshot_available/${arm}" "region/${key}" \
    mr_wait_for "${MR_POD_SNAPSHOT_TIMEOUT_S}" 20 "Pod snapshot in ${key}" snapshot_available "${key}" || return 1
  if [[ "${MR_HPA_ENABLED}" == "true" ]]; then
    mr_kubectl "${key}" apply -f "${dir}/${arm}.hpa.yaml" || return 1
    mr_wait_for 300 5 "HPA minimum replicas in ${key}" deployment_at_min "${key}" || return 1
    mr_stage "arm_pods_restored/${arm}" "region/${key}" wait_ready "${key}"
  fi
}

deployment_at_min() {
  local replicas
  replicas="$(mr_kubectl "${1}" get deployment "$(model_server_deployment)" -n "${MR_NAMESPACE}" -o jsonpath='{.spec.replicas}')"
  [[ -n "${replicas}" && "${replicas}" -ge "${MR_REPLICAS_PER_REGION}" ]]
}

apply_routers() {
  local key="${1}" release file
  for release in ${MR_LLMD_ROUTER_RELEASES}; do
    file="$(mr_render_router "${key}" "${release}")"
    mr_kubectl "${key}" apply --server-side --force-conflicts -f "${file}"
    if [[ "${MR_GLOBAL_LB}" == "mc-gateway" ]]; then
      # Export the InferencePool to the fleet. The multi-cluster Gateway
      # controller then creates a GCPInferencePoolImport with the same name in
      # the config cluster.
      mr_kubectl "${key}" annotate inferencepool "${release}" -n "${MR_NAMESPACE}" \
        networking.gke.io/export="True" --overwrite
    else
      # Standalone Mode: expose the router proxy (Envoy + endpoint picker) as
      # GKE standalone zonal NEGs for the Terraform-managed load balancer.
      mr_kubectl "${key}" annotate service "${release}-epp" -n "${MR_NAMESPACE}" --overwrite \
        cloud.google.com/neg="{\"exposed_ports\":{\"80\":{\"name\":\"$(mr_neg_prefix "${key}")-$(mr_router_short_name "${release}")\"}}}"
    fi
  done
  for release in ${MR_LLMD_ROUTER_RELEASES}; do
    mr_kubectl "${key}" rollout status "deploy/${release}-epp" -n "${MR_NAMESPACE}" --timeout=900s
  done
}

model_server_deployment() {
  echo "precise-prefix-cache-routing-gpu-vllm-decode-${arm}"
}

wait_ready() {
  local key="${1}"
  mr_kubectl "${key}" rollout status "deploy/$(model_server_deployment)" -n "${MR_NAMESPACE}" --timeout=3600s
}

collect_startup() {
  local key="${1}" dir="${startup_root}/${1}"
  mkdir -p "${dir}/logs"
  mr_kubectl "${key}" get pods -n "${MR_NAMESPACE}" -l "acp-mr/arm=${arm}" -o json >"${dir}/pods.json"
  mr_kubectl "${key}" get nodes -o json >"${dir}/nodes.json"
  mr_kubectl "${key}" get events -n "${MR_NAMESPACE}" -o json >"${dir}/events.json"
  local pod
  for pod in $(jq -r '.items[].metadata.name' "${dir}/pods.json"); do
    mr_kubectl "${key}" logs -n "${MR_NAMESPACE}" "${pod}" -c modelserver >"${dir}/logs/${pod}.log" 2>&1 || true
  done
}

declare -A apply_epoch ready_epoch
for key in ${MR_REGION_KEYS}; do
  mr_validate_region_key "${key}"
  mr_stage "arm_apply_common/${arm}" "region/${key}" apply_common "${key}"
done

for key in ${MR_REGION_KEYS}; do
  apply_epoch[${key}]="$(date +%s.%N)"
  mr_stage "arm_apply_model_servers/${arm}" "region/${key}" apply_model_servers "${key}"
  if [[ "${arm}" == "llmd" ]]; then
    mr_stage "arm_apply_routers/${arm}" "region/${key}" apply_routers "${key}"
  fi
done

# Wait for every region in parallel.
pids=()
for key in ${MR_REGION_KEYS}; do
  (mr_stage "arm_pods_ready/${arm}" "region/${key}" wait_ready "${key}") &
  pids+=($!)
done
for pid in "${pids[@]}"; do wait "${pid}"; done
if podsnapshots_on; then
  pids=()
  for key in ${MR_REGION_KEYS}; do
    if [[ -f "${MR_WORK_DIR}/rendered/${key}/model-server/podsnapshot.bootstrap" ]]; then
      finish_snapshot_bootstrap "${key}" &
      pids+=($!)
    fi
  done
  for pid in "${pids[@]}"; do wait "${pid}" || mr_log "WARNING: Pod snapshot bootstrap failed in a region; new pods there start cold"; done
fi
for key in ${MR_REGION_KEYS}; do
  ready_epoch[${key}]="$(date +%s.%N)"
  mr_stage "arm_collect_startup/${arm}" "region/${key}" collect_startup "${key}"
done

if [[ "${route}" == "true" ]]; then
  "${MY_PATH}/set-route.sh" --backend "${backend}" --lb-mode "${lb_mode}"
fi

for key in ${MR_REGION_KEYS}; do
  first_ok="null"
  if [[ "${route}" == "true" ]]; then
    first_ok="$(jq -r --arg k "${key}" '.vips[$k].first_ok_epoch_s' "${MR_RESULTS_DIR}/gateway/active.json")"
  fi
  jq -n \
    --arg arm "${arm}" --arg backend "${backend}" --arg region "$(mr_region "${key}")" \
    --argjson apply "${apply_epoch[${key}]}" --argjson ready "${ready_epoch[${key}]}" \
    --argjson first_ok "${first_ok}" \
    '{arm: $arm, backend: $backend, region: $region, apply_epoch_s: $apply, all_pods_ready_observed_epoch_s: $ready, first_ok_via_gateway_epoch_s: $first_ok}' \
    >"${startup_root}/${key}/markers.json"
done

mr_log "Arm ${arm} deployed. Startup artifacts: ${startup_root}"
