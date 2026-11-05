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

# OPTIONAL, prototype: deploys (or removes) an IAP-protected external HTTPS
# "front door" for the internal multi-cluster Inference Gateway, for demos.
#
#   client --HTTPS--> global external ALB (IAP, managed cert, optional Cloud
#   Armor) --> Envoy (namespace ${MR_FRONT_DOOR_NAMESPACE}, config cluster)
#   --HTTP--> internal multi-cluster Gateway VIP in the config cluster's region
#
# The front door is OFF by default: deploy-all.sh never calls this script, and
# teardown-all.sh removes it only if it exists. See
# manifests/front-door/README.md for the security posture and caveats.
#
# Usage:
#   deploy-front-door.sh [apply]   create or update (idempotent)
#   deploy-front-door.sh destroy   delete the Kubernetes resources, wait for the
#                                  load balancer to be deleted, then destroy
#                                  terraform/front_door
#   deploy-front-door.sh exists    exit 0 if any part of the front door exists
#
# Prerequisites: the regional platforms and the internal cross-region load
# balancer (deploy-arm.sh / set-route.sh) are deployed. Settings:
# MR_FRONT_DOOR_* and MR_IAP_OAUTH_* in mr.env.

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
source "${MY_PATH}/render.sh"

action="${1:-apply}"
cfg="${MR_CONFIG_CLUSTER_KEY}"
ns="${MR_FRONT_DOOR_NAMESPACE}"
# Kubernetes objects in ${ns} all use this name.
k8s_name="llm-front-door"
oauth_secret_name="llm-front-door-iap-oauth"
state_dir="${MR_RESULTS_DIR}/front-door"

# Google Cloud resource names. Keep in sync with the locals in
# terraform/front_door/main.tf.
fd_cert_prefix() {
  "${MR_PYTHON}" -c 'import sys; print(sys.argv[1][:48].rstrip("-"))' "${MR_FRONT_DOOR_NAME}"
}

fd_cert_name() {
  "${MR_PYTHON}" - "${MR_FRONT_DOOR_NAME}" "${MR_FRONT_DOOR_HOSTNAME}" <<'EOF'
import hashlib, sys
name, host = sys.argv[1], sys.argv[2]
prefix = name[:48].rstrip("-")
digest = hashlib.sha256(host.encode("utf-8")).hexdigest()[:8]
print(f"{prefix}-cert-{digest}")
EOF
}

export MR_FRONT_DOOR_ADDRESS_NAME="${MR_FRONT_DOOR_NAME}-ip"
export MR_FRONT_DOOR_CERT_NAME
MR_FRONT_DOOR_CERT_NAME="$(fd_cert_name)"
export MR_FRONT_DOOR_SSL_POLICY_NAME="${MR_FRONT_DOOR_NAME}-ssl"
fd_security_policy_name="${MR_FRONT_DOOR_NAME}-armor"

# Variables substituted in manifests/front-door/*.tpl.yaml, in addition to
# MR_TEMPLATE_VARS from render.sh.
# shellcheck disable=SC2016
FD_TEMPLATE_VARS='${MR_FRONT_DOOR_NAMESPACE} ${MR_FRONT_DOOR_HOSTNAME} ${MR_FRONT_DOOR_ADDRESS_NAME} ${MR_FRONT_DOOR_CERT_NAME} ${MR_FRONT_DOOR_SSL_POLICY_NAME} ${MR_FRONT_DOOR_UPSTREAM_VIP} ${MR_FRONT_DOOR_ENVOY_IMAGE} ${MR_FRONT_DOOR_TIMEOUT_SEC} ${MR_FRONT_DOOR_IAP_OAUTH_FIELDS} ${MR_FRONT_DOOR_SECURITY_POLICY_FIELD}'

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

# fd_split <string>: prints the space- or comma-separated items, one per line.
fd_split() {
  tr ', ' '\n' <<<"${1}" | sed '/^$/d'
}

# Prints the IAP principals, one per line. Defaults to the deploying account.
fd_iap_members() {
  if [[ -n "${MR_FRONT_DOOR_IAP_MEMBERS}" ]]; then
    fd_split "${MR_FRONT_DOOR_IAP_MEMBERS}"
    return
  fi
  local account
  account="$(gcloud config get-value account 2>/dev/null)"
  [[ -n "${account}" ]] || mr_die "no active gcloud account; set MR_FRONT_DOOR_IAP_MEMBERS"
  if [[ "${account}" == *.gserviceaccount.com ]]; then
    echo "serviceAccount:${account}"
  else
    echo "user:${account}"
  fi
}

