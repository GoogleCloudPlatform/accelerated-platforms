# Process to set up AlloyDB

This kubernetes job helps you load the flipkart product catalog to the alloyDB database.Also it creates separate columns to store the embeddings(text and image) in the same database as well.

## Prerequisites

- Use the existing  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

- AlloyDB instance has been created as part of the ML playground deployment.
- Multimodal embedding model has been deployed as per instructions 

Steps : 

1. Source your plaground environment file to export Variables required for the set up.

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

4. Deploy the alloyDB set up job to ML Playground cluster.

<TODO>Add the KSA

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

