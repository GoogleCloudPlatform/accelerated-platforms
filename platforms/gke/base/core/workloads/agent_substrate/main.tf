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
  kubeconfig_directory = "${path.module}/../../../kubernetes/kubeconfig"
  kubeconfig_file      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"

  manifests_directory   = "${local.namespace_directory}/ate-system"
  namespace_directory   = "${local.manifests_directory_root}/namespace"
  substrate_install_dir = "${path.module}/manifests/substrate-${var.agent_substrate_version}"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "credential_namespace_policy" {
  content = templatefile(
    "${path.module}/templates/namespace-policy.tftpl.yaml",
    {
      atespace             = var.agent_substrate_atespace
      credential_namespace = var.agent_substrate_credential_namespace
    }
  )
  filename = "${local.manifests_directory}/k8s-credential-provider-namespace-policy.yaml"
}

resource "terraform_data" "deploy_ate_system" {
  depends_on = [
    google_project_iam_member.atelet_artifactregistry_reader,
    google_service_account_iam_member.ate_api_server_token_creator,
    google_storage_bucket_iam_member.assets_atelet_viewer,
    google_storage_bucket_iam_member.snapshot_bucket_viewer,
    google_storage_bucket_iam_member.snapshot_object_admin,
    local_file.credential_namespace_policy,
  ]

  input = {
    additional_extproc_service  = var.agent_substrate_additional_egress_extproc_service != null ? var.agent_substrate_additional_egress_extproc_service : ""
    ar_repo_url                 = local.cloudbuild_ar_image_repository_url
    atespace                    = var.agent_substrate_atespace
    bucket_name                 = google_storage_bucket.snapshot.name
    cloudbuild_location         = local.cloudbuild_location
    cloudbuild_project_id       = local.cloudbuild_project_id
    cloudbuild_sa_id            = local.cloudbuild_service_account_id
    cluster_location            = local.cluster_region
    cluster_name                = local.cluster_name
    credential_namespace_policy = local_file.credential_namespace_policy.filename
    credential_provider         = var.agent_substrate_credential_provider
    envoy_cloudbuild_config     = abspath("${path.module}/templates/cloudbuild-envoy-dataplane.yaml")
    ingress_allowed_spiffe_ids  = var.agent_substrate_ingress_allowed_spiffe_ids
    kubeconfig_file             = data.local_file.kubeconfig.filename
    project_id                  = data.google_project.cluster.project_id
    substrate_install_dir       = local.substrate_install_dir
    transfer_gsa_name           = google_service_account.snapshot_transfer.account_id
    version                     = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<EOT
set -euo pipefail
KUBECONFIG_ABS="$(realpath "${self.input.kubeconfig_file}")"
POLICY_ABS="$(realpath "${self.input.credential_namespace_policy}")"
mkdir -p "$(dirname "${self.input.substrate_install_dir}")"
if [ ! -d "${self.input.substrate_install_dir}/.git" ]; then
  rm -rf "${self.input.substrate_install_dir}"
  git clone --depth 1 --branch "${self.input.version}" https://github.com/agent-substrate/substrate.git "${self.input.substrate_install_dir}"
fi

cd "${self.input.substrate_install_dir}"
mkdir -p "$${HOME}/.local/bin"
GOBIN="$${HOME}/.local/bin" go install ./cmd/kubectl-ate
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}"
export KUBECONFIG="$${KUBECONFIG_ABS}"

# Build and publish pre-built Substrate images to Artifact Registry if not yet present
if ! gcloud artifacts docker images describe "${self.input.ar_repo_url}/envoy-dataplane:${self.input.version}" --project="${self.input.cloudbuild_project_id}" >/dev/null 2>&1; then
  echo "Building envoy-dataplane:${self.input.version} via Cloud Build..."
  gcloud builds submit "./cmd/dataplane/envoy" \
    --config="${self.input.envoy_cloudbuild_config}" \
    --project="${self.input.cloudbuild_project_id}" \
    --region="${self.input.cloudbuild_location}" \
    --service-account="${self.input.cloudbuild_sa_id}" \
    --default-buckets-behavior=regional-user-owned-bucket \
    --substitutions=_DESTINATION="${self.input.ar_repo_url}/envoy-dataplane:${self.input.version}"
fi

if ! gcloud artifacts docker images describe "${self.input.ar_repo_url}/ateworker-gvisor:${self.input.version}" --project="${self.input.cloudbuild_project_id}" >/dev/null 2>&1; then
  echo "Building Substrate Go component images (${self.input.version}) via ko..."
  KO_BIN="$(cd ./hack/tools/ko && go tool -n ko)"
  KO_DOCKER_REPO="${self.input.ar_repo_url}" \
  KO_DEFAULTPLATFORMS="linux/amd64" \
  "$${KO_BIN}" build \
    --base-import-paths \
    --tags="${self.input.version}" \
    --ldflags="-X=go.ate.dev/substrate/internal/version.Version=${self.input.version}" \
    ./cmd/ate-idp-server \
    ./cmd/ateapi \
    ./cmd/atecontroller \
    ./cmd/atelet \
    ./cmd/atenet \
    ./cmd/ateworker-gvisor \
    ./cmd/ateworker-microvm \
    ./cmd/credential-provider/kubernetes-secrets \
    ./cmd/objectstore-plugin \
    ./cmd/podcertcontroller
fi

EXTRA_FLAGS=()
if [ -n "${self.input.additional_extproc_service}" ]; then
  EXTRA_FLAGS+=("--experimental-additional-egress-extproc-service=${self.input.additional_extproc_service}")
fi

go run ./cmd/ate-setup deploy ate-system \
  --no-dev-env \
  --sandbox-classes="gvisor" \
  --kubeconfig="$${KUBECONFIG_ABS}" \
  --context="gke_${self.input.project_id}_${self.input.cluster_location}_${self.input.cluster_name}" \
  --gcp-project-id="${self.input.project_id}" \
  --gcp-cluster-name="${self.input.cluster_name}" \
  --gcp-cluster-location="${self.input.cluster_location}" \
  --storage-bucket-name="${self.input.bucket_name}" \
  --snapshot-location="gs://${self.input.bucket_name}/" \
  --snapshot-transfer-gsa-name="${self.input.transfer_gsa_name}" \
  --credential-provider='${self.input.credential_provider}' \
  --ingress-allowed-spiffe-ids="${self.input.ingress_allowed_spiffe_ids}" \
  --image-repo="${self.input.ar_repo_url}" \
  --image-tag="${self.input.version}" \
  --ateapi-postgres-storage-class="dynamic-rwo" \
  --rollout-timeout="600s" \
  "$${EXTRA_FLAGS[@]}"

kubectl --kubeconfig="$${KUBECONFIG_ABS}" apply -f "$${POLICY_ABS}"
kubectl --kubeconfig="$${KUBECONFIG_ABS}" -n ate-system rollout restart deployment/k8s-credential-provider
kubectl --kubeconfig="$${KUBECONFIG_ABS}" -n ate-system rollout status deployment/k8s-credential-provider --timeout=120s
kubectl-ate --kubeconfig="$${KUBECONFIG_ABS}" create atespace "${self.input.atespace}" || true
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = <<EOT
set -euo pipefail
if [ -d "${self.input.substrate_install_dir}" ] && [ -f "${self.input.kubeconfig_file}" ]; then
  KUBECONFIG_ABS="$(realpath "${self.input.kubeconfig_file}")"
  export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}"
  export KUBECONFIG="$${KUBECONFIG_ABS}"
  cd "${self.input.substrate_install_dir}"
  go run ./cmd/ate-setup delete ate-system \
    --no-dev-env \
    --kubeconfig="$${KUBECONFIG_ABS}" \
    --context="gke_${self.input.project_id}_${self.input.cluster_location}_${self.input.cluster_name}" || true
  kubectl --kubeconfig="$${KUBECONFIG_ABS}" delete crd/workerpools.ate.dev crd/sandboxconfigs.ate.dev crd/csidriverconfigs.ate.dev --ignore-not-found --wait=true || true
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
