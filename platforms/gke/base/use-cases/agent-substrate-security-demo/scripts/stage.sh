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

# stage.sh — 100% Standalone Zero-Build Stager for the 4-Act Security Detonation Demo.
# Uses ONLY upstream Agent Substrate (v1.0.0) + registry.k8s.io/agent-sandbox/python-runtime-sandbox:v0.5.6
# + GKE Workload Identity -> Vertex AI / Gemini 3.8 Flash.
# Stages the 4 security demo actors in atespace 'security-demo':
#   1. py-detonation-agent   (Act 1: gVisor Python sandbox detonation)
#   2. gemini-agent          (Act 2 & Act 4: Stateful Gemini agent with PINEAPPLE-42 checkpoint)
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

DEFAULT_RUNTIME_IMAGE="registry.k8s.io/agent-sandbox/python-runtime-sandbox:v0.5.6@sha256:147a6a7f3b382683a065e4519b22088e75472317ce861d57031537a758836ab5"
export APP_IMAGE="${APP_IMAGE:-}"
export REFRESH_ACTORS="${REFRESH_ACTORS:-false}"

export PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
export CLUSTER_NAME="${CLUSTER_NAME:-agent-substrate-live}"
export CLUSTER_LOCATION="${CLUSTER_LOCATION:-us-central1-b}"
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
export SUBSTRATE_REF="${SUBSTRATE_REF:-v1.0.0}"
export SUBSTRATE_IMAGE_REPO="${SUBSTRATE_IMAGE_REPO:-ghcr.io/agent-substrate/substrate}"
export SUBSTRATE_IMAGE_TAG="${SUBSTRATE_IMAGE_TAG:-${SUBSTRATE_REF}}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"
BUCKET_PREFIX="$(printf '%s' "${USER:-ate}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')"
export BUCKET_NAME="${BUCKET_NAME:-${BUCKET_PREFIX:-ate}-${CLUSTER_NAME}-${PROJECT_ID:0:8}}"
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
if kubectl get sc dynamic-rwo >/dev/null 2>&1; then
  kubectl annotate sc standard-rwo storageclass.kubernetes.io/is-default-class=false --overwrite >/dev/null 2>&1 || true
  kubectl annotate sc dynamic-rwo storageclass.kubernetes.io/is-default-class=true --overwrite >/dev/null 2>&1 || true
