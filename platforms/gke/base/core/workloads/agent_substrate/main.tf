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

locals {
  agent_substrate_assets_bucket_name   = "${local.agent_substrate_snapshot_bucket_name}-assets"
  agent_substrate_snapshot_bucket_name = var.agent_substrate_snapshot_bucket_name != null ? var.agent_substrate_snapshot_bucket_name : "${local.unique_identifier_prefix}-ate-snapshots-${local.cluster_project_id}"
  ate_api_server_wi_member             = "${local.cluster_wi_principal_prefix}/ns/ate-system/sa/ate-api-server"
  atelet_wi_member                     = "${local.cluster_wi_principal_prefix}/ns/ate-system/sa/atelet"
  cluster_wi_principal_prefix          = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject"
  kubeconfig_file                      = "${path.module}/../../../kubernetes/kubeconfig/${local.kubeconfig_file_name}"
  substrate_install_dir                = "${path.module}/manifests/substrate-${var.agent_substrate_version}"
}

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "google_service_account" "snapshot_transfer" {
  account_id   = var.agent_substrate_transfer_service_account_name
  display_name = "Agent Substrate snapshot transfers"
  project      = data.google_project.cluster.project_id
}

resource "google_storage_bucket" "snapshot" {
  force_destroy               = true
  location                    = local.cluster_region
  name                        = local.agent_substrate_snapshot_bucket_name
  project                     = data.google_project.cluster.project_id
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true
  versioning {
    enabled = true
  }
}

resource "google_storage_bucket" "assets" {
  force_destroy               = true
  location                    = local.cluster_region
  name                        = local.agent_substrate_assets_bucket_name
  project                     = data.google_project.cluster.project_id
  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true
}

resource "google_project_iam_member" "atelet_artifactregistry_reader" {
  member  = local.atelet_wi_member
  project = data.google_project.cluster.project_id
  role    = "roles/artifactregistry.reader"
}

resource "google_service_account_iam_member" "ate_api_server_token_creator" {
  member             = local.ate_api_server_wi_member
  role               = "roles/iam.serviceAccountTokenCreator"
  service_account_id = google_service_account.snapshot_transfer.name
}

resource "google_storage_bucket_iam_member" "snapshot_object_admin" {
  for_each = tomap({
    ate_api_server    = local.ate_api_server_wi_member
    snapshot_transfer = google_service_account.snapshot_transfer.member
  })
  bucket = google_storage_bucket.snapshot.name
  member = each.value
  role   = "roles/storage.objectAdmin"
}

resource "google_storage_bucket_iam_member" "snapshot_bucket_viewer" {
  for_each = tomap({
    ate_api_server    = local.ate_api_server_wi_member
    snapshot_transfer = google_service_account.snapshot_transfer.member
  })
  bucket = google_storage_bucket.snapshot.name
  member = each.value
  role   = "roles/storage.bucketViewer"
}

resource "google_storage_bucket_iam_member" "assets_atelet_viewer" {
  bucket = google_storage_bucket.assets.name
  member = local.atelet_wi_member
  role   = "roles/storage.objectViewer"
}

