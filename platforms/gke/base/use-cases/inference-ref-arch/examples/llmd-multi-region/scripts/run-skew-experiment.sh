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
#             reaches MR_LB_REGION_CAPACITY_QPS, then spill over
#   capacity  WATERFALL_BY_REGION with a low region capacity
#             (MR_LB_CAPACITY_MODE_QPS): spill over early and spread traffic
#             across both regions (more accelerators, plus cross-region latency
#             for part of the requests)
#
# for each arm (plain vLLM baseline and llm-d precise prefix cache routing).
# Any mode of set-route.sh can be listed in --modes (for example zone-spray).
#
# Usage: run-skew-experiment.sh [--arms "baseline llmd"] [--client usc1]
#                               [--qps "2 4 6 8"] [--capacity-qps 3]
#                               [--modes "locality capacity"]

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
client="${MR_CONFIG_CLUSTER_KEY}"
qps="2 4 6 8"
capacity_qps="${MR_LB_REGION_CAPACITY_QPS}"
modes="locality capacity"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --arms) arms="${2}" && shift 2 ;;
  --client) client="${2}" && shift 2 ;;
  --qps) qps="${2}" && shift 2 ;;
  --capacity-qps) capacity_qps="${2}" && shift 2 ;;
  --modes) modes="${2}" && shift 2 ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done
mr_validate_region_key "${client}"
export MR_RUN_ID MR_LB_REGION_CAPACITY_QPS="${capacity_qps}"
base_seed="${MR_BENCH_SEED:-42}"

bench() {
  local label="${1}" seed="${2}"
  MR_BENCH_SEED="${seed}" MR_BENCH_SEED_PER_CLIENT=false "${MY_PATH}/run-benchmark.sh" \
    --arm "${label}" --workload shared-prefix --clients "${client}" --qps "${qps}"
}

for arm in ${arms}; do
  backend="baseline"
  [[ "${arm}" == "llmd" ]] && backend="ppcr"
  i=0
  for mode in ${modes}; do
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
  if [[ "${arm}" == "${arms##* }" ]]; then
    "${MY_PATH}/delete-arm.sh" "${arm}"
  else
    "${MY_PATH}/delete-arm.sh" "${arm}" --hold-gpus
  fi
done

out="${MR_RESULTS_DIR}/analysis/${MR_RUN_ID}"
mkdir -p "${out}"
python3 "${MR_EXAMPLE_DIR}/bench/analyze.py" "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}" \
  --baseline-arm "baseline-skew-${modes%% *}" --out "${out}" || mr_log "WARNING: analysis failed"
mr_log "Skew experiment ${MR_RUN_ID} complete. Analysis: ${out}"
