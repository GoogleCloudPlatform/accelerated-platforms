#!/usr/bin/env bash
#
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

# Creates, updates, or destroys the cross-region internal Application Load
# Balancer (terraservice global_lb) of a NETWORK_MODE=shared-vpc environment.
# It has one VIP per region and one backend service per backend; any regional
# frontend Service can be a backend once it's exposed as a GKE standalone NEG
# named "<resource_name_prefix>-<platform_name>-<backend>" (expose_service_neg
# in helpers.sh) in the regions that serve it.
#
# Usage:
#   global_lb.sh apply --backends <file> --active <backend>
#                      [--algorithm WATERFALL_BY_REGION|SPRAY_TO_REGION|WATERFALL_BY_ZONE]
#                      [--balancing-mode IN_FLIGHT|RATE] [--preferred-region <region>]
#                      [--timeout-sec <seconds>] [--dry-run]
#   global_lb.sh vips
#   global_lb.sh destroy
#
# The backends file is a JSON object keyed by backend name, for example:
#   {
#     "trtllm": {
#       "health_check_path": "/health",
#       "health_check_port": 8000,
#       "max_in_flight_requests_per_endpoint": 16
#     }
#   }
# Each backend needs max_in_flight_requests_per_endpoint (balancing mode
# IN_FLIGHT, the default) or max_rate_per_endpoint (RATE), and can set
# locality_lb_policy (default LEAST_REQUEST). Use a worker-aware
# health_check_path when the frontend is decoupled from its GPU workers (for
# example "/v1/models/<model>/ready" on NVIDIA Dynamo, since Dynamo's "/health"
# returns 200 with zero workers). The active backend must have a NEG in every
# region; the other backends are attached where they have one. To detach a
# backend before you delete its Services, re-run apply without it.
#
# --dry-run prints the Terraform variables (read-only Google Cloud calls).

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# shellcheck source=platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
source "${MY_PATH}/helpers.sh"

usage="Usage: global_lb.sh apply --backends <file> --active <backend> [--algorithm <algorithm>] [--balancing-mode IN_FLIGHT|RATE] [--preferred-region <region>] [--timeout-sec <seconds>] [--dry-run] | vips | destroy"
action="${1:-}"
if (($# > 0)); then
  shift
fi
backends_file=""
active=""
algorithm="WATERFALL_BY_REGION"
balancing_mode="IN_FLIGHT"
preferred_region=""
timeout_sec="3600"
dry_run="false"
while (($# > 0)); do
  case "${1}" in
  --backends | --active | --algorithm | --balancing-mode | --preferred-region | --timeout-sec)
    (($# > 1)) || mr_die "${1} needs a value. ${usage}"
    case "${1}" in
    --backends) backends_file="${2}" ;;
    --active) active="${2}" ;;
    --algorithm) algorithm="${2}" ;;
    --balancing-mode) balancing_mode="${2}" ;;
    --preferred-region) preferred_region="${2}" ;;
    --timeout-sec) timeout_sec="${2}" ;;
    esac
    shift 2
    ;;
  --dry-run)
    dry_run="true"
    shift
    ;;
  *) mr_die "unknown argument '${1}'. ${usage}" ;;
  esac
done

mr_init || exit 1
mr_require_tools gcloud jq terraform
lb_name="${TF_VAR_resource_name_prefix}-${MR_ENVIRONMENT_NAME}-lb"
tfvars="$(mr_tf_dir global_lb)/terraform.tfvars.json"

