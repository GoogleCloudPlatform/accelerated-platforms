
resource "kubernetes_config_map" "get-token" {
  metadata {
    name = "${var.name}"
    namespace = var.k8s_namespace
  }
  data = var.configdata
}

