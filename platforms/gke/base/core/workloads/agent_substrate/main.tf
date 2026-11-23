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

  manifests_directory = "${path.module}/manifests"
  templates_directory = "${path.module}/templates"

  crd_template_files      = fileset("${local.templates_directory}/crds", "*.yaml")
  workload_template_files = fileset("${local.templates_directory}/workload", "*.yaml")

  template_vars = {
    actor_id_ca_cert_pem         = tls_self_signed_cert.ca["actor-id-ca-pool"].cert_pem
    actor_id_ca_key_pem          = tls_private_key.ca["actor-id-ca-pool"].private_key_pem_pkcs8
    actor_id_ca_pool_json        = local.ca_pool_json["actor-id-ca-pool"]
    actor_jwt_jwks_json          = local.actor_jwt_jwks_json
    actor_jwt_pool_json          = local.actor_jwt_pool_json
    ate_bucket_name              = data.google_storage_bucket.ate.name
    ate_cloudsql_connection_name = local.ate_cloudsql_connection_name
    ate_db_iam_user              = local.ate_db_iam_user
    ate_image_repository         = var.ate_image_repository
    ate_kubernetes_namespace     = var.ate_kubernetes_namespace
    ate_postgres_password        = local.ate_postgres_password
    ate_postgres_private_ip      = google_sql_database_instance.ate.private_ip_address
    ate_service_account_email    = data.google_service_account.ate_api_server.email
    ate_version                  = var.ate_version
    cluster_name                 = local.cluster_name
    cluster_project_id           = local.cluster_project_id
    cluster_region               = local.cluster_region
    egress_mitm_ca_cert_pem      = tls_self_signed_cert.ca["egress-mitm-ca-pool"].cert_pem
    egress_mitm_ca_key_pem       = tls_private_key.ca["egress-mitm-ca-pool"].private_key_pem_pkcs8
    egress_mitm_ca_pool_json     = local.ca_pool_json["egress-mitm-ca-pool"]
    pod_identity_ca_cert_pem     = tls_self_signed_cert.ca["pod-identity-ca-pool"].cert_pem
    pod_identity_ca_key_pem      = tls_private_key.ca["pod-identity-ca-pool"].private_key_pem_pkcs8
    pod_identity_ca_pool_json    = local.ca_pool_json["pod-identity-ca-pool"]
    postgres_ca_cert_pem         = tls_self_signed_cert.ca["postgres-ca-pool"].cert_pem
    postgres_ca_key_pem          = tls_private_key.ca["postgres-ca-pool"].private_key_pem_pkcs8
    postgres_ca_pool_json        = local.ca_pool_json["postgres-ca-pool"]
    service_dns_ca_cert_pem      = tls_self_signed_cert.ca["service-dns-ca-pool"].cert_pem
    service_dns_ca_key_pem       = tls_private_key.ca["service-dns-ca-pool"].private_key_pem_pkcs8
    service_dns_ca_pool_json     = local.ca_pool_json["service-dns-ca-pool"]
  }
}

resource "local_file" "namespaces" {
  content = templatefile(
    "${local.templates_directory}/namespaces.yaml",
    {
      ate_kubernetes_namespace = var.ate_kubernetes_namespace
    }
  )
  file_permission = "0644"
  filename        = "${local.manifests_directory}/namespaces.yaml"
}

resource "terraform_data" "namespaces" {
  depends_on = [
    local_file.namespaces,
  ]

  input = {
    kubeconfig_file = local.kubeconfig_file
    manifest_file   = local_file.namespaces.filename
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl apply -f ${self.input.manifest_file}"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl delete -f ${self.input.manifest_file} --ignore-not-found=true --wait=false || true"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    content_md5 = local_file.namespaces.content_md5
  }
}

resource "local_file" "crds" {
  for_each = local.crd_template_files

  content         = file("${local.templates_directory}/crds/${each.value}")
  file_permission = "0644"
  filename        = "${local.manifests_directory}/crds/${each.value}"
}

resource "terraform_data" "crds" {
  depends_on = [
    local_file.crds,
    terraform_data.namespaces,
  ]

  input = {
    kubeconfig_file = local.kubeconfig_file
    manifests_dir   = "${local.manifests_directory}/crds"
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl apply --server-side --force-conflicts -f ${self.input.manifests_dir}"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl delete -f ${self.input.manifests_dir} --ignore-not-found=true || true"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    manifests = join(",", [for k, v in local_file.crds : v.content_md5])
  }
}

resource "local_file" "ca_pools" {
  content = templatefile(
    "${local.templates_directory}/certificates/ca-pools.yaml",
    local.template_vars
  )
  file_permission = "0600"
  filename        = "${local.manifests_directory}/certificates/ca-pools.yaml"
}

