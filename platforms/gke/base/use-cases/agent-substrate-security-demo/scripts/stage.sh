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

# stage.sh — Production Stager for the 4-Act Security & Detonation Reference Implementation.
# Deploys upstream Agent Substrate (v1.0.0), builds & caches an immutable @sha256 container
# image bundling Google ADK (`google-adk`) in Artifact Registry via Cloud Build, and stages
# the 4 security demo actors in atespace 'security-demo' backed by GKE Workload Identity
# -> Google Cloud's Gemini platform (formerly Vertex AI) / Gemini 3.8 Flash:
#   1. py-detonation-agent   (Act 1: gVisor Python sandbox detonation)
#   2. gemini-agent          (Act 2 & Act 4: Stateful Google ADK Gemini actor with PINEAPPLE-42 checkpoint)
#   3. gemini-agent-forensic (Act 2: Forensic clone from clean-checkpoint-tag)
#   4. egress-agent          (Act 3: Zero-secret egress credential injection & DNS relay block)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${USE_CASE_DIR}/app"
MANIFESTS_DIR="${USE_CASE_DIR}/manifests"
STATE_DIR="${USE_CASE_DIR}/.state"
BIN_DIR="${USE_CASE_DIR}/bin"
mkdir -p "${STATE_DIR}" "${BIN_DIR}"

export APP_IMAGE="${APP_IMAGE:-}"
export AR_REPO="${AR_REPO:-agent-substrate}"
export REFRESH_ACTORS="${REFRESH_ACTORS:-false}"

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
export NAMESPACE="${NAMESPACE:-workshop}"
export ATESPACE="${ATESPACE:-security-demo}"
export ROUTER_LOCAL_PORT="${ROUTER_LOCAL_PORT:-8080}"
export GATEWAY_LOCAL_PORT="${GATEWAY_LOCAL_PORT:-8081}"
export PROM_LOCAL_PORT="${PROM_LOCAL_PORT:-9090}"
export SUBSTRATE_REF="${SUBSTRATE_REF:-v1.0.0}"
export SUBSTRATE_IMAGE_REPO="${SUBSTRATE_IMAGE_REPO:-ghcr.io/agent-substrate/substrate}"
export SUBSTRATE_IMAGE_TAG="${SUBSTRATE_IMAGE_TAG:-${SUBSTRATE_REF}}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"
BUCKET_PREFIX="$(printf '%s' "${USER:-ate}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')"
RAW_BUCKET="${BUCKET_PREFIX:-ate}-${CLUSTER_NAME}-${PROJECT_ID:0:8}"
RAW_BUCKET="$(printf '%s' "${RAW_BUCKET:0:63}" | tr '[:upper:]' '[:lower:]' | sed 's/-\+$//; s/^-\+//')"
export BUCKET_NAME="${BUCKET_NAME:-${RAW_BUCKET}}"
export SNAPSHOT_TRANSFER_GSA_NAME="${SNAPSHOT_TRANSFER_GSA_NAME:-ate-snapshot-transfer}"
export PATH="${BIN_DIR}:$(go env GOPATH 2>/dev/null)/bin:${PATH}"

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

ensure_template() {
  local as="$1" name="$2" file="$3"
  kubectl ate get actor-template "${name}" -a "${as}" >/dev/null 2>&1 || kubectl ate create actor-template -f "${file}"
  _tpl_ready() {
    kubectl ate get actor-template "${name}" -a "${as}" -o json | jq -e '.status.goldenSnapshotStatus.goldenTag.name' >/dev/null
  }
  wait_for 600 "golden snapshot for template ${as}/${name}" _tpl_ready
}