validate_apply_arguments() {
  local invalid
  [[ -n "${backends_file}" && -f "${backends_file}" ]] || mr_die "--backends must name an existing JSON file. ${usage}"
  [[ -n "${active}" ]] || mr_die "--active is required. ${usage}"
  [[ "${algorithm}" =~ ^(WATERFALL_BY_REGION|SPRAY_TO_REGION|WATERFALL_BY_ZONE)$ ]] ||
    mr_die "--algorithm must be WATERFALL_BY_REGION, SPRAY_TO_REGION, or WATERFALL_BY_ZONE."
  [[ "${balancing_mode}" =~ ^(IN_FLIGHT|RATE)$ ]] || mr_die "--balancing-mode must be IN_FLIGHT or RATE."
  [[ "${timeout_sec}" =~ ^[1-9][0-9]*$ ]] || mr_die "--timeout-sec must be a positive integer."
  jq -e 'type == "object" and length > 0' "${backends_file}" >/dev/null ||
    mr_die "${backends_file} must contain a non-empty JSON object keyed by backend name."
  invalid="$(jq -r --arg mode "${balancing_mode}" '
    to_entries[]
    | select(
        (.key | test("^[a-z][a-z0-9-]{0,29}$") | not)
        or ((.value.health_check_path | type) != "string" or (.value.health_check_path | startswith("/") | not))
        or ((.value.health_check_port | type) != "number" or .value.health_check_port < 1 or .value.health_check_port > 65535)
        or (if $mode == "IN_FLIGHT"
            then ((.value.max_in_flight_requests_per_endpoint | type) != "number" or .value.max_in_flight_requests_per_endpoint < 1)
            else ((.value.max_rate_per_endpoint | type) != "number" or .value.max_rate_per_endpoint <= 0)
            end))
    | .key' "${backends_file}")"
  [[ -z "${invalid}" ]] ||
    mr_die "invalid backend(s) in ${backends_file}: ${invalid//$'\n'/ }. A backend name has 1-30 lowercase letters, digits, or hyphens; each backend needs health_check_path (starting with /), health_check_port (1-65535), and max_in_flight_requests_per_endpoint (>= 1, balancing mode IN_FLIGHT) or max_rate_per_endpoint (> 0, balancing mode RATE)."
  jq -e --arg active "${active}" 'has($active)' "${backends_file}" >/dev/null ||
    mr_die "--active '${active}' isn't a backend in ${backends_file}."
}

# Prints the outputs of the shared_network terraservice, or fails when the
# environment has no shared network.
shared_network_outputs() {
  mr_tf_state_has_resources shared_network ||
    mr_die "gs://$(mr_state_bucket) has no shared network. global_lb.sh needs an environment provisioned with NETWORK_MODE=shared-vpc and the same PROJECT_ID, TF_VAR_resource_name_prefix, and MR_ENVIRONMENT_NAME."
  mr_tf shared_network output
}

list_project_negs() {
  gcloud compute network-endpoint-groups list \
    --project="${PROJECT_ID}" \
    --filter="name ~ ^${TF_VAR_resource_name_prefix}-" \
    --format=json
}

build_tfvars() {
  local negs="${1}" outputs
  outputs="$(shared_network_outputs)" || return 1
  if [[ -n "${preferred_region}" ]]; then
    jq -e --arg region "${preferred_region}" '[.regions.value[].region] | index($region) != null' <<<"${outputs}" >/dev/null ||
      mr_die "--preferred-region '${preferred_region}' isn't the region of a platform in the shared network."
  fi
  jq -n \
    --argjson outputs "${outputs}" \
    --argjson negs "${negs}" \
    --slurpfile backends "${backends_file}" \
    --arg project "${PROJECT_ID}" \
    --arg prefix "${TF_VAR_resource_name_prefix}" \
    --arg name "${lb_name}" \
    --arg network_name "$(mr_shared_network_name)" \
    --arg active "${active}" \
    --arg balancing_mode "${balancing_mode}" \
    --arg algorithm "${algorithm}" \
    --arg preferred_region "${preferred_region}" \
    --argjson timeout_sec "${timeout_sec}" '
    def zone_name: split("/") | last;
    ($outputs.regions.value | to_entries) as $platforms
    | [$negs[] | select(.network | endswith("/networks/" + $network_name))] as $network_negs
    | {
        project_id: $project,
        name: $name,
        network: $outputs.network.value,
        regions: ($outputs.regions.value | with_entries(.value = {
          region: .value.region,
          subnetwork: "projects/\($project)/regions/\(.value.region)/subnetworks/\($prefix)-\(.key)"
        })),
        backends: ($backends[0] | with_entries(.key as $backend | .value as $spec | .value = {
          health_check_path: $spec.health_check_path,
          health_check_port: $spec.health_check_port,
          locality_lb_policy: $spec.locality_lb_policy,
          negs: [
            $platforms[] as $platform
            | $network_negs[]
            | select(.name == "\($prefix)-\($platform.key)-\($backend)")
            | if (.zone | zone_name | sub("-[a-z]$"; "")) != $platform.value.region then
                error("NEG \(.name) is in zone \(.zone | zone_name), outside the region \($platform.value.region) of platform \($platform.key)")
              else
                {
                  region: $platform.value.region,
                  self_link: .selfLink,
                  max_in_flight_requests_per_endpoint: $spec.max_in_flight_requests_per_endpoint,
                  max_rate_per_endpoint: $spec.max_rate_per_endpoint
                }
              end
          ]
        })),
        active_backend: $active,
        balancing_mode: $balancing_mode,
        load_balancing_algorithm: $algorithm,
        preferred_region: $preferred_region,
        timeout_sec: $timeout_sec
      }'
}

