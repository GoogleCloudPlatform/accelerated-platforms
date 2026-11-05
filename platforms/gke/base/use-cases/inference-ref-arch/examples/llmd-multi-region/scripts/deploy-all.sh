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

# Deploys the multi-region environment from scratch and records the wall-clock
# time of every stage:
#   1. shared VPC network and GLOBAL_MANAGED_PROXY subnets,
#   2. every regional platform, in parallel,
#   3. fleet features (only with MR_GLOBAL_LB=mc-gateway),
#   4. benchmark infrastructure (results bucket and IAM),
#   5. model staging in every region, in parallel.
#
# Experiment arms are deployed separately (deploy-arm.sh / run-experiment.sh),
# so that GPUs are only consumed while an arm is being measured.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

export MR_RUN_ID
mr_require_tools
logs="${MR_WORK_DIR}/logs/${MR_RUN_ID}"
mkdir -p "${logs}"
mr_log "Run ${MR_RUN_ID}: logs in ${logs}, timings in ${MR_TIMINGS_FILE}"

# mr_parallel <stage> <script> : runs <script> <key> for every region in parallel.
mr_parallel() {
  local stage="${1}" script="${2}" key pids=() rc=0
  for key in ${MR_REGION_KEYS}; do
    "${MY_PATH}/${script}" "${key}" >"${logs}/${stage}-${key}.log" 2>&1 &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "${pid}" || rc=1; done
  [[ ${rc} -eq 0 ]] || mr_die "${stage} failed in at least one region; see ${logs}/${stage}-*.log"
}

setup_start="$(date +%s.%N)"
"${MY_PATH}/deploy-shared-network.sh"
mr_parallel regions deploy-region.sh
if [[ "${MR_GLOBAL_LB}" == "mc-gateway" ]]; then
  "${MY_PATH}/deploy-fleet.sh"
fi
if [[ -x "${MY_PATH}/deploy-bench-infra.sh" ]]; then
  "${MY_PATH}/deploy-bench-infra.sh"
fi
mr_parallel models stage-model.sh
mr_record_timing "setup_total" "global" "${setup_start}" "$(date +%s.%N)" "ok"

"${MR_PYTHON}" "${MR_EXAMPLE_DIR}/bench/setup_report.py" "${MR_TIMINGS_FILE}" | tee "${MR_RESULTS_DIR}/setup-${MR_RUN_ID}.md"
