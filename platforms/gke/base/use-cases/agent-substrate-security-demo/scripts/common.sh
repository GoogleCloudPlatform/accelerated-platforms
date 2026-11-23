#!/usr/bin/env bash
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

# Shared target-cluster resolution and error-classification helpers.
# Never adopts an unrelated ambient kubectl current-context as the target cluster.

declare -gA STAGED=()

load_staged_env() {
  local env_file="$1" k v
  STAGED=()
  [[ -f "${env_file}" ]] || return 0
  while IFS='=' read -r k v; do
    [[ -n "${k}" && "${k}" != \#* ]] && STAGED["${k}"]="${v}"
  done < "${env_file}"
}

is_not_found_output() {
  local lower
  lower="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  [[ "${lower}" == *"not found"* \
     || "${lower}" == *"not_found"* \
     || "${lower}" == *"notfound"* \
     || "${lower}" == *"does not exist"* \
     || "${lower}" == *"matched no objects"* \
     || "${lower}" == *"has no egress policy"* \
     || "${lower}" == *"http 404"* \
     || "${lower}" == *"code=404"* \
     || "${lower}" == *"code: 404"* \
     || "${lower}" == *"error 404"* ]]
}

resolve_demo_target() {
  local state_dir="$1"
  local caller_cluster="${CLUSTER_NAME:-}"
  load_staged_env "${state_dir}/staged.env"

  if [[ -n "${caller_cluster}" && -n "${STAGED[CLUSTER_NAME]:-}" \
     && "${caller_cluster}" != "${STAGED[CLUSTER_NAME]}" ]]; then
    STAGED=()
  fi

  local default_project
  default_project="$(gcloud config get-value project 2>/dev/null || true)"
  [[ "${default_project}" == "(unset)" ]] && default_project=""

  PROJECT_ID="${PROJECT_ID:-${STAGED[PROJECT_ID]:-${default_project}}}"
  CLUSTER_NAME="${CLUSTER_NAME:-${STAGED[CLUSTER_NAME]:-agent-substrate-live}}"
  CLUSTER_LOCATION="${CLUSTER_LOCATION:-${STAGED[CLUSTER_LOCATION]:-us-central1-b}}"
  if [[ -z "${REGION:-}" ]]; then
    if [[ "${CLUSTER_LOCATION}" =~ -[a-z]$ ]]; then
      REGION="${CLUSTER_LOCATION%-*}"
    else
      REGION="${CLUSTER_LOCATION}"
    fi
  fi
  EXPECTED_KUBE_CTX="gke_${PROJECT_ID}_${CLUSTER_LOCATION}_${CLUSTER_NAME}"

  local current_ctx
  current_ctx="$(kubectl config current-context 2>/dev/null || true)"
  if [[ -z "${caller_cluster}" && -z "${STAGED[CLUSTER_NAME]:-}" \
     && "${current_ctx}" == gke_* && "${current_ctx}" != "${EXPECTED_KUBE_CTX}" ]]; then
    echo "Error: ambient kubectl context '${current_ctx}' disagrees with default target '${EXPECTED_KUBE_CTX}' and no .state/staged.env exists." >&2
    echo "Export CLUSTER_NAME, CLUSTER_LOCATION, and PROJECT_ID explicitly to confirm the target cluster." >&2
    return 1
  fi
  export PROJECT_ID CLUSTER_NAME CLUSTER_LOCATION REGION EXPECTED_KUBE_CTX
}
