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
# Validates GKE >= 1.37, deploys Agent Substrate v1.0.0 (`b34fbee7`) with mTLS ingress,
# builds/pins an `@sha256` Google ADK (`google-adk`) image in Artifact Registry, and
# stages the 4 security demo actors in atespace 'security-demo'.

set -euo pipefail

for required_bin in gcloud kubectl git go jq curl envsubst python3 awk sed base64 sha256sum; do
  command -v "${required_bin}" >/dev/null 2>&1 || {
    echo "Error: required CLI tool '${required_bin}' is not installed on PATH." >&2
    exit 1
  }
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USE_CASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_DIR="${USE_CASE_DIR}/app"
MANIFESTS_DIR="${USE_CASE_DIR}/manifests"
STATE_DIR="${USE_CASE_DIR}/.state"
BIN_DIR="${USE_CASE_DIR}/bin"
mkdir -m 0700 -p "${STATE_DIR}"
chmod 0700 "${STATE_DIR}"
mkdir -p "${BIN_DIR}"

AUTH_HEADER_FILE=""
TMP_FILES=()
cleanup_stage_tmp() {
  rm -f ${AUTH_HEADER_FILE:+"${AUTH_HEADER_FILE}"}
  local f
  for f in ${TMP_FILES[@]+"${TMP_FILES[@]}"}; do
    rm -f "${f}"
  done
}
trap cleanup_stage_tmp EXIT

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/port-forward.sh"

KUBE_CTX="$(kubectl config current-context 2>/dev/null || true)"
CTX_PROJECT=""
CTX_LOCATION=""
CTX_CLUSTER=""
if [[ "${KUBE_CTX}" =~ ^gke_([^_]+)_([^_]+)_(.+)$ ]]; then
  CTX_PROJECT="${BASH_REMATCH[1]}"
  CTX_LOCATION="${BASH_REMATCH[2]}"
  CTX_CLUSTER="${BASH_REMATCH[3]}"
fi

