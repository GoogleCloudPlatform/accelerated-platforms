source $MLP_PLATFORM_ENV_FILE

gcloud config set project $MLP_PROJECT_ID

gcloud artifacts repositories create embedding-artifacts --repository-format=docker --location=us --description="My RAG artifacts repository"

gcloud builds submit . 

kubectl apply -f embedding-job.yaml
