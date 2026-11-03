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

# Creates (or destroys) the benchmark results bucket and grants the benchmark
# client Kubernetes service account access to it and to Cloud Monitoring.
#
# Usage: deploy-bench-infra.sh [apply|destroy]

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
# shellcheck source=/dev/null
source "${MY_PATH}/bench-lib.sh"

action="${1:-apply}"
[[ "${action}" == "apply" || "${action}" == "destroy" ]] || mr_die "usage: $0 [apply|destroy]"

mr_require_tools
mr_validate_region_key "${MR_CONFIG_CLUSTER_KEY}"
mr_log "Project: ${MR_PROJECT_ID}, bench bucket: gs://$(mr_bench_bucket)"

mr_stage "shared_state_bucket" "global" mr_ensure_shared_state_bucket
tfvars="$(mr_write_bench_tfvars)"
mr_stage "bench_infra_${action}" "global" mr_tf bench "${action}" "${tfvars}"
