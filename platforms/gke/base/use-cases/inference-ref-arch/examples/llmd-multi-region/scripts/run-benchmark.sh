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

# Runs one benchmark (one arm x one workload) with one inference-perf client
# Job per client region, all clients concurrently, against the regional
# internal VIPs of the load balancer (MR_GLOBAL_LB). With more than one client
# region, a start barrier releases Stage 0 in every region at the same time
# (MR_BENCH_SYNC_START). Collects Job logs and the inference-perf reports into
# ${MR_RESULTS_DIR}/runs/${MR_RUN_ID}/<arm>/<workload>/<client>/.
#
# See bench/README.md.

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
# shellcheck source=/dev/null
source "${MY_PATH}/bench-lib.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") --arm <label> --workload <shared-prefix|chat> [options]

Required:
  --arm <label>             Experiment arm label for bookkeeping, for example
                            "vllm" or "llmd" ([a-z0-9-], at most 30 characters).
                            The HTTPRoute backend must already point at this arm.
  --workload <name>         shared-prefix | chat

Options:
  --clients "<keys>"        Client region keys (default: "${MR_REGION_KEYS}").
  --gateway <name>          Multi-cluster Gateway name (default: ${MR_BENCH_GATEWAY}).
  --target-region <target>  Which regional VIP each client sends requests to:
                              local  - the client's own region (default)
                              cross  - the next region in MR_REGION_KEYS
                              <key>  - this region, for every client
  --qps "<rates>"           Request rates per client, one stage each
                            (default: "${MR_BENCH_QPS}").
  --stage-duration <s>      Duration of each stage (default: ${MR_BENCH_STAGE_DURATION_S}).
  --force                   Delete existing results for this run, arm, and
                            workload (local and in Cloud Storage) first.
  --dry-run                 Render the manifests only.
  -h, --help                Show this help.
EOF
}

arm=""
workload=""
clients="${MR_REGION_KEYS}"
gateway="${MR_BENCH_GATEWAY}"
target_mode="local"
force=false
dry_run=false

need_value() {
  [[ $# -ge 2 && -n "${2}" ]] || mr_die "option ${1} requires a value"
}

while [[ $# -gt 0 ]]; do
  case "${1}" in
  --arm)
    need_value "$@"
    arm="${2}"
    shift 2
    ;;
  --workload)
    need_value "$@"
    workload="${2}"
    shift 2
    ;;
  --clients)
    need_value "$@"
    clients="${2}"
    shift 2
    ;;
  --gateway)
    need_value "$@"
    gateway="${2}"
    shift 2
    ;;
  --target-region)
    need_value "$@"
    target_mode="${2}"
    shift 2
    ;;
  --qps)
    need_value "$@"
    MR_BENCH_QPS="${2}"
    shift 2
    ;;
  --stage-duration)
    need_value "$@"
    MR_BENCH_STAGE_DURATION_S="${2}"
    shift 2
    ;;
  --force)
    force=true
    shift
    ;;
  --dry-run)
    dry_run=true
    shift
    ;;
  -h | --help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    mr_die "unknown argument: ${1}"
    ;;
  esac
done

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
[[ -n "${arm}" ]] || {
  usage >&2
  mr_die "--arm is required"
}
[[ "${arm}" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ && ${#arm} -le 30 ]] ||
  mr_die "invalid --arm '${arm}': use [a-z0-9-], at most 30 characters"
case "${workload}" in
shared-prefix) workload_short="sp" ;;
chat) workload_short="chat" ;;
*)
  usage >&2
  mr_die "--workload must be shared-prefix or chat"
  ;;
esac
[[ "${MR_BENCH_STAGE_DURATION_S}" =~ ^[1-9][0-9]*$ ]] || mr_die "invalid stage duration '${MR_BENCH_STAGE_DURATION_S}'"
[[ "${MR_BENCH_SYNC_TIMEOUT_S}" =~ ^[1-9][0-9]*$ ]] ||
  mr_die "invalid MR_BENCH_SYNC_TIMEOUT_S '${MR_BENCH_SYNC_TIMEOUT_S}': use a whole number of seconds"
