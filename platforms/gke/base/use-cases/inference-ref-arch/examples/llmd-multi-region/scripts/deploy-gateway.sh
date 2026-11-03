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

# Creates or updates the multi-cluster Gateway in the config cluster and points
# it at one experiment arm, with one load balancing mode.
#
# Usage:
#   deploy-gateway.sh --backend <baseline|ppcr|ob> [--lb-mode <locality|capacity|preferred>]
#                     [--preferred-region <region_key>]
#
#   baseline  plain vLLM ServiceImport (arm A)
#   ppcr      llm-d precise prefix cache routing InferencePool (arm B)
#   ob        llm-d optimized baseline InferencePool (arm B, approximate prefix)
#
#   locality  closest region first, spill over at MR_LB_LOCALITY_MAX_UTIL % KV
#             cache utilization (default 80)
#   capacity  closest region first, spill over early at MR_LB_CAPACITY_MAX_UTIL %
#             KV cache utilization (default 30), to use every region's capacity
#             at the cost of cross-region latency
#   zone-spray not supported by the multi-cluster Gateway (Terraform load
#             balancer only)
#   preferred send everything to --preferred-region until it reaches
#             MR_LB_LOCALITY_MAX_UTIL %, then spill over (Preview: scopes)

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

backend=""
lb_mode="locality"
preferred_key="${MR_CONFIG_CLUSTER_KEY}"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --backend) backend="${2}" && shift 2 ;;
  --lb-mode) lb_mode="${2}" && shift 2 ;;
  --preferred-region) preferred_key="${2}" && shift 2 ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done

export MR_LB_LOCALITY_MAX_UTIL="${MR_LB_LOCALITY_MAX_UTIL:-80}"
export MR_LB_CAPACITY_MAX_UTIL="${MR_LB_CAPACITY_MAX_UTIL:-30}"

case "${backend}" in
baseline)
  export MR_ROUTE_BACKEND_GROUP="net.gke.io" MR_ROUTE_BACKEND_KIND="ServiceImport" MR_ROUTE_BACKEND_NAME="vllm-baseline"
  export MR_ROUTE_BACKEND_PORT="          port: 8000"
  ;;
ppcr | ob)
  export MR_ROUTE_BACKEND_GROUP="networking.gke.io" MR_ROUTE_BACKEND_KIND="GCPInferencePoolImport" MR_ROUTE_BACKEND_PORT=""
  if [[ "${backend}" == "ppcr" ]]; then
    export MR_ROUTE_BACKEND_NAME="precise-prefix-cache-routing"
  else
    export MR_ROUTE_BACKEND_NAME="optimized-baseline"
  fi
  ;;
*) mr_die "--backend must be one of: baseline, ppcr, ob" ;;
esac

case "${lb_mode}" in
locality)
  policy_template="locality"
  export MR_LB_MAX_UTILIZATION_PERCENT="${MR_LB_LOCALITY_MAX_UTIL}"
  ;;
capacity)
  policy_template="locality"
  export MR_LB_MAX_UTILIZATION_PERCENT="${MR_LB_CAPACITY_MAX_UTIL}"
  ;;
preferred)
  mr_validate_region_key "${preferred_key}"
  policy_template="preferred"
  export MR_LB_MAX_UTILIZATION_PERCENT="${MR_LB_LOCALITY_MAX_UTIL}"
  export MR_LB_PREFERRED_REGION="$(mr_region "${preferred_key}")"
  ;;
*) mr_die "--lb-mode must be one of: locality, capacity, preferred" ;;
esac

MR_GATEWAY_ADDRESSES=""
for key in ${MR_REGION_KEYS}; do
  r="$(mr_region "${key}")"
  MR_GATEWAY_ADDRESSES+="    - type: networking.gke.io/ephemeral-ipv4-address/${r}"$'\n'"      value: \"${r}\""$'\n'
done
export MR_GATEWAY_ADDRESSES="${MR_GATEWAY_ADDRESSES%$'\n'}"

cfg="${MR_CONFIG_CLUSTER_KEY}"
dst="${MR_WORK_DIR}/rendered/${cfg}/gateway"
mr_render_dir "${MR_EXAMPLE_DIR}/manifests/gateway" "${dst}"
mr_log "Gateway: backend=${MR_ROUTE_BACKEND_KIND}/${MR_ROUTE_BACKEND_NAME}, lb_mode=${lb_mode} (max utilization ${MR_LB_MAX_UTILIZATION_PERCENT}%)"

