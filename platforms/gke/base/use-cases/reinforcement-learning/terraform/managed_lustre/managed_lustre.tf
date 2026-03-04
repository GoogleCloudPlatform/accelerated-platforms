resource "google_lustre_instance" "vllm_kv_cache" {
  instance_id  = "vllm-lustre-cache"
  location     = local.cluster_region
  capacity_gib = 18000
  network      = local.network_cluster_network_name
  filesystem   = "vllmfs"

  # 250, 500, or 1000 MB/s/TiB
  per_unit_storage_throughput = 250

  gke_support_enabled = true

  labels = {
    workload = "vllm-offloading"
  }
}
