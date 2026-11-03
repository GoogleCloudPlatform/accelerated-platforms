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

# Print best-effort diagnostics to the build log before the CI project is torn
# down or deleted, so that failures that depend on project state can be
# investigated after the build finishes.
#
# Usage:
#   print_build_diagnostics.sh cluster
#     GKE clusters, node pools, managed instance group errors, cluster
#     operations, and regional Compute Engine quota usage.
#   print_build_diagnostics.sh project
#     Cloud Endpoints services, Service Management audit log entries, and
#     enabled services.
#   print_build_diagnostics.sh project-delete-failure <delete_project_log_file>
#     Child resources that blocked "gcloud projects delete", and log entries
#     that mention them.
#
# This script is purely informational. It doesn't use errexit, every command is
# allowed to fail, and it always exits with status 0, so it never changes the
# result of the calling build step.

if [ -f /workspace/build.env ]; then
  # shellcheck disable=SC1091
  source /workspace/build.env
fi
if [ "${DEBUG,,}" == "true" ]; then
  set -o xtrace
fi

MODE="${1:-}"
# Maximum time, in seconds, for each diagnostic command
DIAGNOSTICS_COMMAND_TIMEOUT="${DIAGNOSTICS_COMMAND_TIMEOUT:-120}"

if [[ ! -v cluster_project_id ]]; then
  set --
  # shellcheck disable=SC1091
  source "${ACP_PLATFORM_BASE_DIR}/_shared_config/scripts/set_environment_variables.sh" ||
    echo "WARNING: Failed to load the shared configuration, using values from the build environment" >&2
fi

project_id="${cluster_project_id:-${platform_default_project_id:-${TF_VAR_platform_default_project_id:-}}}"
region="${cluster_region:-${LOCATION:-}}"

if [ -z "${project_id}" ]; then
  echo "WARNING: Unable to determine the project ID, skipping diagnostics" >&2
  exit 0
fi

print_header() {
  echo
  echo "=== [diagnostics] ${1}"
}

# Print and run a command, without failing if the command fails
run() {
  echo "\$ $*"
  timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" "$@" 2>&1
  local exit_code=$?
  if [ "${exit_code}" -ne 0 ]; then
    echo "(command exited with status ${exit_code})"
  fi
  return 0
}

print_cluster_diagnostics() {
  print_header "GKE clusters in project '${project_id}'"
  run gcloud container clusters list \
    --format="json(name,location,status,statusMessage,conditions,currentNodeCount,locations,createTime)" \
    --project="${project_id}"

  local clusters
  clusters=$(
    timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" gcloud container clusters list \
      --format="value(name,location,autopilot.enabled)" \
      --project="${project_id}" 2>/dev/null
  )

  local cluster_name_item cluster_location cluster_autopilot node_pool instance_group_url instance_group_name instance_group_zone
  while read -r cluster_name_item cluster_location cluster_autopilot; do
    if [ -z "${cluster_name_item}" ]; then
      continue
    fi

    if [ "${cluster_autopilot,,}" == "true" ]; then
      print_header "Cluster '${cluster_name_item}' (${cluster_location}) is an Autopilot cluster, skipping node pools"
      continue
    fi

    print_header "Node pools in cluster '${cluster_name_item}' (${cluster_location})"
    run gcloud container node-pools list \
      --cluster="${cluster_name_item}" \
      --format="table(name,status,config.machineType,locations.list(),autoscaling.totalMinNodeCount,autoscaling.locationPolicy)" \
      --location="${cluster_location}" \
      --project="${project_id}"

    for node_pool in $(
      timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" gcloud container node-pools list \
        --cluster="${cluster_name_item}" \
        --format="value(name)" \
        --location="${cluster_location}" \
        --project="${project_id}" 2>/dev/null
    ); do
      print_header "Node pool '${node_pool}' in cluster '${cluster_name_item}'"
      run gcloud container node-pools describe "${node_pool}" \
        --cluster="${cluster_name_item}" \
        --format="json(name,status,statusMessage,conditions,locations,instanceGroupUrls,autoscaling,config.machineType)" \
        --location="${cluster_location}" \
        --project="${project_id}"

      for instance_group_url in $(
        timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" gcloud container node-pools describe "${node_pool}" \
          --cluster="${cluster_name_item}" \
          --format="value[delimiter=' '](instanceGroupUrls)" \
          --location="${cluster_location}" \
          --project="${project_id}" 2>/dev/null
      ); do
        # https://www.googleapis.com/compute/v1/projects/<project>/zones/<zone>/instanceGroupManagers/<name>
        instance_group_name="${instance_group_url##*/}"
        instance_group_zone=$(echo "${instance_group_url}" | awk -F'/' '{print $(NF-2)}')

        print_header "Managed instance group '${instance_group_name}' (${instance_group_zone})"
        run gcloud compute instance-groups managed describe "${instance_group_name}" \
          --format="table(targetSize,currentActions.none:label=RUNNING,currentActions.creating:label=CREATING,currentActions.creatingWithoutRetries:label=CREATING_WITHOUT_RETRIES,status.isStable:label=STABLE)" \
          --project="${project_id}" \
          --zone="${instance_group_zone}"
        run gcloud compute instance-groups managed list-errors "${instance_group_name}" \
          --format="table(timestamp,instanceActionDetails.action,error.code,error.message)" \
          --limit=10 \
          --project="${project_id}" \
          --zone="${instance_group_zone}"
      done
    done
  done <<<"${clusters}"

  print_header "GKE operations that are not done or that have an error"
  run gcloud container operations list \
    --filter="status!=DONE OR error:* OR statusMessage:*" \
    --format="json(name,operationType,status,statusMessage,error,targetLink.basename(),zone,startTime,endTime)" \
    --project="${project_id}" \
    --verbosity=error

  local operation_type operation_name operation_location
  for operation_type in CREATE_NODE_POOL CREATE_CLUSTER; do
    read -r operation_name operation_location < <(
      timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" gcloud container operations list \
        --filter="operationType=${operation_type} AND (error:* OR statusMessage:*)" \
        --format="value(name,zone)" \
        --limit=1 \
        --project="${project_id}" \
        --sort-by="~startTime" \
        --verbosity=error 2>/dev/null
    )
    if [ -n "${operation_name}" ]; then
      print_header "Most recent failed ${operation_type} operation"
      run gcloud container operations describe "${operation_name}" \
        --format=json \
        --location="${operation_location}" \
        --project="${project_id}"
    fi
  done

  if [ -n "${region}" ]; then
    print_header "Compute Engine quotas in use in region '${region}'"
    timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" gcloud compute regions describe "${region}" \
      --format=json \
      --project="${project_id}" 2>&1 |
      jq -c '.quotas[] | select(.usage > 0 or (.metric | test("^(CPUS|N4_CPUS|INSTANCES|IN_USE_ADDRESSES)$")))' 2>&1
  fi
}

