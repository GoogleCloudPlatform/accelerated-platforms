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

# stage.sh — Stager for the 4-Act Security & Detonation Reference Implementation.
# Validates GKE control-plane and worker-node versions (>= 1.37), deploys upstream
# Agent Substrate v1.0.0 (`b34fbee7`) with native SPIFFE mTLS ingress (`atenet-router:443`),
# builds & pins an immutable `@sha256` Google ADK (`google-adk`) container image in
# Artifact Registry, and stages the 4 security demo actors in atespace 'security-demo'.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${USE_CASE_DIR}/app"
MANIFESTS_DIR="${USE_CASE_DIR}/manifests"
STATE_DIR="${USE_CASE_DIR}/.state"
BIN_DIR="${USE_CASE_DIR}/bin"
mkdir -p "${STATE_DIR}" "${BIN_DIR}"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/port-forward.sh"

export APP_IMAGE="${APP_IMAGE:-}"
export AR_REPO="${AR_REPO:-agent-substrate}"
export REFRESH_ACTORS="${REFRESH_ACTORS:-false}"
export PROVISION_GCP_INFRA="${PROVISION_GCP_INFRA:-true}"
export MIN_GKE_VERSION="${MIN_GKE_VERSION:-1.37}"

KUBE_CTX="$(kubectl config current-context 2>/dev/null || true)"
CTX_PROJECT=""
CTX_LOCATION=""
CTX_CLUSTER=""
if [[ "${KUBE_CTX}" =~ ^gke_([^_]+)_([^_]+)_(.+)$ ]]; then
  CTX_PROJECT="${BASH_REMATCH[1]}"
  CTX_LOCATION="${BASH_REMATCH[2]}"
  CTX_CLUSTER="${BASH_REMATCH[3]}"
fi

export PROJECT_ID="${PROJECT_ID:-${CTX_PROJECT:-$(gcloud config get-value project 2>/dev/null)}}"
export CLUSTER_NAME="${CLUSTER_NAME:-${CTX_CLUSTER:-agent-substrate-live}}"
export CLUSTER_LOCATION="${CLUSTER_LOCATION:-${CTX_LOCATION:-us-central1-b}}"
if [[ -z "${REGION:-}" ]]; then
  if [[ "${CLUSTER_LOCATION}" =~ -[a-z]$ ]]; then
    REGION="${CLUSTER_LOCATION%-*}"
  else
    REGION="${CLUSTER_LOCATION}"
  fi
fi
export REGION
export NAMESPACE="${NAMESPACE:-agent-sandbox}"
export SECRETS_NAMESPACE="${SECRETS_NAMESPACE:-agent-secrets}"
export ATESPACE="${ATESPACE:-security-demo}"
export GATEWAY_LOCAL_PORT="${GATEWAY_LOCAL_PORT:-8081}"
export PROM_LOCAL_PORT="${PROM_LOCAL_PORT:-9090}"
export SUBSTRATE_REF="${SUBSTRATE_REF:-v1.0.0}"
export SUBSTRATE_COMMIT="${SUBSTRATE_COMMIT:-b34fbee742906494b5eb4f1f36987176bf8770a4}"
export SUBSTRATE_IMAGE_REPO="${SUBSTRATE_IMAGE_REPO:-ghcr.io/agent-substrate/substrate}"
export SUBSTRATE_IMAGE_TAG="${SUBSTRATE_IMAGE_TAG:-${SUBSTRATE_REF}}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"
CLEAN_CLUSTER_SLUG="$(printf '%s' "${CLUSTER_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | cut -c1-18 | sed 's/-\+$//')"
RAW_BUCKET="$(printf '%s-%s-ate-snaps' "${PROJECT_ID:0:28}" "${CLUSTER_NAME:0:20}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | sed 's/-\+$//; s/^-\+//')"
export BUCKET_NAME="${BUCKET_NAME:-${RAW_BUCKET:0:63}}"
export SNAPSHOT_TRANSFER_GSA_NAME="${SNAPSHOT_TRANSFER_GSA_NAME:-ate-snap-${CLEAN_CLUSTER_SLUG:-gke}}"
export PATH="${BIN_DIR}:$(go env GOPATH 2>/dev/null)/bin:${PATH}"