resource "terraform_data" "ca_pools" {
  depends_on = [
    local_file.ca_pools,
    terraform_data.namespaces,
  ]

  input = {
    kubeconfig_file = local.kubeconfig_file
    manifest_file   = local_file.ca_pools.filename
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl apply -f ${self.input.manifest_file}"
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl delete -f ${self.input.manifest_file} --ignore-not-found=true || true"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    content_md5 = local_file.ca_pools.content_md5
  }
}

resource "local_file" "podcertificate_controller" {
  content = templatefile(
    "${local.templates_directory}/podcert/podcertificate-controller.yaml",
    local.template_vars
  )
  file_permission = "0644"
  filename        = "${local.manifests_directory}/podcert/podcertificate-controller.yaml"
}

resource "terraform_data" "podcertificate_controller" {
  depends_on = [
    local_file.podcertificate_controller,
    terraform_data.ca_pools,
    terraform_data.crds,
  ]

  input = {
    kubeconfig_file = local.kubeconfig_file
    manifest_file   = local_file.podcertificate_controller.filename
  }

  provisioner "local-exec" {
    command     = <<EOT
set -e
KUBECONFIG=${self.input.kubeconfig_file} kubectl apply -f ${self.input.manifest_file}
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status deployment/podcertificate-controller -n podcertificate-controller-system --timeout=300s
for i in $(seq 1 60); do
  count=$(KUBECONFIG=${self.input.kubeconfig_file} kubectl get clustertrustbundles.certificates.k8s.io -l podcert.ate.dev/canarying=live --no-headers 2>/dev/null | wc -l)
  if [ "$count" -ge 2 ]; then
    break
  fi
  sleep 2
done
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl delete -f ${self.input.manifest_file} --ignore-not-found=true || true"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    content_md5 = local_file.podcertificate_controller.content_md5
  }
}

resource "local_file" "workload" {
  for_each = local.workload_template_files

  content = templatefile(
    "${local.templates_directory}/workload/${each.value}",
    local.template_vars
  )
  file_permission = "0600"
  filename        = "${local.manifests_directory}/workload/${each.value}"
}

resource "terraform_data" "manifest" {
  depends_on = [
    google_project_iam_member.ate_api_server_cloudsql_client,
    google_project_iam_member.ate_api_server_cloudsql_instance_user,
    google_project_iam_member.atelet_artifact_registry_reader,
    google_service_account_iam_member.ate_api_server_token_creator,
    google_service_account_iam_member.ate_api_server_workload_identity,
    google_sql_database.ate,
    google_sql_user.ate_iam_user,
    google_sql_user.postgres,
    google_storage_bucket_iam_member.ate_api_server_bucket_viewer,
    google_storage_bucket_iam_member.ate_api_server_object_admin,
    google_storage_bucket_iam_member.atelet_bucket_viewer,
    google_storage_bucket_iam_member.atelet_object_admin,
    local_file.workload,
    terraform_data.podcertificate_controller,
  ]

  input = {
    ate_kubernetes_namespace = var.ate_kubernetes_namespace
    kubeconfig_file          = local.kubeconfig_file
    manifests_dir            = "${local.manifests_directory}/workload"
  }

  provisioner "local-exec" {
    command     = <<EOT
set -e
KUBECONFIG=${self.input.kubeconfig_file} kubectl apply -f ${self.input.manifests_dir}
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status deployment/ate-api-server -n ${self.input.ate_kubernetes_namespace} --timeout=300s
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status deployment/ate-controller -n ${self.input.ate_kubernetes_namespace} --timeout=300s
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status deployment/atenet-router -n ${self.input.ate_kubernetes_namespace} --timeout=300s
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status deployment/atenet-egress -n ${self.input.ate_kubernetes_namespace} --timeout=300s
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status deployment/k8s-credential-provider -n ${self.input.ate_kubernetes_namespace} --timeout=300s
KUBECONFIG=${self.input.kubeconfig_file} kubectl rollout status daemonset/atelet -n ${self.input.ate_kubernetes_namespace} --timeout=300s
EOT
    interpreter = ["bash", "-c"]
    working_dir = path.module
  }

  provisioner "local-exec" {
    command     = "KUBECONFIG=${self.input.kubeconfig_file} kubectl delete -f ${self.input.manifests_dir} --ignore-not-found=true || true"
    interpreter = ["bash", "-c"]
    when        = destroy
    working_dir = path.module
  }

  triggers_replace = {
    manifests = join(",", [for k, v in local_file.workload : v.content_md5])
  }
}
