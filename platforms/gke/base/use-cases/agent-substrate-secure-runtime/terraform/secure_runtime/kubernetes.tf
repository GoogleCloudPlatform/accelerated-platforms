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
  kubeconfig_directory    = "${path.module}/../../../../kubernetes/kubeconfig"
  kubeconfig_file         = "${local.kubeconfig_directory}/${local.kubeconfig_file_name}"
  manifests_out_directory = "${local.manifests_directory}/use-cases/agent-substrate-secure-runtime"
  use_case_manifests_dir  = "${path.module}/../../kubernetes-manifests"
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

resource "local_file" "workerpool_manifest" {
  content = replace(
    file("${local.use_case_manifests_dir}/substrate/workerpool.yaml"),
    "$${SUBSTRATE_VERSION}",
    var.agent_substrate_version
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

resource "local_file" "actortemplate_manifest" {
  content = replace(
    replace(
      file("${local.use_case_manifests_dir}/substrate/actortemplate.yaml.tmpl"),
      "$${SUBSTRATE_ATESPACE}",
      var.agent_substrate_atespace
    ),
    "$${RUNNER_IMAGE}",
    local.secure_runtime_runner_image_url
  )
  filename = "${local.manifests_out_directory}/actortemplate.yaml"
}

resource "terraform_data" "apply_substrate_actortemplate" {
  depends_on = [
    terraform_data.build_secure_runtime_images["runner"],
    module.kubectl_apply_workerpool,
    local_file.actortemplate_manifest,
  ]

  input = {
    actortemplate_file = local_file.actortemplate_manifest.filename
    atespace           = var.agent_substrate_atespace
    kubeconfig_file    = data.local_file.kubeconfig.filename
    substrate_version  = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<-EOT
set -o errexit
set -o nounset
set -o pipefail

export KUBECONFIG="${self.input.kubeconfig_file}"
export GOBIN="${path.module}/.bin"
mkdir -p "$${GOBIN}"

if [ ! -x "$${GOBIN}/kubectl-ate" ]; then
  go install "go.ate.dev/substrate/cmd/kubectl-ate@${self.input.substrate_version}"
fi

# Wait for the WorkerPool to have at least 1 Ready worker pod before creating
# the ActorTemplate (which builds the Golden Snapshot on a warm worker).
for _ in $(seq 1 60); do
  ready="$(kubectl get workerpool scientific-gvisor -n ate-workers -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)"
  if [ "$${ready:-0}" -ge 1 ]; then
    break
  fi
  sleep 5
done

if ! "$${GOBIN}/kubectl-ate" get actor-template scientific-python -a "${self.input.atespace}" >/dev/null 2>&1; then
  "$${GOBIN}/kubectl-ate" create actor-template -f "${self.input.actortemplate_file}"
fi
EOT
    interpreter = ["bash", "-c"]
  }

  triggers_replace = {
    actortemplate_sha = sha256(local_file.actortemplate_manifest.content)
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