fd_validate_inputs() {
  local members m c
  members="$(fd_iap_members)"
  [[ -n "${members}" ]] || mr_die "no IAP members"
  while IFS= read -r m; do
    case "${m,,}" in
    allusers | allauthenticatedusers)
      mr_die "IAP member '${m}' is not allowed: the front door must never be public"
      ;;
    esac
    [[ "${m}" =~ ^(user|group|serviceAccount|domain):[^[:space:]]+$ || "${m}" =~ ^principal(Set)?://[^[:space:]]+$ ]] ||
      mr_die "invalid IAP member '${m}' (use user:, group:, serviceAccount:, domain:, principal://, or principalSet://)"
  done <<<"${members}"

  case "${MR_FRONT_DOOR_IAP_SCOPE}" in
  backend-service | project) ;;
  *) mr_die "MR_FRONT_DOOR_IAP_SCOPE must be 'backend-service' or 'project'" ;;
  esac

  [[ "${MR_FRONT_DOOR_HOSTNAME}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?\.endpoints\.[a-z0-9][-a-z0-9.]*\.cloud\.goog$ ]] ||
    mr_die "MR_FRONT_DOOR_HOSTNAME '${MR_FRONT_DOOR_HOSTNAME}' must be <name>.endpoints.<project_id>.cloud.goog (set it explicitly for domain-scoped project IDs)"

  if [[ -n "${MR_IAP_OAUTH_CLIENT_ID}" || -n "${MR_IAP_OAUTH_CLIENT_SECRET_FILE}" ]]; then
    [[ -n "${MR_IAP_OAUTH_CLIENT_ID}" && -n "${MR_IAP_OAUTH_CLIENT_SECRET_FILE}" ]] ||
      mr_die "set both MR_IAP_OAUTH_CLIENT_ID and MR_IAP_OAUTH_CLIENT_SECRET_FILE, or neither"
    [[ -s "${MR_IAP_OAUTH_CLIENT_SECRET_FILE}" ]] ||
      mr_die "MR_IAP_OAUTH_CLIENT_SECRET_FILE '${MR_IAP_OAUTH_CLIENT_SECRET_FILE}' is missing or empty"
  fi

  case "${MR_FRONT_DOOR_CLOUD_ARMOR}" in
  true)
    local cidrs
    cidrs="$(fd_split "${MR_FRONT_DOOR_ALLOWED_CIDRS}")"
    [[ -n "${cidrs}" ]] ||
      mr_die "MR_FRONT_DOOR_CLOUD_ARMOR=true requires MR_FRONT_DOOR_ALLOWED_CIDRS"
    while IFS= read -r c; do
      "${MR_PYTHON}" -c 'import ipaddress, sys; ipaddress.ip_network(sys.argv[1])' "${c}" 2>/dev/null ||
        mr_die "invalid CIDR '${c}' in MR_FRONT_DOOR_ALLOWED_CIDRS"
    done <<<"${cidrs}"
    ;;
  false) ;;
  *) mr_die "MR_FRONT_DOOR_CLOUD_ARMOR must be 'true' or 'false'" ;;
  esac
}

fd_write_tfvars() {
  local out="${MR_WORK_DIR}/terraform/front_door.tfvars.json"
  mkdir -p "$(dirname "${out}")"
  jq -n \
    --arg project_id "${MR_PROJECT_ID}" \
    --arg name "${MR_FRONT_DOOR_NAME}" \
    --arg hostname "${MR_FRONT_DOOR_HOSTNAME}" \
    --argjson iap_members "$(fd_iap_members | jq -R . | jq -s .)" \
    --argjson iap_grant_project_level "$([[ "${MR_FRONT_DOOR_IAP_SCOPE}" == "project" ]] && echo true || echo false)" \
    --argjson cloud_armor_enabled "$([[ "${MR_FRONT_DOOR_CLOUD_ARMOR}" == "true" ]] && echo true || echo false)" \
    --argjson cloud_armor_allowed_source_cidrs "$(fd_split "${MR_FRONT_DOOR_ALLOWED_CIDRS}" | jq -R . | jq -s .)" \
    '{
      project_id: $project_id,
      name: $name,
      hostname: $hostname,
      iap_members: $iap_members,
      iap_grant_project_level: $iap_grant_project_level,
      cloud_armor_enabled: $cloud_armor_enabled,
      cloud_armor_allowed_source_cidrs: $cloud_armor_allowed_source_cidrs
    }' >"${out}"
  echo "${out}"
}

