# Howto init the database

## Create the database cluster

Follow the `README.md` in `build-db` to create the database cluster. 

The terraform manifests in `build-db` will create a database cluster with two `IAM_USER`:

- `alloydb-superuser@${var.project_id}.iam`
  - This user has role `alloydbsuperuser`.
  - This user is bound to the GCP service account: `alloydb-superuser@${var.project_id}.iam.gserviceaccount.com`.
- `alloydb-raguser@${var.project_id}.iam`
  - This user has role `alloydbiamuser`.
  - This user is bound to the GCP service account: `alloydb-raguser@${var.project_id}.iam.gserviceaccount.com`.

## Enter `init_database_objects` to create the in-database objects

### Prerequisites

- A GKE cluster
  - The GKE should have workload identity enabled
  - The GKE cluster should have `GKE_METADATA` set for the node-pools

### Provide the variables

All of the following variables are to be provided

- `project_id`
  The project_id of all resources. At this momemnt the alloydb and the gke cluster should be in the same project.   
- `gke_cluster_name`
  The name of the GKE cluster
- `gke_cluster_location`
  The location of the GKE cluster
- `dba_service_account`
  The k8s service account of alloydb superuser, for example: `dba-ksa`,
  this service account will then attach to the GCP service account `alloydb-superuser@${var.project_id}.iam.gserviceaccount.com`
- `rag_service_account`
  The k8s service account of alloydb raguser, for example: `rag-ksa`,
  this service account will then attach to the GCP service account `alloydb-raguser@${var.project_id}.iam.gserviceaccount.com`
- `alloydb_cluster` 
  The cluster name of alloydb, should be `cluster-us-central1`
- `alloydb_instance` 
  The name of the primary instance in the alloydb cluster, should be `cluster-us-central1-instance1`
- `alloydb_region` 
  The region the alloydb cluster is in, should be `us-central1`
- `finetuned_model_endpoint`
  The endpoing to the finetuned model, for example `http://10.150.0.32:8000/v1/completions`
- `pretrained_model_endpoint`
  The endpoint to the pretrained model, for example `http://10.150.0.23:8000/v1/completions`
- `embedding_endpoint`
  The endpoint to the embedding service, for example `http://10.150.15.227/embeddings`