[[ "${MR_BENCH_LOAD_TYPE}" == "poisson" || "${MR_BENCH_LOAD_TYPE}" == "constant" ]] ||
  mr_die "MR_BENCH_LOAD_TYPE must be poisson or constant"

read -r -a client_keys <<<"${clients}"
[[ ${#client_keys[@]} -gt 0 ]] || mr_die "no clients"
read -r -a region_keys <<<"${MR_REGION_KEYS}"
for key in "${client_keys[@]}"; do
  mr_validate_active_region_key "${key}"
done
case "${target_mode}" in
local | cross) ;;
*) mr_validate_active_region_key "${target_mode}" ;;
esac

sync_start="false"
case "${MR_BENCH_SYNC_START}" in
auto) [[ ${#client_keys[@]} -gt 1 ]] && sync_start="true" ;;
true | false) sync_start="${MR_BENCH_SYNC_START}" ;;
*) mr_die "MR_BENCH_SYNC_START must be auto, true, or false" ;;
esac

if [[ "${dry_run}" == "true" ]]; then
  for tool in envsubst jq "${MR_PYTHON}"; do
    command -v "${tool}" >/dev/null 2>&1 || mr_die "missing required tool: ${tool}"
  done
else
  mr_require_example_tools
  declare -F mr_gateway_vip >/dev/null || mr_die "mr_gateway_vip is not defined in lib.sh"
fi

# target_key <client_key>
target_key() {
  local client="${1}" i
  case "${target_mode}" in
  local) echo "${client}" ;;
  cross)
    [[ ${#region_keys[@]} -ge 2 ]] || mr_die "--target-region cross needs at least two regions in MR_REGION_KEYS"
    for i in "${!region_keys[@]}"; do
      if [[ "${region_keys[${i}]}" == "${client}" ]]; then
        echo "${region_keys[$(((i + 1) % ${#region_keys[@]}))]}"
        return
      fi
    done
    mr_die "client ${client} is not in MR_REGION_KEYS"
    ;;
  *) echo "${target_mode}" ;;
  esac
}

# ---------------------------------------------------------------------------
# Run layout
# ---------------------------------------------------------------------------
bucket="$(mr_bench_bucket)"
run_rel="runs/${MR_RUN_ID}/${arm}/${workload}"
run_dir="${MR_RESULTS_DIR}/${run_rel}"
read -r -a qps_list <<<"${MR_BENCH_QPS}"
stages="$(mr_bench_stages "${MR_BENCH_STAGE_DURATION_S}" "${qps_list[@]}")"
job_timeout="${MR_BENCH_JOB_TIMEOUT_S:-$(mr_bench_default_timeout "${#qps_list[@]}")}"

if [[ -e "${run_dir}" ]]; then
  [[ "${force}" == "true" ]] || mr_die "${run_dir} already exists. Use a new MR_RUN_ID or --force."
  rm -rf "${run_dir}"
fi

if [[ "${dry_run}" != "true" ]]; then
  gcloud storage buckets describe "gs://${bucket}" --project "${MR_PROJECT_ID}" >/dev/null 2>&1 ||
    mr_die "results bucket gs://${bucket} not found. Run scripts/deploy-bench-infra.sh first."
  # inference-perf skips uploading a report whose object already exists, so a
  # stale prefix would silently mix results from different runs.
  if gcloud storage ls "gs://${bucket}/${run_rel}/" >/dev/null 2>&1; then
    [[ "${force}" == "true" ]] || mr_die "gs://${bucket}/${run_rel}/ already exists. Use a new MR_RUN_ID or --force."
    gcloud storage rm -r "gs://${bucket}/${run_rel}/"
  fi
  for key in "${client_keys[@]}"; do
    mr_kubectl "${key}" -n "${MR_NAMESPACE}" get serviceaccount "${MR_NAMESPACE}" >/dev/null ||
      mr_die "service account ${MR_NAMESPACE}/${MR_NAMESPACE} not found in $(mr_cluster_name "${key}")"
    if [[ "${MR_BENCH_COMPUTE_CLASS}" == "${MR_NAMESPACE}-bench-cpu" ]]; then
      dst_common="${MR_WORK_DIR}/rendered/${key}/common"
      mr_render_dir "${MR_EXAMPLE_DIR}/manifests/common" "${dst_common}"
      mr_kubectl "${key}" apply -f "${dst_common}/compute-class-bench.yaml" >/dev/null
    fi
  done
fi

# Resolve each target region's Gateway VIP once.
declare -A vip_by_key=()
for key in "${client_keys[@]}"; do
  tkey="$(target_key "${key}")"
  [[ -n "${vip_by_key[${tkey}]:-}" ]] && continue
  if [[ "${dry_run}" == "true" ]]; then
    vip_by_key[${tkey}]="$( (declare -F mr_gateway_vip >/dev/null && mr_gateway_vip "${gateway}" "${tkey}") 2>/dev/null || echo "192.0.2.1")"
  else
    vip_by_key[${tkey}]="$(mr_gateway_vip "${gateway}" "${tkey}")"
    [[ -n "${vip_by_key[${tkey}]}" ]] || mr_die "no VIP for Gateway ${gateway} in region ${tkey}"
  fi
  mr_log "Gateway ${gateway} VIP in ${tkey}: ${vip_by_key[${tkey}]}"
done

# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
job_name() { echo "ipf-${arm}-${workload_short}-${1}"; }

# render_client <client_key> <client_index>
render_client() {
  local client="${1}" index="${2}"
  local dir="${run_dir}/${client}"
  local manifests="${dir}/manifests"
  local tkey seed vars template
  tkey="$(target_key "${client}")"
  seed="${MR_BENCH_SEED}"
  [[ "${MR_BENCH_SEED_PER_CLIENT}" == "true" ]] && seed=$((MR_BENCH_SEED + index))
  mkdir -p "${manifests}" "${dir}/logs" "${dir}/reports"

  export BENCH_ARM="${arm}"
  export BENCH_BASE_URL="http://${vip_by_key[${tkey}]}:${MR_BENCH_GATEWAY_PORT}"
  export BENCH_BUCKET="${bucket}"
  export BENCH_CHAT_INPUT_MAX="${MR_BENCH_CHAT_INPUT_MAX}"
  export BENCH_CHAT_INPUT_MEAN="${MR_BENCH_CHAT_INPUT_MEAN}"
  export BENCH_CHAT_INPUT_MIN="${MR_BENCH_CHAT_INPUT_MIN}"
  export BENCH_CHAT_INPUT_STD_DEV="${MR_BENCH_CHAT_INPUT_STD_DEV}"
  export BENCH_CHAT_NUM_PROMPTS="${MR_BENCH_CHAT_NUM_PROMPTS}"
  export BENCH_CHAT_OUTPUT_LEN="${MR_BENCH_CHAT_OUTPUT_LEN}"
  export BENCH_CLIENT="${client}"
  # shellcheck disable=SC2153
  export BENCH_CPU="${MR_BENCH_CPU}"
  export BENCH_GCS_PATH="${run_rel}/${client}"
  export BENCH_GMP_SCRAPE_INTERVAL_S="${MR_BENCH_GMP_SCRAPE_INTERVAL_S}"
  export BENCH_IMAGE="${MR_INFERENCE_PERF_IMAGE}"
  export BENCH_JOB_NAME
  BENCH_JOB_NAME="$(job_name "${client}")"
  export BENCH_JOB_TIMEOUT_S="${job_timeout}"
  export BENCH_LOAD_TYPE="${MR_BENCH_LOAD_TYPE}"
  export BENCH_MEMORY="${MR_BENCH_MEMORY}"
  export BENCH_MODELS_BUCKET
  BENCH_MODELS_BUCKET="$(mr_models_bucket "${client}")"
  export BENCH_MODEL_NAME="${MR_SERVED_MODEL_NAME}"
  # The regional model bucket holds the served model's tokenizer; any other
  # MR_BENCH_TOKENIZER is downloaded from Hugging Face by inference-perf.
  export BENCH_MODEL_PATH=""
  if [[ "${MR_BENCH_TOKENIZER}" == "${MR_HF_MODEL_ID}" ]]; then
    BENCH_MODEL_PATH="${MR_MODEL_PATH}"
  fi
  export BENCH_NAMESPACE="${MR_NAMESPACE}"
  export BENCH_NODE_SELECTOR="{}"
  if [[ -n "${MR_BENCH_COMPUTE_CLASS}" ]]; then
    BENCH_NODE_SELECTOR="{\"cloud.google.com/compute-class\": \"${MR_BENCH_COMPUTE_CLASS}\"}"
  fi
  export BENCH_NUM_WORKERS="${MR_BENCH_NUM_WORKERS}"
  export BENCH_REQUEST_TIMEOUT_S="${MR_BENCH_REQUEST_TIMEOUT_S}"
  export BENCH_RUN_ID="${MR_RUN_ID}"
  export BENCH_SEED="${seed}"
  export BENCH_SERVICE_ACCOUNT="${MR_NAMESPACE}"
  export BENCH_SLO_TPOT_S="${MR_BENCH_SLO_TPOT_S}"
  export BENCH_SLO_TTFT_S="${MR_BENCH_SLO_TTFT_S}"
  export BENCH_SP_NUM_GROUPS="${MR_BENCH_SP_NUM_GROUPS}"
  export BENCH_SP_OUTPUT_LEN="${MR_BENCH_SP_OUTPUT_LEN}"
  export BENCH_SP_PROMPTS_PER_GROUP="${MR_BENCH_SP_PROMPTS_PER_GROUP}"
  export BENCH_SP_QUESTION_LEN="${MR_BENCH_SP_QUESTION_LEN}"
  export BENCH_SP_SYSTEM_PROMPT_LEN="${MR_BENCH_SP_SYSTEM_PROMPT_LEN}"
  export BENCH_STAGE_INTERVAL_S="${MR_BENCH_STAGE_INTERVAL_S}"
  export BENCH_STAGES="${stages}"
  export BENCH_SYNC_START="${sync_start}"
  # The harness times out first (release_start_barrier), with the clearer
  # message; the pod-side timeout only guards against a lost harness.
  export BENCH_SYNC_TIMEOUT_S="$((MR_BENCH_SYNC_TIMEOUT_S + 120))"
  export BENCH_TOKENIZER="${MR_BENCH_TOKENIZER}"
  export BENCH_WORKER_MAX_CONCURRENCY="${MR_BENCH_WORKER_MAX_CONCURRENCY}"
  export BENCH_WORKLOAD="${workload}"

  # Substitute only BENCH_* variables.
  vars="$(compgen -v BENCH_ | sed 's/^/${/; s/$/}/' | tr '\n' ' ')"

  local templates=("common" "${workload}")
  [[ "${MR_BENCH_GMP}" == "true" ]] && templates+=("metrics-gmp")
  {
    echo "# Generated by run-benchmark.sh for ${MR_INFERENCE_PERF_IMAGE}"
    echo "# run=${MR_RUN_ID} arm=${arm} workload=${workload} client=${client} target=${tkey}"
    for template in "${templates[@]}"; do
      echo
      grep -v '^#' "${MR_BENCH_DIR}/workloads/${template}.yaml.tmpl" | envsubst "${vars}"
    done
  } | cat -s >"${manifests}/config.yaml"

  {
    cat <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${BENCH_JOB_NAME}
  namespace: ${BENCH_NAMESPACE}
  labels:
    app.kubernetes.io/name: inference-perf
    app.kubernetes.io/part-of: llmd-multi-region-bench
    bench.llmd-multi-region/run-id: "${BENCH_RUN_ID}"
data:
  config.yaml: |
EOF
    sed 's/^/    /' "${manifests}/config.yaml"
    echo "  entrypoint.py: |"
    sed 's/^/    /' "${MR_BENCH_DIR}/entrypoint.py"
  } >"${manifests}/00-configmap.yaml"

  envsubst "${vars}" <"${MR_BENCH_DIR}/manifests/job.yaml.tmpl" >"${manifests}/10-job.yaml"

  # shellcheck disable=SC2016 # literal ${ marks an unrendered variable
  if grep -n '\${' "${manifests}/config.yaml" "${manifests}/10-job.yaml"; then
    mr_die "unrendered variables in ${manifests}"
  fi

  jq -n \
    --arg key "${client}" \
    --arg region "$(mr_region "${client}")" \
    --arg cluster "$(mr_cluster_name "${client}")" \
    --arg target_key "${tkey}" \
    --arg target_region "$(mr_region "${tkey}")" \
    --arg vip "${vip_by_key[${tkey}]}" \
    --arg base_url "${BENCH_BASE_URL}" \
    --arg job "${BENCH_JOB_NAME}" \
    --argjson seed "${seed}" \
    --arg gcs_uri "gs://${bucket}/${BENCH_GCS_PATH}/" \
    '{key: $key, region: $region, cluster: $cluster, target_key: $target_key,
      target_region: $target_region, vip: $vip, base_url: $base_url, job: $job,
      seed: $seed, gcs_uri: $gcs_uri, status: "rendered"}' >"${dir}/client.json"
}

# ---------------------------------------------------------------------------
# Execution and collection (one background subshell per client)
# ---------------------------------------------------------------------------
# wait_job <client_key> <job_name>
wait_job() {
  local client="${1}" job="${2}" conditions
  local deadline=$(($(date +%s) + job_timeout + 300))
  while true; do
    conditions="$(mr_kubectl "${client}" -n "${MR_NAMESPACE}" get job "${job}" \
      -o jsonpath='{range .status.conditions[?(@.status=="True")]}{.type}{" "}{end}' 2>/dev/null)" || conditions=""
    case " ${conditions} " in
    *" Complete "*) return 0 ;;
    *" Failed "*)
      mr_log "Job ${job} in ${client} failed"
      return 1
      ;;
    esac
    if [[ $(date +%s) -ge ${deadline} ]]; then
      mr_log "timed out waiting for Job ${job} in ${client}"
      return 1
    fi
    sleep 15
  done
}

