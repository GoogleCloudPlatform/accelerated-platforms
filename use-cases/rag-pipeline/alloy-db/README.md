```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project $MLP_PROJECT_ID
```

- Build the Docker image:

```
docker build -t alloydb-setup:latest .
```

- Push the image to a container registry:

```
docker tag catalog-onboarding:latest gcr.io/${MLP_PROJECT_ID}/alloydb-setup:latest
docker push gcr.io/${MLP_PROJECT_ID}/alloydb-setup:latest
```

- Use KSA in the job and Apply the Job to your GKE cluster:

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```

```
kubectl apply -f alloydb-setup-job.yaml -n ml-team
```

```
kubectl get pods -n ml-team
```

```
kubectl logs -f alloydb-setup-xxxxx -n ml-team
```