apply_lb() {
  local negs tfvars_json missing empty_platforms
  validate_apply_arguments
  negs="$(list_project_negs)" || mr_die "listing project NEGs failed; see the error above."
  tfvars_json="$(build_tfvars "${negs}")" || mr_die "building the load balancer variables failed; see the error above."
  missing="$(jq -r '
    .active_backend as $active
    | [.backends[$active].negs[].region] as $served
    | [.regions | to_entries[] | select(.value.region as $region | $served | index($region) | not) | .key]
    | join(" ")' <<<"${tfvars_json}")"
  [[ -z "${missing}" ]] ||
    mr_die "the active backend '${active}' has no NEG in platform(s): ${missing}. Expose its frontend there first, for example: expose_service_neg <platform_name> <namespace> <service> <port> ${active}"
  empty_platforms="$(jq -rn \
    --argjson tfvars "${tfvars_json}" \
    --argjson negs "${negs}" '
    ($tfvars.active_backend) as $active
    | [$tfvars.backends[$active].negs[].self_link] as $links
    | [
        $tfvars.regions | to_entries[] as $p
        | select(
            [$negs[] | select((.selfLink as $s | $links | index($s) != null) and (.zone | split("/") | last | sub("-[a-z]$"; "") == $p.value.region) and ((.size // 0) > 0))]
            | length == 0
          )
        | $p.key
      ]
    | join(" ")')"
  if [[ -n "${empty_platforms}" ]]; then
    mr_log "WARNING: active backend '${active}' currently has 0 endpoints across its NEGs in platform(s): ${empty_platforms}. On GKE Autopilot, zonal NEGs are created only after nodes join each zone; once the frontend Pods are Ready, re-run 'global_lb.sh apply' so any new zonal NEGs are attached."
  fi
  mr_log "Backends (NEG count): $(jq -r '[.backends | to_entries[] | "\(.key)=\(.value.negs | length)"] | join(", ")' <<<"${tfvars_json}"); active: ${active}"
  if [[ "${dry_run}" == "true" ]]; then
    jq . <<<"${tfvars_json}"
    return 0
  fi
  mkdir -p "$(dirname "${tfvars}")"
  echo "${tfvars_json}" >"${tfvars}"
  mr_tf global_lb apply
  print_vips
}

print_vips() {
  mr_tf global_lb output | jq '.vips.value'
}

destroy_lb() {
  if ! mr_tf_state_has_resources global_lb; then
    mr_log "The global load balancer doesn't exist; nothing to destroy."
    return 0
  fi
  if [[ ! -f "${tfvars}" ]]; then
    # Destroying uses the state; the variables only have to be valid.
    mkdir -p "$(dirname "${tfvars}")"
    jq -n \
      --arg project_id "${PROJECT_ID}" \
      --arg name "${lb_name}" \
      --arg network "projects/${PROJECT_ID}/global/networks/$(mr_shared_network_name)" \
      '{
        project_id: $project_id,
        name: $name,
        network: $network,
        regions: {},
        backends: {default: {health_check_path: "/", health_check_port: 80, negs: []}},
        active_backend: "default"
      }' >"${tfvars}"
  fi
  mr_tf global_lb destroy
}

case "${action}" in
apply) apply_lb ;;
vips)
  mr_tf_state_has_resources global_lb || mr_die "the global load balancer doesn't exist; run 'global_lb.sh apply' first."
  print_vips
  ;;
destroy) destroy_lb ;;
*) mr_die "${usage}" ;;
esac
