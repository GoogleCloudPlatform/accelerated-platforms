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

# Creates or updates the Agent Substrate Security Demo dashboard and the 3 upstream
# Agent Substrate Cloud Monitoring dashboards, scoped to CLUSTER_NAME.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
OBS_DIR="${USE_CASE_DIR}/observability"

export PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
export CLUSTER_NAME="${CLUSTER_NAME:-agent-substrate-live}"

scoped() {
  python3 "${SCRIPT_DIR}/promql_scope.py" dashboard "${CLUSTER_NAME}" < "$1"
}

upsert_dashboard() {
  local file
  file="$(mktemp)"
  scoped "$1" > "${file}"
  local title existing name etag
  title="$(jq -r .displayName "${file}")"
  existing="$(gcloud monitoring dashboards list --project "${PROJECT_ID}" --verbosity=error \
    --filter="displayName=\"${title}\"" --format='value(name,etag)' | head -n1)"
  if [[ -z "${existing}" ]]; then
    gcloud monitoring dashboards create --project "${PROJECT_ID}" --config-from-file="${file}" --quiet >/dev/null
    echo "  ✓ created dashboard: ${title}"
  else
    read -r name etag <<<"${existing}"
    jq --arg etag "${etag}" '. + {etag: $etag}' "${file}" \
      | gcloud monitoring dashboards update "${name}" --project "${PROJECT_ID}" --config-from-file=- --quiet >/dev/null
    echo "  ✓ updated dashboard: ${title}"
  fi
  rm -f "${file}"
}

echo "==> Provisioning Cloud Monitoring dashboards (scoped to cluster=\"${CLUSTER_NAME}\")"
upsert_dashboard "${OBS_DIR}/dashboard.json"
for f in "${OBS_DIR}"/substrate-dashboards/*.json; do
  upsert_dashboard "$f"
done
echo "  ✓ Cloud Monitoring Dashboards ready: https://console.cloud.google.com/monitoring/dashboards?project=${PROJECT_ID}"