# ---------------------------------------------------------------------------
# Discovery and checks
# ---------------------------------------------------------------------------

fd_address() {
  gcloud compute addresses describe "${MR_FRONT_DOOR_ADDRESS_NAME}" --global \
    --project "${MR_PROJECT_ID}" --format='value(address)' 2>/dev/null
}

# Prints the name of the backend service that the Gateway controller created
# for the Envoy Service (from the networking.gke.io/backend-services annotation
# of the Gateway, like examples/llmd/initialize/external_gateway.tf).
fd_backend_service() {
  local all match
  all="$(mr_kubectl "${cfg}" get gateway "${k8s_name}" -n "${ns}" \
    -o jsonpath='{.metadata.annotations.networking\.gke\.io/backend-services}' 2>/dev/null |
    tr ',' '\n' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's#.*/##' | sed '/^$/d' | grep -v 'serve404' || true)"
  match="$(grep -e "-${ns}-${k8s_name}-8080-" <<<"${all}" || true)"
  # Names are truncated for long namespaces; the Gateway has a single backend.
  [[ -n "${match}" ]] || match="${all}"
  [[ -n "${match}" && "$(wc -l <<<"${match}")" -eq 1 ]] || return 1
  echo "${match}"
}

fd_gateway_programmed() {
  [[ "$(mr_kubectl "${cfg}" get gateway "${k8s_name}" -n "${ns}" \
    -o jsonpath='{.status.conditions[?(@.type=="Programmed")].status}')" == "True" ]] &&
    fd_backend_service >/dev/null
}

fd_iap_enabled() {
  local bs
  bs="$(fd_backend_service)" || return 1
  [[ "$(gcloud compute backend-services describe "${bs}" --global --project "${MR_PROJECT_ID}" \
    --format='value(iap.enabled)')" == "True" ]]
}

fd_cert_active() {
  [[ "$(gcloud compute ssl-certificates describe "${MR_FRONT_DOOR_CERT_NAME}" --global \
    --project "${MR_PROJECT_ID}" --format='value(managed.status)')" == "ACTIVE" ]]
}

# Classifies the response to an unauthenticated request carrying a forged
# x-goog-iap-jwt-assertion header, in ${state_dir}/iap-check: "iap" (redirect
# to Google sign-in), "envoy-guard" (reached Envoy without IAP), "open" (HTTP
# 200), "forbidden" (other 403, for example Cloud Armor denying this machine).
# Succeeds once the response is conclusive.
fd_iap_enforced() {
  local headers code location body="${state_dir}/iap-check.body" result
  headers="$(curl -sS -o "${body}" -D - --max-time 30 \
    -H 'x-goog-iap-jwt-assertion: forged-probe' \
    "https://${MR_FRONT_DOOR_HOSTNAME}/v1/models" 2>/dev/null || true)"
  code="$(awk 'toupper($1) ~ /^HTTP/ {c=$2} END {print c}' <<<"${headers}")"
  location="$(awk 'tolower($1) == "location:" {print $2}' <<<"${headers}" | tr -d '\r')"
  case "${code}" in
  302) [[ "${location}" == https://accounts.google.com/* ]] && result="iap" || result="302 ${location}" ;;
  200) result="open" ;;
  403) grep -q "did not pass IAP" "${body}" 2>/dev/null && result="envoy-guard" || result="forbidden" ;;
  *) result="${code:-000}" ;;
  esac
  echo "${result}" >"${state_dir}/iap-check"
  [[ "${result}" =~ ^(iap|envoy-guard|open)$ ||
    ("${result}" == "forbidden" && "${MR_FRONT_DOOR_CLOUD_ARMOR}" == "true") ]]
}

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

fd_render() {
  local dst="${MR_WORK_DIR}/rendered/${cfg}/front-door"
  (
    MR_TEMPLATE_VARS="${MR_TEMPLATE_VARS} ${FD_TEMPLATE_VARS}"
    mr_render_dir "${MR_EXAMPLE_DIR}/manifests/front-door" "${dst}"
  )
  echo "${dst}"
}