[[ -n "${PROJECT_ID}" ]] || { echo "Error: PROJECT_ID is empty; set PROJECT_ID=<gcp-project-id>" >&2; exit 1; }

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }

wait_for() {
  local timeout="$1" desc="$2"; shift 2
  local deadline=$((SECONDS + timeout))
  while ! "$@" >/dev/null 2>&1; do
    if (( SECONDS >= deadline )); then
      echo "Error: timed out after ${timeout}s waiting for ${desc}" >&2
      return 1
    fi
    sleep 3
  done
  ok "${desc}"
}

verify_gke_version() {
  local ver_json nodes_json
  ver_json="$(kubectl version -o json)"
  nodes_json="$(kubectl get nodes -o json)"
  python3 - "${MIN_GKE_VERSION}" "${ver_json}" "${nodes_json}" <<'EOF'
import json, re, sys

min_parts = [int(x) for x in sys.argv[1].split(".")[:2]]
ver_doc = json.loads(sys.argv[2])
nodes_doc = json.loads(sys.argv[3])

def parse_minor(raw: str) -> tuple[int, int]:
    m = re.match(r"^v?(\d+)\.(\d+)", raw.strip())
    if not m:
        raise SystemExit(f"Error: unable to parse Kubernetes version {raw!r}")
    return int(m.group(1)), int(m.group(2))

srv = ver_doc.get("serverVersion") or {}
srv_str = f"{srv.get('major', '')}.{re.sub(r'[^0-9].*$', '', str(srv.get('minor', '')))}"
if parse_minor(srv_str) < tuple(min_parts):
    raise SystemExit(
        f"Error: GKE control plane is {srv.get('gitVersion')}, but Agent Substrate requires >= {sys.argv[1]} "
        "(native PodCertificateRequest & ClusterTrustBundle)."
    )

items = nodes_doc.get("items") or []
if not items:
    raise SystemExit("Error: cluster has 0 ready worker nodes.")
for node in items:
    name = (node.get("metadata") or {}).get("name", "<unknown>")
    kv = ((node.get("status") or {}).get("nodeInfo") or {}).get("kubeletVersion", "")
    if parse_minor(kv) < tuple(min_parts):
        raise SystemExit(
            f"Error: worker node {name} runs kubelet {kv}, but Agent Substrate requires >= {sys.argv[1]}."
        )
EOF
}

ensure_template() {
  local as="$1" name="$2" file="$3"
  if ! kubectl ate get actor-template "${name}" -a "${as}" >/dev/null 2>&1; then
    kubectl ate create actor-template -f "${file}"
  fi
  _tpl_ready() {
    kubectl ate get actor-template "${name}" -a "${as}" -o json | jq -e '.status.goldenSnapshotStatus.goldenTag.name' >/dev/null
  }
  wait_for 600 "golden snapshot for template ${as}/${name}" _tpl_ready
}

ensure_actor() {
  local as="$1" name="$2" template="$3"
  if ! kubectl ate get actor "${name}" -a "${as}" >/dev/null 2>&1; then
    kubectl ate create actor "${name}" --template="${template}" -a "${as}"
  fi
}

actor_state() {
  kubectl ate get actor "$2" -a "$1" -o json | jq -r '.status.state // "UNKNOWN"' | sed 's/^ACTOR_STATE_//'
}

suspend_actor() {
  local as="$1" name="$2"
  if [[ "$(actor_state "${as}" "${name}")" == "RUNNING" ]]; then
    kubectl ate suspend actor "${name}" -a "${as}" >/dev/null
  fi
  _is_susp() { [[ "$(actor_state "${as}" "${name}")" == "SUSPENDED" ]]; }
  wait_for 120 "actor ${as}/${name} SUSPENDED" _is_susp
}

