# AlloyDb set up

This set up script helps you load the flipkart product catalog to the alloyDB database.
Also it creates separate columns to store the embeddings( text and image) in the same database as well.

## Prerequisites

- Use the existing  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

- AlloyDB instance has been created as part of the ML playground deployment.

Steps : 

1. Source your plaground environment file to export Variables required for the set up.

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project $MLP_PROJECT_ID
```

2. Build the Docker image for alloyDB set up script:

```
docker build -t alloydb-setup:latest .
```

3. Push this Docker image to a Artifact registry:

```
docker tag catalog-onboarding:latest gcr.io/${MLP_PROJECT_ID}/alloydb-setup:latest
docker push gcr.io/${MLP_PROJECT_ID}/alloydb-setup:latest
```

4. Use KSA in the job and Apply the Job to your GKE cluster:

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```

5. Deploy the alloyDb set up job to ML Playground.
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
