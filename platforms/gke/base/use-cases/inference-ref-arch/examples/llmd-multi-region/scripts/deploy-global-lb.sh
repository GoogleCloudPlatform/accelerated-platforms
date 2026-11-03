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

# Creates or updates the Terraform-managed cross-region internal Application
# Load Balancer (terraform/global_lb) and points it at one experiment arm, with
# one cross-region load balancing mode. Used when MR_GLOBAL_LB=terraform.
#
# Usage:
#   deploy-global-lb.sh --backend <baseline|ppcr|ob> [--lb-mode <locality|capacity|zone-spray|preferred>]
#                       [--preferred-region <region_key>] [--no-wait]
#
# Capacity is measured with MR_LB_BALANCING_MODE: IN_FLIGHT (in-progress
# requests; MR_LB_REGION_CAPACITY_INFLIGHT and MR_LB_CAPACITY_MODE_INFLIGHT) or
# RATE (requests per second; MR_LB_REGION_CAPACITY_QPS and
# MR_LB_CAPACITY_MODE_QPS).
#
#   locality   WATERFALL_BY_REGION: the closest region first, spill over to
#              the next region when it reaches its capacity
#   capacity   WATERFALL_BY_REGION with a low region capacity: spill over
#              early, so that load from
#              one region is spread across every region's accelerators, trading
#              cross-region latency for utilization. When every region is at
#              its capacity, the load balancer fills them in proportion to it.
#   zone-spray SPRAY_TO_REGION: like locality, but each proxy spreads requests
#              across every zone of the chosen region. This does NOT spread
#              traffic across regions.
#   preferred  WATERFALL_BY_REGION with the backends of --preferred-region
#              marked PREFERRED: fill that region first, from every client
#
# Set MR_LB_EXCLUDE_ARM=<baseline|llmd> to detach an arm's NEGs (done by
# delete-arm.sh before it deletes the arm, so that GKE can delete the NEGs).

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

backend=""
lb_mode="locality"
preferred_key="${MR_CONFIG_CLUSTER_KEY}"
wait_for_traffic="true"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --backend) backend="${2}" && shift 2 ;;
  --lb-mode) lb_mode="${2}" && shift 2 ;;
  --preferred-region) preferred_key="${2}" && shift 2 ;;
  --no-wait) wait_for_traffic="false" && shift ;;
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
  mr_validate_region_key "${preferred_key}"
  preferred_region="$(mr_region "${preferred_key}")"
  ;;
*) mr_die "--lb-mode must be one of: locality, capacity, zone-spray, preferred" ;;
esac

lb_name="${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-llm"
tfvars="${MR_WORK_DIR}/terraform/global_lb.tfvars.json"
state_dir="${MR_RESULTS_DIR}/gateway"
mkdir -p "${state_dir}" "$(dirname "${tfvars}")"

write_tfvars() {
  # Every GKE standalone NEG of this environment, as "name zone selfLink".
  local negs
  negs="$(gcloud compute network-endpoint-groups list --project "${MR_PROJECT_ID}" \
    --filter="name ~ ^${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-" \
    --format="value(name,zone.basename(),selfLink)")"
  python3 - "${tfvars}" <<EOF
import json, sys
keys = "${MR_REGION_KEYS}".split()
region = dict(x.split("=", 1) for x in """$(for k in ${MR_REGION_KEYS}; do echo "${k}=${MR_REGION[${k}]}"; done)""".split())
prefix = "${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-"
exclude = "${MR_LB_EXCLUDE_ARM:-}"
capacity = float("${region_capacity_qps}")
capacity_inflight = float("${region_capacity_inflight}")
replicas = int("${MR_REPLICAS_PER_REGION}")
# Endpoints per region: the vLLM pods for the baseline, one router (Envoy +
# endpoint picker) pod for each llm-d router release.
endpoints = {"baseline": replicas, "ppcr": 1, "ob": 1}
backends = {
    "baseline": {"health_check_path": "/health", "health_check_port": 8000, "negs": []},
    "ppcr": {"health_check_path": "/ready", "health_check_port": 19001, "negs": []},
    "ob": {"health_check_path": "/ready", "health_check_port": 19001, "negs": []},
}
excluded = {"baseline": ["baseline"], "llmd": ["ppcr", "ob"]}.get(exclude, [])
for line in """${negs}""".splitlines():
    if not line.strip():
        continue
    name, zone, self_link = line.split()
    rest = name[len(prefix):]
    key, _, b = rest.partition("-")
    if key not in keys or b not in backends or b in excluded:
        continue
    backends[b]["negs"].append({
        "region": region[key],
        "self_link": self_link,
        "max_rate_per_endpoint": round(capacity / endpoints[b], 3),
        "max_in_flight_requests_per_endpoint": max(1, round(capacity_inflight / endpoints[b])),
    })
tfvars = {
    "project_id": "${MR_PROJECT_ID}",
    "name": "${lb_name}",
    "network": "projects/${MR_PROJECT_ID}/global/networks/${MR_NETWORK_NAME}",
    "regions": {k: {"region": region[k], "subnetwork": "projects/${MR_PROJECT_ID}/regions/%s/subnetworks/%s" % (region[k], "${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}" + k)} for k in keys},
    "backends": backends,
    "active_backend": "${backend}",
    "balancing_mode": "${MR_LB_BALANCING_MODE}",
    "load_balancing_algorithm": "${algorithm}",
    "preferred_region": "${preferred_region}",
    "timeout_sec": int("${MR_BACKEND_TIMEOUT_SEC:-3600}"),
}
json.dump(tfvars, open(sys.argv[1], "w"), indent=2)
active = len(backends["${backend}"]["negs"])
print(f"active backend ${backend}: {active} NEG(s); " + ", ".join(f"{b}={len(v['negs'])}" for b, v in backends.items()), file=sys.stderr)
EOF
}

apply_lb() {
  mr_tf global_lb apply "${tfvars}" || return 1
  (
    cd "${MR_EXAMPLE_DIR}/terraform/global_lb"
    export TF_DATA_DIR="${MR_WORK_DIR}/terraform/global_lb/.terraform"
    terraform output -json vips
  ) >"${state_dir}/vips.json"
}

route_ok_in_region() {
  local key="${1}" vip
  vip="$(mr_gateway_vip "" "${key}")" || return 1
  mr_probe_completion "${key}" "${vip}"
}

mr_ensure_shared_state_bucket
mr_log "Load balancer: backend=${backend}, lb_mode=${lb_mode}, balancing_mode=${MR_LB_BALANCING_MODE}"
mr_stage "global_lb_tfvars/${backend}/${lb_mode}" "global" write_tfvars
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
