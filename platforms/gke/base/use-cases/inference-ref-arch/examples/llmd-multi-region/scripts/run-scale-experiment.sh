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

# Scale-out experiment: deploys one arm (llm-d by default) in every region with
# a Horizontal Pod Autoscaler (MR_REPLICAS_PER_REGION .. MR_HPA_MAX_REPLICAS),
# then drives load from the clients of every region so that the HPA scales each
# region out, while bench/record_scaling.py records the autoscaling timeline.
#
# Default load, per client region, MR_SCALE_STAGE_DURATION_S (300 s) per stage:
#   3 QPS          warm-up, within the capacity of MR_REPLICAS_PER_REGION
#   8 8 8 8 QPS    hammer: about twice that capacity, so that requests queue in
#                  vLLM and the HPA scales out to MR_HPA_MAX_REPLICAS
#   2 2 QPS        cool-down, to observe the scale-in
#
# Usage: run-scale-experiment.sh [--arm llmd|baseline] [--backend ppcr|ob]
#                                [--qps "3 8 8 8 8 2 2"] [--clients "<keys>"]
#                                [--keep]
#
# --keep leaves the arm deployed (at its current scale) afterwards.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
# shellcheck source=/dev/null
source "${MY_PATH}/lib.sh"

arm="llmd"
backend="ppcr"
qps="3 8 8 8 8 2 2"
clients="${MR_REGION_KEYS}"
keep="false"
while [[ $# -gt 0 ]]; do
  case "${1}" in
  --arm) arm="${2}" && shift 2 ;;
  --backend) backend="${2}" && shift 2 ;;
  --qps) qps="${2}" && shift 2 ;;
  --clients) clients="${2}" && shift 2 ;;
  --keep) keep="true" && shift ;;
  *) mr_die "unknown argument: ${1}" ;;
  esac
done
[[ "${arm}" == "baseline" ]] && backend="baseline"
[[ "${MR_HPA_ENABLED}" == "true" ]] || mr_die "MR_HPA_ENABLED must be true for a scale-out experiment"
export MR_RUN_ID

out="${MR_RESULTS_DIR}/scale/${MR_RUN_ID}"
mkdir -p "${out}"
recorder="${out}/recorder.jsonl"
label="${arm}-scale"
deployment="precise-prefix-cache-routing-gpu-vllm-decode-${arm}"

"${MY_PATH}/deploy-arm.sh" "${arm}" --backend "${backend}" --lb-mode locality

# The HPA needs the queue metric before it can scale (up to a few minutes after
# the pods start serving).
hpa_has_metric() {
  local key="${1}" v
  v="$(mr_kubectl "${key}" get hpa "${deployment}" -n "${MR_NAMESPACE}" \
    -o jsonpath='{.status.currentMetrics[0].pods.current.averageValue}' 2>/dev/null)"
  [[ -n "${v}" ]]
}
for key in ${MR_REGION_KEYS}; do
  mr_stage "hpa_metric_available/${arm}" "region/${key}" \
    mr_wait_for 900 15 "HPA metric in ${key}" hpa_has_metric "${key}" ||
    mr_log "WARNING: the HPA in ${key} has no metric yet; it can't scale until it does"
done

regions=()
for key in ${MR_REGION_KEYS}; do regions+=("${key}=$(mr_kubeconfig "${key}")"); done
rm -f "${recorder}.stop"
python3 "${MR_EXAMPLE_DIR}/bench/record_scaling.py" "${recorder}" "${MR_NAMESPACE}" "${arm}" "${regions[@]}" \
  >"${out}/recorder.log" 2>&1 &
recorder_pid=$!
stop_recorder() {
  touch "${recorder}.stop"
  wait "${recorder_pid}" 2>/dev/null || true
}
trap stop_recorder EXIT

rc=0
"${MY_PATH}/run-benchmark.sh" --arm "${label}" --workload shared-prefix --clients "${clients}" --qps "${qps}" \
  --stage-duration "${MR_SCALE_STAGE_DURATION_S:-300}" || rc=$?

# Keep recording for the scale-in after the last stage.
mr_log "Recording the scale-in for MR_SCALE_TAIL_S=${MR_SCALE_TAIL_S:-120} s"
sleep "${MR_SCALE_TAIL_S:-120}"
stop_recorder
trap - EXIT

for key in ${MR_REGION_KEYS}; do
  mkdir -p "${out}/${key}"
  mr_kubectl "${key}" get hpa,deployment,pods -n "${MR_NAMESPACE}" -o json >"${out}/${key}/objects.json" || true
  mr_kubectl "${key}" get events -n "${MR_NAMESPACE}" -o json >"${out}/${key}/events.json" || true
  mr_kubectl "${key}" describe hpa "${deployment}" -n "${MR_NAMESPACE}" >"${out}/${key}/hpa-describe.txt" 2>&1 || true
done

analysis="${MR_RESULTS_DIR}/analysis/${MR_RUN_ID}"
python_bin="${MR_PYTHON:-python3}"
"${python_bin}" "${MR_EXAMPLE_DIR}/bench/scale_report.py" \
  --runs "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}/${label}" --recorder "${recorder}" --out "${analysis}" \
  --project "${MR_PROJECT_ID}" --cluster-regex "${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}.*" \
  --namespace "${MR_NAMESPACE}" || mr_log "WARNING: scale report failed"

if [[ "${keep}" != "true" ]]; then
  "${MY_PATH}/delete-arm.sh" "${arm}"
fi
mr_log "Scale experiment ${MR_RUN_ID} complete (benchmark exit code ${rc}). Report: ${analysis}/report.md"
exit "${rc}"