# Runs under mr_stage (errexit off), so every step checks its own status.
fd_apply_manifests() {
  local dst="${1}"
  mr_kubectl "${cfg}" apply -f "${dst}/namespace.yaml" || return 1
  if [[ -n "${MR_IAP_OAUTH_CLIENT_ID}" ]]; then
    # The client secret is read from a local file; it's never rendered to disk.
    mr_kubectl "${cfg}" create secret generic "${oauth_secret_name}" -n "${ns}" \
      --from-file=key="${MR_IAP_OAUTH_CLIENT_SECRET_FILE}" --dry-run=client -o yaml |
      mr_kubectl "${cfg}" apply -f - || return 1
  else
    mr_kubectl "${cfg}" delete secret "${oauth_secret_name}" -n "${ns}" --ignore-not-found || return 1
  fi
  mr_kubectl "${cfg}" apply -f "${dst}/envoy.yaml" || return 1
  if [[ "${MR_FRONT_DOOR_NETWORK_POLICY}" == "true" ]]; then
    mr_kubectl "${cfg}" apply -f "${dst}/networkpolicy.yaml" || return 1
  else
    mr_kubectl "${cfg}" delete networkpolicy "${k8s_name}" -n "${ns}" --ignore-not-found || return 1
  fi
  mr_kubectl "${cfg}" apply -f "${dst}/policies.yaml" || return 1
  mr_kubectl "${cfg}" apply -f "${dst}/gateway.yaml" || return 1
  mr_kubectl "${cfg}" apply -f "${dst}/httproute.yaml"
}

# Grants roles/iap.httpsResourceAccessor on the front door backend service to
# exactly MR_FRONT_DOOR_IAP_MEMBERS (the policy is replaced, so members that
# were removed from the list, or added out of band, lose access).
fd_grant_iap_backend_service() {
  local bs policy
  bs="$(fd_backend_service)" || return 1
  policy="${state_dir}/iap-policy.json"
  fd_iap_members | jq -R . | jq -s '{bindings: [{role: "roles/iap.httpsResourceAccessor", members: .}]}' >"${policy}" || return 1
  mr_log "IAP access on backend service ${bs}: $(jq -c '.bindings[0].members' "${policy}")"
  gcloud iap web set-iam-policy "${policy}" --resource-type=backend-services --service="${bs}" \
    --project "${MR_PROJECT_ID}" --quiet >/dev/null
}

fd_print_usage() {
  local url="https://${MR_FRONT_DOOR_HOSTNAME}"
  cat <<EOF

Front door: ${url}  (IP $(fd_address))
Upstream:   http://${MR_FRONT_DOOR_UPSTREAM_VIP} (internal Gateway ${MR_GATEWAY_NAME}, $(mr_region "${cfg}"))
IAP access: $(fd_iap_members | paste -sd' ' -) (scope: ${MR_FRONT_DOOR_IAP_SCOPE})

Browser: open ${url}/v1/models and sign in with an allowed Google account.

Programmatic access: IAP accepts Google-signed credentials for an allowed
principal. With the Google-managed OAuth client (default), use a service
account that is in MR_FRONT_DOOR_IAP_MEMBERS (serviceAccount:...) and on which
you have roles/iam.serviceAccountTokenCreator:

  SA="<name>@${MR_PROJECT_ID}.iam.gserviceaccount.com"
  TOKEN="\$(gcloud auth print-access-token --impersonate-service-account="\${SA}" \\
    --scopes=openid,https://www.googleapis.com/auth/userinfo.email)"
  curl -sS -H "Authorization: Bearer \${TOKEN}" ${url}/v1/models
  curl -N -H "Authorization: Bearer \${TOKEN}" -H 'Content-Type: application/json' \\
    -d '{"model":"${MR_SERVED_MODEL_NAME}","messages":[{"role":"user","content":"Say hello."}],"max_tokens":32,"stream":true}' \\
    ${url}/v1/chat/completions
EOF
  if [[ -n "${MR_IAP_OAUTH_CLIENT_ID}" ]]; then
    cat <<EOF

With the custom OAuth client (MR_IAP_OAUTH_CLIENT_ID), an OIDC ID token whose
audience is the client ID also works. gcloud only mints ID tokens with a custom
audience for service accounts:

  TOKEN="\$(gcloud auth print-identity-token --impersonate-service-account="\${SA}" \\
    --audiences="${MR_IAP_OAUTH_CLIENT_ID}" --include-email)"
