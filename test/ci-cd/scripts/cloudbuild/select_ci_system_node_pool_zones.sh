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

# Print the zones to use for the system node pool in a CI build, as a Terraform
# list (for example ["us-central1-b","us-central1-f"]), or nothing if two zones
# can't be selected.
#
# The system node pool creates one node in each of its zones, so a stockout in
# any one zone fails the whole deploy after about 35 minutes (GCE_STOCKOUT, see
# https://github.com/GoogleCloudPlatform/accelerated-platforms/issues/590).
# Two random zones are enough for the pool's minimum of two nodes and lower the
# chance of hitting a stocked-out zone.
#
# Usage: select_ci_system_node_pool_zones.sh <region> <project_id>
set -o errexit
set -o nounset
set -o pipefail

REGION="${1}"
PROJECT_ID_TO_CHECK="${2}"

# The Compute Engine API rejects some filters with more than two terms, so only
# the region is filtered on the server.
zones=$(
  gcloud compute zones list \
    --filter="region ~ /${REGION}\$" \
    --format="value(name,status)" \
    --project="${PROJECT_ID_TO_CHECK}" |
    awk '$2 == "UP" && $1 !~ /-ai/ {print $1}' | shuf -n 2 | sort || true
)

if [ "$(echo "${zones}" | wc -w)" -ne 2 ]; then
  echo "WARNING: Unable to select two zones in '${REGION}', the system node pool uses all of the cluster's zones" >&2
  exit 0
fi

echo "${zones}" | jq -R . | jq -c -s .
