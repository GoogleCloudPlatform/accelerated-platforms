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
  agent_substrate_snapshot_bucket_name = var.agent_substrate_snapshot_bucket_name != null ? var.agent_substrate_snapshot_bucket_name : "${local.unique_identifier_prefix}-ate-snapshots-${local.cluster_project_id}"
  kubeconfig_directory                 = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file                      = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  manifests_out_directory              = "${path.module}/../../../../kubernetes/manifests/use-cases/agent-substrate-secure-runtime"
  substrate_install_dir                = "${path.module}/../../../../core/workloads/agent_substrate/manifests/substrate-${var.agent_substrate_version}"
  use_case_manifests_dir               = "${path.module}/../../kubernetes-manifests"
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "local_file" "intent_extproc_manifest" {
  content = replace(
    file("${local.use_case_manifests_dir}/intent-extproc/intent-extproc.yaml"),
    "$${INTENT_EXTPROC_IMAGE}",
    local.secure_runtime_intent_extproc_image_url
  )
  filename = "${local.manifests_out_directory}/intent-extproc.yaml"
}

module "kubectl_apply_intent_extproc" {
  depends_on = [
    terraform_data.build_secure_runtime_images["intent_extproc"],
    local_file.intent_extproc_manifest,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.intent_extproc_manifest.filename
  manifest_includes_namespace = true
}

resource "terraform_data" "configure_atenet_egress_extproc" {
  depends_on = [
    module.kubectl_apply_intent_extproc,
  ]

  input = {
    ar_repo_url                = local.cloudbuild_ar_image_repository_url
    cluster_location           = local.cluster_region
    cluster_name               = local.cluster_name
    credential_provider        = var.agent_substrate_credential_provider
    ingress_allowed_spiffe_ids = var.agent_substrate_ingress_allowed_spiffe_ids
    kubeconfig_file            = data.local_file.kubeconfig.filename
    project_id                 = data.google_project.cluster.project_id
    substrate_install_dir      = local.substrate_install_dir
    version                    = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<-EOT
set -euo pipefail
KUBECONFIG_ABS="$(realpath "${self.input.kubeconfig_file}")"
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}"
export KUBECONFIG="$${KUBECONFIG_ABS}"

kubectl --kubeconfig="$${KUBECONFIG_ABS}" -n ate-system rollout status deployment/intent-extproc --timeout=120s

cd "${self.input.substrate_install_dir}"
go run ./cmd/ate-setup deploy atenet \
  --no-dev-env \
  --kubeconfig="$${KUBECONFIG_ABS}" \
  --context="gke_${self.input.project_id}_${self.input.cluster_location}_${self.input.cluster_name}" \
  --gcp-project-id="${self.input.project_id}" \
  --gcp-cluster-name="${self.input.cluster_name}" \
  --gcp-cluster-location="${self.input.cluster_location}" \
  --credential-provider='${self.input.credential_provider}' \
  --ingress-allowed-spiffe-ids="${self.input.ingress_allowed_spiffe_ids}" \
  --experimental-additional-egress-extproc-service="ate-system/intent-extproc:50051" \
  --image-repo="${self.input.ar_repo_url}" \
  --image-tag="${self.input.version}" \
  --rollout-timeout="180s"
EOT
    interpreter = ["bash", "-c"]
  }

  triggers_replace = {
    intent_extproc_manifest_sha = sha256(local_file.intent_extproc_manifest.content)
    version                     = var.agent_substrate_version
  }
}

resource "local_file" "workerpool_manifest" {
  content = replace(
    file("${local.use_case_manifests_dir}/substrate/workerpool.yaml"),
    "$${WORKER_IMAGE}",
    "${local.cloudbuild_ar_image_repository_url}/ateworker-gvisor:${var.agent_substrate_version}"
  )
  filename = "${local.manifests_out_directory}/workerpool.yaml"
}