# collect_logs <client_key> <job_name> <logs_dir>
collect_logs() {
  local client="${1}" job="${2}" logs="${3}" pod
  mr_kubectl "${client}" -n "${MR_NAMESPACE}" get job "${job}" -o json >"${logs}/job.json" || true
  mr_kubectl "${client}" -n "${MR_NAMESPACE}" get pods -l "job-name=${job}" -o json >"${logs}/pods.json" || true
  mr_kubectl "${client}" -n "${MR_NAMESPACE}" get events -o json >"${logs}/events.json" || true
  for pod in $(mr_kubectl "${client}" -n "${MR_NAMESPACE}" get pods -l "job-name=${job}" -o name 2>/dev/null); do
    mr_kubectl "${client}" -n "${MR_NAMESPACE}" logs "${pod}" --all-containers --timestamps \
      >"${logs}/${pod#pod/}.log" 2>&1 || true
  done
}

# download_reports <client_key>
download_reports() {
  local client="${1}"
  local dest="${run_dir}/${client}/reports"
  gcloud storage cp -r "gs://${bucket}/${run_rel}/${client}/*" "${dest}/" &&
    [[ -s "${dest}/summary_lifecycle_metrics.json" ]] ||
    {
      mr_log "no summary_lifecycle_metrics.json in gs://${bucket}/${run_rel}/${client}/"
      return 1
    }
}

