cluster_auto_monitoring_config_scope         = "ALL"
cluster_autopilot_enabled                    = false
cluster_binary_authorization_evaluation_mode = "DISABLED"
cluster_check_custom_compute_classes_healthy = false
cluster_confidential_nodes_enabled           = false
cluster_database_encryption_key_name         = null
cluster_database_encryption_state            = "DECRYPTED"
cluster_enable_private_endpoint              = true
cluster_gateway_api_config_channel           = "CHANNEL_STANDARD"
cluster_gpu_driver_version                   = "LATEST"
cluster_master_global_access_enabled         = false
cluster_master_ipv4_cidr_block               = "172.16.0.32/28"
cluster_node_auto_provisioning_enabled       = true
cluster_node_auto_provisioning_resource_limits = [{
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "cpu"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "memory"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-a100-80gb"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-h100-80gb"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-h100-mega-80gb"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-l4"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-tesla-a100"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-tesla-k80"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-tesla-p4"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-tesla-p100"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-tesla-t4"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "nvidia-tesla-v100"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "tpu-v4-podslice"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "tpu-v5-lite-podslice"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "tpu-v5p-slice"
  }, {
  maximum       = 9223372036854775806
  minimum       = 0
  resource_type = "tpu-v6e-slice"
}]
cluster_node_pool_default_service_account_id         = null
cluster_node_pool_default_service_account_project_id = null
cluster_private_endpoint_subnetwork                  = null
cluster_project_id                                   = null
cluster_region                                       = "us-central1"
cluster_system_node_pool_machine_type                = "n4-standard-4"
cluster_use_connect_gateway                          = false
