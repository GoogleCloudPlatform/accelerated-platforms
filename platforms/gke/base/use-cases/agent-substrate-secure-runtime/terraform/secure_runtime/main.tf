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
  kubeconfig_file         = "${path.module}/../../../../kubernetes/kubeconfig/${local.kubeconfig_file_name}"
  manifests_out_directory = "${path.module}/../../../../kubernetes/manifests/use-cases/agent-substrate-secure-runtime"
  repo_root               = abspath("${path.module}/../../../../../../..")
  secure_runtime_images = {
    agent          = { dir = "container-images/cpu/secure-runtime-agent", destination = local.secure_runtime_agent_image_url }
    intent_extproc = { dir = "container-images/cpu/secure-runtime-intent-extproc", destination = local.secure_runtime_intent_extproc_image_url }
    runner         = { dir = "container-images/cpu/secure-runtime-runner", destination = local.secure_runtime_runner_image_url }
  }
  substrate_install_dir           = "${path.module}/../../../../core/workloads/agent_substrate/manifests/substrate-${var.agent_substrate_version}"
  use_case_manifests_dir          = "${path.module}/../../kubernetes-manifests"
  workload_identity_member_triage = "principal://iam.googleapis.com/projects/${data.google_project.cluster.number}/locations/global/workloadIdentityPools/${data.google_project.cluster.project_id}.svc.id.goog/subject/ns/${var.secure_runtime_agent_namespace}/sa/${var.secure_runtime_agent_service_account}"
}

data "google_project" "cluster" {
  project_id = local.cluster_project_id
}

data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}

resource "google_project_iam_member" "triage_agent_roles" {
  for_each = toset(["roles/aiplatform.user", "roles/cloudtrace.agent"])
  member   = local.workload_identity_member_triage
  project  = data.google_project.cluster.project_id
  role     = each.value
}

resource "terraform_data" "build_secure_runtime_images" {
  for_each = local.secure_runtime_images
  input = {
    cloudbuild_project_id         = local.cloudbuild_project_id
    cloudbuild_service_account_id = local.cloudbuild_service_account_id
    cloudbuild_source_bucket_name = local.cloudbuild_source_bucket_name
    dir                           = each.value.dir
    image_destination             = each.value.destination
    repo_root                     = local.repo_root
  }

  provisioner "local-exec" {
    command     = <<-EOT
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}"
gcloud builds submit "${self.input.dir}" \
  --config="${self.input.dir}/cloudbuild.yaml" \
  --gcs-source-staging-dir="gs://${self.input.cloudbuild_source_bucket_name}/source" \
  --project="${self.input.cloudbuild_project_id}" --quiet \
  --service-account="${self.input.cloudbuild_service_account_id}" \
  --substitutions=_DESTINATION="${self.input.image_destination}"
EOT
    interpreter = ["bash", "-c"]
    working_dir = self.input.repo_root
  }

  triggers_replace = {
    cloudbuild_yaml_hash = filebase64sha256("${local.repo_root}/${each.value.dir}/cloudbuild.yaml")
    dockerfile_hash      = filebase64sha256("${local.repo_root}/${each.value.dir}/Dockerfile")
    image_destination    = each.value.destination
    source_hash          = sha256(join("", [for f in fileset("${local.repo_root}/${each.value.dir}/src", "**") : filesha256("${local.repo_root}/${each.value.dir}/src/${f}")]))
  }
}

resource "local_sensitive_file" "secure_runtime_manifest" {
  content = replace(replace(replace(replace(replace(replace(replace(replace(
    file("${local.use_case_manifests_dir}/secure-runtime.yaml"),
    "$${GITHUB_READONLY_TOKEN}", var.secure_runtime_github_readonly_token),
    "$${WORKER_IMAGE}", "${local.cloudbuild_ar_image_repository_url}/ateworker-gvisor:${var.agent_substrate_version}"),
    "$${INTENT_EXTPROC_IMAGE}", local.secure_runtime_intent_extproc_image_url),
    "$${AGENT_IMAGE}", local.secure_runtime_agent_image_url),
    "$${GOOGLE_CLOUD_PROJECT}", data.google_project.cluster.project_id),
    "$${GOOGLE_CLOUD_LOCATION}", local.cluster_region),
    "$${GEMINI_MODEL}", var.secure_runtime_gemini_model),
  "$${GITHUB_REPO}", var.secure_runtime_github_repo)
  file_permission = "0600"
  filename        = "${local.manifests_out_directory}/secure-runtime.yaml"
}

resource "local_file" "actortemplate_manifest_tmpl" {
  content  = replace(file("${local.use_case_manifests_dir}/actortemplate.yaml"), "$${SUBSTRATE_ATESPACE}", var.agent_substrate_atespace)
  filename = "${local.manifests_out_directory}/actortemplate.yaml.tmpl"
}

