1. Build the Docker image:

Bash
docker build -t catalog-onboarding:latest .


2. Push the image to a container registry:

If you're using Google Container Registry (GCR):
Bash
docker tag catalog-onboarding:latest gcr.io/[YOUR_PROJECT_ID]/catalog-onboarding:latest
docker push gcr.io/[YOUR_PROJECT_ID]/catalog-onboarding:latest

Replace [YOUR_PROJECT_ID] with your actual Google Cloud project ID.

3. Create a Kubernetes Secret for sensitive data:

Bash
kubectl create secret generic alloydb-secrets \
  --from-literal=project_id=[YOUR_PROJECT_ID] \
  --from-literal=password=[YOUR_PASSWORD] \
  --from-literal=catalog-admin-password=[CATALOG_ADMIN_PASSWORD] \
  --from-literal=rag-user-password=[RAG_USER_PASSWORD]
  -n ml-team

4. Create Google Service Account

gcloud iam service-accounts create alloydb-admin-sa \
  --display-name="AlloyDB Admin Service Account"

Add following roles:

gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
  --member="serviceAccount:alloydb-admin-sa@[YOUR_PROJECT_ID].iam.gserviceaccount.com" \
  --role="roles/alloydb.admin"

gcloud projects add-iam-policy-binding gkebatchexpce3c8dcb --member=serviceAccount:alloydb-admin-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com --role="roles/alloydb.client"
gcloud projects add-iam-policy-binding gkebatchexpce3c8dcb --member=serviceAccount:alloydb-admin-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com --role="roles/serviceusage.serviceUsageConsumer"

Add Cloud AlloyDB Database User

Add Storage Admin


5. Workload Identity Creation

# 1. 
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}


# 2. Create a Kubernetes service account in your GKE cluster
kubectl create serviceaccount alloydb-setup-ksa

# 3. Annotate the Kubernetes service account with the email address of the Google Cloud service account
kubectl annotate serviceaccount alloydb-setup-ksa \
  iam.gke.io/gcp-service-account=alloydb-admin-sa@[YOUR_PROJECT_ID].iam.gserviceaccount.com

# 4. Bind the Google Cloud service account to the Kubernetes service account using Workload Identity

gcloud iam service-accounts add-iam-policy-binding \
   --role="roles/iam.workloadIdentityUser" \
   --member="serviceAccount:gkebatchexpce3c8dcb.svc.id.goog[ml-team/alloydb-setup-ksa]" \
   alloydb-admin-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com

6. Use KSA in the job and Apply the Job to your GKE cluster:

Bash
kubectl apply -f  catalog-onboarding-job.yaml -n ml-team

Check logs:
kubectl get pods -n ml-team
kubectl logs -f catalog-onboarding-job-X -n ml-team