EOF
  fi
  cat <<EOF

Human users calling from scripts need an OAuth client that is allowlisted for
programmatic access (IAP programmatic_clients); see
manifests/front-door/README.md.
EOF
}

fd_emergency_rollback() {
  mr_log "Rolling back the external HTTPRoute and Gateway in ${ns} (fail closed)"
  mr_kubectl "${cfg}" delete httproute,gateway --all -n "${ns}" --ignore-not-found --wait=true --timeout=300s ||
    mr_log "ERROR: the rollback failed; delete the external Gateway now: kubectl --kubeconfig $(mr_kubeconfig "${cfg}") delete httproute,gateway --all -n ${ns}"
}

fd_security_policy_unused() {
  [[ -z "$(gcloud compute backend-services list --global --project "${MR_PROJECT_ID}" \
    --filter="securityPolicy~/${fd_security_policy_name}\$" --format='value(name)' 2>/dev/null)" ]]
}

fd_cert_unused() {
  local cert="${1}"
  [[ -z "$(gcloud compute target-https-proxies list --global --project "${MR_PROJECT_ID}" \
    --filter="sslCertificates~/${cert}\$" --format='value(name)' 2>/dev/null)" ]]
}

# Detaches Kubernetes Gateway/GCPBackendPolicy references to Cloud Armor or a
# previous certificate before Terraform destroys or replaces those GCP
# resources.
fd_prepare_existing_lb_for_tf() {
  local dst="${1}" current_cert
  mr_kubectl "${cfg}" get gateway "${k8s_name}" -n "${ns}" >/dev/null 2>&1 || return 0
  if [[ "${MR_FRONT_DOOR_CLOUD_ARMOR}" == "false" ]] && ! fd_security_policy_unused; then
    mr_log "Detaching Cloud Armor policy ${fd_security_policy_name} from GCPBackendPolicy before Terraform apply"
    mr_kubectl "${cfg}" apply -f "${dst}/policies.yaml" || return 1
    mr_wait_for 600 15 "Cloud Armor policy ${fd_security_policy_name} detached" fd_security_policy_unused || return 1
  fi
  current_cert="$(mr_kubectl "${cfg}" get gateway "${k8s_name}" -n "${ns}" \
    -o jsonpath='{.spec.listeners[0].tls.options.networking\.gke\.io/pre-shared-certs}' 2>/dev/null || true)"
  if [[ -n "${current_cert}" && "${current_cert}" != "${MR_FRONT_DOOR_CERT_NAME}" ]]; then
    mr_log "Certificate changed (${current_cert} -> ${MR_FRONT_DOOR_CERT_NAME}); recreating Gateway ${ns}/${k8s_name}"
    mr_kubectl "${cfg}" delete httproute,gateway --all -n "${ns}" --ignore-not-found --wait=true --timeout=600s || true
    mr_wait_for 600 15 "previous certificate ${current_cert} detached" fd_cert_unused "${current_cert}" || return 1
  fi
}

