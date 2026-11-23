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

# Runs the full experiment matrix, one arm at a time, so that each arm uses the
# same GPUs and GPUs are released between arms:
#
#   arm A (baseline, plain vLLM)       x lb-mode locality: shared-prefix, chat
#                                      x lb-mode capacity: shared-prefix
#   arm B (llm-d)  backend ppcr        x lb-mode locality: shared-prefix, chat
#                  backend ob          x lb-mode locality: shared-prefix, chat
#                  backend ppcr        x lb-mode capacity: shared-prefix
#
# Every benchmark run on pods that already served traffic uses a different
# seed, so that it starts from a cold prefix cache (same prompt distribution,
# different prompts). Runs on fresh pods use the base seed, so the first
# shared-prefix run of each arm sees exactly the same prompts.
#
# Usage: run-experiment.sh [--arms "baseline llmd"] [--workloads "shared-prefix chat"]
#                          [--skip-capacity] [--keep-last-arm] [--with-hpa]
#
# Fixed-replica throughput/SLO comparisons disable the HPA by default so that
# autoscaling doesn't alter replica counts mid-sweep. Pass --with-hpa to keep
# MR_HPA_ENABLED=true.

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
workloads="shared-prefix chat"
capacity="true"
keep_last="false"
with_hpa="false"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --arms) arms="${2}" && shift 2 ;;
  --workloads) workloads="${2}" && shift 2 ;;
  --skip-capacity) capacity="false" && shift ;;
  --keep-last-arm) keep_last="true" && shift ;;
  --with-hpa) with_hpa="true" && shift ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done

if [[ "${with_hpa}" == "true" ]]; then
  export MR_HPA_ENABLED="true"
else
  export MR_HPA_ENABLED="false"
fi
export MR_RUN_ID
base_seed="${MR_BENCH_SEED:-42}"
read -r -a arms_arr <<<"${arms}"
read -r -a workloads_arr <<<"${workloads}"
[[ ${#arms_arr[@]} -gt 0 ]] || mr_die "no arms specified"
[[ ${#workloads_arr[@]} -gt 0 ]] || mr_die "no workloads specified"
# Validate before the first deployment: an unknown arm after the first one would
# otherwise leave held GPU nodes behind.
for a in "${arms_arr[@]}"; do
  [[ "${a}" =~ ^(baseline|llmd)$ ]] || mr_die "unknown arm: ${a} (use baseline and/or llmd)"
done
for w in "${workloads_arr[@]}"; do
  [[ "${w}" =~ ^(shared-prefix|chat)$ ]] || mr_die "unknown workload: ${w} (use shared-prefix and/or chat)"
done

# Deterministic seed offset per (slot, workload): every benchmark run on pods
# that already served traffic uses a distinct seed so it starts from a cold KV
# cache, while matching slots across arms (for example baseline-capacity vs
# llmd-ppcr-capacity) receive identical prompt sequences.
seed_for_slot() {
  local slot="${1}" workload="${2}" offset=0
  case "${slot}:${workload}" in
  locality:shared-prefix) offset=0 ;;
  locality:chat) offset=50 ;;
  ob-locality:shared-prefix) offset=100 ;;
  ob-locality:chat) offset=150 ;;
  capacity:shared-prefix) offset=200 ;;
  *) mr_die "unknown slot/workload: ${slot}:${workload}" ;;
  esac
  echo $((base_seed + offset))
}

# bench <arm_label> <slot> <workload>
bench() {
  local label="${1}" slot="${2}" workload="${3}" seed
  seed="$(seed_for_slot "${slot}" "${workload}")"
  MR_BENCH_SEED="${seed}" "${MY_PATH}/run-benchmark.sh" --arm "${label}" --workload "${workload}"
}

last_arm=""
last_idx=$((${#arms_arr[@]} - 1))
for idx in "${!arms_arr[@]}"; do
  arm="${arms_arr[${idx}]}"
  case "${arm}" in
  baseline)
    "${MY_PATH}/deploy-arm.sh" baseline --lb-mode locality
    for w in "${workloads_arr[@]}"; do bench "baseline-locality" "locality" "${w}"; done
    if [[ "${capacity}" == "true" ]]; then
      "${MY_PATH}/set-route.sh" --backend baseline --lb-mode capacity
      bench "baseline-capacity" "capacity" "shared-prefix"
    fi
    ;;
  llmd)
    "${MY_PATH}/deploy-arm.sh" llmd --backend ppcr --lb-mode locality
    for w in "${workloads_arr[@]}"; do bench "llmd-ppcr-locality" "locality" "${w}"; done
    "${MY_PATH}/set-route.sh" --backend ob --lb-mode locality
    for w in "${workloads_arr[@]}"; do bench "llmd-ob-locality" "ob-locality" "${w}"; done
    if [[ "${capacity}" == "true" ]]; then
      "${MY_PATH}/set-route.sh" --backend ppcr --lb-mode capacity
      bench "llmd-ppcr-capacity" "capacity" "shared-prefix"
    fi
    ;;
  *) mr_die "unknown arm: ${arm}" ;;
  esac
  last_arm="${arm}"
  if [[ ${idx} -lt ${last_idx} ]]; then
    # Keep the GPU nodes for the next arm.
    "${MY_PATH}/delete-arm.sh" "${arm}" --hold-gpus
  elif [[ "${keep_last}" != "true" ]]; then
    "${MY_PATH}/delete-arm.sh" "${arm}"
  fi
done

out="${MR_RESULTS_DIR}/analysis/${MR_RUN_ID}"
mkdir -p "${out}"
"${MR_PYTHON}" "${MR_EXAMPLE_DIR}/bench/analyze.py" "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}" \
  --baseline-arm baseline-locality --out "${out}" || mr_log "WARNING: analysis failed"
for arm in "${arms_arr[@]}"; do
  for key in ${MR_REGION_KEYS}; do
    d="${MR_RESULTS_DIR}/startup/${MR_RUN_ID}/${arm}/${key}"
    [[ -d "${d}" ]] && "${MR_PYTHON}" "${MR_EXAMPLE_DIR}/bench/startup_report.py" "${d}" --out "${out}/startup-${arm}-${key}" || true
  done
done
"${MR_PYTHON}" "${MR_EXAMPLE_DIR}/bench/setup_report.py" "${MR_TIMINGS_FILE}" >"${out}/timings.md" || true
mr_log "Experiment ${MR_RUN_ID} complete (last arm: ${last_arm}). Analysis: ${out}"
