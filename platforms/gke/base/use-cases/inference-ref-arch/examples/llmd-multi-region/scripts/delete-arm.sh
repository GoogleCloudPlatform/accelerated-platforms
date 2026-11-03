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

# Removes an experiment arm from every region (or scales it to zero), so that
# its GPU nodes are released between benchmark sessions.
#
# Usage: delete-arm.sh <baseline|llmd> [--scale-to-zero | --hold-gpus]
#
#   --hold-gpus  keep the arm's GPU nodes with placeholder pods
#                (manifests/common/gpu-hold), for the next arm. The cluster
#                autoscaler removes empty GPU nodes within about a minute, and
#                getting them back can fail during a stockout. deploy-arm.sh
#                releases them. Without this flag, any placeholder is removed.

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

arm="${1:?usage: delete-arm.sh <baseline|llmd> [--scale-to-zero | --hold-gpus]}"
mode="${2:-delete}"
[[ "${mode}" =~ ^(delete|--scale-to-zero|--hold-gpus)$ ]] || mr_die "unknown argument: ${mode}"
[[ "${arm}" == "baseline" || "${arm}" == "llmd" ]] || mr_die "arm must be one of: baseline, llmd"

delete_arm() {
  local key="${1}"
  local deployment="precise-prefix-cache-routing-gpu-vllm-decode-${arm}"
  # The HPA would scale the arm back up.
  mr_kubectl "${key}" delete hpa -l "acp-mr/arm=${arm}" -n "${MR_NAMESPACE}" --ignore-not-found || true
  if [[ "${mode}" == "--scale-to-zero" ]]; then
    mr_kubectl "${key}" scale deploy "${deployment}" -n "${MR_NAMESPACE}" --replicas=0 || true
    return 0
  fi
  if [[ "${arm}" == "llmd" ]]; then
    local release file
    for release in ${MR_LLMD_ROUTER_RELEASES}; do
      file="${MR_WORK_DIR}/rendered/${key}/router/${release}.yaml"
      [[ -f "${file}" ]] || file="$(mr_render_router "${key}" "${release}")"
      mr_kubectl "${key}" delete -f "${file}" --ignore-not-found --wait=true || true
    done
  fi
  local rendered="${MR_WORK_DIR}/rendered/${key}/model-server/${arm}.rendered.yaml"
  if [[ ! -f "${rendered}" ]]; then
    local dir
    dir="$(mr_render_model_server "${key}")"
    kustomize build "${dir}/${arm}" >"${rendered}"
  fi
  mr_kubectl "${key}" delete -f "${rendered}" --ignore-not-found --wait=true
  if [[ "${mode}" == "--hold-gpus" ]]; then
    # Create the placeholders as soon as the model server pods are gone (so
    # that they aren't pending, which would trigger a scale-up), before the
    # autoscaler considers the GPU nodes unneeded.
    mr_kubectl "${key}" wait --for=delete pod -l "acp-mr/arm=${arm}" -n "${MR_NAMESPACE}" --timeout=900s || true
    local dst="${MR_WORK_DIR}/rendered/${key}/common"
    MR_COMPUTE_CLASS="$(mr_compute_class "${key}")" mr_render_dir "${MR_EXAMPLE_DIR}/manifests/common" "${dst}"
    mr_kubectl "${key}" apply -f "${dst}/gpu-hold.yaml"
  else
    mr_kubectl "${key}" delete deployment gpu-hold -n "${MR_NAMESPACE}" --ignore-not-found
  fi
}

# Detach the arm's NEGs from the Terraform-managed load balancer first, so that
# GKE can delete them together with the Services.
if [[ "${mode}" != "--scale-to-zero" && "${MR_GLOBAL_LB}" != "mc-gateway" && -f "${MR_RESULTS_DIR}/gateway/active.json" ]]; then
  active_backend="$(jq -r '.backend' "${MR_RESULTS_DIR}/gateway/active.json")"
  active_mode="$(jq -r '.lb_mode' "${MR_RESULTS_DIR}/gateway/active.json")"
  MR_LB_EXCLUDE_ARM="${arm}" "${MY_PATH}/deploy-global-lb.sh" --backend "${active_backend}" --lb-mode "${active_mode}" --no-wait
fi

for key in ${MR_REGION_KEYS}; do
  mr_stage "arm_delete/${arm}" "region/${key}" delete_arm "${key}"
done
