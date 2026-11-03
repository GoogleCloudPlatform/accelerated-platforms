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
#                          [--skip-capacity] [--keep-last-arm]

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
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --arms) arms="${2}" && shift 2 ;;
  --workloads) workloads="${2}" && shift 2 ;;
  --skip-capacity) capacity="false" && shift ;;
  --keep-last-arm) keep_last="true" && shift ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done

export MR_RUN_ID
base_seed="${MR_BENCH_SEED:-42}"
seed_offset=0

# bench <arm_label> <workload>
bench() {
  local label="${1}" workload="${2}" seed
  if [[ "${workload}" == "shared-prefix" ]]; then
    seed=$((base_seed + seed_offset))
    seed_offset=$((seed_offset + 100))
  else
    seed="${base_seed}"
  fi
  MR_BENCH_SEED="${seed}" "${MY_PATH}/run-benchmark.sh" --arm "${label}" --workload "${workload}"
}

last_arm=""
for arm in ${arms}; do
  seed_offset=0
  case "${arm}" in
  baseline)
    "${MY_PATH}/deploy-arm.sh" baseline --lb-mode locality
    for w in ${workloads}; do bench "baseline-locality" "${w}"; done
    if [[ "${capacity}" == "true" ]]; then
      "${MY_PATH}/set-route.sh" --backend baseline --lb-mode capacity
      bench "baseline-capacity" "shared-prefix"
    fi
    ;;
  llmd)
    "${MY_PATH}/deploy-arm.sh" llmd --backend ppcr --lb-mode locality
    for w in ${workloads}; do bench "llmd-ppcr-locality" "${w}"; done
    "${MY_PATH}/set-route.sh" --backend ob --lb-mode locality
    for w in ${workloads}; do bench "llmd-ob-locality" "${w}"; done
    if [[ "${capacity}" == "true" ]]; then
      "${MY_PATH}/set-route.sh" --backend ppcr --lb-mode capacity
      bench "llmd-ppcr-capacity" "shared-prefix"
    fi
    ;;
  *) mr_die "unknown arm: ${arm}" ;;
  esac
  last_arm="${arm}"
  if [[ "${arm}" != "${arms##* }" ]]; then
    # Keep the GPU nodes for the next arm.
    "${MY_PATH}/delete-arm.sh" "${arm}" --hold-gpus
  elif [[ "${keep_last}" != "true" ]]; then
    "${MY_PATH}/delete-arm.sh" "${arm}"
  fi
done

out="${MR_RESULTS_DIR}/analysis/${MR_RUN_ID}"
mkdir -p "${out}"
python3 "${MR_EXAMPLE_DIR}/bench/analyze.py" "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}" \
  --baseline-arm baseline-locality --out "${out}" || mr_log "WARNING: analysis failed"
for arm in ${arms}; do
  for key in ${MR_REGION_KEYS}; do
    d="${MR_RESULTS_DIR}/startup/${MR_RUN_ID}/${arm}/${key}"
    [[ -d "${d}" ]] && python3 "${MR_EXAMPLE_DIR}/bench/startup_report.py" "${d}" --out "${out}/startup-${arm}-${key}" || true
  done
done
python3 "${MR_EXAMPLE_DIR}/bench/setup_report.py" "${MR_TIMINGS_FILE}" >"${out}/timings.md" || true
mr_log "Experiment ${MR_RUN_ID} complete (last arm: ${last_arm}). Analysis: ${out}"
