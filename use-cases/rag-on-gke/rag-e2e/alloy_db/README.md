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

4. Create Google Service Account

gcloud iam service-accounts create alloydb-access-sa \
  --display-name="AlloyDB Admin Service Account"

Add following roles:

gcloud projects add-iam-policy-binding $MLP_PROJECT_ID \
  --member="serviceAccount:alloydb-access-sa@$MLP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/alloydb.admin" \
  --condition="None"

gcloud projects add-iam-policy-binding $MLP_PROJECT_ID \
  --member=serviceAccount:alloydb-access-sa@$MLP_PROJECT_ID.iam.gserviceaccount.com --role="roles/alloydb.client" \
  --condition="None"

gcloud projects add-iam-policy-binding $MLP_PROJECT_ID \
  --member=serviceAccount:alloydb-access-sa@$MLP_PROJECT_ID.iam.gserviceaccount.com --role="roles/serviceusage.serviceUsageConsumer" \
  --condition="None"

-- Add Storage Admin
gcloud projects add-iam-policy-binding $MLP_PROJECT_ID --member=serviceAccount:alloydb-access-sa@$MLP_PROJECT_ID.iam.gserviceaccount.com --role="roles/storage.objectAdmin" --condition="None"


# Workload Identity Creation
# 1. Get fleet credentials
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}


# 2. Create a Kubernetes service account in your GKE cluster
kubectl create serviceaccount rag-ksa -n ml-team

# 3. Annotate the Kubernetes service account with the email address of the Google Cloud service account
kubectl annotate serviceaccount rag-ksa \
  iam.gke.io/gcp-service-account=alloydb-access-sa@$MLP_PROJECT_ID.iam.gserviceaccount.com
  -n ml-team


# 4. Bind the Google Cloud service account to the Kubernetes service account using Workload Identity

gcloud iam service-accounts add-iam-policy-binding \
   --role="roles/iam.workloadIdentityUser" \
   --member="serviceAccount:gkebatchexpce3c8dcb.svc.id.goog[ml-team/rag-ksa]" \
   alloydb-access-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com \
   --condition="None"


# 5. 
gcloud iam service-accounts add-iam-policy-binding \
    alloydb-access-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com \
    --member="serviceAccount:gkebatchexpce3c8dcb.svc.id.goog[ml-team/rag-ksa]" \
    --role="roles/iam.serviceAccountTokenCreator"

# 6. Use KSA in the job and Apply the Job to your GKE cluster:

Bash
kubectl apply -f  alloydb-setup-job.yaml -n ml-team 

Check logs:
kubectl get pods -n ml-team
kubectl logs -f catalog-onboarding-job-X -n ml-team