resource "terraform_data" "deploy_secure_runtime" {
  depends_on = [
    google_project_iam_member.triage_agent_roles,
    terraform_data.build_secure_runtime_images,
    local_sensitive_file.secure_runtime_manifest,
    local_file.actortemplate_manifest_tmpl,
  ]

  input = {
    actortemplate_file         = local_file.actortemplate_manifest_tmpl.filename
    actortemplate_out_file     = "${local.manifests_out_directory}/actortemplate.yaml"
    ar_repo_url                = local.cloudbuild_ar_image_repository_url
    atespace                   = var.agent_substrate_atespace
    cloudbuild_project_id      = local.cloudbuild_project_id
    cluster_location           = local.cluster_region
    cluster_name               = local.cluster_name
    credential_provider        = var.agent_substrate_credential_provider
    ingress_allowed_spiffe_ids = var.agent_substrate_ingress_allowed_spiffe_ids
    kubeconfig_file            = data.local_file.kubeconfig.filename
    project_id                 = data.google_project.cluster.project_id
    runner_image_url           = local.secure_runtime_runner_image_url
    secure_runtime_manifest    = local_sensitive_file.secure_runtime_manifest.filename
    substrate_install_dir      = local.substrate_install_dir
    version                    = var.agent_substrate_version
  }

  provisioner "local-exec" {
    command     = <<-EOT
set -euo pipefail
KUBECONFIG_ABS="$(realpath "${self.input.kubeconfig_file}")"
export PATH="$${HOME}/.local/bin:$${HOME}/google-cloud-sdk/bin:$${PATH}" KUBECONFIG="$${KUBECONFIG_ABS}"

sed "s|\$${SUBSTRATE_ATESPACE}|${self.input.atespace}|g" "${self.input.secure_runtime_manifest}" | kubectl apply -f -
kubectl -n ate-system rollout status deployment/intent-extproc --timeout=120s

(
  cd "${self.input.substrate_install_dir}"
  go run ./cmd/ate-setup deploy atenet --no-dev-env --kubeconfig="$${KUBECONFIG_ABS}" \
    --context="gke_${self.input.project_id}_${self.input.cluster_location}_${self.input.cluster_name}" \
    --gcp-project-id="${self.input.project_id}" --gcp-cluster-name="${self.input.cluster_name}" --gcp-cluster-location="${self.input.cluster_location}" \
    --credential-provider='${self.input.credential_provider}' --ingress-allowed-spiffe-ids="${self.input.ingress_allowed_spiffe_ids}" \
    --experimental-additional-egress-extproc-service="ate-system/intent-extproc:50051" \
    --image-repo="${self.input.ar_repo_url}" --image-tag="${self.input.version}" --rollout-timeout="180s"
  kubectl apply -f "./manifests/ate-install/atenet-router-monitoring.yaml"
)

kubectl -n ate-system patch deploy atenet-router --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--parked-request-budget=60s"},{"op":"replace","path":"/spec/template/spec/terminationGracePeriodSeconds","value":120}]'
kubectl -n ate-system rollout status deploy/atenet-router --timeout=180s
kubectl -n ate-workers rollout status deployment/scientific-gvisor --timeout=180s
kubectl -n agent-harness rollout status deployment/triage-agent --timeout=120s

RUNNER_DIGEST="$(gcloud artifacts docker images describe "${self.input.runner_image_url}" --project="${self.input.cloudbuild_project_id}" --format='value(image_summary.digest)')"
sed "s|\$${RUNNER_IMAGE}|${self.input.runner_image_url}@$${RUNNER_DIGEST}|g" "${self.input.actortemplate_file}" > "${self.input.actortemplate_out_file}"

for a in $(kubectl-ate get actor -a "${self.input.atespace}" -o json 2>/dev/null | jq -r '.actors[]?.metadata.name // empty'); do
  kubectl-ate delete actor "$${a}" -a "${self.input.atespace}" || true
done
kubectl-ate delete actor-template scientific-python -a "${self.input.atespace}" 2>/dev/null || true
kubectl-ate create actor-template -f "${self.input.actortemplate_out_file}"

for _ in $(seq 1 60); do
  tag="$(kubectl-ate get actor-template scientific-python -a "${self.input.atespace}" -o jsonpath='{.status.goldenSnapshotStatus.goldenTag.name}' 2>/dev/null || true)"
  if [ -n "$${tag}" ]; then
    echo "Golden Snapshot ready: $${tag}"
    break
  fi
  sleep 5
done
EOT
    interpreter = ["bash", "-c"]
  }

  triggers_replace = {
    actortemplate_sha       = sha256(local_file.actortemplate_manifest_tmpl.content)
    runner_image_url        = local.secure_runtime_runner_image_url
    secure_runtime_manifest = sha256(local_sensitive_file.secure_runtime_manifest.content)
    version                 = var.agent_substrate_version
  }
}
