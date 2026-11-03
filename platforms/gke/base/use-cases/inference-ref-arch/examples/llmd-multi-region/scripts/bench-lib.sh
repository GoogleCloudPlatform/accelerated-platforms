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

# Benchmark settings and helpers. Source this file after lib.sh. Every setting
# can be overridden by exporting it before running a script. See
# bench/README.md for how each value maps to the inference-perf configuration.

export MR_BENCH_DIR="${MR_EXAMPLE_DIR}/bench"

# ---------------------------------------------------------------------------
# Client Jobs
# ---------------------------------------------------------------------------
# Multi-cluster Gateway that the clients send requests to, and its listener
# port. Clients use http://<regional internal VIP>:<port>.
export MR_BENCH_GATEWAY="${MR_BENCH_GATEWAY:-llm-mr-gateway}"
export MR_BENCH_GATEWAY_PORT="${MR_BENCH_GATEWAY_PORT:-80}"
# Tokenizer used by inference-perf to generate exact-length prompts and count
# tokens. Downloaded from Hugging Face by the client Pod.
export MR_BENCH_TOKENIZER="${MR_BENCH_TOKENIZER:-${MR_HF_MODEL_ID}}"
# Custom compute class for the client Pods (manifests/common/compute-class-bench:
# on-demand 8 vCPU machines across several families, so that a single machine
# family stockout doesn't block the benchmark). Set to "" to omit the node
# selector.
export MR_BENCH_COMPUTE_CLASS="${MR_BENCH_COMPUTE_CLASS-llm-mr-bench-cpu}"
export MR_BENCH_CPU="${MR_BENCH_CPU:-4}"
export MR_BENCH_MEMORY="${MR_BENCH_MEMORY:-8Gi}"
# Hard limit for a client Job. Empty: derived from the load stages.
export MR_BENCH_JOB_TIMEOUT_S="${MR_BENCH_JOB_TIMEOUT_S:-}"

# ---------------------------------------------------------------------------
# Load (inference-perf `load` section)
# ---------------------------------------------------------------------------
# Arrival process: poisson or constant.
export MR_BENCH_LOAD_TYPE="${MR_BENCH_LOAD_TYPE:-poisson}"
# Space-separated request rates (QPS) per client, one load stage each.
export MR_BENCH_QPS="${MR_BENCH_QPS:-1 2 3 4 6 8}"
export MR_BENCH_STAGE_DURATION_S="${MR_BENCH_STAGE_DURATION_S:-60}"
# Pause between stages, so that queues drain before the next rate starts.
export MR_BENCH_STAGE_INTERVAL_S="${MR_BENCH_STAGE_INTERVAL_S:-10}"
export MR_BENCH_NUM_WORKERS="${MR_BENCH_NUM_WORKERS:-${MR_BENCH_CPU}}"
export MR_BENCH_WORKER_MAX_CONCURRENCY="${MR_BENCH_WORKER_MAX_CONCURRENCY:-128}"
export MR_BENCH_REQUEST_TIMEOUT_S="${MR_BENCH_REQUEST_TIMEOUT_S:-600}"
# Base random seed. With MR_BENCH_SEED_PER_CLIENT=true, client i (0-based, in
# --clients order) uses MR_BENCH_SEED + i, so that clients in different regions
# send different prompts and different shared prefixes.
export MR_BENCH_SEED="${MR_BENCH_SEED:-42}"
export MR_BENCH_SEED_PER_CLIENT="${MR_BENCH_SEED_PER_CLIENT:-true}"

# ---------------------------------------------------------------------------
# Service level objectives (seconds), used for goodput
# ---------------------------------------------------------------------------
export MR_BENCH_SLO_TTFT_S="${MR_BENCH_SLO_TTFT_S:-2}"
export MR_BENCH_SLO_TPOT_S="${MR_BENCH_SLO_TPOT_S:-0.1}"

