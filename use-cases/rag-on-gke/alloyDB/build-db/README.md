# Deploy an AlloyDB cluster for the RAG user-case

The terraform manifests in this directory let you deploy the AlloyDB cluster and 

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

## Deploy the AlloyDB database cluster

You can create a `terraform.tfvars` file providing the value of the following
variables:

| Variable              | Description                                                        | Default Value | Example           |
|-----------------------|--------------------------------------------------------------------|---------------|-------------------|
| project_id            | The ID of the project in which to provision resources              | N/A           | your-project-id   |
| region                | The region to deploy                                               | us-central1   | us-central1       |
| cluster_name          | The name of the cluster                                            | N/A           | your-cluster-name |
| primary_instance_name | The name of the primary instance in the cluster                    | main          | instance-name     |
| network_name          | The ID of the network in which to provision resources              | default       | your-network-id   |
| alloydb_ip_range      | The ip range allocated for AlloyDB instances                       | 172.16.0.0    | 172.16.0.0        |
| alloydb_ip_prefix     | The ip prefix used for allocating ip address for AlloyDB instances | 12            | 12                |

Then run the following commands

```bash
terraform init
terraform apply
```

When prompted, answer "yes"

