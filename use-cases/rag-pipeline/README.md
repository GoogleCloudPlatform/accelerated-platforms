# Steps
Run following commands in cloud shell

# Pre Req
source $MLP_PLATFORM_ENV_FILE
gcloud config set project $MLP_PROJECT_ID

## Create Google Service Account
gcloud iam service-accounts create alloydb-access-sa \
  --display-name="AlloyDB Admin Service Account"

## Add following roles:

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

gcloud iam service-accounts add-iam-policy-binding \
    alloydb-access-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com \
    --member="serviceAccount:gkebatchexpce3c8dcb.svc.id.goog[ml-team/rag-ksa]" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --condition="None"


# Workload Identity Creation
## 1. Get fleet credentials
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}

## 2. Create a Kubernetes service account in your GKE cluster
kubectl create serviceaccount rag-ksa -n ml-team

## 3. Annotate the Kubernetes service account with the email address of the Google Cloud service account
kubectl annotate serviceaccount rag-ksa \
  iam.gke.io/gcp-service-account=alloydb-access-sa@$MLP_PROJECT_ID.iam.gserviceaccount.com
  -n ml-team


## 4. Bind the Google Cloud service account to the Kubernetes service account using Workload Identity

gcloud iam service-accounts add-iam-policy-binding \
   --role="roles/iam.workloadIdentityUser" \
   --member="serviceAccount:gkebatchexpce3c8dcb.svc.id.goog[ml-team/rag-ksa]" \
   alloydb-access-sa@gkebatchexpce3c8dcb.iam.gserviceaccount.com \
   --condition="None"

# Deploy RAG Architecture
1. Deploy Multi modal embedding model in GKE
- cd multimodal-emb/
- Follow README.md

2. Build AlloyDB
- cd alloy-db/
- Follow README.md:
    - Creates AlloyDB cluster, instance, users, database, table; Populate the product catalog and generate embeddings, vector index on text_embeddings

3. Deploy instruction-tuned model in GKE
- cd instruction-tuned-model-deployment/
- Follow README.md 

4. Deploy backend application in GKE
- cd backend-application
- Follow README.md 