apply_egress_policy() {
  local as="$1" actor="$2" file="$3"
  local cur uid ver tmp
  cur="$(kubectl ate get egress-policy "${actor}" -a "${as}" -o json 2>/dev/null || true)"
  uid="$(jq -r '.metadata.uid // empty' <<<"${cur}" 2>/dev/null || true)"
  ver="$(jq -r '.metadata.version // empty' <<<"${cur}" 2>/dev/null || true)"
  if [[ -n "${uid}" && -n "${ver}" ]]; then
    tmp="$(mktemp)"
    cat > "${tmp}" <<EOF
metadata:
  atespace: ${as}
  name: default
  uid: "${uid}"
  version: "${ver}"
$(cat "${file}")
EOF
    kubectl ate update egress-policy "${actor}" -a "${as}" -f "${tmp}" >/dev/null
    rm -f "${tmp}"
  else
    kubectl ate create egress-policy "${actor}" -a "${as}" -f "${file}" >/dev/null
  fi
}

step "1/6: Verifying GKE >= ${MIN_GKE_VERSION}, GCP Snapshot Storage, and Agent Substrate (${SUBSTRATE_REF})"
if ! kubectl --request-timeout=5s cluster-info >/dev/null 2>&1; then
  echo "Fetching cluster credentials for '${CLUSTER_NAME}' (${CLUSTER_LOCATION})..."
  gcloud container clusters get-credentials "${CLUSTER_NAME}" \
    --location "${CLUSTER_LOCATION}" \
    --project "${PROJECT_ID}" \
    --dns-endpoint >/dev/null
fi
verify_gke_version
ok "Verified GKE control plane and worker nodes >= ${MIN_GKE_VERSION}"

if ! kubectl get ns gke-managed-otel >/dev/null 2>&1; then
  gcloud beta container clusters update "${CLUSTER_NAME}" \
    --project "${PROJECT_ID}" \
    --location "${CLUSTER_LOCATION}" \
    --managed-otel-scope=COLLECTION_AND_INSTRUMENTATION_COMPONENTS \
    --quiet >/dev/null
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
WI="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject"
TRANSFER_GSA_EMAIL="${SNAPSHOT_TRANSFER_GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ "${PROVISION_GCP_INFRA}" == "true" ]]; then
  gcloud services enable --project "${PROJECT_ID}" \
    container.googleapis.com storage.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
    artifactregistry.googleapis.com cloudbuild.googleapis.com \
    aiplatform.googleapis.com monitoring.googleapis.com logging.googleapis.com cloudtrace.googleapis.com >/dev/null

  LIFECYCLE_FILE="$(mktemp)"
  cat > "${LIFECYCLE_FILE}" <<'EOF'
{
  "rule": [
    {"action": {"type": "Delete"}, "condition": {"age": 7}},
    {"action": {"type": "AbortIncompleteMultipartUpload"}, "condition": {"age": 1}}
  ]
}
EOF
  if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${BUCKET_NAME}" \
      --project "${PROJECT_ID}" \
      --location "${REGION}" \
      --uniform-bucket-level-access \
      --pap
  fi
  gcloud storage buckets update "gs://${BUCKET_NAME}" \
    --project "${PROJECT_ID}" \
    --pap \
    --lifecycle-file="${LIFECYCLE_FILE}" >/dev/null
  rm -f "${LIFECYCLE_FILE}"

  if ! gcloud iam service-accounts describe "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${SNAPSHOT_TRANSFER_GSA_NAME}" \
      --project "${PROJECT_ID}" \
      --display-name "Agent Substrate Snapshot Transfers" >/dev/null
  fi

  retry_iam() {
    local attempt
    for attempt in 1 2 3 4 5 6; do
      if "$@" >/dev/null 2>&1; then
        return 0
      fi
      sleep $((attempt * 2))
    done
    "$@" >/dev/null
  }

  for member in "${WI}/ns/ate-system/sa/ate-api-server" "serviceAccount:${TRANSFER_GSA_EMAIL}"; do
    retry_iam gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
      --member="${member}" --role="roles/storage.objectAdmin" --condition=None
    retry_iam gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
      --member="${member}" --role="roles/storage.bucketViewer" --condition=None
  done
  retry_iam gcloud iam service-accounts add-iam-policy-binding "${TRANSFER_GSA_EMAIL}" \
    --project "${PROJECT_ID}" \
    --member="${WI}/ns/ate-system/sa/ate-api-server" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --condition=None
  retry_iam gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="${WI}/ns/${NAMESPACE}/sa/gateway" \
    --role="roles/aiplatform.user" \
    --condition=None --quiet
  retry_iam gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="${WI}/ns/${NAMESPACE}/sa/prometheus-ui" \
    --role="roles/monitoring.viewer" \
    --condition=None --quiet
  ok "Standalone Option A GCP bucket & Workload Identity IAM bindings ready"