fd_apply() {
  mr_require_example_tools
  mr_validate_active_region_key "${cfg}"
  fd_validate_inputs
  mkdir -p "${state_dir}"
  [[ -f "$(mr_kubeconfig "${cfg}")" ]] || mr_get_credentials "${cfg}"

  # The only upstream: the internal Gateway VIP in the config cluster's region.
  local vip="${MR_FRONT_DOOR_UPSTREAM_VIP:-}"
  if [[ -z "${vip}" ]]; then
    vip="$(mr_gateway_vip "${MR_GATEWAY_NAME}" "${cfg}")" ||
      mr_die "no VIP for Gateway ${MR_GATEWAY_NAME} in ${cfg}; run scripts/deploy-arm.sh or scripts/set-route.sh first"
  fi
  "${MR_PYTHON}" -c 'import ipaddress, sys; assert ipaddress.ip_address(sys.argv[1]).is_private' "${vip}" 2>/dev/null ||
    mr_die "upstream '${vip}' is not a private IPv4 address"
  export MR_FRONT_DOOR_UPSTREAM_VIP="${vip}"

  if [[ -n "${MR_IAP_OAUTH_CLIENT_ID}" ]]; then
    export MR_FRONT_DOOR_IAP_OAUTH_FIELDS="      clientID: \"${MR_IAP_OAUTH_CLIENT_ID}\""$'\n'"      oauth2ClientSecret:"$'\n'"        name: ${oauth_secret_name}"
  else
    export MR_FRONT_DOOR_IAP_OAUTH_FIELDS=""
  fi
  if [[ "${MR_FRONT_DOOR_CLOUD_ARMOR}" == "true" ]]; then
    export MR_FRONT_DOOR_SECURITY_POLICY_FIELD="    securityPolicy: ${fd_security_policy_name}"
  else
    export MR_FRONT_DOOR_SECURITY_POLICY_FIELD=""
  fi

  mr_ensure_example_state_bucket
  local tfvars dst
  dst="$(fd_render)"
  mr_stage "front_door_prepare_lb" "global" fd_prepare_existing_lb_for_tf "${dst}"
  tfvars="$(fd_write_tfvars)"
  mr_stage "front_door_terraform" "global" mr_example_tf front_door apply "${tfvars}"

  # Fail closed: until IAP enforcement is verified below, any exit (an error,
  # mr_die, or Ctrl-C) deletes the external HTTPRoute and Gateway.
  trap fd_emergency_rollback EXIT
  mr_stage "front_door_apply_manifests" "global" fd_apply_manifests "${dst}"
  mr_stage "front_door_envoy_ready" "global" \
    mr_kubectl "${cfg}" rollout status "deployment/${k8s_name}" -n "${ns}" --timeout=600s
  mr_stage "front_door_gateway_programmed" "global" \
    mr_wait_for 1800 15 "Gateway ${ns}/${k8s_name} programmed" fd_gateway_programmed
  mr_log "Front door backend service: $(fd_backend_service)"
  if [[ "${MR_FRONT_DOOR_IAP_SCOPE}" == "backend-service" ]]; then
    mr_stage "front_door_iap_access" "global" fd_grant_iap_backend_service
  fi
  if ! mr_stage "front_door_iap_enabled" "global" \
    mr_wait_for 900 15 "IAP enabled on the front door backend service" fd_iap_enabled; then
    mr_kubectl "${cfg}" describe gcpbackendpolicy "${k8s_name}" -n "${ns}" >&2 || true
    mr_die "IAP is not enabled on the front door backend service; see 'Troubleshooting' in manifests/front-door/README.md"
  fi
  mr_log "Waiting for certificate ${MR_FRONT_DOOR_CERT_NAME} (usually 15-60 minutes after the load balancer is programmed)"
  if ! mr_stage "front_door_certificate_active" "global" \
    mr_wait_for "${MR_FRONT_DOOR_CERT_TIMEOUT_S}" 30 "certificate ${MR_FRONT_DOOR_CERT_NAME} ACTIVE" fd_cert_active; then
    mr_die "certificate ${MR_FRONT_DOOR_CERT_NAME} did not become ACTIVE within ${MR_FRONT_DOOR_CERT_TIMEOUT_S}s"
  fi
  rm -f "${state_dir}/iap-check"
  mr_stage "front_door_iap_enforced" "global" \
    mr_wait_for 600 15 "unauthenticated requests redirected to Google sign-in" fd_iap_enforced || true
  local check
  check="$(cat "${state_dir}/iap-check" 2>/dev/null || echo "000")"
  case "${check}" in
  iap) mr_log "IAP is enforced: unauthenticated requests are redirected to Google sign-in" ;;
  open)
    mr_die "SECURITY: an unauthenticated request with a forged IAP header got HTTP 200. Run '${0} destroy' and investigate."
    ;;
  envoy-guard)
    mr_die "IAP isn't enforced (the request reached Envoy without passing IAP); see 'Troubleshooting' in manifests/front-door/README.md"
    ;;
  forbidden)
    if [[ "${MR_FRONT_DOOR_CLOUD_ARMOR}" == "true" ]]; then
      mr_log "WARNING: unauthenticated request denied with 403 before IAP (this machine is likely outside MR_FRONT_DOOR_ALLOWED_CIDRS); backend iap.enabled=True verified via control plane"
    else
      mr_die "unexpected 403 (${check}) with Cloud Armor disabled; investigate before re-running apply"
    fi
    ;;
  *)
    mr_die "couldn't verify IAP enforcement (last response: ${check})"
    ;;
  esac
  trap - EXIT

  fd_print_usage
}