# apply_client <client_key>
apply_client() {
  local client="${1}"
  local dir="${run_dir}/${client}" job
  job="$(job_name "${client}")"
  date +%s >"${dir}/start.epoch"
  mr_kubectl "${client}" -n "${MR_NAMESPACE}" delete job "${job}" --ignore-not-found --wait=true >/dev/null 2>&1 || true
  mr_stage "bench_apply_${arm}_${workload}" "${client}" \
    mr_kubectl "${client}" apply -f "${dir}/manifests/00-configmap.yaml" -f "${dir}/manifests/10-job.yaml"
}

# release_start_barrier
# Waits until every client pod has staged its tokenizer (/tmp/bench-ready), then
# signals /tmp/bench-go in all client pods at once, so that Stage 0 starts at the
# same time in every region regardless of node scale-up or image pulls. Later
# stages can still drift by the per-stage drain time.
release_start_barrier() {
  local deadline=$(($(date +%s) + MR_BENCH_SYNC_TIMEOUT_S))
  local -A ready_pods=()
  local key job conditions pod all_ready missing pids=() rc=0
  while true; do
    all_ready="true"
    for key in "${client_keys[@]}"; do
      job="$(job_name "${key}")"
      conditions="$(mr_kubectl "${key}" -n "${MR_NAMESPACE}" get job "${job}" \
        -o jsonpath='{range .status.conditions[?(@.status=="True")]}{.type}{" "}{end}' 2>/dev/null || true)"
      if [[ " ${conditions} " == *" Failed "* ]]; then
        mr_log "Job ${job} in ${key} failed before start barrier"
        return 1
      fi
      if [[ -n "${ready_pods[${key}]:-}" ]]; then
        continue
      fi
      pod="$(mr_kubectl "${key}" -n "${MR_NAMESPACE}" get pods -l "job-name=${job}" \
        --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
      if [[ -n "${pod}" ]] && mr_kubectl "${key}" -n "${MR_NAMESPACE}" exec "${pod}" -- test -f /tmp/bench-ready >/dev/null 2>&1; then
        ready_pods[${key}]="${pod}"
        mr_log "Client pod ${pod} (${key}) ready at start barrier"
      else
        all_ready="false"
      fi
    done
    if [[ "${all_ready}" == "true" ]]; then
      break
    fi
    if [[ $(date +%s) -ge ${deadline} ]]; then
      missing=()
      for key in "${client_keys[@]}"; do
        [[ -n "${ready_pods[${key}]:-}" ]] || missing+=("${key}")
      done
      mr_log "timed out after ${MR_BENCH_SYNC_TIMEOUT_S}s waiting for the client pods in: ${missing[*]}" \
        "(not running, or tokenizer not staged); see ${run_dir}/<client>/logs/"
      return 1
    fi
    sleep 3
  done
  # Retry each signal: one transient exec error must not leave the other
  # regions running alone.
  for key in "${client_keys[@]}"; do
    (
      for _ in 1 2 3; do
        mr_kubectl "${key}" -n "${MR_NAMESPACE}" exec "${ready_pods[${key}]}" -- touch /tmp/bench-go >/dev/null && exit 0
        sleep 1
      done
      exit 1
    ) &
    pids+=("$!")
  done
  for pid in "${pids[@]}"; do
    wait "${pid}" || rc=1
  done
  return "${rc}"
}

