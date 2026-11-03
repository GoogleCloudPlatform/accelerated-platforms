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

# Enables the fleet features for multi-cluster Gateways (Multi-cluster Services
# and Multi-cluster Ingress/Gateway with a config cluster) after the regional
# clusters are registered to the fleet.

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

mr_require_tools

config_cluster="$(mr_cluster_name "${MR_CONFIG_CLUSTER_KEY}")"

check_memberships() {
  local key
  for key in ${MR_REGION_KEYS}; do
    gcloud container fleet memberships describe "$(mr_cluster_name "${key}")" \
      --location global --project "${MR_PROJECT_ID}" >/dev/null ||
      mr_die "cluster $(mr_cluster_name "${key}") is not registered to the fleet. Run deploy-region.sh ${key} first."
  done
}

# The multi-cluster Gateway controller might fail to start if the Gateway API
# CRDs are installed on the config cluster after the fleet ingress feature is
# enabled. The core platform enables the Gateway API (CHANNEL_STANDARD) when it
# creates the cluster, so verify it before enabling the feature.
check_gateway_api() {
  mr_kubectl "${MR_CONFIG_CLUSTER_KEY}" get crd gateways.gateway.networking.k8s.io >/dev/null ||
    mr_die "Gateway API CRDs are missing on the config cluster ${config_cluster}"
}

# Wait for the multi-cluster GatewayClasses to appear in the config cluster,
# which confirms that the multi-cluster Gateway controller is running.
wait_for_mc_gatewayclasses() {
  mr_wait_for 1200 15 "gke-l7-cross-regional-internal-managed-mc GatewayClass" \
    mr_kubectl "${MR_CONFIG_CLUSTER_KEY}" get gatewayclass gke-l7-cross-regional-internal-managed-mc
}

mr_stage "fleet_check_memberships" "global" check_memberships
mr_stage "fleet_check_gateway_api" "global" check_gateway_api
tfvars="$(mr_write_fleet_tfvars)"
mr_stage "fleet_features" "global" mr_tf fleet apply "${tfvars}"
mr_stage "fleet_mc_gatewayclasses_ready" "global" wait_for_mc_gatewayclasses

mr_log "Fleet features enabled. Config cluster: ${config_cluster}"