wait_for_import() {
  if [[ "${MR_ROUTE_BACKEND_KIND}" == "ServiceImport" ]]; then
    mr_wait_for 900 10 "ServiceImport ${MR_ROUTE_BACKEND_NAME}" \
      mr_kubectl "${cfg}" get serviceimport "${MR_ROUTE_BACKEND_NAME}" -n "${MR_NAMESPACE}"
  else
    mr_wait_for 900 10 "GCPInferencePoolImport ${MR_ROUTE_BACKEND_NAME}" \
      mr_kubectl "${cfg}" get gcpinferencepoolimport "${MR_ROUTE_BACKEND_NAME}" -n "${MR_NAMESPACE}"
  fi
}

apply_gateway() {
  mr_kubectl "${cfg}" apply -f "${dst}/gateway.yaml"
  mr_kubectl "${cfg}" apply -f "${dst}/healthcheckpolicy.yaml"
  mr_kubectl "${cfg}" apply -f "${dst}/backend-policies/${policy_template}.yaml"
  mr_kubectl "${cfg}" apply -f "${dst}/httproute.yaml"
}

gateway_programmed() {
  [[ "$(mr_kubectl "${cfg}" get gateway "${MR_GATEWAY_NAME}" -n "${MR_NAMESPACE}" \
    -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}')" == "True" ]] &&
    for key in ${MR_REGION_KEYS}; do mr_gateway_vip "${MR_GATEWAY_NAME}" "${key}" >/dev/null || return 1; done
}

route_ok_in_region() {
  local key="${1}" vip
  vip="$(mr_gateway_vip "${MR_GATEWAY_NAME}" "${key}")" || return 1
  mr_probe_completion "${key}" "${vip}"
}

mr_stage "gateway_wait_for_import/${backend}" "global" wait_for_import
mr_stage "gateway_apply/${backend}/${lb_mode}" "global" apply_gateway
mr_stage "gateway_programmed" "global" mr_wait_for 1800 10 "Gateway ${MR_GATEWAY_NAME} programmed" gateway_programmed

for key in ${MR_REGION_KEYS}; do
  mr_log "Gateway VIP in ${key} ($(mr_region "${key}")): $(mr_gateway_vip "${MR_GATEWAY_NAME}" "${key}")"
done

# Time from route change to the first successful completion through the VIP in
# each region (load balancer programming + health checks + endpoint picker).
declare -A first_ok
for key in ${MR_REGION_KEYS}; do
  mr_stage "gateway_first_ok/${backend}" "region/${key}" \
    mr_wait_for 1800 5 "first OK completion via the Gateway VIP in ${key}" route_ok_in_region "${key}"
  first_ok[${key}]="$(date +%s.%N)"
done

state_dir="${MR_RESULTS_DIR}/gateway"
mkdir -p "${state_dir}"
{
  echo "{"
  echo "  \"run_id\": \"${MR_RUN_ID}\","
  echo "  \"backend\": \"${backend}\","
  echo "  \"backend_ref\": \"${MR_ROUTE_BACKEND_GROUP}/${MR_ROUTE_BACKEND_KIND}/${MR_ROUTE_BACKEND_NAME}\","
  echo "  \"lb_mode\": \"${lb_mode}\","
  echo "  \"max_utilization_percent\": ${MR_LB_MAX_UTILIZATION_PERCENT},"
  echo "  \"preferred_region\": \"${MR_LB_PREFERRED_REGION:-}\","
  echo "  \"vips\": {"
  sep=""
  for key in ${MR_REGION_KEYS}; do
    printf '%s    "%s": {"region": "%s", "vip": "%s", "first_ok_epoch_s": %s}' "${sep}" "${key}" "$(mr_region "${key}")" "$(mr_gateway_vip "${MR_GATEWAY_NAME}" "${key}")" "${first_ok[${key}]}"
    sep=$',\n'
  done
  echo
  echo "  }"
  echo "}"
} >"${state_dir}/active.json"
cp "${state_dir}/active.json" "${state_dir}/${MR_RUN_ID}-${backend}-${lb_mode}.json"
mr_log "Active gateway state: ${state_dir}/active.json"