# finish_client <client_key> <barrier_ok>
finish_client() {
  local client="${1}" barrier_ok="${2}"
  local dir="${run_dir}/${client}" job start end status="failed"
  job="$(job_name "${client}")"
  start="$(cat "${dir}/start.epoch" 2>/dev/null || date +%s)"
  rm -f "${dir}/start.epoch"

  if [[ "${barrier_ok}" == "true" ]]; then
    if mr_stage "bench_run_${arm}_${workload}" "${client}" wait_job "${client}" "${job}"; then
      status="succeeded"
    fi
  fi
  collect_logs "${client}" "${job}" "${dir}/logs"
  if [[ "${status}" == "succeeded" ]]; then
    if ! mr_stage "bench_download_${arm}_${workload}" "${client}" download_reports "${client}"; then
      status="failed"
    fi
  fi
  mr_kubectl "${client}" delete --ignore-not-found --wait=false \
    -f "${dir}/manifests/10-job.yaml" -f "${dir}/manifests/00-configmap.yaml" >/dev/null || true
  end="$(date +%s)"

  local images="[]"
  if [[ -s "${dir}/logs/pods.json" ]]; then
    images="$(jq -c '[.items[].status.containerStatuses[]? | {image, imageID}]' "${dir}/logs/pods.json" 2>/dev/null || echo "[]")"
  fi
  jq --arg status "${status}" --argjson start "${start}" --argjson end "${end}" --argjson images "${images}" \
    '. + {status: $status, start_epoch_s: $start, end_epoch_s: $end, images: $images}' \
    "${dir}/client.json" >"${dir}/client.json.tmp" && mv "${dir}/client.json.tmp" "${dir}/client.json"
  [[ "${status}" == "succeeded" ]]
}

