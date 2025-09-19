locals {
  acp_root                        = "${path.module}/../../../../../.."
  kubernetes_kubeconfig_directory = "${local.acp_root}/platforms/gke/base/kubernetes/kubeconfig"
  kubernetes_manifests_directory  = "${local.acp_root}/platforms/gke/base/kubernetes/manifests"
  kubernetes_namespace_directory  = "${local.kubernetes_manifests_directory}/namespace"

  kubeconfig_file = "${local.kubernetes_kubeconfig_directory}/${local.kubeconfig_file_name}"

  my_kubernetes_namespace           = var.gke_gateway_kubernetes_namespace_name
  my_kubernetes_namespace_directory = "${local.kubernetes_namespace_directory}/${local.my_kubernetes_namespace}"
  my_kubernetes_namespace_file      = "${local.kubernetes_namespace_directory}/namespace-${local.my_kubernetes_namespace}.yaml"
}


data "local_file" "kubeconfig" {
  filename = local.kubeconfig_file
}


#Namespace
##############################################################################
resource "local_file" "namespace_yaml" {
  content = templatefile(
    "${path.module}/templates/namespace.yaml",
    {
      kubernetes_namespace = local.my_kubernetes_namespace
    }
  )
  file_permission = "0644"
  filename        = local.my_kubernetes_namespace_file
}

module "kubectl_apply_namespace" {
  depends_on = [
    local_file.namespace_yaml,
  ]

  source = "../../../modules/kubectl_apply"

  delete_timeout              = "60s"
  error_on_delete_failure     = false
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = local.my_kubernetes_namespace_file
  manifest_includes_namespace = true
}

resource "local_file" "gke_l7_global_external_managed_gateway_yaml" {
  for_each = toset(contains(var.gke_gateway_class_names, "gke-l7-global-external-managed") ? ["managed"] : [])

  content = templatefile(
    "${path.module}/templates/gke-l7-global-external-managed/gateway.yaml",
    {
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/gateway-gke-l7-global-external-managed.yaml"
}

resource "local_file" "gke_l7_regional_external_managed_gateway_yaml" {
  for_each = toset(contains(var.gke_gateway_class_names, "gke-l7-regional-external-managed") ? ["managed"] : [])

  content = templatefile(
    "${path.module}/templates/gke-l7-regional-external-managed/gateway.yaml",
    {
    }
  )
  file_permission = "0644"
  filename        = "${local.my_kubernetes_namespace_directory}/gateways/gateway-gke-l7-regional-external-managed.yaml"
}

module "kubectl_apply_gateway_manifests" {
  depends_on = [
    local_file.gke_l7_global_external_managed_gateway_yaml,
    local_file.gke_l7_regional_external_managed_gateway_yaml,
    module.kubectl_apply_namespace,
  ]

  source = "../../../modules/kubectl_apply"

  apply_server_side           = true
  kubeconfig_file             = data.local_file.kubeconfig.filename
  manifest                    = "${local.my_kubernetes_namespace_directory}/gateways"
  manifest_includes_namespace = false
  namespace                   = local.my_kubernetes_namespace
}