# ---------------------------------------------------------------------------
# Destroy
# ---------------------------------------------------------------------------

fd_state_has_resources() {
  mr_example_tf_state_has_resources front_door
}

fd_namespace_exists() {
  [[ -f "$(mr_kubeconfig "${cfg}")" ]] &&
    mr_kubectl "${cfg}" get namespace "${ns}" >/dev/null 2>&1
}

# Succeeds when no load balancer resource uses the address, any certificate for
# this front door, or the Cloud Armor policy anymore.
fd_lb_deleted() {
  local users cert_prefix
  cert_prefix="$(fd_cert_prefix)"
  users="$(gcloud compute addresses describe "${MR_FRONT_DOOR_ADDRESS_NAME}" --global \
    --project "${MR_PROJECT_ID}" --format='value(users)' 2>/dev/null || true)"
  [[ -z "${users}" ]] || return 1
  [[ -z "$(gcloud compute target-https-proxies list --global --project "${MR_PROJECT_ID}" \
    --filter="sslCertificates~/${cert_prefix}-cert-" --format='value(name)')" ]] || return 1
  [[ -z "$(gcloud compute backend-services list --global --project "${MR_PROJECT_ID}" \
    --filter="securityPolicy~/${fd_security_policy_name}\$" --format='value(name)')" ]] || return 1
  [[ -z "$(gcloud compute backend-services list --global --project "${MR_PROJECT_ID}" \
    --filter="name~^gkegw1-.*-${ns}-${k8s_name}-" --format='value(name)')" ]]
}

# Runs under mr_stage (errexit off), so every step checks its own status.
fd_delete_kubernetes() {
  mr_kubectl "${cfg}" delete httproute,gateway --all -n "${ns}" --ignore-not-found --wait=true --timeout=900s || true
  mr_wait_for 900 15 "front door load balancer deleted" fd_lb_deleted || return 1
  mr_kubectl "${cfg}" delete namespace "${ns}" --ignore-not-found --wait=true --timeout=900s
}

fd_destroy_tfvars() {
  local saved="${MR_WORK_DIR}/terraform/front_door.tfvars.json"
  if [[ -s "${saved}" ]]; then
    echo "${saved}"
    return
  fi
  mkdir -p "$(dirname "${saved}")"
  local hostname="${MR_FRONT_DOOR_HOSTNAME}"
  if [[ ! "${hostname}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?\.endpoints\.[a-z0-9][-a-z0-9.]*\.cloud\.goog$ ]]; then
    hostname="destroy.endpoints.${MR_PROJECT_ID//:/-}.cloud.goog"
  fi
  jq -n \
    --arg project_id "${MR_PROJECT_ID}" \
    --arg name "${MR_FRONT_DOOR_NAME}" \
    --arg hostname "${hostname}" \
    '{
      project_id: $project_id,
      name: $name,
      hostname: $hostname,
      iap_members: ["user:destroy@example.com"],
      iap_grant_project_level: false,
      cloud_armor_enabled: false,
      cloud_armor_allowed_source_cidrs: []
    }' >"${saved}"
  echo "${saved}"
}

fd_destroy() {
  # The cluster might exist without a local kubeconfig (for example, on another
  # machine); without it, the load balancer can't be deleted.
  [[ -f "$(mr_kubeconfig "${cfg}")" ]] || mr_get_credentials "${cfg}" 2>/dev/null || true
  if fd_namespace_exists; then
    mr_stage "front_door_delete_kubernetes" "global" fd_delete_kubernetes
  fi
  if fd_state_has_resources; then
    local tfvars
    tfvars="$(fd_destroy_tfvars)"
    mr_stage "front_door_terraform_destroy" "global" mr_example_tf front_door destroy "${tfvars}"
  fi
  rm -f "${MR_WORK_DIR}/terraform/front_door.tfvars.json"
  mr_log "Front door removed."
}

case "${action}" in
apply) fd_apply ;;
destroy) fd_destroy ;;
exists) fd_namespace_exists || fd_state_has_resources ;;
*) mr_die "usage: ${0} [apply|destroy|exists]" ;;
esac