module "kubectl_apply_workerpool" {
  depends_on = [
    local_file.workerpool_manifest,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.workerpool_manifest.filename
  manifest_includes_namespace = true
}

resource "local_sensitive_file" "credential_secret_manifest" {
  content = replace(
    file("${local.use_case_manifests_dir}/substrate/credential-secret.yaml.tmpl"),
    "$${GITHUB_READONLY_TOKEN}",
    var.secure_runtime_github_readonly_token
  )
  filename        = "${local.manifests_out_directory}/credential-secret.yaml"
  file_permission = "0600"
}

module "kubectl_apply_credential_secret" {
  depends_on = [
    local_sensitive_file.credential_secret_manifest,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_sensitive_file.credential_secret_manifest.filename
  manifest_includes_namespace = true
}

resource "local_file" "actortemplate_manifest_tmpl" {
  content = replace(
    replace(
      file("${local.use_case_manifests_dir}/substrate/actortemplate.yaml.tmpl"),
      "$${SUBSTRATE_ATESPACE}",
      var.agent_substrate_atespace
    ),
    "$${SNAPSHOT_BUCKET_NAME}",
    local.agent_substrate_snapshot_bucket_name
  )
  filename = "${local.manifests_out_directory}/actortemplate.yaml.tmpl"
}

resource "terraform_data" "apply_substrate_actortemplate" {
  depends_on = [
    terraform_data.build_secure_runtime_images["runner"],
    module.kubectl_apply_workerpool,
    local_file.actortemplate_manifest_tmpl,
  ]

  input = {
    actortemplate_file      = local_file.actortemplate_manifest_tmpl.filename
    actortemplate_out_file  = "${local.manifests_out_directory}/actortemplate.yaml"
    atespace                = var.agent_substrate_atespace
    cloudbuild_project_id   = local.cloudbuild_project_id
    kubeconfig_file         = data.local_file.kubeconfig.filename
    runner_image_url        = local.secure_runtime_runner_image_url
    substrate_version       = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<-EOT
set -o errexit
set -o nounset
set -o pipefail

export KUBECONFIG="${self.input.kubeconfig_file}"
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}"

# Resolve the digest of the runner image (required by ActorTemplate admission CEL rule self.contains('@'))
RUNNER_DIGEST="$(gcloud artifacts docker images describe "${self.input.runner_image_url}" --project="${self.input.cloudbuild_project_id}" --format='value(image_summary.digest)')"
RUNNER_IMAGE_PINNED="${self.input.runner_image_url}@$${RUNNER_DIGEST}"

sed "s|\$${RUNNER_IMAGE}|$${RUNNER_IMAGE_PINNED}|g" "${self.input.actortemplate_file}" > "${self.input.actortemplate_out_file}"

# Wait for the WorkerPool to have at least 1 Ready worker pod before creating
# the ActorTemplate (which builds the Golden Snapshot on a warm worker).
for _ in $(seq 1 60); do
  ready="$(kubectl get deployment scientific-gvisor -n ate-workers -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)"
  if [ "$${ready:-0}" -ge 1 ]; then
    break
  fi
  sleep 5
done

if kubectl-ate get actor-template scientific-python -a "${self.input.atespace}" >/dev/null 2>&1; then
  kubectl-ate delete actor-template scientific-python -a "${self.input.atespace}" || true
fi
kubectl-ate create actor-template -f "${self.input.actortemplate_out_file}"

echo "Waiting for scientific-python Golden Snapshot to become Ready..."
for _ in $(seq 1 60); do
  tag="$(kubectl-ate get actor-template scientific-python -a "${self.input.atespace}" -o jsonpath='{.status.goldenSnapshotStatus.tag}' 2>/dev/null || true)"
  err="$(kubectl-ate get actor-template scientific-python -a "${self.input.atespace}" -o jsonpath='{.status.goldenSnapshotStatus.errorMessage}' 2>/dev/null || true)"
  if [ -n "$${tag}" ]; then
    echo "Golden Snapshot ready: $${tag}"
    break
  fi
  if [ -n "$${err}" ]; then
    echo "Golden Snapshot failed: $${err}" >&2
    exit 1
  fi
  sleep 5
done
EOT
    interpreter = ["bash", "-c"]
  }

  triggers_replace = {
    actortemplate_sha = sha256(local_file.actortemplate_manifest_tmpl.content)
    runner_image_url  = local.secure_runtime_runner_image_url
  }
}

resource "local_file" "agent_deployment_manifest" {
  content = replace(
    replace(
      replace(
        replace(
          replace(
            replace(
              file("${local.use_case_manifests_dir}/agent/agent-deployment.yaml"),
              "$${AGENT_IMAGE}",
              local.secure_runtime_agent_image_url
            ),
            "$${GOOGLE_CLOUD_PROJECT}",
            data.google_project.cluster.project_id
          ),
          "$${GOOGLE_CLOUD_LOCATION}",
          local.cluster_region
        ),
        "$${GEMINI_MODEL}",
        var.secure_runtime_gemini_model
      ),
      "$${GITHUB_REPO}",
      var.secure_runtime_github_repo
    ),
    "$${SUBSTRATE_ATESPACE}",
    var.agent_substrate_atespace
  )
  filename = "${local.manifests_out_directory}/agent-deployment.yaml"
}

module "kubectl_apply_agent_deployment" {
  depends_on = [
    google_project_iam_member.triage_agent_vertex_ai_user,
    google_project_iam_member.triage_agent_cloud_trace_agent,
    terraform_data.build_secure_runtime_images["agent"],
    module.kubectl_apply_intent_extproc,
    terraform_data.configure_atenet_egress_extproc,
    module.kubectl_apply_credential_secret,
    terraform_data.apply_substrate_actortemplate,
    local_file.agent_deployment_manifest,
  ]

  source = "../../../../modules/kubectl_apply"

  apply_once                  = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local_file.agent_deployment_manifest.filename
  manifest_includes_namespace = true
}