else
  ok "Using Terraform-managed GCP bucket (gs://${BUCKET_NAME}) & IAM bindings"
fi

SUBSTRATE_SRC="${STATE_DIR}/substrate"
if [[ ! -d "${SUBSTRATE_SRC}/.git" ]]; then
  git clone --quiet https://github.com/agent-substrate/substrate "${SUBSTRATE_SRC}"
fi
if ! git -C "${SUBSTRATE_SRC}" cat-file -e "${SUBSTRATE_COMMIT}^{commit}" 2>/dev/null; then
  git -C "${SUBSTRATE_SRC}" fetch --quiet --tags origin
fi
git -C "${SUBSTRATE_SRC}" checkout --quiet "${SUBSTRATE_COMMIT}"

CACHED_KUBECTL_ATE="${BIN_DIR}/kubectl-ate-${SUBSTRATE_COMMIT:0:12}"
if [[ ! -x "${CACHED_KUBECTL_ATE}" ]]; then
  (cd "${SUBSTRATE_SRC}" && GOWORK=off go build -o "${CACHED_KUBECTL_ATE}" ./cmd/kubectl-ate)
fi
cp -f "${CACHED_KUBECTL_ATE}" "${BIN_DIR}/kubectl-ate"
ok "kubectl-ate (${SUBSTRATE_REF} @ ${SUBSTRATE_COMMIT:0:8}) ready"

INGRESS_SPIFFE="spiffe://cluster.local/ns/${NAMESPACE}/sa/gateway"
INSTALLED_APISERVER_IMG="$(kubectl -n ate-system get deploy ate-api-server -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
INSTALLED_ROUTER_ARGS="$(kubectl -n ate-system get deploy atenet-router -o jsonpath='{.spec.template.spec.containers[0].args[*]}' 2>/dev/null || true)"

if [[ -z "${INSTALLED_APISERVER_IMG}" \
   || "${INSTALLED_APISERVER_IMG}" != *":${SUBSTRATE_IMAGE_TAG}"* \
   || "${INSTALLED_ROUTER_ARGS}" != *"--ingress-allowed-spiffe-ids=${INGRESS_SPIFFE}"* ]]; then
  CURRENT_CTX="$(kubectl config current-context)"
  PG_SC_ARGS=()
  if kubectl get sc dynamic-rwo >/dev/null 2>&1 && ! kubectl -n ate-system get sts postgres >/dev/null 2>&1; then
    PG_SC_ARGS+=(--ateapi-postgres-storage-class=dynamic-rwo)
  fi
  (cd "${SUBSTRATE_SRC}" && GOWORK=off go run ./cmd/ate-setup deploy ate-system \
    --context="${CURRENT_CTX}" \
    --rollout-timeout=5m \
    --sandbox-classes="gvisor" \
    --credential-provider='{"name":"k8s.io"}' \
    --snapshot-location="gs://${BUCKET_NAME}/" \
    --snapshot-transfer-gsa-name="${SNAPSHOT_TRANSFER_GSA_NAME}" \
    --ingress-allowed-spiffe-ids="${INGRESS_SPIFFE}" \
    --image-repo "${SUBSTRATE_IMAGE_REPO}" \
    --image-tag "${SUBSTRATE_IMAGE_TAG}" \
    "${PG_SC_ARGS[@]}")
fi

WORKER_DIGEST="$(cd "${SUBSTRATE_SRC}" && GOWORK=off go run github.com/google/go-containerregistry/cmd/crane@v0.20.3 digest "${SUBSTRATE_IMAGE_REPO}/ateworker-gvisor:${SUBSTRATE_IMAGE_TAG}")"
export WORKER_IMAGE="${SUBSTRATE_IMAGE_REPO}/ateworker-gvisor:${SUBSTRATE_IMAGE_TAG}@${WORKER_DIGEST}"

