# Process to set up AlloyDB

This kubernetes job helps you load the flipkart product catalog to the alloyDB database.Also it creates separate columns to store the embeddings(text and image) in the same database as well.

## Prerequisites

<TODO> Write few lines about alloydb set up various users for IAM, workload identity , different users in ML_ENV_FILE to use .

wi-mlp-ishmeet-rag-db-admin@gkebatchenv3a4ec43f.iam granted Storage Object user permission to the bucket where the processed data exists

<TODO> decide where we would host these buckets for catalog and processed data . 
Should they be public datasets for RAG pipeline?

- Use the existing  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

- AlloyDB instance has been created as part of the ML playground deployment.
- Multimodal embedding model has been deployed as per instructions 

Steps : 

1. Source your playground environment file to export Variables required for the set up.

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project $MLP_PROJECT_ID
```

2. Create the artifact repostiory(if it not already exists) to store the container images:

```
cd src
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="RAG artifacts repository"
```

```
gcloud builds submit . 
```

4. Create the KSA required to connect to google cloud storage buckets.

```
kubectl create serviceaccount dev-rag-ml-team-db-admin \
    --namespace ml-team
```

```
gcloud projects add-iam-policy-binding projects/V_PROJECT_ID \
    --role=roles/container.clusterViewer \
    --member=principal://iam.googleapis.com/projects/V_PROJECT_NUMBER/locations/global/workloadIdentityPools/V_PROJECT_ID.svc.id.goog/subject/ns/$NAMESPACE/sa/dev-rag-ml-team-db-admin \
    --condition=None
```

5. Create wi-mlp-dev-rag-db-admin IAM service account and grant following IAM roles to it.

Cloud AlloyDB Client
Cloud AlloyDB Database User
Service Usage Consumer


5. Deploy the alloyDB set up job to ML Playground cluster.

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```
```
kubectl apply -f alloydb-setup-job.yaml -n ml-team
```

6. Check the job completion status :
```
kubectl get pods -n ml-team
```

7. Check logs for any errors:

```
kubectl logs -f alloydb-setup-xxxxx -n ml-team
```