# write_run_metadata <status>
write_run_metadata() {
  local status="${1}" git_commit git_dirty=0
  git_commit="$(git -C "${ACP_REPO_DIR}" rev-parse HEAD 2>/dev/null || echo "unknown")"
  if [[ -n "$(git -C "${ACP_REPO_DIR}" status --porcelain 2>/dev/null || true)" ]]; then
    git_dirty=1
  fi
  RUN_STATUS="${status}" RUN_ARM="${arm}" RUN_WORKLOAD="${workload}" RUN_GATEWAY="${gateway}" \
    RUN_TARGET_MODE="${target_mode}" RUN_CLIENTS="${client_keys[*]}" RUN_DIR="${run_dir}" \
    RUN_BUCKET="${bucket}" RUN_REL="${run_rel}" RUN_START="${run_start}" RUN_END="$(date +%s)" \
    RUN_GIT_COMMIT="${git_commit}" RUN_GIT_DIRTY="${git_dirty}" RUN_JOB_TIMEOUT_S="${job_timeout}" \
    RUN_SYNC_START="${sync_start}" RUN_DRY_RUN="${dry_run}" "${MR_PYTHON}" - <<'EOF'
import json
import os

e = os.environ
clients = []
for key in e["RUN_CLIENTS"].split():
    path = os.path.join(e["RUN_DIR"], key, "client.json")
    if os.path.exists(path):
        with open(path) as f:
            clients.append(json.load(f))


def env_float(name):
    return float(e[name])


workload = e["RUN_WORKLOAD"]
if workload == "shared-prefix":
    params = {
        "data_type": "shared_prefix",
        "num_groups": int(e["MR_BENCH_SP_NUM_GROUPS"]),
        "num_prompts_per_group": int(e["MR_BENCH_SP_PROMPTS_PER_GROUP"]),
        "system_prompt_len": int(e["MR_BENCH_SP_SYSTEM_PROMPT_LEN"]),
        "question_len": int(e["MR_BENCH_SP_QUESTION_LEN"]),
        "output_len": int(e["MR_BENCH_SP_OUTPUT_LEN"]),
    }
else:
    params = {
        "data_type": "random",
        "input_mean": int(e["MR_BENCH_CHAT_INPUT_MEAN"]),
        "input_std_dev": int(e["MR_BENCH_CHAT_INPUT_STD_DEV"]),
        "input_min": int(e["MR_BENCH_CHAT_INPUT_MIN"]),
        "input_max": int(e["MR_BENCH_CHAT_INPUT_MAX"]),
        "output_len": int(e["MR_BENCH_CHAT_OUTPUT_LEN"]),
        "num_prompts": int(e["MR_BENCH_CHAT_NUM_PROMPTS"]),
    }

global_lb = e.get("MR_GLOBAL_LB", "terraform")
router_chart = (
    e["MR_LLMD_ROUTER_CHART"]
    if global_lb == "mc-gateway"
    else e["MR_LLMD_ROUTER_STANDALONE_CHART"]
)
router_chart_digest = (
    e["MR_LLMD_ROUTER_CHART_DIGEST"]
    if global_lb == "mc-gateway"
    else e["MR_LLMD_ROUTER_STANDALONE_CHART_DIGEST"]
)

metadata = {
    "schema_version": 1,
    "status": e["RUN_STATUS"],
    "dry_run": e["RUN_DRY_RUN"] == "true",
    "run_id": e["MR_RUN_ID"],
    "arm": e["RUN_ARM"],
    "workload": workload,
    "gateway": e["RUN_GATEWAY"],
    "global_lb": global_lb,
    "target_region_mode": e["RUN_TARGET_MODE"],
    "start_epoch_s": int(e["RUN_START"]),
    "end_epoch_s": int(e["RUN_END"]),
    "project_id": e["MR_PROJECT_ID"],
    "namespace": e["MR_NAMESPACE"],
    "results_uri": f"gs://{e['RUN_BUCKET']}/{e['RUN_REL']}/",
    "timings_file": e["MR_TIMINGS_FILE"],
    "git": {"repo": e["ACP_REPO_DIR"], "commit": e["RUN_GIT_COMMIT"], "dirty": e["RUN_GIT_DIRTY"] != "0"},
    "images": {
        "inference_perf": e["MR_INFERENCE_PERF_IMAGE"],
        "vllm": e["MR_VLLM_IMAGE"],
        "llmd_git_ref": e["MR_LLMD_GIT_REF"],
        "llmd_router_chart": router_chart,
        "llmd_router_chart_version": e["MR_LLMD_ROUTER_CHART_VERSION"],
        "llmd_router_chart_digest": router_chart_digest,
    },
    "model": {
        "hf_model_id": e["MR_HF_MODEL_ID"],
        "served_model_name": e["MR_SERVED_MODEL_NAME"],
        "max_model_len": int(e["MR_MAX_MODEL_LEN"]),
        "accelerator_type": e["MR_ACCELERATOR_TYPE"],
        "compute_class": e["MR_COMPUTE_CLASS"],
        "replicas_per_region": int(e["MR_REPLICAS_PER_REGION"]),
        "hpa_enabled": e.get("MR_HPA_ENABLED", "false") == "true",
        "hpa_max_replicas": int(e["MR_HPA_MAX_REPLICAS"]),
    },
    "load": {
        "type": e["MR_BENCH_LOAD_TYPE"],
        "qps": [float(q) for q in e["MR_BENCH_QPS"].split()],
        "stage_duration_s": int(e["MR_BENCH_STAGE_DURATION_S"]),
        "stage_interval_s": env_float("MR_BENCH_STAGE_INTERVAL_S"),
        "num_workers": int(e["MR_BENCH_NUM_WORKERS"]),
        "worker_max_concurrency": int(e["MR_BENCH_WORKER_MAX_CONCURRENCY"]),
        "request_timeout_s": env_float("MR_BENCH_REQUEST_TIMEOUT_S"),
        "job_timeout_s": int(e["RUN_JOB_TIMEOUT_S"]),
        "base_seed": int(e["MR_BENCH_SEED"]),
        "seed_per_client": e["MR_BENCH_SEED_PER_CLIENT"] == "true",
        "sync_start": e["RUN_SYNC_START"] == "true",
    },
    "slo": {"ttft_s": env_float("MR_BENCH_SLO_TTFT_S"), "tpot_s": env_float("MR_BENCH_SLO_TPOT_S")},
    "workload_params": params,
    "gmp_metrics": e["MR_BENCH_GMP"] == "true",
    "clients": clients,
}
with open(os.path.join(e["RUN_DIR"], "run.json"), "w") as f:
    json.dump(metadata, f, indent=2)
    f.write("\n")
EOF
}