kubectl -n ate-system wait --for=condition=Available deploy --all --timeout=10m >/dev/null
kubectl -n ate-system rollout status ds/atelet --timeout=10m >/dev/null
ok "Agent Substrate (${SUBSTRATE_REF}) control plane ready (native SPIFFE mTLS on atenet-router:443)"

resolve_image_digest() {
  local img="$1"
  local digest=""
  digest="$(gcloud artifacts docker images describe "${img}" --project "${PROJECT_ID}" --format='value(image_summary.digest)' 2>/dev/null || true)"
  if [[ -z "${digest}" ]]; then
    digest="$(cd "${SUBSTRATE_SRC}" && GOWORK=off go run github.com/google/go-containerregistry/cmd/crane@v0.20.3 digest "${img}")"
  fi
  printf '%s' "${digest}"
}

if [[ -n "${APP_IMAGE}" ]]; then
  if [[ "${APP_IMAGE}" != *"@sha256:"* ]]; then
    APP_DIGEST="$(resolve_image_digest "${APP_IMAGE}")"
    APP_IMAGE="${APP_IMAGE}@${APP_DIGEST}"
  fi
  ok "Using caller-supplied container image (${APP_IMAGE})"
else
  if [[ "${PROVISION_GCP_INFRA}" == "true" ]]; then
    if ! gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
      gcloud artifacts repositories create "${AR_REPO}" \
        --repository-format=docker \
        --location="${REGION}" \
        --project="${PROJECT_ID}" \
        --description="Agent Substrate Security Demo container images" >/dev/null
    fi
    NODE_SA="$(gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --format='value(nodePools[0].config.serviceAccount)' 2>/dev/null || true)"
    if [[ -n "${NODE_SA}" && "${NODE_SA}" != "default" ]]; then
      gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
        --location="${REGION}" \
        --project="${PROJECT_ID}" \
        --member="serviceAccount:${NODE_SA}" \
        --role="roles/artifactregistry.reader" \
        --condition=None >/dev/null
    fi
  fi

  APP_CONTENT_SHA="$(cat "${APP_DIR}/Dockerfile" "${APP_DIR}/gateway.py" "${APP_DIR}/gemini_agent.py" "${APP_DIR}/egress_agent.py" "${APP_DIR}/partner_api.py" | sha256sum | cut -c1-12)"
  CANDIDATE_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/demo-app:adk-${APP_CONTENT_SHA}"
  APP_DIGEST="$(gcloud artifacts docker images describe "${CANDIDATE_IMAGE}" --project "${PROJECT_ID}" --format='value(image_summary.digest)' 2>/dev/null || true)"
  if [[ -z "${APP_DIGEST}" ]]; then
    step "Building Google ADK container image (${CANDIDATE_IMAGE}) via Cloud Build"
    gcloud builds submit "${APP_DIR}" --project "${PROJECT_ID}" --tag "${CANDIDATE_IMAGE}" --quiet
    APP_DIGEST="$(gcloud artifacts docker images describe "${CANDIDATE_IMAGE}" --project "${PROJECT_ID}" --format='value(image_summary.digest)')"
    ok "Built immutable Google ADK image (${CANDIDATE_IMAGE}@${APP_DIGEST})"
  else
    ok "Reusing cached Google ADK image (${CANDIDATE_IMAGE}@${APP_DIGEST})"
  fi
  APP_IMAGE="${CANDIDATE_IMAGE}@${APP_DIGEST}"
fi

export GATEWAY_IMAGE="${APP_IMAGE}"
export AGENT_IMAGE="${APP_IMAGE}"
export GATEWAY_CODE_SHA="$(printf '%s' "${APP_IMAGE}" | sha256sum | awk '{print $1}')"

step "2/6: Ensuring WorkerPool (2 gVisor worker pods), atespace (${ATESPACE}), and mTLS Gateway"
envsubst '${NAMESPACE} ${WORKER_IMAGE}' < "${MANIFESTS_DIR}/workerpool.yaml.tmpl" | kubectl apply -f -
_two_workers() {
  [[ "$(kubectl -n "${NAMESPACE}" get pods -l workload=substrate-agent --field-selector=status.phase=Running -o name | wc -l)" -ge 2 ]]
}
wait_for 600 "2 running gVisor worker pods" _two_workers

if ! kubectl ate get atespace "${ATESPACE}" >/dev/null 2>&1; then
  kubectl ate create atespace "${ATESPACE}"