print_project_diagnostics() {
  print_header "Cloud Endpoints services produced by project '${project_id}'"
  run gcloud endpoints services list \
    --format="table(serviceName,producerProjectId)" \
    --project="${project_id}"

  print_header "Service Management audit log entries (last 6h)"
  run gcloud logging read \
    "protoPayload.serviceName=\"servicemanagement.googleapis.com\"" \
    --format="table(timestamp,protoPayload.methodName,protoPayload.resourceName,protoPayload.status.code)" \
    --freshness=6h \
    --limit=50 \
    --order=asc \
    --project="${project_id}"

  print_header "Enabled services in project '${project_id}'"
  timeout "${DIAGNOSTICS_COMMAND_TIMEOUT}" gcloud services list \
    --enabled \
    --format="value(config.name)" \
    --project="${project_id}" 2>&1 | paste -s -d ' '
}

print_project_delete_failure_diagnostics() {
  local delete_log_file="${1:-}"

  print_header "Child resources that blocked deleting project '${project_id}'"
  if [ -z "${delete_log_file}" ] || [ ! -f "${delete_log_file}" ]; then
    echo "No project deletion log file was provided"
  else
    local child_resource child_resource_id
    while read -r child_resource; do
      if [ -z "${child_resource}" ]; then
        continue
      fi
      child_resource_id="${child_resource#services/}"
      print_header "Log entries that mention '${child_resource}' (last 1d)"
      run gcloud logging read "\"${child_resource_id}\"" \
        --format="table(timestamp,logName.basename(),protoPayload.serviceName,protoPayload.methodName,protoPayload.resourceName)" \
        --freshness=1d \
        --limit=20 \
        --project="${project_id}"
    done < <(grep -o -E 'services/[0-9]+' "${delete_log_file}" | sort -u)
  fi

  print_project_diagnostics
}

echo
echo "################################################################################"
echo "# Build diagnostics (${MODE:-none}) for project '${project_id}' region '${region:-unknown}'"
echo "# These diagnostics are informational only and don't change the build result."
echo "################################################################################"

case "${MODE}" in
cluster)
  print_cluster_diagnostics
  ;;
project)
  print_project_diagnostics
  ;;
project-delete-failure)
  print_project_delete_failure_diagnostics "${2:-}"
  ;;
*)
  echo "WARNING: Unknown diagnostics mode '${MODE}', expected 'cluster', 'project', or 'project-delete-failure'" >&2
  ;;
esac

echo
echo "# End of build diagnostics (${MODE:-none})"
echo "################################################################################"
exit 0