run_start="$(date +%s)"
mkdir -p "${run_dir}"
index=0
for key in "${client_keys[@]}"; do
  render_client "${key}" "${index}"
  index=$((index + 1))
done
mr_log "Rendered manifests under ${run_dir}/<client>/manifests"

if [[ "${dry_run}" == "true" ]]; then
  write_run_metadata "dry-run"
  mr_log "Dry run: wrote ${run_dir}/run.json"
  exit 0
fi

write_run_metadata "running"
mr_log "Running arm=${arm} workload=${workload} clients=(${client_keys[*]}) target=${target_mode}" \
  "stages=${stages} sync_start=${sync_start} timeout=${job_timeout}s"

apply_ok="true"
pids=()
for key in "${client_keys[@]}"; do
  (apply_client "${key}") 2>&1 | tee -a "${run_dir}/${key}/logs/harness.log" | sed -u "s/^/[${key}] /" >&2 &
  pids+=("$!")
done
for pid in "${pids[@]}"; do
  wait "${pid}" || apply_ok="false"
done

barrier_ok="${apply_ok}"
if [[ "${apply_ok}" == "true" && "${sync_start}" == "true" ]]; then
  if ! mr_stage "bench_sync_${arm}_${workload}" "global" release_start_barrier; then
    barrier_ok="false"
  fi
fi

pids=()
for key in "${client_keys[@]}"; do
  (finish_client "${key}" "${barrier_ok}") 2>&1 | tee -a "${run_dir}/${key}/logs/harness.log" | sed -u "s/^/[${key}] /" >&2 &
  pids+=("$!")
done
for pid in "${pids[@]}"; do
  wait "${pid}" || true
done

# Each client records its own outcome in client.json.
failed=0
for key in "${client_keys[@]}"; do
  [[ "$(jq -r .status "${run_dir}/${key}/client.json")" == "succeeded" ]] || failed=$((failed + 1))
done

if [[ ${failed} -eq 0 ]]; then
  write_run_metadata "succeeded"
  mr_log "Benchmark complete: ${run_dir}"
else
  write_run_metadata "failed"
  mr_die "${failed} of ${#client_keys[@]} clients failed. See ${run_dir}/<client>/logs."
fi
