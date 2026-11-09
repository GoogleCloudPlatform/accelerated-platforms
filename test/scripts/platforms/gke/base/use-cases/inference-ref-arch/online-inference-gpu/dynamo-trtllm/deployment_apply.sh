#!/usr/bin/env bash

# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1 || exit 1
  pwd -P
)"

DYNAMO_MODE="${DYNAMO_MODE:-kv-routing}"
DYNAMO_VARIANT_SUFFIX="${DYNAMO_VARIANT_SUFFIX:-}"
if [[ -z "${DYNAMO_VARIANT_SUFFIX}" && "${ENABLE_POOL_RELAY:-false}" == "true" ]]; then
  DYNAMO_VARIANT_SUFFIX="-pool-relay"
fi

IRA_GPU_ENGINE_DIR="dynamo-trtllm/${DYNAMO_MODE}"
IRA_GPU_CONFIGURE="configure_dynamo_trtllm.sh"
IRA_GPU_SERVICE="dynamo-frontend"
IRA_GPU_VARIANT_SUFFIX="${DYNAMO_VARIANT_SUFFIX}"
# shellcheck source=test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/common.sh
source "${MY_PATH}/../common.sh"
# shellcheck disable=SC2154
IRA_GPU_MODELS=("${hf_gpu_dynamo_trtllm_models[@]}")

ira_gpu_for_each_variant ira_gpu_apply
