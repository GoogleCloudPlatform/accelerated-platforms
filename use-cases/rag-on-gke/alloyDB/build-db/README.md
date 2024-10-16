# Simple Example

This example illustrates how to use the `alloy-db` module. It creates two clusters, `primary` cluster `cluster-us-central1` in `us-central1` and a `DR` cluster `cluster-us-east1` in `us-east1`.

## Usage

To run this example you need to execute:

```bash
export TF_VAR_project_id="your_project_id"
```

```bash
terraform init
terraform plan
terraform apply
terraform destroy
```

<!-- BEGINNING OF PRE-COMMIT-TERRAFORM DOCS HOOK -->
## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| network\_name | The ID of the network in which to provision resources. | `string` | `"simple-adb"` | no |
| project\_id | The ID of the project in which to provision resources. | `string` | n/a | yes |
| region\_central | The region for cluster in central us | `string` | `"us-central1"` | no |
| region\_east | The region for cluster in east us | `string` | `"us-east1"` | no |

## Outputs

| Name | Description |
|------|-------------|
| cluster\_id | ID of the Alloy DB Cluster created |
| cluster\_name | The name of the cluster resource |
| kms\_key\_name | he fully-qualified resource name of the KMS key |
| primary\_instance\_id | ID of the primary instance created |
| project\_id | Project ID of the Alloy DB Cluster created |
| region | The region for primary cluster |
| secondary\_cluster\_id | ID of the Secondary Alloy DB Cluster created |
| secondary\_cluster\_name | The name of the Secondary cluster resource |
| secondary\_kms\_key\_name | he fully-qualified resource name of the Secondary clusterKMS key |
| secondary\_primary\_instance\_id | ID of the Secondary Cluster primary instance created |
| secondary\_region | The region for cross region replica secondary cluster |

<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->

## Failover to DR Cluster

There are two clusters deployed in this example. `cluster-us-central1` is the primary cluster and `cluster-us-east1` is the failover replica. Here are the steps to promote `cluster-us-east1` as primary. You will have to drop and recreate `cluster-us-central1` as failover replica after the promotion.

1) remove  `primary_cluster_name` from `cluster-us-east1` and Execute `terraform apply`

```diff
module "alloydb_east" {
  source  = "GoogleCloudPlatform/alloy-db/google"
  version = "~> 3.2"

  ## Comment this out in order to promote cluster as primary cluster
-  primary_cluster_name = module.alloydb_central.cluster_name
}
```

2) Remove `cluster-us-central1` from the code and Execute `terraform apply`

```diff
- module "alloydb_central" {
-   source  = "GoogleCloudPlatform/alloy-db/google"
-   version = "~> 2.0"
-   cluster_id       = "cluster-1"
-   cluster_location = var.region1
-   project_id       = var.project_id
-   network_self_link           = "projects/${var.project_id}/global/networks/${var.network_name}"
-   cluster_encryption_key_name = google_kms_crypto_key.key_region1.id
- ...
- }
- output "cluster_id" {
-   description = "ID of the Alloy DB Cluster created"
-   value       = module.alloydb_central.cluster_id
- }
- output "primary_instance_id" {
-   description = "ID of the primary instance created"
-   value       = module.alloydb_central.primary_instance_id
- }
- output "cluster_name" {
-   description = "The name of the cluster resource"
-   value       = module.alloydb_central.cluster_name
- }
```

3) Create `cluster-us-central1` as failover replica by adding it back to the code with following additional lines and Execute `terraform apply`

```diff
module "alloydb_central" {
  source  = "GoogleCloudPlatform/alloy-db/google"
  version = "~> 2.0"

+  primary_cluster_name = module.alloydb_east.cluster_name

  cluster_id       = "cluster-1"
  cluster_location = var.region1
  project_id       = var.project_id

  network_self_link           = "projects/${var.project_id}/global/networks/${var.network_name}"
  cluster_encryption_key_name = google_kms_crypto_key.key_region1.id
...
  depends_on = [
-    module.alloydb_central,
    google_service_networking_connection.vpc_connection,
    google_kms_crypto_key_iam_member.alloydb_sa_iam_secondary,
  ]
}
```

## Switchover to DR Cluster

Switchover is supported in terraform by refreshing the state of the terraform configurations. You can `switchover` from `primary` to `DR` cluster and switch back from `DR` to `primary` cluster. Steps 2-5 are not needed if you are planning to switch back to primary cluster after switchover testing.

1. The [switchover operation](https://cloud.google.com/alloydb/docs/cross-region-replication/work-with-cross-region-replication#switchover-secondary) needs to be called outside of terraform.

```tf
   gcloud alloydb clusters switchover SECONDARY_CLUSTER_ID \
   --region=SECONDARY_CLUSTER_REGION_ID \
   --project=PROJECT_ID \
```

2. After the switchover operation is completed successfully refresh the state of the AlloyDB resources by running `terraform apply -refresh-only` .

3. Remove  `primary_cluster_name` and `dependency` in `cluster-us-east1`

```diff
module "alloydb_east" {
  source  = "GoogleCloudPlatform/alloy-db/google"
  version = "~> 3.0"

-  primary_cluster_name = module.alloydb_central.cluster_name
...

  depends_on = [
-   module.alloydb_central
    google_service_networking_connection.vpc_connection,
    google_kms_crypto_key_iam_member.alloydb_sa_iam,
  ]

}
```

4. Add `primary_cluster_name` and dependency in `cluster-us-central1`

```diff
module "alloydb_central" {
  source  = "GoogleCloudPlatform/alloy-db/google"
  version = "~> 2.0"

+  primary_cluster_name = module.alloydb_east.cluster_name

  cluster_id       = "cluster-1"
  cluster_location = var.region1
  project_id       = var.project_id

  network_self_link           = "projects/${var.project_id}/global/networks/${var.network_name}"
  cluster_encryption_key_name = google_kms_crypto_key.key_region1.id
...
  depends_on = [
+    module.alloydb_east,
    google_service_networking_connection.vpc_connection,
    google_kms_crypto_key_iam_member.alloydb_sa_iam_secondary,
  ]
}
```

5. Execute `terraform apply`. This will update `deletion_policy`.

