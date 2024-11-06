# Create and initialize AlloyDB for the Retrieval-Augmented Generation(RAG) use-case

In this directory you will find the terraform manifests to create and initialize
an AlloyDB cluster which you will use for the rest of the RAG use-case.

You need to do the following steps one by one:

- Deploy the AlloyDB database cluster
- Initialize the database by creating the in-database objects
- Create a configmap in the GKE cluster
  - This configmap holds the database connectivity information

## Create the database cluster

This step you are going to deploy the AlloyDB cluster and 

- Create the primary instance in the cluster
- Enable `iam_authentication` for the instance
- Create two users of type IAM\_USER
  - A user having the `alloydbsuperuser` and `alloydbiamuser` roles
  - A user only having the `alloydbiamuser` role(normal user)
- Two GCP service accounts bound to the created AlloyDB users
  - These service accounts can authenticate to the AlloyDB by using the OAuth
    `access_token`
  - By assigning these service accounts to the application, the authentication
    can happen in a way that no secrets are needed


Follow the [README.md](build-db/README.md) to create the database cluster. This
is required before you move on the other steps.

## Initialize the database by creating the in-database objects

This step you are creating a database in the AlloyDB cluster and grant
privileges to the normal user. Also you are creating the extensions in the
database and creating the google\_ml\_integration functions to be used by the
RAG application.

To finish this step you need to have an existing GKE cluster, and the endpoints
to the following ready-to-use ML services:

- pretrained model endpoint provided by vLLM
  - e.g. `http://10.1.1.10:8000/v1/completions`
- embedding service endpoint
  - e.g. `http://10.1.1.20/embeddings`

Follow the [README.md](init-database-objects/README.md) to accomplish this task.

## Create a configmap in the GKE cluster

This step you are creating a configmap in the GKE cluster, the configmap holds
the connection information to the database, the keys in the configmap are:

- `pghost` the ip-address to the primary instance
- `pgdatabase` the postgresql database name in the AlloyDB cluster

Follow the [README.md](create-database-configmap/README.md) to accomplish this
task.