ensure_actor() {
  local as="$1" name="$2" template="$3"
  kubectl ate get actor "${name}" -a "${as}" >/dev/null 2>&1 || kubectl ate create actor "${name}" --template="${template}" -a "${as}"
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

start_port_forward() {
  local name="$1" ns="$2" target="$3" lport="$4" rport="$5"
  local pidfile="${STATE_DIR}/pf-${name}.pid"
  if [[ -f "${pidfile}" ]] && kill -0 "$(cat "${pidfile}")" 2>/dev/null; then
    kill "$(cat "${pidfile}")" 2>/dev/null || true
    rm -f "${pidfile}"
  fi
  pkill -f "kubectl[[:space:]]+port-forward.*${lport}:${rport}" 2>/dev/null || true
  kubectl -n "${ns}" port-forward --address 127.0.0.1 "${target}" "${lport}:${rport}" >/dev/null 2>&1 &
  echo $! > "${pidfile}"
  sleep 2
}

step "1/6: Ensuring GCP APIs, Snapshot Bucket (gs://${BUCKET_NAME}), Workload Identity IAM, and Agent Substrate (${SUBSTRATE_REF})"
if ! kubectl --request-timeout=5s cluster-info >/dev/null 2>&1; then
  gcloud container clusters get-credentials "${CLUSTER_NAME}" \
    --location "${CLUSTER_LOCATION}" \
    --project "${PROJECT_ID}" >/dev/null 2>&1 || true
  if ! kubectl --request-timeout=5s cluster-info >/dev/null 2>&1; then
    gcloud container clusters get-credentials "${CLUSTER_NAME}" \
      --location "${CLUSTER_LOCATION}" \
      --project "${PROJECT_ID}" \
      --dns-endpoint >/dev/null
  fi
fi
if ! kubectl get ns gke-managed-otel >/dev/null 2>&1; then
  gcloud beta container clusters update "${CLUSTER_NAME}" \
    --project "${PROJECT_ID}" \
    --location "${CLUSTER_LOCATION}" \
    --managed-otel-scope=COLLECTION_AND_INSTRUMENTATION_COMPONENTS >/dev/null || true
fi
if kubectl get sc dynamic-rwo >/dev/null 2>&1; then
  kubectl annotate sc standard-rwo storageclass.kubernetes.io/is-default-class=false --overwrite >/dev/null 2>&1 || true
  kubectl annotate sc dynamic-rwo storageclass.kubernetes.io/is-default-class=true --overwrite >/dev/null 2>&1 || true
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
WI="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject"
TRANSFER_GSA_EMAIL="${SNAPSHOT_TRANSFER_GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud services enable --project "${PROJECT_ID}" \
  container.googleapis.com storage.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com \
  aiplatform.googleapis.com monitoring.googleapis.com logging.googleapis.com cloudtrace.googleapis.com >/dev/null

if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --location "${REGION}" --uniform-bucket-level-access
fi
if ! gcloud iam service-accounts describe "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SNAPSHOT_TRANSFER_GSA_NAME}" --project "${PROJECT_ID}" --display-name "Substrate snapshot transfers" >/dev/null
fi

for sa in atelet ate-api-server; do
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" --member="${WI}/ns/ate-system/sa/${sa}" --role="roles/storage.objectAdmin" --condition=None >/dev/null
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" --member="${WI}/ns/ate-system/sa/${sa}" --role="roles/storage.bucketViewer" --condition=None >/dev/null
done
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" --member="serviceAccount:${TRANSFER_GSA_EMAIL}" --role="roles/storage.objectAdmin" --condition=None >/dev/null
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" --member="serviceAccount:${TRANSFER_GSA_EMAIL}" --role="roles/storage.bucketViewer" --condition=None >/dev/null
gcloud iam service-accounts add-iam-policy-binding "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" --member="${WI}/ns/ate-system/sa/ate-api-server" --role="roles/iam.serviceAccountTokenCreator" --condition=None >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="${WI}/ns/${NAMESPACE}/sa/gateway" --role="roles/aiplatform.user" --condition=None >/dev/null
gcloud projects add-iam-policy-binding "${PROJECT_ID}" --member="${WI}/ns/${NAMESPACE}/sa/prometheus-ui" --role="roles/monitoring.viewer" --condition=None >/dev/null
ok "GCP bucket & Workload Identity IAM bindings ready"

SUBSTRATE_SRC="${STATE_DIR}/substrate"
if [[ ! -d "${SUBSTRATE_SRC}/.git" ]]; then
  git clone --quiet https://github.com/agent-substrate/substrate "${SUBSTRATE_SRC}"
fi
git -C "${SUBSTRATE_SRC}" fetch --quiet --tags origin
git -C "${SUBSTRATE_SRC}" checkout --quiet "${SUBSTRATE_REF}"
if [[ ! -x "${BIN_DIR}/kubectl-ate" ]]; then
  (cd "${SUBSTRATE_SRC}" && GOWORK=off go build -o "${BIN_DIR}/kubectl-ate" ./cmd/kubectl-ate)
fi
ok "kubectl-ate (${SUBSTRATE_REF}) ready"

if ! kubectl -n ate-system get deploy ate-api-server >/dev/null 2>&1; then
  INGRESS_SPIFFE="spiffe://cluster.local/ns/${NAMESPACE}/sa/gateway,spiffe://cluster.local/ns/ate-system/sa/atenet-router"
  CURRENT_CTX="$(kubectl config current-context)"
  (cd "${SUBSTRATE_SRC}" && GOWORK=off go run ./cmd/ate-setup deploy ate-system \
    --context="${CURRENT_CTX}" \
    --rollout-timeout=5m \
    --sandbox-classes="gvisor" \
    --credential-provider='{"name":"k8s.io"}' \
    --snapshot-location="gs://${BUCKET_NAME}/" \
    --snapshot-transfer-gsa-name="${SNAPSHOT_TRANSFER_GSA_NAME}" \
    --ingress-allowed-spiffe-ids="${INGRESS_SPIFFE}" \
    --image-repo "${SUBSTRATE_IMAGE_REPO}" --image-tag "${SUBSTRATE_IMAGE_TAG}")
fi

WORKER_DIGEST="$(cd "${SUBSTRATE_SRC}" && GOWORK=off go run github.com/google/go-containerregistry/cmd/crane@v0.20.3 digest "${SUBSTRATE_IMAGE_REPO}/ateworker-gvisor:${SUBSTRATE_IMAGE_TAG}")"
export WORKER_IMAGE="${SUBSTRATE_IMAGE_REPO}/ateworker-gvisor:${SUBSTRATE_IMAGE_TAG}@${WORKER_DIGEST}"

# Ensure HTTP bridge on atenet-router (:80 -> :8080 -> :8443 mTLS loopback) and 60s parked-request budget
"${SCRIPT_DIR}/patch-router.sh"
kubectl -n ate-system wait --for=condition=Available deploy --all --timeout=10m >/dev/null
kubectl -n ate-system rollout status ds/atelet --timeout=10m >/dev/null
ok "Agent Substrate (${SUBSTRATE_REF}) control plane ready"

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
  if ! gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${AR_REPO}" \
      --repository-format=docker \
      --location="${REGION}" \
      --project="${PROJECT_ID}" \
      --description="Agent Substrate Security Demo container images" >/dev/null
  fi
  NODE_SA="$(gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --format='value(nodePools[0].config.serviceAccount)' 2>/dev/null || true)"
  if [[ -z "${NODE_SA}" || "${NODE_SA}" == "default" ]]; then
    NODE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
  fi
  gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${NODE_SA}" \
    --role="roles/artifactregistry.reader" \
    --condition=None >/dev/null

  APP_CONTENT_SHA="$(cat "${APP_DIR}/Dockerfile" "${APP_DIR}/gateway.py" "${APP_DIR}/gemini_agent.py" "${APP_DIR}/egress_agent.py" | sha256sum | cut -c1-12)"
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

step "2/6: Ensuring WorkerPool (2 gVisor worker pods), atespace (${ATESPACE}), and Python Gateway (app/gateway.py)"
envsubst '${NAMESPACE} ${WORKER_IMAGE}' < "${MANIFESTS_DIR}/workerpool.yaml.tmpl" | kubectl apply -f -
_two_workers() {
  [[ "$(kubectl -n "${NAMESPACE}" get pods -l workload=workshop-agent --field-selector=status.phase=Running -o name | wc -l)" -ge 2 ]]
}
wait_for 600 "2 running gVisor worker pods" _two_workers

kubectl ate get atespace "${ATESPACE}" >/dev/null 2>&1 || kubectl ate create atespace "${ATESPACE}"
kubectl -n "${NAMESPACE}" delete configmap gateway-app --ignore-not-found >/dev/null 2>&1 || true
envsubst '${NAMESPACE} ${ATESPACE} ${GEMINI_MODEL} ${PROJECT_ID} ${GATEWAY_IMAGE} ${GATEWAY_CODE_SHA}' \
  < "${MANIFESTS_DIR}/gateway.yaml.tmpl" | kubectl apply -f -
envsubst '${NAMESPACE} ${PROJECT_ID}' < "${MANIFESTS_DIR}/observability.yaml.tmpl" | kubectl apply -f -
kubectl -n "${NAMESPACE}" rollout status deploy/gateway --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/prometheus-ui --timeout=180s
start_port_forward router ate-system svc/atenet-router "${ROUTER_LOCAL_PORT}" 80
start_port_forward gateway "${NAMESPACE}" svc/gateway "${GATEWAY_LOCAL_PORT}" 8081
start_port_forward prometheus "${NAMESPACE}" svc/prometheus-ui "${PROM_LOCAL_PORT}" 9090
if ! "${SCRIPT_DIR}/dashboards.sh"; then
  echo "Warning: Cloud Monitoring dashboard provisioning failed; continuing stage.sh." >&2
fi

step "3/6: Configuring Act 3 isolated Secret (ns/workshop-secrets) and k8s-credential-provider policy"
kubectl create namespace workshop-secrets --dry-run=client -o yaml | kubectl apply -f -
kubectl -n workshop-secrets create secret generic example-api \
  --from-literal=token=ghp_demo_secret_token_998877 --dry-run=client -o yaml | kubectl apply -f -
envsubst '${ATESPACE}' < "${MANIFESTS_DIR}/namespace-policy.yaml.tmpl" | kubectl apply -f -
kubectl -n ate-system rollout restart deploy/k8s-credential-provider
kubectl -n ate-system rollout status deploy/k8s-credential-provider

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
ensure_template "${ATESPACE}" egress-agent-v1 "${STATE_DIR}/egress-agent-v1.yaml"
ensure_actor "${ATESPACE}" egress-agent egress-agent-v1
apply_egress_policy "${ATESPACE}" egress-agent "${MANIFESTS_DIR}/egress-fetch.yaml"
suspend_actor "${ATESPACE}" egress-agent

step "6/6: Staging Act 2 & Act 4 Google ADK Actors 'gemini-agent' and 'gemini-agent-forensic' (app/gemini_agent.py + clean-checkpoint-tag)"
if [[ "${REFRESH_ACTORS}" == "true" ]]; then
  kubectl ate delete actor gemini-agent-forensic -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete tag clean-checkpoint-tag -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor gemini-agent -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor-template gemini-agent-v1 -a "${ATESPACE}" >/dev/null 2>&1 || true
fi
envsubst '${ATESPACE} ${NAMESPACE} ${AGENT_IMAGE} ${GEMINI_MODEL}' \
  < "${MANIFESTS_DIR}/gemini-agent-v1.yaml.tmpl" > "${STATE_DIR}/gemini-agent-v1.yaml"
ensure_template "${ATESPACE}" gemini-agent-v1 "${STATE_DIR}/gemini-agent-v1.yaml"
ensure_actor "${ATESPACE}" gemini-agent gemini-agent-v1
apply_egress_policy "${ATESPACE}" gemini-agent "${MANIFESTS_DIR}/egress-gateway.yaml"

_seed_pineapple() {
  if ! curl -fsS "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/readyz" >/dev/null 2>&1; then
    start_port_forward gateway "${NAMESPACE}" svc/gateway "${GATEWAY_LOCAL_PORT}" 8081
  fi
  local resp
  resp="$(curl -fsS --max-time 45 "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/chat/gemini-agent" \
    -H "Content-Type: application/json" \
    -d '{"message":"Remember this: The secret launch code is PINEAPPLE-42."}')" || return 1
  jq -e '.reply | length > 0' <<<"${resp}" >/dev/null 2>&1
}
wait_for 180 "seed PINEAPPLE-42 checkpoint into Google ADK actor gemini-agent" _seed_pineapple
suspend_actor "${ATESPACE}" gemini-agent

if ! kubectl ate get tag clean-checkpoint-tag -a "${ATESPACE}" >/dev/null 2>&1; then
  kubectl ate create tag clean-checkpoint-tag --actor=gemini-agent -a "${ATESPACE}"
fi
if ! kubectl ate get actor gemini-agent-forensic -a "${ATESPACE}" >/dev/null 2>&1; then
  kubectl ate create actor gemini-agent-forensic --template=gemini-agent-v1 --tag=clean-checkpoint-tag -a "${ATESPACE}"
fi
apply_egress_policy "${ATESPACE}" gemini-agent-forensic "${MANIFESTS_DIR}/egress-gateway.yaml"
suspend_actor "${ATESPACE}" gemini-agent-forensic

ok "4-Act Security Detonation Demo staged in atespace '${ATESPACE}' (4 actors):"
kubectl ate get actors -a "${ATESPACE}"
