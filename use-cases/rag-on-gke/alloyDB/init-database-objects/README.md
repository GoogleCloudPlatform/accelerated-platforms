# Initialize the database by creating the in-database objects

This step you are creating a database in the AlloyDB cluster and grant
privileges to the normal user. Also you are creating the extensions in the
database and creating the google\_ml\_integration functions to be used by the
RAG application.

To finish this step we need to have an existing GKE cluster, and the endpoints
to the following ML services:

- pretrained model endpoint provided by vLLM
  - e.g. `http://10.1.1.10:8000/v1/completions`
- embedding service endpoint
  - e.g. `http://10.1.1.20/embeddings`

## Execute the initialization task

You create a `terraform.tfvars` file for these variables:

| Variable                  | Description                                                        | Default Value | Example                              |
| project_id                | The ID of the project in which to provision resources              | N/A           | your-project-id                      |
| alloydb_region            | The region of the AlloyDB cluster                                  | us-central1   | us-central1                          |
| alloydb_cluster           | The name of the AlloyDB Cluster                                    | N/A           | your-cluster-name                    |
| alloydb_primary_instance  | The name of the primary instance in the AlloyDB Cluster            | main          | instance-name                        |
| dba_service_account       | The k8s service account of AlloyDB superuser                       | N/A           | dba-ksa                              |
| rag_service_account       | The k8s service account of AlloyDB raguser                         | N/A           | rag-ksa                              |
| gke_cluster_name          | The name of the existing GKE cluster to run jobs on                | N/A           | a-gke-cluster                        |
| gke_cluster_location      | The location of the existing GKE cluster to run jobs on            | N/A           | us-central1                          |
| use_gke_connect_gateway   | Whether or not using the connect gateway to access the gke cluster | false         | true                                 |
| k8s_namespace             | The Kubernetes namespace to use                                    | default       | your-namespace                       |
| postgres_image            | The container image of postgresql                                  | postgres:16.4 |                                      |
| pretrained_model_endpoint | The endpoint to the pretrained model                               | N/A           | http://10.1.1.10:8000/v1/completions |
| embedding_endpoint        | The endpoint to the embedding service                              | N/A           | http://10.1.1.20/embeddings          |

Then run the following commands

```bash
terraform init
terraform apply
```

When prompted, answer "yes"