resource "terraform_data" "deploy_ate_system" {
  depends_on = [
    google_project_iam_member.atelet_artifactregistry_reader,
    google_service_account_iam_member.ate_api_server_token_creator,
    google_storage_bucket_iam_member.assets_atelet_viewer,
    google_storage_bucket_iam_member.snapshot_bucket_viewer,
    google_storage_bucket_iam_member.snapshot_object_admin,
  ]

  input = {
    additional_extproc_service = var.agent_substrate_additional_egress_extproc_service != null ? var.agent_substrate_additional_egress_extproc_service : ""
    ar_repo_url                = local.cloudbuild_ar_image_repository_url
    atespace                   = var.agent_substrate_atespace
    bucket_name                = google_storage_bucket.snapshot.name
    cloudbuild_location        = local.cloudbuild_location
    cloudbuild_project_id      = local.cloudbuild_project_id
    cloudbuild_sa_id           = local.cloudbuild_service_account_id
    cluster_location           = local.cluster_region
    cluster_name               = local.cluster_name
    credential_namespace       = var.agent_substrate_credential_namespace
    credential_provider        = var.agent_substrate_credential_provider
    envoy_cloudbuild_config    = abspath("${path.module}/templates/cloudbuild-envoy-dataplane.yaml")
    ingress_allowed_spiffe_ids = var.agent_substrate_ingress_allowed_spiffe_ids
    kubeconfig_file            = data.local_file.kubeconfig.filename
    project_id                 = data.google_project.cluster.project_id
    substrate_install_dir      = local.substrate_install_dir
    transfer_gsa_name          = google_service_account.snapshot_transfer.account_id
    version                    = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<EOT
set -euo pipefail
KUBECONFIG_ABS="$(realpath "${self.input.kubeconfig_file}")"
mkdir -p "$(dirname "${self.input.substrate_install_dir}")"
if [ ! -d "${self.input.substrate_install_dir}/.git" ]; then
  rm -rf "${self.input.substrate_install_dir}"
  git clone --depth 1 --branch "${self.input.version}" https://github.com/agent-substrate/substrate.git "${self.input.substrate_install_dir}"
fi

cd "${self.input.substrate_install_dir}"
mkdir -p "$${HOME}/.local/bin"
GOBIN="$${HOME}/.local/bin" go install ./cmd/kubectl-ate
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}" KUBECONFIG="$${KUBECONFIG_ABS}"

if ! gcloud artifacts docker images describe "${self.input.ar_repo_url}/envoy-dataplane:${self.input.version}" --project="${self.input.cloudbuild_project_id}" >/dev/null 2>&1; then
  gcloud builds submit "./cmd/dataplane/envoy" \
    --config="${self.input.envoy_cloudbuild_config}" \
    --project="${self.input.cloudbuild_project_id}" --region="${self.input.cloudbuild_location}" \
    --service-account="${self.input.cloudbuild_sa_id}" --default-buckets-behavior=regional-user-owned-bucket \
    --substitutions=_DESTINATION="${self.input.ar_repo_url}/envoy-dataplane:${self.input.version}"
fi

if ! gcloud artifacts docker images describe "${self.input.ar_repo_url}/ateworker-gvisor:${self.input.version}" --project="${self.input.cloudbuild_project_id}" >/dev/null 2>&1; then
  KO_BIN="$(cd ./hack/tools/ko && go tool -n ko)"
  KO_DOCKER_REPO="${self.input.ar_repo_url}" KO_DEFAULTPLATFORMS="linux/amd64" "$${KO_BIN}" build \
    --base-import-paths --tags="${self.input.version}" \
    --ldflags="-X=go.ate.dev/substrate/internal/version.Version=${self.input.version}" \
    ./cmd/ate-idp-server ./cmd/ateapi ./cmd/atecontroller ./cmd/atelet ./cmd/atenet \
    ./cmd/ateworker-gvisor ./cmd/ateworker-microvm ./cmd/credential-provider/kubernetes-secrets \
    ./cmd/objectstore-plugin ./cmd/podcertcontroller
fi

EXTRA_FLAGS=()
if [ -n "${self.input.additional_extproc_service}" ]; then
  EXTRA_FLAGS+=("--experimental-additional-egress-extproc-service=${self.input.additional_extproc_service}")
fi

go run ./cmd/ate-setup deploy ate-system \
  --no-dev-env --sandbox-classes="gvisor" --kubeconfig="$${KUBECONFIG_ABS}" \
  --context="gke_${self.input.project_id}_${self.input.cluster_location}_${self.input.cluster_name}" \
  --gcp-project-id="${self.input.project_id}" --gcp-cluster-name="${self.input.cluster_name}" --gcp-cluster-location="${self.input.cluster_location}" \
  --storage-bucket-name="${self.input.bucket_name}" --snapshot-location="gs://${self.input.bucket_name}/" \
  --snapshot-transfer-gsa-name="${self.input.transfer_gsa_name}" --credential-provider='${self.input.credential_provider}' \
  --ingress-allowed-spiffe-ids="${self.input.ingress_allowed_spiffe_ids}" --image-repo="${self.input.ar_repo_url}" --image-tag="${self.input.version}" \
  --ateapi-postgres-storage-class="dynamic-rwo" --rollout-timeout="600s" "$${EXTRA_FLAGS[@]}"

kubectl create configmap k8s-credential-provider-namespace-policy -n ate-system \
  --from-literal="namespace-policy.yaml=$(printf 'policies:\n- atespace: %s\n  allowedNamespaces:\n  - %s\n' "${self.input.atespace}" "${self.input.credential_namespace}")" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl -n ate-system rollout restart deployment/k8s-credential-provider
kubectl -n ate-system rollout status deployment/k8s-credential-provider --timeout=120s
kubectl-ate create atespace "${self.input.atespace}" || true
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = <<EOT
set -euo pipefail
if [ -d "${self.input.substrate_install_dir}" ] && [ -f "${self.input.kubeconfig_file}" ]; then
  KUBECONFIG_ABS="$(realpath "${self.input.kubeconfig_file}")"
  export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}" KUBECONFIG="$${KUBECONFIG_ABS}"
  cd "${self.input.substrate_install_dir}"
  go run ./cmd/ate-setup delete ate-system --no-dev-env --kubeconfig="$${KUBECONFIG_ABS}" \
    --context="gke_${self.input.project_id}_${self.input.cluster_location}_${self.input.cluster_name}" || true
  kubectl delete crd/workerpools.ate.dev crd/sandboxconfigs.ate.dev crd/csidriverconfigs.ate.dev --ignore-not-found --wait=true || true
  rm -rf "$${HOME}/.kube/cache/discovery"
fi
EOT
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    additional_extproc_service = var.agent_substrate_additional_egress_extproc_service != null ? var.agent_substrate_additional_egress_extproc_service : ""
    atespace                   = var.agent_substrate_atespace
    bucket_name                = google_storage_bucket.snapshot.name
    credential_namespace       = var.agent_substrate_credential_namespace
    credential_provider        = var.agent_substrate_credential_provider
    ingress_allowed_spiffe_ids = var.agent_substrate_ingress_allowed_spiffe_ids
    version                    = var.agent_substrate_version
  }
}
