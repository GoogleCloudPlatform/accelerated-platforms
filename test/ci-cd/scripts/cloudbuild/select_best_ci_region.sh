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

set -o errexit
set -o nounset
set -o pipefail

# Candidate regions for CI execution to prevent capacity bottlenecks
CANDIDATE_REGIONS=(
  "us-east4"
  "us-central1"
  "us-west1"
  "us-west3"
  "europe-west4"
  "europe-west1"
  "asia-south1"
  "asia-south2"
  "asia-southeast1"
)

# Shuffle candidate regions so parallel CI jobs don't evaluate in exact same order
SHUFFLED_REGIONS=($(shuf -e "${CANDIDATE_REGIONS[@]}"))

PROJECT_ID_TO_CHECK="${1:-${PROJECT_ID:-}}"
SELECTED_REGION=""

echo "Evaluating candidate regions for CI deployment..." >&2

for region in "${SHUFFLED_REGIONS[@]}"; do
  echo "Checking region '${region}' availability..." >&2

  # Query region details from GCP
  if [ -n "${PROJECT_ID_TO_CHECK}" ]; then
    region_info=$(gcloud compute regions describe "${region}" --project="${PROJECT_ID_TO_CHECK}" --format="json" 2>/dev/null || true)
  else
    region_info=$(gcloud compute regions describe "${region}" --format="json" 2>/dev/null || true)
  fi

  if [ -z "${region_info}" ]; then
    echo "  Region '${region}' query failed or not accessible, skipping." >&2
    continue
  fi

  # Check region status
  status=$(echo "${region_info}" | jq -r '.status // "UP"')
  if [ "${status}" != "UP" ]; then
    echo "  Region '${region}' status is '${status}', skipping." >&2
    continue
  fi

  # Check if region supports required N4 machine types for the system node pool (n4-standard-4)
  if [ -n "${PROJECT_ID_TO_CHECK}" ]; then
    n4_check=$(gcloud compute machine-types list --filter="zone ~ ${region} AND name=n4-standard-4" --project="${PROJECT_ID_TO_CHECK}" --format="value(name)" 2>/dev/null | head -n 1 || true)
  else
    n4_check=$(gcloud compute machine-types list --filter="zone ~ ${region} AND name=n4-standard-4" --format="value(name)" 2>/dev/null | head -n 1 || true)
  fi

  if [ -z "${n4_check}" ]; then
    echo "  Region '${region}' missing required n4-standard-4 machine type for system node pool, skipping." >&2
    continue
  fi

  # Check if region supports required GPU & TPU v6e machine types (ct6e-standard-4t OR a2-highgpu-1g / g2-standard-4)
  if [ -n "${PROJECT_ID_TO_CHECK}" ]; then
    mt_check=$(gcloud compute machine-types list --filter="zone ~ ${region} AND name=(ct6e-standard-4t OR a2-highgpu-1g OR g2-standard-4)" --project="${PROJECT_ID_TO_CHECK}" --format="value(name)" 2>/dev/null | head -n 1 || true)
  else
    mt_check=$(gcloud compute machine-types list --filter="zone ~ ${region} AND name=(ct6e-standard-4t OR a2-highgpu-1g OR g2-standard-4)" --format="value(name)" 2>/dev/null | head -n 1 || true)
  fi

  if [ -z "${mt_check}" ]; then
    echo "  Region '${region}' missing required GPU/TPU machine types, skipping." >&2
    continue
  fi

  # Check CPU quota usage if quota block is returned
  cpus_limit=$(echo "${region_info}" | jq -r '.quotas[]? | select(.metric == "CPUS") | .limit' 2>/dev/null | head -n 1)
  cpus_usage=$(echo "${region_info}" | jq -r '.quotas[]? | select(.metric == "CPUS") | .usage' 2>/dev/null | head -n 1)

  if [ -n "${cpus_limit}" ] && [ "${cpus_limit}" != "null" ] && [ "${cpus_limit%.*}" -gt 0 ]; then
    usage_int="${cpus_usage%.*}"
    limit_int="${cpus_limit%.*}"
    available=$((limit_int - usage_int))

    # Ensure at least 32 CPUs available in quota
    if [ "${available}" -lt 32 ]; then
      echo "  Region '${region}' available CPUs (${available}) < 32, skipping." >&2
      continue
    fi
  fi

  SELECTED_REGION="${region}"
  echo "Selected region '${SELECTED_REGION}' for CI run!" >&2
  break
done

# Fallback to us-east4 if preflight check yields no candidate
if [ -z "${SELECTED_REGION}" ]; then
  SELECTED_REGION="us-east4"
  echo "Preflight fallback: selected default region '${SELECTED_REGION}'" >&2
fi

echo "${SELECTED_REGION}"