# ---------------------------------------------------------------------------
# Workload: shared-prefix (inference-perf `data.type: shared_prefix`)
# ---------------------------------------------------------------------------
# Sized for Qwen3-32B (BF16) on one 96 GB GPU per replica, two replicas per
# region: about 80k tokens of KV cache per replica. 64 groups x 2048 tokens is
# about 131k prefix tokens per client region, which doesn't fit in one
# replica's cache but fits when the prefixes are partitioned across the two
# replicas, which is what prefix-cache aware routing does.
export MR_BENCH_SP_NUM_GROUPS="${MR_BENCH_SP_NUM_GROUPS:-64}"
export MR_BENCH_SP_PROMPTS_PER_GROUP="${MR_BENCH_SP_PROMPTS_PER_GROUP:-64}"
export MR_BENCH_SP_SYSTEM_PROMPT_LEN="${MR_BENCH_SP_SYSTEM_PROMPT_LEN:-2048}"
export MR_BENCH_SP_QUESTION_LEN="${MR_BENCH_SP_QUESTION_LEN:-256}"
export MR_BENCH_SP_OUTPUT_LEN="${MR_BENCH_SP_OUTPUT_LEN:-256}"

# ---------------------------------------------------------------------------
# Workload: chat (control; inference-perf `data.type: random`)
# ---------------------------------------------------------------------------
# Random token prompts with no deliberate sharing. The mean input length
# matches the shared-prefix workload (system prompt + question).
export MR_BENCH_CHAT_INPUT_MEAN="${MR_BENCH_CHAT_INPUT_MEAN:-2304}"
export MR_BENCH_CHAT_INPUT_STD_DEV="${MR_BENCH_CHAT_INPUT_STD_DEV:-512}"
export MR_BENCH_CHAT_INPUT_MIN="${MR_BENCH_CHAT_INPUT_MIN:-256}"
export MR_BENCH_CHAT_INPUT_MAX="${MR_BENCH_CHAT_INPUT_MAX:-8192}"
export MR_BENCH_CHAT_OUTPUT_LEN="${MR_BENCH_CHAT_OUTPUT_LEN:-256}"
export MR_BENCH_CHAT_NUM_PROMPTS="${MR_BENCH_CHAT_NUM_PROMPTS:-4096}"

# ---------------------------------------------------------------------------
# Optional server-side metrics from Google Cloud Managed Service for Prometheus
# ---------------------------------------------------------------------------
# Uses the vLLM metrics that GKE automatic application monitoring collects.
export MR_BENCH_GMP="${MR_BENCH_GMP:-false}"
export MR_BENCH_GMP_SCRAPE_INTERVAL_S="${MR_BENCH_GMP_SCRAPE_INTERVAL_S:-15}"

mr_bench_bucket() {
  echo "${MR_PROJECT_ID}-${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-bench"
}

mr_write_bench_tfvars() {
  local out="${MR_WORK_DIR}/terraform/bench.tfvars.json"
  mkdir -p "$(dirname "${out}")"
  jq -n \
    --arg project_id "${MR_PROJECT_ID}" \
    --arg bucket_name "$(mr_bench_bucket)" \
    --arg bucket_location "$(mr_region "${MR_CONFIG_CLUSTER_KEY}")" \
    --arg kubernetes_namespace "${MR_NAMESPACE}" \
    --arg kubernetes_service_account "${MR_NAMESPACE}" \
    '{
      project_id: $project_id,
      bucket_name: $bucket_name,
      bucket_location: $bucket_location,
      kubernetes_namespace: $kubernetes_namespace,
      kubernetes_service_account: $kubernetes_service_account
    }' >"${out}"
  echo "${out}"
}

# mr_bench_stages <duration_s> <qps...>
# Prints the inference-perf `load.stages` list as a YAML flow sequence.
mr_bench_stages() {
  local duration="${1}"
  shift
  local stages="" qps
  for qps in "$@"; do
    [[ "${qps}" =~ ^[0-9]+([.][0-9]+)?$ ]] || mr_die "invalid QPS value '${qps}'"
    stages+="${stages:+, }{rate: ${qps}, duration: ${duration}}"
  done
  [[ -n "${stages}" ]] || mr_die "no QPS stages"
  echo "[${stages}]"
}

# mr_bench_default_timeout <num_stages>
# Upper bound for one client Job: prompt generation and tokenizer download,
# every stage plus its teardown grace (120 s in inference-perf v0.7.0) and
# interval, and report upload.
mr_bench_default_timeout() {
  local num_stages="${1}"
  echo $((1800 + num_stages * (MR_BENCH_STAGE_DURATION_S + MR_BENCH_STAGE_INTERVAL_S + 120)))
}
