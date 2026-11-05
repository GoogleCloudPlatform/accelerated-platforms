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

# Regional-skew experiment: all load comes from the clients of ONE region, so
# that the cross-region load balancing mode matters:
#
#   locality  WATERFALL_BY_REGION: keep traffic in the clients' region until it
#             reaches MR_LB_REGION_CAPACITY_INFLIGHT (or MR_LB_REGION_CAPACITY_QPS
#             when MR_LB_BALANCING_MODE=RATE), then spill over
#   capacity  WATERFALL_BY_REGION with a low region capacity
#             (MR_LB_CAPACITY_MODE_INFLIGHT / MR_LB_CAPACITY_MODE_QPS): spill
#             over early and spread traffic across regions (more accelerators,
#             plus cross-region latency for part of the requests)
#
# for each arm (plain vLLM baseline and llm-d precise prefix cache routing).
# Any mode of set-route.sh can be listed in --modes (for example zone-spray).
#
# Usage: run-skew-experiment.sh [--arms "baseline llmd"] [--client usc1]
#                               [--qps "2 4 6 8"] [--modes "locality capacity"]
#                               [--region-capacity-inflight 32]
#                               [--capacity-mode-inflight 8]
#                               [--region-capacity-qps 6] [--capacity-mode-qps 1]
#                               [--with-hpa]
#
# The --*-inflight options need MR_LB_BALANCING_MODE=IN_FLIGHT (the default),
# the --*-qps options MR_LB_BALANCING_MODE=RATE.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

arms="baseline llmd"
client="${MR_REGION_KEYS%% *}"
qps="2 4 6 8"
region_capacity_inflight="${MR_LB_REGION_CAPACITY_INFLIGHT}"
capacity_mode_inflight="${MR_LB_CAPACITY_MODE_INFLIGHT}"
capacity_qps="${MR_LB_REGION_CAPACITY_QPS}"
capacity_mode_qps="${MR_LB_CAPACITY_MODE_QPS}"
inflight_explicit="false"
qps_explicit="false"
modes="locality capacity"
with_hpa="false"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --arms) arms="${2}" && shift 2 ;;
  --client) client="${2}" && shift 2 ;;
  --qps) qps="${2}" && shift 2 ;;
  --region-capacity-inflight)
    region_capacity_inflight="${2}"
    inflight_explicit="true"
    shift 2
    ;;
  --capacity-mode-inflight)
    capacity_mode_inflight="${2}"
    inflight_explicit="true"
    shift 2
    ;;
  --region-capacity-qps)
    capacity_qps="${2}"
    qps_explicit="true"
    shift 2
    ;;
  --capacity-mode-qps)
    capacity_mode_qps="${2}"
    qps_explicit="true"
    shift 2
    ;;
  --modes) modes="${2}" && shift 2 ;;
  --with-hpa) with_hpa="true" && shift ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done
mr_validate_active_region_key "${client}"
if [[ "${qps_explicit}" == "true" && "${MR_LB_BALANCING_MODE}" != "RATE" ]]; then
  mr_die "--region-capacity-qps/--capacity-mode-qps need MR_LB_BALANCING_MODE=RATE (current: ${MR_LB_BALANCING_MODE}); export it, or use the --*-inflight options"
fi
if [[ "${inflight_explicit}" == "true" && "${MR_LB_BALANCING_MODE}" != "IN_FLIGHT" ]]; then
  mr_die "--region-capacity-inflight/--capacity-mode-inflight need MR_LB_BALANCING_MODE=IN_FLIGHT (current: ${MR_LB_BALANCING_MODE}); unset it, or use the --*-qps options"
fi
if [[ "${with_hpa}" == "true" ]]; then
  export MR_HPA_ENABLED="true"
else
  export MR_HPA_ENABLED="false"
fi
export MR_RUN_ID
export MR_LB_REGION_CAPACITY_INFLIGHT="${region_capacity_inflight}"
export MR_LB_CAPACITY_MODE_INFLIGHT="${capacity_mode_inflight}"
export MR_LB_REGION_CAPACITY_QPS="${capacity_qps}"
export MR_LB_CAPACITY_MODE_QPS="${capacity_mode_qps}"
base_seed="${MR_BENCH_SEED:-42}"
read -r -a arms_arr <<<"${arms}"
read -r -a modes_arr <<<"${modes}"
[[ ${#arms_arr[@]} -gt 0 ]] || mr_die "no arms specified"
[[ ${#modes_arr[@]} -gt 0 ]] || mr_die "no modes specified"
# Validate before the first deployment: an unknown value after the first one
# would otherwise leave held GPU nodes behind.
for a in "${arms_arr[@]}"; do
  [[ "${a}" =~ ^(baseline|llmd)$ ]] || mr_die "unknown arm: ${a} (use baseline and/or llmd)"
done
for m in "${modes_arr[@]}"; do
  [[ "${m}" =~ ^(locality|capacity|zone-spray|preferred)$ ]] ||
    mr_die "unknown mode: ${m} (use locality, capacity, zone-spray, or preferred)"
done

bench() {
  local label="${1}" seed="${2}"
  MR_BENCH_SEED="${seed}" MR_BENCH_SEED_PER_CLIENT=false "${MY_PATH}/run-benchmark.sh" \
    --arm "${label}" --workload shared-prefix --clients "${client}" --qps "${qps}"
}

last_idx=$((${#arms_arr[@]} - 1))
for idx in "${!arms_arr[@]}"; do
  arm="${arms_arr[${idx}]}"
  backend="baseline"
  [[ "${arm}" == "llmd" ]] && backend="ppcr"
  i=0
  for mode in "${modes_arr[@]}"; do
    if [[ "${i}" -eq 0 ]]; then
      "${MY_PATH}/deploy-arm.sh" "${arm}" --backend "${backend}" --lb-mode "${mode}"
    else
      "${MY_PATH}/set-route.sh" --backend "${backend}" --lb-mode "${mode}"
    fi
    # A different seed (so different shared prefixes) for each mode, so that a
    # mode does not hit the prefix cache warmed by the previous one. The same
    # seeds for every arm.
    bench "${arm}-skew-${mode}" $((base_seed + 1000 + 100 * i))
    i=$((i + 1))
  done
  if [[ ${idx} -eq ${last_idx} ]]; then
    "${MY_PATH}/delete-arm.sh" "${arm}"
  else
    "${MY_PATH}/delete-arm.sh" "${arm}" --hold-gpus
  fi
done

out="${MR_RESULTS_DIR}/analysis/${MR_RUN_ID}"
mkdir -p "${out}"
"${MR_PYTHON}" "${MR_EXAMPLE_DIR}/bench/analyze.py" "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}" \
  --baseline-arm "baseline-skew-${modes_arr[0]}" --out "${out}" || mr_log "WARNING: analysis failed"
mr_log "Skew experiment ${MR_RUN_ID} complete. Analysis: ${out}"
