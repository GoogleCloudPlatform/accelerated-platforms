# Create a configmap in the GKE cluster

This step you are creating a configmap in the GKE cluster, the configmap holds the connection information to the database, the keys in the configmap are:

- `pghost` the ip-address to the primary instance
- `pgdatabase` the postgresql database name in the AlloyDB cluster

## Execute the task

You create a `terraform.tfvars` file for these variables:

| Variable                 | Description                                                               | Default Value | Example             |
| project_id               | The ID of the project in which to provision resources                     | N/A           | your-project-id     |
| alloydb_region           | The region of the AlloyDB cluster                                         | us-central1   | us-central1         |
| alloydb_cluster          | The name of the AlloyDB Cluster                                           | N/A           | your-cluster-name   |
| alloydb_primary_instance | The name of the primary instance in the AlloyDB Cluster                   | main          | instance-name       |
| gke_cluster_project_id   | The project where the GKE cluster is in. If not specified, use project_id | null          | your-gke-project-id |
| gke_cluster_name         | The name of the existing GKE cluster to run jobs on                       | N/A           | a-gke-cluster       |
| gke_cluster_location     | The location of the existing GKE cluster to run jobs on                   | N/A           | us-central1         |
| use_gke_connect_gateway  | Whether or not using the connect gateway to access the gke cluster        | false         | true                |
| k8s_namespace            | The Kubernetes namespace to use                                           | default       | your-namespace      |

Then run the following commands:

```bash
terraform init
terraform apply
```

When prompted, answer "yes"