fi

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
WI="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject"
TRANSFER_GSA_EMAIL="${SNAPSHOT_TRANSFER_GSA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud services enable --project "${PROJECT_ID}" \
  container.googleapis.com storage.googleapis.com iam.googleapis.com iamcredentials.googleapis.com \
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
  (cd "${SUBSTRATE_SRC}" && GOWORK=off go run ./cmd/ate-setup deploy ate-system \
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

encode_actor_command() {
  # Agent Substrate enforces maxLength=4096 per argv element (maxItems=64).
  # In zero-build mode, zlib+base64 encode app/<script>.py into <=4000-char argv
  # chunks while preserving exact source filenames and line numbers for tracebacks.
  python3 - "$1" << 'EOF'
import base64
import json
import os
import sys
import zlib

path = sys.argv[1]
with open(path, "rb") as handle:
    encoded = base64.b64encode(zlib.compress(handle.read(), 9)).decode("ascii")
chunks = [encoded[i : i + 4000] for i in range(0, len(encoded), 4000)]
loader = (
    "import base64,sys,zlib;"
    f"exec(compile(zlib.decompress(base64.b64decode(''.join(sys.argv[1:]))),{os.path.basename(path)!r},'exec'))"
)
print(json.dumps(["python3", "-c", loader, *chunks]))
EOF
}

if [[ -n "${APP_IMAGE}" ]]; then
  if [[ "${APP_IMAGE}" != *"@sha256:"* ]]; then
    APP_DIGEST="$(cd "${SUBSTRATE_SRC}" && GOWORK=off go run github.com/google/go-containerregistry/cmd/crane@v0.20.3 digest "${APP_IMAGE}")"
    APP_IMAGE="${APP_IMAGE}@${APP_DIGEST}"
  fi
  export GATEWAY_IMAGE="${APP_IMAGE}"
  export AGENT_IMAGE="${APP_IMAGE}"
  export GATEWAY_CODE_SHA="$(printf '%s' "${APP_IMAGE}" | sha256sum | awk '{print $1}')"
  export GATEWAY_VOLUME_MOUNTS_JSON='[]'
  export GATEWAY_VOLUMES_JSON='[]'
  export GEMINI_AGENT_COMMAND_JSON='["python3", "/app-src/gemini_agent.py"]'
  export EGRESS_AGENT_COMMAND_JSON='["python3", "/app-src/egress_agent.py"]'
else
  export GATEWAY_IMAGE="${DEFAULT_RUNTIME_IMAGE}"
  export AGENT_IMAGE="${DEFAULT_RUNTIME_IMAGE}"
  export GATEWAY_CODE_SHA="$(sha256sum "${APP_DIR}/gateway.py" | awk '{print $1}')"
  export GATEWAY_VOLUME_MOUNTS_JSON='[{"name": "gateway-app", "mountPath": "/app-src", "readOnly": true}]'
  export GATEWAY_VOLUMES_JSON='[{"name": "gateway-app", "configMap": {"name": "gateway-app"}}]'
  GEMINI_AGENT_COMMAND_JSON="$(encode_actor_command "${APP_DIR}/gemini_agent.py")"
  EGRESS_AGENT_COMMAND_JSON="$(encode_actor_command "${APP_DIR}/egress_agent.py")"
  export GEMINI_AGENT_COMMAND_JSON EGRESS_AGENT_COMMAND_JSON
fi

step "2/6: Ensuring WorkerPool (2 gVisor worker pods), atespace (${ATESPACE}), and Python Gateway (app/gateway.py)"
envsubst '${NAMESPACE} ${WORKER_IMAGE}' < "${MANIFESTS_DIR}/workerpool.yaml.tmpl" | kubectl apply -f -
_two_workers() {
  [[ "$(kubectl -n "${NAMESPACE}" get pods -l workload=workshop-agent --field-selector=status.phase=Running -o name | wc -l)" -ge 2 ]]
}
wait_for 600 "2 running gVisor worker pods" _two_workers

kubectl ate get atespace "${ATESPACE}" >/dev/null 2>&1 || kubectl ate create atespace "${ATESPACE}"
if [[ -z "${APP_IMAGE}" ]]; then
  kubectl -n "${NAMESPACE}" create configmap gateway-app \
    --from-file=gateway.py="${APP_DIR}/gateway.py" \
    --dry-run=client -o yaml | kubectl apply -f -
fi
envsubst '${NAMESPACE} ${ATESPACE} ${GEMINI_MODEL} ${PROJECT_ID} ${GATEWAY_IMAGE} ${GATEWAY_CODE_SHA} ${GATEWAY_VOLUME_MOUNTS_JSON} ${GATEWAY_VOLUMES_JSON}' \
  < "${MANIFESTS_DIR}/gateway.yaml.tmpl" | kubectl apply -f -
envsubst '${NAMESPACE} ${PROJECT_ID}' < "${MANIFESTS_DIR}/observability.yaml.tmpl" | kubectl apply -f -
kubectl -n "${NAMESPACE}" rollout status deploy/gateway --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/prometheus-ui --timeout=180s
start_port_forward router ate-system svc/atenet-router 8080 80
start_port_forward gateway "${NAMESPACE}" svc/gateway 8081 8081
start_port_forward prometheus "${NAMESPACE}" svc/prometheus-ui 9090 9090
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
envsubst '${ATESPACE} ${AGENT_IMAGE} ${EGRESS_AGENT_COMMAND_JSON}' \
  < "${MANIFESTS_DIR}/egress-agent-v1.yaml.tmpl" > "${STATE_DIR}/egress-agent-v1.yaml"
ensure_template "${ATESPACE}" egress-agent-v1 "${STATE_DIR}/egress-agent-v1.yaml"
ensure_actor "${ATESPACE}" egress-agent egress-agent-v1
apply_egress_policy "${ATESPACE}" egress-agent "${MANIFESTS_DIR}/egress-fetch.yaml"
suspend_actor "${ATESPACE}" egress-agent

step "6/6: Staging Act 2 & Act 4 Actors 'gemini-agent' and 'gemini-agent-forensic' (app/gemini_agent.py + clean-checkpoint-tag)"
if [[ "${REFRESH_ACTORS}" == "true" ]]; then
  kubectl ate delete actor gemini-agent-forensic -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete tag clean-checkpoint-tag -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor gemini-agent -a "${ATESPACE}" >/dev/null 2>&1 || true
  kubectl ate delete actor-template gemini-agent-v1 -a "${ATESPACE}" >/dev/null 2>&1 || true
fi
envsubst '${ATESPACE} ${NAMESPACE} ${AGENT_IMAGE} ${GEMINI_AGENT_COMMAND_JSON}' \
  < "${MANIFESTS_DIR}/gemini-agent-v1.yaml.tmpl" > "${STATE_DIR}/gemini-agent-v1.yaml"
ensure_template "${ATESPACE}" gemini-agent-v1 "${STATE_DIR}/gemini-agent-v1.yaml"
ensure_actor "${ATESPACE}" gemini-agent gemini-agent-v1
apply_egress_policy "${ATESPACE}" gemini-agent "${MANIFESTS_DIR}/egress-gateway.yaml"

curl -s "http://127.0.0.1:8081/chat/gemini-agent" \
  -H "Content-Type: application/json" \
  -d '{"message":"Remember this: The secret launch code is PINEAPPLE-42."}' >/dev/null
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
