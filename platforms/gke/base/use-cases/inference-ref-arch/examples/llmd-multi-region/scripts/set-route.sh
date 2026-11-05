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

# Points the cross-region load balancer at an experiment arm with a load
# balancing mode, using the implementation selected by MR_GLOBAL_LB:
#   - MR_GLOBAL_LB=terraform (default): builds backends.json with per-endpoint
#     capacities and delegates to terraform/multi-region/global_lb.sh
#   - MR_GLOBAL_LB=mc-gateway: delegates to scripts/deploy-gateway.sh
#
# Usage:
#   set-route.sh --backend <baseline|ppcr|ob> [--lb-mode <locality|capacity|zone-spray|preferred>]
#                [--preferred-region <region_key>] [--no-wait] [--dry-run]
#
# Capacity is measured with MR_LB_BALANCING_MODE: IN_FLIGHT (in-progress
# requests; MR_LB_REGION_CAPACITY_INFLIGHT and MR_LB_CAPACITY_MODE_INFLIGHT) or
# RATE (requests per second; MR_LB_REGION_CAPACITY_QPS and
# MR_LB_CAPACITY_MODE_QPS).
#
#   locality   WATERFALL_BY_REGION: the closest region first, spill over to
#              the next region when it reaches its capacity
#   capacity   WATERFALL_BY_REGION with a low region capacity: spill over
#              early, so that load from one region is spread across every
#              region's accelerators, trading cross-region latency for
#              utilization. When every region is at its capacity, the load
#              balancer fills them in proportion to it.
#   zone-spray SPRAY_TO_REGION: like locality, but each proxy spreads requests
#              across every zone of the chosen region. This does NOT spread
#              traffic across regions.
#   preferred  WATERFALL_BY_REGION with the backends of --preferred-region
#              marked PREFERRED: fill that region first, from every client
#
# Set MR_LB_EXCLUDE_ARM=<baseline|llmd> to omit an arm's backends when another
# arm remains deployed (used by delete-arm.sh so GKE can delete the NEGs).

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

if [[ "${MR_GLOBAL_LB}" == "mc-gateway" ]]; then
  exec "${MY_PATH}/deploy-gateway.sh" "$@"
fi

backend=""
lb_mode="locality"
preferred_key="${MR_CONFIG_CLUSTER_KEY}"
wait_for_traffic="true"
dry_run="false"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --backend) backend="${2}" && shift 2 ;;
  --lb-mode) lb_mode="${2}" && shift 2 ;;
  --preferred-region) preferred_key="${2}" && shift 2 ;;
  --no-wait) wait_for_traffic="false" && shift ;;
  --dry-run) dry_run="true" && shift ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done
[[ "${backend}" =~ ^(baseline|ppcr|ob)$ ]] || mr_die "--backend must be one of: baseline, ppcr, ob"

algorithm="WATERFALL_BY_REGION"
preferred_region=""
[[ "${MR_LB_BALANCING_MODE}" =~ ^(IN_FLIGHT|RATE)$ ]] || mr_die "MR_LB_BALANCING_MODE must be IN_FLIGHT or RATE"
region_capacity_qps="${MR_LB_REGION_CAPACITY_QPS}"
region_capacity_inflight="${MR_LB_REGION_CAPACITY_INFLIGHT}"
case "${lb_mode}" in
locality) ;;
capacity)
  region_capacity_qps="${MR_LB_CAPACITY_MODE_QPS}"
  region_capacity_inflight="${MR_LB_CAPACITY_MODE_INFLIGHT}"
  ;;
zone-spray) algorithm="SPRAY_TO_REGION" ;;
preferred)
  mr_validate_active_region_key "${preferred_key}"
  preferred_region="$(mr_region "${preferred_key}")"
  ;;
*) mr_die "--lb-mode must be one of: locality, capacity, zone-spray, preferred" ;;
esac

backends_file="${MR_WORK_DIR}/terraform/backends.json"
persistent_vips="${MR_WORK_DIR}/terraform/global_lb.vips.json"
persistent_state="${MR_WORK_DIR}/terraform/global_lb.state.json"
state_dir="${MR_RESULTS_DIR}/gateway"
mkdir -p "${state_dir}" "$(dirname "${backends_file}")"

