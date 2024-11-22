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


3. Use KSA in the job and Apply the Job to your GKE cluster:

gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}

Bash
kubectl apply -f  alloydb-setup-job.yaml -n ml-team 

Check logs:
kubectl get pods -n ml-team
kubectl logs -f alloydb-setup-xxxxx -n ml-team