fi

if ! kubectl -n "${NAMESPACE}" get secret gateway-admin-token >/dev/null 2>&1; then
  ADMIN_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  kubectl -n "${NAMESPACE}" create secret generic gateway-admin-token \
    --from-literal=token="${ADMIN_TOKEN}" >/dev/null
fi
ADMIN_TOKEN="$(kubectl -n "${NAMESPACE}" get secret gateway-admin-token -o jsonpath='{.data.token}' | base64 -d)"

envsubst '${NAMESPACE} ${ATESPACE} ${GEMINI_MODEL} ${PROJECT_ID} ${GATEWAY_IMAGE} ${GATEWAY_CODE_SHA}' \
  < "${MANIFESTS_DIR}/gateway.yaml.tmpl" | kubectl apply -f -
envsubst '${NAMESPACE} ${PROJECT_ID}' < "${MANIFESTS_DIR}/observability.yaml.tmpl" | kubectl apply -f -
kubectl -n "${NAMESPACE}" rollout status deploy/gateway --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/prometheus-ui --timeout=180s

ensure_managed_port_forward "${STATE_DIR}" gateway "${NAMESPACE}" deploy/gateway "${GATEWAY_LOCAL_PORT}" 8081 "/identity" "agent-substrate-gateway"
ensure_managed_port_forward "${STATE_DIR}" prometheus "${NAMESPACE}" deploy/prometheus-ui "${PROM_LOCAL_PORT}" 9090 "/-/ready" ""
if ! "${SCRIPT_DIR}/dashboards.sh"; then
  echo "Warning: Cloud Monitoring dashboard provisioning failed; continuing stage.sh." >&2
fi

step "3/6: Configuring Act 3 isolated Secret (${SECRETS_NAMESPACE}), non-reflecting partner-api, and credential policy"
kubectl create namespace "${SECRETS_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
if ! kubectl -n "${SECRETS_NAMESPACE}" get secret example-api >/dev/null 2>&1; then
  DEMO_API_TOKEN="demo-substrate-cred-$(python3 -c 'import secrets; print(secrets.token_hex(12))')"
  kubectl -n "${SECRETS_NAMESPACE}" create secret generic example-api \
    --from-literal=token="${DEMO_API_TOKEN}" >/dev/null
fi
envsubst '${SECRETS_NAMESPACE} ${GATEWAY_IMAGE} ${GATEWAY_CODE_SHA}' \
  < "${MANIFESTS_DIR}/partner-api.yaml.tmpl" | kubectl apply -f -
kubectl -n "${SECRETS_NAMESPACE}" rollout status deploy/partner-api --timeout=180s

envsubst '${ATESPACE} ${SECRETS_NAMESPACE}' < "${MANIFESTS_DIR}/namespace-policy.yaml.tmpl" | kubectl apply -f -
kubectl -n ate-system rollout restart deploy/k8s-credential-provider
kubectl -n ate-system rollout status deploy/k8s-credential-provider --timeout=180s

step "4/6: Staging Act 1 Actor 'py-detonation-agent' (python-sandbox-v1 on gVisor)"
envsubst '${ATESPACE}' < "${MANIFESTS_DIR}/python-sandbox-v1.yaml.tmpl" > "${STATE_DIR}/python-sandbox-v1.yaml"
ensure_template "${ATESPACE}" python-sandbox-v1 "${STATE_DIR}/python-sandbox-v1.yaml"
ensure_actor "${ATESPACE}" py-detonation-agent python-sandbox-v1
kubectl ate delete egress-policy py-detonation-agent -a "${ATESPACE}" >/dev/null 2>&1 || true
suspend_actor "${ATESPACE}" py-detonation-agent

step "5/6: Staging Act 3 Actor 'egress-agent' (app/egress_agent.py with MITM ClusterTrustBundle)"
if [[ "${REFRESH_ACTORS}" == "true" ]]; then
  kubectl ate delete actor egress-agent -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor-template egress-agent-v1 -a "${ATESPACE}" >/dev/null 2>&1 || true
fi
envsubst '${ATESPACE} ${AGENT_IMAGE}' \
  < "${MANIFESTS_DIR}/egress-agent-v1.yaml.tmpl" > "${STATE_DIR}/egress-agent-v1.yaml"
