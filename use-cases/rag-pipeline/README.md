# Steps
Run following commands in cloud shell

## Pre Req
source $MLP_PLATFORM_ENV_FILE
gcloud config set project $MLP_PROJECT_ID

## Setup the platform:
Follow Readme under accelerated-platforms/platforms folder
It will create AlloyDB instance and GKE cluster and enable PSC

## Get Fleet credentials
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}

# Deploy RAG Architecture
1. Deploy Multi modal embedding model in GKE
- cd multimodal-emb/
- Follow README.md

2. Build AlloyDB
- cd alloy-db/
- Follow README.md:
    - Creates Database, Table; Populates the product catalog with embeddings; Create vector index on text_embeddings.

3. Deploy instruction-tuned model in GKE
- cd instruction-tuned-model-deployment/
- Follow README.md 

4. Deploy backend application in GKE
- cd backend-application
- Follow README.md 

5. Test with curl job in backend-application
   kubectl apply -f curl-job.yaml -n ml-team
