source $MLP_PLATFORM_ENV_FILE

gcloud config set project $MLP_PROJECT_ID

1. Build the Docker image:

Bash
docker build -t alloydb-setup:latest .


2. Push the image to a container registry:

If you're using Google Container Registry (GCR):
Bash
docker tag catalog-onboarding:latest gcr.io/$MLP_PROJECT_ID/alloydb-setup:latest
docker push gcr.io/$MLP_PROJECT_ID/alloydb-setup:latest


3. TODO: Revisit this step

kubectl create secret generic alloydb-secrets \
  --from-literal=project_id=$MLP_PROJECT_ID \
  --from-literal=password=[YOUR_PASSWORD] \
  -n ml-team

Create a Kubernetes Secret for sensitive data.

Bash
kubectl create secret generic alloydb-secrets \
  --from-literal=project_id=$MLP_PROJECT_ID \
  --from-literal=password=[YOUR_PASSWORD] \
  --from-literal=catalog-admin-password=[CATALOG_ADMIN_PASSWORD] \
  --from-literal=rag-user-password=[RAG_USER_PASSWORD]
  -n ml-team


# 6. Use KSA in the job and Apply the Job to your GKE cluster:

Bash
kubectl apply -f  alloydb-setup-job.yaml -n ml-team 

Check logs:
kubectl get pods -n ml-team
kubectl logs -f catalog-onboarding-job-X -n ml-team
