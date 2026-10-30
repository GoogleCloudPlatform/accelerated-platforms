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
    atespace                    = var.agent_substrate_atespace
    bucket_name                 = google_storage_bucket.snapshot.name
    cluster_location            = local.cluster_region
    cluster_name                = local.cluster_name
    credential_namespace_policy = local_file.credential_namespace_policy.filename
    credential_provider         = var.agent_substrate_credential_provider
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
mkdir -p "$(dirname "${self.input.substrate_install_dir}")"
if [ ! -d "${self.input.substrate_install_dir}/.git" ]; then
  rm -rf "${self.input.substrate_install_dir}"
  git clone --depth 1 --branch "${self.input.version}" https://github.com/agent-substrate/substrate.git "${self.input.substrate_install_dir}"
fi

cd "${self.input.substrate_install_dir}"
mkdir -p "${HOME}/.local/bin"
GOBIN="${HOME}/.local/bin" go install ./cmd/kubectl-ate
export PATH="${HOME}/.local/bin:${PATH}"

EXTRA_FLAGS=()
if [ -n "${self.input.additional_extproc_service}" ]; then
  EXTRA_FLAGS+=("--experimental-additional-egress-extproc-service=${self.input.additional_extproc_service}")
fi

go run ./cmd/ate-setup deploy ate-system \
  --no-dev-env \
  --kubeconfig="${self.input.kubeconfig_file}" \
  --gcp-project-id="${self.input.project_id}" \
  --gcp-cluster-name="${self.input.cluster_name}" \
  --gcp-cluster-location="${self.input.cluster_location}" \
  --storage-bucket-name="${self.input.bucket_name}" \
  --snapshot-location="gs://${self.input.bucket_name}/" \
  --snapshot-transfer-gsa-name="${self.input.transfer_gsa_name}" \
  --credential-provider='${self.input.credential_provider}' \
  --ingress-allowed-spiffe-ids="${self.input.ingress_allowed_spiffe_ids}" \
  --image-repo="ghcr.io/agent-substrate/substrate" \
  --image-tag="${self.input.version}" \
  --rollout-timeout="180s" \
  "$${EXTRA_FLAGS[@]}"

kubectl --kubeconfig="${self.input.kubeconfig_file}" apply -f "${self.input.credential_namespace_policy}"
kubectl --kubeconfig="${self.input.kubeconfig_file}" -n ate-system rollout restart deployment/k8s-credential-provider
kubectl --kubeconfig="${self.input.kubeconfig_file}" -n ate-system rollout status deployment/k8s-credential-provider --timeout=120s
kubectl-ate --kubeconfig="${self.input.kubeconfig_file}" create atespace "${self.input.atespace}" || true
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = <<EOT
set -euo pipefail
if [ -d "${self.input.substrate_install_dir}" ] && [ -f "${self.input.kubeconfig_file}" ]; then
  cd "${self.input.substrate_install_dir}"
  go run ./cmd/ate-setup delete ate-system \
    --no-dev-env \
    --kubeconfig="${self.input.kubeconfig_file}" || true
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