declare -A STAGED=()
if [[ -f "${STATE_DIR}/staged.env" ]]; then
  while IFS='=' read -r k v; do
    [[ -n "${k}" && "${k}" != \#* ]] && STAGED["${k}"]="${v}"
  done < "${STATE_DIR}/staged.env"
fi
TARGET_CLUSTER_HINT="${CLUSTER_NAME:-${CTX_CLUSTER:-${STAGED[CLUSTER_NAME]:-}}}"
if [[ -n "${STAGED[CLUSTER_NAME]:-}" && "${TARGET_CLUSTER_HINT}" != "${STAGED[CLUSTER_NAME]}" ]]; then
  STAGED=()
fi

DEFAULT_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
[[ "${DEFAULT_PROJECT}" == "(unset)" ]] && DEFAULT_PROJECT=""

export APP_IMAGE="${APP_IMAGE:-}"
export AR_REPO="${AR_REPO:-${STAGED[AR_REPO]:-agent-substrate}}"
export REFRESH_ACTORS="${REFRESH_ACTORS:-false}"
export PROVISION_GCP_INFRA="${PROVISION_GCP_INFRA:-${STAGED[PROVISION_GCP_INFRA]:-true}}"
export MIN_GKE_VERSION="${MIN_GKE_VERSION:-1.37}"
export PROJECT_ID="${PROJECT_ID:-${CTX_PROJECT:-${STAGED[PROJECT_ID]:-${DEFAULT_PROJECT}}}}"
export CLUSTER_NAME="${CLUSTER_NAME:-${CTX_CLUSTER:-${STAGED[CLUSTER_NAME]:-agent-substrate-live}}}"
export CLUSTER_LOCATION="${CLUSTER_LOCATION:-${CTX_LOCATION:-${STAGED[CLUSTER_LOCATION]:-us-central1-b}}}"
if [[ -z "${REGION:-}" ]]; then
  if [[ "${CLUSTER_LOCATION}" =~ -[a-z]$ ]]; then
    REGION="${CLUSTER_LOCATION%-*}"
  else
    REGION="${CLUSTER_LOCATION}"
  fi
fi
export REGION
export NAMESPACE="${NAMESPACE:-${STAGED[NAMESPACE]:-agent-sandbox}}"
export SECRETS_NAMESPACE="${SECRETS_NAMESPACE:-${STAGED[SECRETS_NAMESPACE]:-agent-secrets}}"
export ATESPACE="${ATESPACE:-${STAGED[ATESPACE]:-security-demo}}"
export GATEWAY_LOCAL_PORT="${GATEWAY_LOCAL_PORT:-8081}"
export PROM_LOCAL_PORT="${PROM_LOCAL_PORT:-9090}"
export SUBSTRATE_REF="${SUBSTRATE_REF:-v1.0.0}"
if [[ -z "${SUBSTRATE_COMMIT:-}" && "${SUBSTRATE_REF}" == "v1.0.0" ]]; then
  export SUBSTRATE_COMMIT="b34fbee742906494b5eb4f1f36987176bf8770a4"
else
  export SUBSTRATE_COMMIT="${SUBSTRATE_COMMIT:-}"
fi
export SUBSTRATE_IMAGE_REPO="${SUBSTRATE_IMAGE_REPO:-ghcr.io/agent-substrate/substrate}"
export SUBSTRATE_IMAGE_TAG="${SUBSTRATE_IMAGE_TAG:-${SUBSTRATE_REF}}"
export GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"
CLEAN_CLUSTER_SLUG="$(printf '%s' "${CLUSTER_NAME}" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-' | cut -c1-18 | sed 's/-\+$//')"
RAW_BUCKET="$(printf '%s-%s-ate-snaps' "${PROJECT_ID:0:28}" "${CLUSTER_NAME:0:20}" | tr '[:upper:]' '[:lower:]' | sed 's/google/ggl/g' | tr -cd 'a-z0-9-' | sed 's/-\+$//; s/^-\+//')"
export BUCKET_NAME="${BUCKET_NAME:-${STAGED[BUCKET_NAME]:-${RAW_BUCKET:0:63}}}"
export SNAPSHOT_TRANSFER_GSA_NAME="${SNAPSHOT_TRANSFER_GSA_NAME:-${STAGED[SNAPSHOT_TRANSFER_GSA_NAME]:-ate-snap-${CLEAN_CLUSTER_SLUG:-gke}}}"
export PATH="${BIN_DIR}:$(go env GOPATH 2>/dev/null)/bin:${PATH}"

[[ -n "${PROJECT_ID}" ]] || { echo "Error: PROJECT_ID is empty; set PROJECT_ID=<gcp-project-id>" >&2; exit 1; }

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }

assert_sha256_digest() {
  [[ "$2" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    echo "Error: failed to resolve immutable sha256 digest for $1 (got '$2')." >&2
    exit 1
  }
}

render_manifest() {
  local vars="$1" tmpl="$2" rendered
  rendered="$(envsubst "${vars}" < "${tmpl}")"
  if grep -Eq '\$\{[A-Za-z_][A-Za-z0-9_]*\}' <<<"${rendered}"; then
    echo "Error: unexpanded placeholder remained after rendering ${tmpl}" >&2
    exit 1
  fi
  printf '%s\n' "${rendered}"
}

ignore_not_found() {
  local err_out lower rc=0
  err_out="$("$@" 2>&1)" || rc=$?
  [[ "${rc}" -eq 0 ]] && return 0
  lower="$(printf '%s' "${err_out}" | tr '[:upper:]' '[:lower:]')"
  if [[ "${lower}" == *"not found"* || "${lower}" == *"not_found"* || "${lower}" == *"404"* \
     || "${lower}" == *"does not exist"* || "${lower}" == *"has no egress policy"* ]]; then
    return 0
  fi
  printf '%s\n' "${err_out}" >&2
  return "${rc}"
}

retry_iam() {
  local attempt
  for attempt in 1 2 3 4 5 6; do
    "$@" >/dev/null 2>&1 && return 0
    sleep $((attempt * 2))
  done
  "$@" >/dev/null
}

wait_for() {
  local timeout="$1" desc="$2"; shift 2
  local deadline=$((SECONDS + timeout)) last_err=""
  while ! last_err="$("$@" 2>&1)"; do
    if (( SECONDS >= deadline )); then
      echo "Error: timed out after ${timeout}s waiting for ${desc}${last_err:+ (last output: ${last_err})}" >&2
      return 1
    fi
    sleep 3
  done
  ok "${desc}"
}

wait_absent() {
  local kind="$1" name="$2" as="$3"
  _gone() { ! kubectl ate get "${kind}" "${name}" -a "${as}" >/dev/null 2>&1; }
  wait_for 120 "${kind} ${as}/${name} deletion" _gone
}

verify_gke_version() {
  local ver_json nodes_tsv
  ver_json="$(kubectl version -o json)"
  nodes_tsv="$(kubectl get nodes -o 'jsonpath={range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.kubeletVersion}{"\n"}{end}')"
  python3 - "${MIN_GKE_VERSION}" "${ver_json}" "${nodes_tsv}" <<'EOF'
import json, re, sys

min_parts = tuple(int(x) for x in sys.argv[1].split(".")[:2])
ver_doc = json.loads(sys.argv[2])
nodes_lines = [ln for ln in sys.argv[3].splitlines() if ln.strip()]

def parse_minor(raw: str) -> tuple[int, int]:
    m = re.match(r"^v?(\d+)\.(\d+)", raw.strip())
    if not m:
        raise SystemExit(f"Error: unable to parse Kubernetes version {raw!r}")
    return int(m.group(1)), int(m.group(2))

srv = ver_doc.get("serverVersion") or {}
srv_str = f"{srv.get('major', '')}.{re.sub(r'[^0-9].*$', '', str(srv.get('minor', '')))}"
if parse_minor(srv_str) < min_parts:
    raise SystemExit(
        f"Error: GKE control plane is {srv.get('gitVersion')}, but Agent Substrate requires >= {sys.argv[1]} "
        "(native PodCertificateRequest & ClusterTrustBundle)."
    )
if not nodes_lines:
    raise SystemExit("Error: cluster has 0 ready worker nodes.")
for ln in nodes_lines:
    name, _, kv = ln.partition("\t")
    if parse_minor(kv) < min_parts:
        raise SystemExit(f"Error: worker node {name} runs kubelet {kv}, requires >= {sys.argv[1]}.")
EOF
}

ensure_template() {
  local as="$1" name="$2" file="$3"
  kubectl ate get actor-template "${name}" -a "${as}" >/dev/null 2>&1 \
    || kubectl ate create actor-template -f "${file}"
  _tpl_ready() {
    kubectl ate get actor-template "${name}" -a "${as}" -o json | jq -e '.status.goldenSnapshotStatus.goldenTag.name' >/dev/null
  }
  wait_for 600 "golden snapshot for template ${as}/${name}" _tpl_ready
}

ensure_actor() {
  local as="$1" name="$2" template="$3"
  kubectl ate get actor "${name}" -a "${as}" >/dev/null 2>&1 \
    || kubectl ate create actor "${name}" --template="${template}" -a "${as}"
}

actor_state() {
  kubectl ate get actor "$2" -a "$1" -o json | jq -r '.status.state // "UNKNOWN"' | sed 's/^ACTOR_STATE_//'
}

suspend_actor() {
  local as="$1" name="$2"
  [[ "$(actor_state "${as}" "${name}")" == "RUNNING" ]] && kubectl ate suspend actor "${name}" -a "${as}" >/dev/null
  _is_susp() { [[ "$(actor_state "${as}" "${name}")" == "SUSPENDED" ]]; }
  wait_for 120 "actor ${as}/${name} SUSPENDED" _is_susp
}

apply_egress_policy() {
  local as="$1" actor="$2" file="$3" cur uid ver tmp
  cur="$(kubectl ate get egress-policy "${actor}" -a "${as}" -o json 2>/dev/null || true)"
  uid="$(jq -r '.metadata.uid // empty' <<<"${cur}" 2>/dev/null || true)"
  ver="$(jq -r '.metadata.version // empty' <<<"${cur}" 2>/dev/null || true)"
  if [[ -n "${uid}" && -n "${ver}" ]]; then
    tmp="$(mktemp)"
    TMP_FILES+=("${tmp}")
    cat > "${tmp}" <<EOF
metadata:
  atespace: "${as}"
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
EXPECTED_KUBE_CTX="gke_${PROJECT_ID}_${CLUSTER_LOCATION}_${CLUSTER_NAME}"
CURRENT_KUBE_CTX="$(kubectl config current-context 2>/dev/null || true)"
if [[ "${CURRENT_KUBE_CTX}" != "${EXPECTED_KUBE_CTX}" ]] || ! kubectl --request-timeout=5s cluster-info >/dev/null 2>&1; then
  echo "Fetching cluster credentials for '${CLUSTER_NAME}' (${CLUSTER_LOCATION})..."
  gcloud container clusters get-credentials "${CLUSTER_NAME}" \
    --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --dns-endpoint >/dev/null
fi
verify_gke_version
ok "Verified GKE control plane and worker nodes >= ${MIN_GKE_VERSION}"

if ! kubectl get ns gke-managed-otel >/dev/null 2>&1; then
  if [[ "${PROVISION_GCP_INFRA}" == "true" ]]; then
    gcloud beta container clusters update "${CLUSTER_NAME}" --project "${PROJECT_ID}" \
      --location "${CLUSTER_LOCATION}" --managed-otel-scope=COLLECTION_AND_INSTRUMENTATION_COMPONENTS --quiet >/dev/null
  else
    echo "Warning: namespace 'gke-managed-otel' is absent on Terraform-managed cluster '${CLUSTER_NAME}'; skipping out-of-band gcloud cluster update." >&2
  fi
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
  TMP_FILES+=("${LIFECYCLE_FILE}")
  cat > "${LIFECYCLE_FILE}" <<'EOF'
{"rule":[{"action":{"type":"Delete"},"condition":{"age":7}},{"action":{"type":"AbortIncompleteMultipartUpload"},"condition":{"age":1}}]}
EOF
  if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" \
      --location "${REGION}" --uniform-bucket-level-access --pap >/dev/null
    gcloud storage buckets update "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" \
      --update-labels="created-by=agent-substrate-demo,managed-by=agent-substrate-demo" \
      --lifecycle-file="${LIFECYCLE_FILE}" >/dev/null
  else
    BUCKET_LABELS="$(gcloud storage buckets describe "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" --format='value(labels.created-by,labels.managed-by)' 2>/dev/null || true)"
    if [[ "${BUCKET_LABELS}" == *"agent-substrate-demo"* ]]; then
      gcloud storage buckets update "gs://${BUCKET_NAME}" --project "${PROJECT_ID}" \
        --pap --lifecycle-file="${LIFECYCLE_FILE}" >/dev/null
    fi
  fi
  rm -f "${LIFECYCLE_FILE}"

  if ! gcloud iam service-accounts describe "${TRANSFER_GSA_EMAIL}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${SNAPSHOT_TRANSFER_GSA_NAME}" \
      --project "${PROJECT_ID}" --display-name "Agent Substrate Snapshot Transfers" >/dev/null
  fi

  for member in "${WI}/ns/ate-system/sa/ate-api-server" "serviceAccount:${TRANSFER_GSA_EMAIL}"; do
    retry_iam gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
      --member="${member}" --role="roles/storage.objectAdmin" --condition=None
    retry_iam gcloud storage buckets add-iam-policy-binding "gs://${BUCKET_NAME}" \
      --member="${member}" --role="roles/storage.bucketViewer" --condition=None
  done
  retry_iam gcloud iam service-accounts add-iam-policy-binding "${TRANSFER_GSA_EMAIL}" \
    --project "${PROJECT_ID}" --member="${WI}/ns/ate-system/sa/ate-api-server" \
    --role="roles/iam.serviceAccountTokenCreator" --condition=None
  retry_iam gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="${WI}/ns/${NAMESPACE}/sa/gateway" --role="roles/aiplatform.user" --condition=None --quiet
  retry_iam gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="${WI}/ns/${NAMESPACE}/sa/prometheus-ui" --role="roles/monitoring.viewer" --condition=None --quiet

  if [[ -z "${APP_IMAGE}" ]] && ! gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${AR_REPO}" --repository-format=docker \
      --location="${REGION}" --project="${PROJECT_ID}" \
      --labels="created-by=agent-substrate-demo,managed-by=agent-substrate-demo" \
      --description="Agent Substrate Security Demo container images" >/dev/null
  fi
  if gcloud artifacts repositories describe "${AR_REPO}" --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    while IFS= read -r node_sa; do
      [[ -n "${node_sa}" && "${node_sa}" != "default" ]] || continue
      retry_iam gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
        --location="${REGION}" --project="${PROJECT_ID}" \
        --member="serviceAccount:${node_sa}" --role="roles/artifactregistry.reader" --condition=None
    done < <(gcloud container clusters describe "${CLUSTER_NAME}" --location "${CLUSTER_LOCATION}" --project "${PROJECT_ID}" --format='value(nodePools[].config.serviceAccount)' | tr ';' '\n' | sort -u)
    retry_iam gcloud artifacts repositories add-iam-policy-binding "${AR_REPO}" \
      --location="${REGION}" --project="${PROJECT_ID}" \
      --member="${WI}/ns/ate-system/sa/atelet" --role="roles/artifactregistry.reader" --condition=None
  fi
  ok "Standalone Option A GCP bucket, Artifact Registry, & Workload Identity IAM bindings ready"
else
  ok "Using Terraform-managed GCP bucket (gs://${BUCKET_NAME}) & IAM bindings"
fi

SUBSTRATE_SRC="${STATE_DIR}/substrate"
[[ -d "${SUBSTRATE_SRC}/.git" ]] || git clone --quiet https://github.com/agent-substrate/substrate "${SUBSTRATE_SRC}"
if [[ -z "${SUBSTRATE_COMMIT}" ]]; then
  git -C "${SUBSTRATE_SRC}" fetch --quiet --tags origin
  SUBSTRATE_COMMIT="$(git -C "${SUBSTRATE_SRC}" rev-parse "${SUBSTRATE_REF}^{commit}" 2>/dev/null)" \
    || { echo "Error: unable to resolve SUBSTRATE_REF='${SUBSTRATE_REF}' in upstream repository." >&2; exit 1; }
elif ! git -C "${SUBSTRATE_SRC}" cat-file -e "${SUBSTRATE_COMMIT}^{commit}" 2>/dev/null; then
  git -C "${SUBSTRATE_SRC}" fetch --quiet --tags origin
fi
git -C "${SUBSTRATE_SRC}" checkout --quiet "${SUBSTRATE_COMMIT}"

CACHED_KUBECTL_ATE="${BIN_DIR}/kubectl-ate-${SUBSTRATE_COMMIT:0:12}"
[[ -x "${CACHED_KUBECTL_ATE}" ]] || (cd "${SUBSTRATE_SRC}" && GOWORK=off go build -o "${CACHED_KUBECTL_ATE}" ./cmd/kubectl-ate)
cp -f "${CACHED_KUBECTL_ATE}" "${BIN_DIR}/kubectl-ate"
ok "kubectl-ate (${SUBSTRATE_REF} @ ${SUBSTRATE_COMMIT:0:8}) ready"

INGRESS_SPIFFE="spiffe://cluster.local/ns/${NAMESPACE}/sa/gateway"
INSTALLED_APISERVER_IMG="$(kubectl -n ate-system get deploy ate-api-server -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
INSTALLED_APISERVER_ARGS="$(kubectl -n ate-system get deploy ate-api-server -o jsonpath='{.spec.template.spec.containers[0].args[*]}' 2>/dev/null || true)"
INSTALLED_ROUTER_ARGS="$(kubectl -n ate-system get deploy atenet-router -o jsonpath='{.spec.template.spec.containers[0].args[*]}' 2>/dev/null || true)"

if [[ -z "${INSTALLED_APISERVER_IMG}" \
   || ! "${INSTALLED_APISERVER_IMG}" =~ :${SUBSTRATE_IMAGE_TAG}(@|$) \
   || "${INSTALLED_APISERVER_ARGS}" != *"gs://${BUCKET_NAME}/"* \
   || "${INSTALLED_APISERVER_ARGS}" != *"${SNAPSHOT_TRANSFER_GSA_NAME}"* \
   || "${INSTALLED_ROUTER_ARGS}" != *"--ingress-allowed-spiffe-ids=${INGRESS_SPIFFE}"* ]] \
   || ! kubectl -n ate-system get ds atelet >/dev/null 2>&1; then
  CURRENT_CTX="$(kubectl config current-context)"
  PG_SC_ARGS=()
  if kubectl -n ate-system get sts postgres >/dev/null 2>&1; then
    EXISTING_PG_SC="$(kubectl -n ate-system get sts postgres -o jsonpath='{.spec.volumeClaimTemplates[0].spec.storageClassName}' 2>/dev/null || true)"
    [[ -n "${EXISTING_PG_SC}" ]] && PG_SC_ARGS+=(--ateapi-postgres-storage-class="${EXISTING_PG_SC}")
  elif ! kubectl get sc -o jsonpath='{.items[*].metadata.annotations.storageclass\.kubernetes\.io/is-default-class}' 2>/dev/null | grep -q "true" \
       && kubectl get sc dynamic-rwo >/dev/null 2>&1; then
    PG_SC_ARGS+=(--ateapi-postgres-storage-class=dynamic-rwo)
  fi
  (cd "${SUBSTRATE_SRC}" && GOWORK=off go run ./cmd/ate-setup deploy ate-system \
    --context="${CURRENT_CTX}" --rollout-timeout=5m --sandbox-classes="gvisor" \
    --credential-provider='{"name":"k8s.io"}' \
    --snapshot-location="gs://${BUCKET_NAME}/" \
    --snapshot-transfer-gsa-name="${SNAPSHOT_TRANSFER_GSA_NAME}" \
    --ingress-allowed-spiffe-ids="${INGRESS_SPIFFE}" \
    --image-repo "${SUBSTRATE_IMAGE_REPO}" --image-tag "${SUBSTRATE_IMAGE_TAG}" \
    ${PG_SC_ARGS[@]+"${PG_SC_ARGS[@]}"})
fi

WORKER_DIGEST="$(cd "${SUBSTRATE_SRC}" && GOWORK=off go run github.com/google/go-containerregistry/cmd/crane@v0.20.3 digest "${SUBSTRATE_IMAGE_REPO}/ateworker-gvisor:${SUBSTRATE_IMAGE_TAG}")"
assert_sha256_digest "ateworker-gvisor" "${WORKER_DIGEST}"
export WORKER_IMAGE="${SUBSTRATE_IMAGE_REPO}/ateworker-gvisor:${SUBSTRATE_IMAGE_TAG}@${WORKER_DIGEST}"

kubectl -n ate-system wait --for=condition=Available deploy --all --timeout=10m >/dev/null
kubectl -n ate-system rollout status ds/atelet --timeout=10m >/dev/null
ok "Agent Substrate (${SUBSTRATE_REF}) control plane ready (mTLS on atenet-router:443)"

resolve_image_digest() {
  local img="$1" digest=""
  digest="$(gcloud artifacts docker images describe "${img}" --project "${PROJECT_ID}" --format='value(image_summary.digest)' 2>/dev/null || true)"
  [[ -n "${digest}" ]] || digest="$(cd "${SUBSTRATE_SRC}" && GOWORK=off go run github.com/google/go-containerregistry/cmd/crane@v0.20.3 digest "${img}")"
  printf '%s' "${digest}"
}

if [[ -n "${APP_IMAGE}" ]]; then
  if [[ "${APP_IMAGE}" != *"@sha256:"* ]]; then
    APP_DIGEST="$(resolve_image_digest "${APP_IMAGE}")"
    assert_sha256_digest "${APP_IMAGE}" "${APP_DIGEST}"
    APP_IMAGE="${APP_IMAGE}@${APP_DIGEST}"
  fi
  ok "Using caller-supplied container image (${APP_IMAGE})"
else
  APP_CONTENT_SHA="$(cat "${APP_DIR}/Dockerfile" "${APP_DIR}/requirements.txt" "${APP_DIR}/gateway.py" "${APP_DIR}/gemini_agent.py" "${APP_DIR}/egress_agent.py" "${APP_DIR}/partner_api.py" | sha256sum | cut -c1-12)"
  CANDIDATE_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/demo-app:adk-${APP_CONTENT_SHA}"
  APP_DIGEST="$(gcloud artifacts docker images describe "${CANDIDATE_IMAGE}" --project "${PROJECT_ID}" --format='value(image_summary.digest)' 2>/dev/null || true)"
  if [[ -z "${APP_DIGEST}" ]]; then
    step "Building Google ADK container image (${CANDIDATE_IMAGE}) via Cloud Build"
    gcloud builds submit "${APP_DIR}" --project "${PROJECT_ID}" --tag "${CANDIDATE_IMAGE}" --quiet
    APP_DIGEST="$(gcloud artifacts docker images describe "${CANDIDATE_IMAGE}" --project "${PROJECT_ID}" --format='value(image_summary.digest)')"
    assert_sha256_digest "${CANDIDATE_IMAGE}" "${APP_DIGEST}"
    ok "Built immutable Google ADK image (${CANDIDATE_IMAGE}@${APP_DIGEST})"
  else
    assert_sha256_digest "${CANDIDATE_IMAGE}" "${APP_DIGEST}"
    ok "Reusing cached Google ADK image (${CANDIDATE_IMAGE}@${APP_DIGEST})"
  fi
  APP_IMAGE="${CANDIDATE_IMAGE}@${APP_DIGEST}"
fi

export GATEWAY_IMAGE="${APP_IMAGE}"
export AGENT_IMAGE="${APP_IMAGE}"
export GATEWAY_CODE_SHA="$(printf '%s' "${APP_IMAGE}" | sha256sum | awk '{print $1}')"

step "2/6: Ensuring WorkerPool (2 gVisor worker pods), atespace (${ATESPACE}), and mTLS Gateway"
if [[ "${PROVISION_GCP_INFRA}" == "true" ]] && [[ "$(kubectl get nodes -l workload=agent-substrate -o name | wc -l)" -eq 0 ]]; then
  kubectl label nodes --all workload=agent-substrate --overwrite >/dev/null
fi
render_manifest '${NAMESPACE} ${WORKER_IMAGE}' "${MANIFESTS_DIR}/workerpool.yaml.tmpl" | kubectl apply -f -
_two_workers() {
  [[ "$(kubectl -n "${NAMESPACE}" get pods -l workload=substrate-agent --field-selector=status.phase=Running -o name | wc -l)" -ge 2 ]]
}
wait_for 600 "2 running gVisor worker pods" _two_workers

kubectl ate get atespace "${ATESPACE}" >/dev/null 2>&1 || kubectl ate create atespace "${ATESPACE}"

if ! kubectl -n "${NAMESPACE}" get secret gateway-admin-token >/dev/null 2>&1; then
  ADMIN_TOKEN="$(python3 - <<'EOF'
import secrets; print(secrets.token_urlsafe(24))
EOF
)"
  printf '%s' "${ADMIN_TOKEN}" | kubectl -n "${NAMESPACE}" create secret generic gateway-admin-token --from-file=token=/dev/stdin >/dev/null
fi
ADMIN_TOKEN="$(kubectl -n "${NAMESPACE}" get secret gateway-admin-token -o jsonpath='{.data.token}' | base64 -d)"
AUTH_HEADER_FILE="$(mktemp "${STATE_DIR}/admin-hdr.XXXXXX")"
chmod 0600 "${AUTH_HEADER_FILE}"
printf 'X-Gateway-Admin-Token: %s\n' "${ADMIN_TOKEN}" > "${AUTH_HEADER_FILE}"

render_manifest '${NAMESPACE} ${ATESPACE} ${GEMINI_MODEL} ${PROJECT_ID} ${GATEWAY_IMAGE} ${GATEWAY_CODE_SHA}' \
  "${MANIFESTS_DIR}/gateway.yaml.tmpl" | kubectl apply -f -
render_manifest '${NAMESPACE} ${PROJECT_ID}' "${MANIFESTS_DIR}/observability.yaml.tmpl" | kubectl apply -f -
kubectl -n "${NAMESPACE}" rollout status deploy/gateway --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deploy/prometheus-ui --timeout=180s

ensure_managed_port_forward "${STATE_DIR}" gateway "${NAMESPACE}" deploy/gateway "${GATEWAY_LOCAL_PORT}" 8081 "/identity" "agent-substrate-gateway"
ensure_managed_port_forward "${STATE_DIR}" prometheus "${NAMESPACE}" deploy/prometheus-ui "${PROM_LOCAL_PORT}" 9090 "/-/ready" ""
"${SCRIPT_DIR}/dashboards.sh" apply || echo "Warning: Cloud Monitoring dashboard provisioning failed; continuing stage.sh." >&2

step "3/6: Configuring Act 3 isolated Secret (${SECRETS_NAMESPACE}), non-reflecting partner-api, and credential policy"
PARTNER_MANIFEST="$(render_manifest '${SECRETS_NAMESPACE} ${GATEWAY_IMAGE} ${GATEWAY_CODE_SHA}' "${MANIFESTS_DIR}/partner-api.yaml.tmpl")"
kubectl create namespace "${SECRETS_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
if ! kubectl -n "${SECRETS_NAMESPACE}" get secret example-api >/dev/null 2>&1; then
  DEMO_API_TOKEN="demo-substrate-cred-$(python3 - <<'EOF'
import secrets; print(secrets.token_hex(12))
EOF
)"
  printf '%s' "${DEMO_API_TOKEN}" | kubectl -n "${SECRETS_NAMESPACE}" create secret generic example-api --from-file=token=/dev/stdin >/dev/null
fi
printf '%s\n' "${PARTNER_MANIFEST}" | kubectl apply -f -
kubectl -n "${SECRETS_NAMESPACE}" rollout status deploy/partner-api --timeout=180s

DESIRED_POLICY_MANIFEST="$(render_manifest '${ATESPACE} ${SECRETS_NAMESPACE}' "${MANIFESTS_DIR}/namespace-policy.yaml.tmpl")"
PREV_POLICY_DATA="$(kubectl -n ate-system get cm k8s-credential-provider-namespace-policy -o jsonpath='{.data.namespace-policy\.yaml}' 2>/dev/null || true)"
printf '%s\n' "${DESIRED_POLICY_MANIFEST}" | kubectl apply -f -
NEW_POLICY_DATA="$(kubectl -n ate-system get cm k8s-credential-provider-namespace-policy -o jsonpath='{.data.namespace-policy\.yaml}' 2>/dev/null || true)"
[[ "${PREV_POLICY_DATA}" != "${NEW_POLICY_DATA}" ]] && kubectl -n ate-system rollout restart deploy/k8s-credential-provider
kubectl -n ate-system rollout status deploy/k8s-credential-provider --timeout=180s

if [[ "${REFRESH_ACTORS}" == "true" ]]; then
  step "Refreshing existing actors, tags, and templates in atespace '${ATESPACE}'"
  for act in gemini-agent-forensic gemini-agent egress-agent py-detonation-agent; do
    ignore_not_found kubectl ate delete actor "${act}" -a "${ATESPACE}"
  done
  for act in gemini-agent-forensic gemini-agent egress-agent py-detonation-agent; do
    wait_absent actor "${act}" "${ATESPACE}"
  done
  ignore_not_found kubectl ate delete tag clean-checkpoint-tag -a "${ATESPACE}"
  for tpl in gemini-agent-v1 egress-agent-v1 python-sandbox-v1; do
    ignore_not_found kubectl ate delete actor-template "${tpl}" -a "${ATESPACE}"
    wait_absent actor-template "${tpl}" "${ATESPACE}"
  done
else
  for act in py-detonation-agent egress-agent gemini-agent gemini-agent-forensic; do
    kubectl ate get actor "${act}" -a "${ATESPACE}" >/dev/null 2>&1 && suspend_actor "${ATESPACE}" "${act}"
  done
fi

step "4/6: Staging Act 1 Actor 'py-detonation-agent' (python-sandbox-v1 on gVisor)"
render_manifest '${ATESPACE}' "${MANIFESTS_DIR}/python-sandbox-v1.yaml.tmpl" > "${STATE_DIR}/python-sandbox-v1.yaml"
ensure_template "${ATESPACE}" python-sandbox-v1 "${STATE_DIR}/python-sandbox-v1.yaml"
ensure_actor "${ATESPACE}" py-detonation-agent python-sandbox-v1
ignore_not_found kubectl ate delete egress-policy py-detonation-agent -a "${ATESPACE}"
suspend_actor "${ATESPACE}" py-detonation-agent

step "5/6: Staging Act 3 Actor 'egress-agent' (app/egress_agent.py with MITM ClusterTrustBundle)"
render_manifest '${ATESPACE} ${AGENT_IMAGE}' "${MANIFESTS_DIR}/egress-agent-v1.yaml.tmpl" > "${STATE_DIR}/egress-agent-v1.yaml"
render_manifest '${SECRETS_NAMESPACE}' "${MANIFESTS_DIR}/egress-fetch.yaml.tmpl" > "${STATE_DIR}/egress-fetch.yaml"
ensure_template "${ATESPACE}" egress-agent-v1 "${STATE_DIR}/egress-agent-v1.yaml"
ensure_actor "${ATESPACE}" egress-agent egress-agent-v1
apply_egress_policy "${ATESPACE}" egress-agent "${STATE_DIR}/egress-fetch.yaml"
suspend_actor "${ATESPACE}" egress-agent

step "6/6: Staging Act 2 & Act 4 Google ADK Actors 'gemini-agent' and 'gemini-agent-forensic'"
render_manifest '${ATESPACE} ${NAMESPACE} ${AGENT_IMAGE} ${GEMINI_MODEL}' \
  "${MANIFESTS_DIR}/gemini-agent-v1.yaml.tmpl" > "${STATE_DIR}/gemini-agent-v1.yaml"
render_manifest '${NAMESPACE}' "${MANIFESTS_DIR}/egress-gateway.yaml.tmpl" > "${STATE_DIR}/egress-gateway.yaml"
ensure_template "${ATESPACE}" gemini-agent-v1 "${STATE_DIR}/gemini-agent-v1.yaml"
ensure_actor "${ATESPACE}" gemini-agent gemini-agent-v1
apply_egress_policy "${ATESPACE}" gemini-agent "${STATE_DIR}/egress-gateway.yaml"

_seed_clean_policy() {
  ensure_managed_port_forward "${STATE_DIR}" gateway "${NAMESPACE}" deploy/gateway "${GATEWAY_LOCAL_PORT}" 8081 "/identity" "agent-substrate-gateway" || return 1
  local resp st
  st="$(curl -fsS --max-time 20 "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/actors/gemini-agent/state" -H "@${AUTH_HEADER_FILE}")" || return 1
  jq -e '.approvalPolicy == "REQUIRE_HUMAN_APPROVAL" and .diskPolicy == "REQUIRE_HUMAN_APPROVAL" and (.diskCount // 0) >= 1' <<<"${st}" >/dev/null 2>&1 && return 0
  resp="$(curl -fsS --max-time 45 "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/chat/gemini-agent" \
    -H "Content-Type: application/json" -H "@${AUTH_HEADER_FILE}" \
    -d '{"message":"Set our runtime approval policy to REQUIRE_HUMAN_APPROVAL using set_approval_policy."}')" || return 1
  jq -e '.approvalPolicy == "REQUIRE_HUMAN_APPROVAL"' <<<"${resp}" >/dev/null 2>&1 || return 1
  st="$(curl -fsS --max-time 15 "http://127.0.0.1:${GATEWAY_LOCAL_PORT}/actors/gemini-agent/state" -H "@${AUTH_HEADER_FILE}")" || return 1
  jq -e '.approvalPolicy == "REQUIRE_HUMAN_APPROVAL" and .diskPolicy == "REQUIRE_HUMAN_APPROVAL"' <<<"${st}" >/dev/null 2>&1
}
wait_for 180 "seed REQUIRE_HUMAN_APPROVAL checkpoint into Google ADK actor gemini-agent" _seed_clean_policy
suspend_actor "${ATESPACE}" gemini-agent

kubectl ate get tag clean-checkpoint-tag -a "${ATESPACE}" >/dev/null 2>&1 \
  || kubectl ate create tag clean-checkpoint-tag --actor=gemini-agent -a "${ATESPACE}"
kubectl ate get actor gemini-agent-forensic -a "${ATESPACE}" >/dev/null 2>&1 \
  || kubectl ate create actor gemini-agent-forensic --template=gemini-agent-v1 --tag=clean-checkpoint-tag -a "${ATESPACE}"
apply_egress_policy "${ATESPACE}" gemini-agent-forensic "${STATE_DIR}/egress-gateway.yaml"
suspend_actor "${ATESPACE}" gemini-agent-forensic

STAGED_ENV_FILE="${STATE_DIR}/staged.env"
cat > "${STAGED_ENV_FILE}" <<EOF
PROJECT_ID=${PROJECT_ID}
CLUSTER_NAME=${CLUSTER_NAME}
CLUSTER_LOCATION=${CLUSTER_LOCATION}
REGION=${REGION}
AR_REPO=${AR_REPO}
BUCKET_NAME=${BUCKET_NAME}
SNAPSHOT_TRANSFER_GSA_NAME=${SNAPSHOT_TRANSFER_GSA_NAME}
PROVISION_GCP_INFRA=${PROVISION_GCP_INFRA}
NAMESPACE=${NAMESPACE}
SECRETS_NAMESPACE=${SECRETS_NAMESPACE}
ATESPACE=${ATESPACE}
EOF
chmod 0600 "${STAGED_ENV_FILE}"

ok "4-Act Security Detonation Demo staged in atespace '${ATESPACE}' (4 actors):"
kubectl ate get actors -a "${ATESPACE}"