write_backends_json() {
  "${MR_PYTHON}" - "${backends_file}" <<EOF
import json, sys

exclude = "${MR_LB_EXCLUDE_ARM:-}"
hpa_enabled = "${MR_HPA_ENABLED}" == "true"
capacity = float("${region_capacity_qps}")
capacity_inflight = float("${region_capacity_inflight}")
replicas = int("${MR_REPLICAS_PER_REGION}")
hpa_max_replicas = int("${MR_HPA_MAX_REPLICAS}")
if replicas < 1 or (hpa_enabled and hpa_max_replicas < replicas):
    sys.exit(
        f"MR_REPLICAS_PER_REGION={replicas} must be at least 1, and at most "
        f"MR_HPA_MAX_REPLICAS={hpa_max_replicas} when MR_HPA_ENABLED=true"
    )
# Endpoints per region: the vLLM pods for the baseline, one router (Envoy +
# endpoint picker) pod for each llm-d router release.
endpoints = {"baseline": replicas, "ppcr": 1, "ob": 1}
# With the HPA, the baseline's regional capacity grows with its NEG endpoints,
# up to hpa_max_replicas times the per-endpoint capacity. The load balancer
# can't see the vLLM pods behind an llm-d router, so give the router that
# full-scale-out capacity from the start: both arms then spill over at the same
# load once scaled out (before that, an llm-d region accepts more).
router_hpa_scale = hpa_max_replicas / replicas if hpa_enabled else 1.0
scale_by_backend = {"baseline": 1.0, "ppcr": router_hpa_scale, "ob": router_hpa_scale}
specs = {
    "baseline": {
        "health_check_path": "/health",
        "health_check_port": 8000,
        "locality_lb_policy": "${MR_BASELINE_LOCALITY_LB_POLICY}",
    },
    "ppcr": {
        "health_check_path": "/ready",
        "health_check_port": 19001,
        "locality_lb_policy": "LEAST_REQUEST",
    },
    "ob": {
        "health_check_path": "/ready",
        "health_check_port": 19001,
        "locality_lb_policy": "LEAST_REQUEST",
    },
}
excluded = set({"baseline": ["baseline"], "llmd": ["ppcr", "ob"]}.get(exclude, []))
backends = {}
for b, spec in specs.items():
    if b in excluded:
        continue
    mult = scale_by_backend[b]
    backends[b] = {
        **spec,
        "max_rate_per_endpoint": max(0.001, round((capacity * mult) / endpoints[b], 3)),
        "max_in_flight_requests_per_endpoint": max(1, round((capacity_inflight * mult) / endpoints[b])),
    }
if "${backend}" not in backends:
    sys.exit(f"Active backend '${backend}' was excluded by MR_LB_EXCLUDE_ARM='{exclude}'")
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(backends, f, indent=2)
    f.write("\n")
EOF
}

glb_args=(
  apply
  --backends "${backends_file}"
  --active "${backend}"
  --algorithm "${algorithm}"
  --balancing-mode "${MR_LB_BALANCING_MODE}"
  --timeout-sec "${MR_BACKEND_TIMEOUT_SEC}"
)
if [[ -n "${preferred_region}" ]]; then
  glb_args+=(--preferred-region "${preferred_region}")
fi

if [[ "${dry_run}" == "true" ]]; then
  mr_require_tools "${MR_PYTHON}" jq
  write_backends_json
  mr_log "Dry run: wrote ${backends_file}; global_lb.sh ${glb_args[*]}"
  jq . "${backends_file}"
  exit 0
fi

mr_require_example_tools

apply_lb() {
  "${MR_MULTI_REGION_DIR}/global_lb.sh" "${glb_args[@]}" || return 1
  "${MR_MULTI_REGION_DIR}/global_lb.sh" vips >"${state_dir}/vips.json" || return 1
  cp "${state_dir}/vips.json" "${persistent_vips}" || return 1
  jq -n --arg backend "${backend}" --arg lb_mode "${lb_mode}" --arg preferred_key "${preferred_key}" \
    '{backend: $backend, lb_mode: $lb_mode, preferred_key: $preferred_key}' >"${persistent_state}"
}

route_ok_in_region() {
  local key="${1}" vip
  vip="$(mr_gateway_vip "" "${key}")" || return 1
  mr_probe_completion "${key}" "${vip}"
}

mr_log "Load balancer: backend=${backend}, lb_mode=${lb_mode}, balancing_mode=${MR_LB_BALANCING_MODE}"
mr_stage "global_lb_backends/${backend}/${lb_mode}" "global" write_backends_json
mr_stage "global_lb_apply/${backend}/${lb_mode}" "global" apply_lb

declare -A first_ok
for key in ${MR_REGION_KEYS}; do
  mr_log "VIP in ${key} ($(mr_region "${key}")): $(mr_gateway_vip "" "${key}")"
  first_ok[${key}]="null"
done

if [[ "${wait_for_traffic}" == "true" ]]; then
  # Time from the load balancer change to the first successful completion
  # through the VIP in each region (programming + health checks).
  for key in ${MR_REGION_KEYS}; do
    mr_stage "global_lb_first_ok/${backend}" "region/${key}" \
      mr_wait_for 1800 5 "first OK completion via the VIP in ${key}" route_ok_in_region "${key}"
    first_ok[${key}]="$(date +%s.%N)"
  done
fi

{
  echo "{"
  echo "  \"run_id\": \"${MR_RUN_ID}\","
  echo "  \"implementation\": \"terraform\","
  echo "  \"backend\": \"${backend}\","
  echo "  \"lb_mode\": \"${lb_mode}\","
  echo "  \"load_balancing_algorithm\": \"${algorithm}\","
  echo "  \"balancing_mode\": \"${MR_LB_BALANCING_MODE}\","
  echo "  \"region_capacity_qps\": ${region_capacity_qps},"
  echo "  \"region_capacity_inflight\": ${region_capacity_inflight},"
  echo "  \"preferred_region\": \"${preferred_region}\","
  echo "  \"preferred_key\": \"${preferred_key}\","
  echo "  \"vips\": {"
  sep=""
  for key in ${MR_REGION_KEYS}; do
    printf '%s    "%s": {"region": "%s", "vip": "%s", "first_ok_epoch_s": %s}' "${sep}" "${key}" "$(mr_region "${key}")" "$(mr_gateway_vip "" "${key}")" "${first_ok[${key}]}"
    sep=$',\n'
  done
  echo
  echo "  }"
  echo "}"
} >"${state_dir}/active.json"
cp "${state_dir}/active.json" "${state_dir}/${MR_RUN_ID}-${backend}-${lb_mode}.json"
mr_log "Active load balancer state: ${state_dir}/active.json"