envsubst '${SECRETS_NAMESPACE}' \
  < "${MANIFESTS_DIR}/egress-fetch.yaml.tmpl" > "${STATE_DIR}/egress-fetch.yaml"
ensure_template "${ATESPACE}" egress-agent-v1 "${STATE_DIR}/egress-agent-v1.yaml"
ensure_actor "${ATESPACE}" egress-agent egress-agent-v1
apply_egress_policy "${ATESPACE}" egress-agent "${STATE_DIR}/egress-fetch.yaml"
suspend_actor "${ATESPACE}" egress-agent

step "6/6: Staging Act 2 & Act 4 Google ADK Actors 'gemini-agent' and 'gemini-agent-forensic'"
if [[ "${REFRESH_ACTORS}" == "true" ]]; then
  kubectl ate delete actor gemini-agent-forensic -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete tag clean-checkpoint-tag -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor gemini-agent -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor-template gemini-agent-v1 -a "${ATESPACE}" >/dev/null 2>&1 || true
fi
envsubst '${ATESPACE} ${NAMESPACE} ${AGENT_IMAGE} ${GEMINI_MODEL}' \
  < "${MANIFESTS_DIR}/gemini-agent-v1.yaml.tmpl" > "${STATE_DIR}/gemini-agent-v1.yaml"
envsubst '${NAMESPACE}' \
  < "${MANIFESTS_DIR}/egress-gateway.yaml.tmpl" > "${STATE_DIR}/egress-gateway.yaml"
ensure_template "${ATESPACE}" gemini-agent-v1 "${STATE_DIR}/gemini-agent-v1.yaml"
ensure_actor "${ATESPACE}" gemini-agent gemini-agent-v1
apply_egress_policy "${ATESPACE}" gemini-agent "${STATE_DIR}/egress-gateway.yaml"

_seed_clean_policy() {
  ensure_managed_port_forward "${STATE_DIR}" gateway "${NAMESPACE}" deploy/gateway "${GATEWAY_LOCAL_PORT}" 8081 "/identity" "agent-substrate-gateway" || return 1
  local resp st
  resp="$(curl -fsS --max-time 45 "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/chat/gemini-agent" \
    -H "Content-Type: application/json" \
    -H "X-Gateway-Admin-Token: ${ADMIN_TOKEN}" \
    -d '{"message":"Set our runtime approval policy to REQUIRE_HUMAN_APPROVAL using set_approval_policy."}')" || return 1
  jq -e '.approvalPolicy == "REQUIRE_HUMAN_APPROVAL"' <<<"${resp}" >/dev/null 2>&1 || return 1
  st="$(curl -fsS --max-time 15 "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/actors/gemini-agent/state" \
    -H "X-Gateway-Admin-Token: ${ADMIN_TOKEN}")" || return 1
  jq -e '.approvalPolicy == "REQUIRE_HUMAN_APPROVAL" and .diskPolicy == "REQUIRE_HUMAN_APPROVAL"' <<<"${st}" >/dev/null 2>&1
}
wait_for 180 "seed REQUIRE_HUMAN_APPROVAL checkpoint into Google ADK actor gemini-agent" _seed_clean_policy
suspend_actor "${ATESPACE}" gemini-agent

if ! kubectl ate get tag clean-checkpoint-tag -a "${ATESPACE}" >/dev/null 2>&1; then
  kubectl ate create tag clean-checkpoint-tag --actor=gemini-agent -a "${ATESPACE}"
fi
if ! kubectl ate get actor gemini-agent-forensic -a "${ATESPACE}" >/dev/null 2>&1; then
  kubectl ate create actor gemini-agent-forensic --template=gemini-agent-v1 --tag=clean-checkpoint-tag -a "${ATESPACE}"
fi
apply_egress_policy "${ATESPACE}" gemini-agent-forensic "${STATE_DIR}/egress-gateway.yaml"
suspend_actor "${ATESPACE}" gemini-agent-forensic

ok "4-Act Security Detonation Demo staged in atespace '${ATESPACE}' (4 actors):"
kubectl ate get actors -a "${ATESPACE}"
