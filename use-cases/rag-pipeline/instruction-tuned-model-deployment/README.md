# Steps to deploy instruction tuned model

```
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project ${MLP_PROJECT_ID}
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```

## set HF Token

HF_TOKEN=<your-hugging-face-api-token>

## Create secret

```
kubectl create secret generic hf-secret \
--from-literal=hf_api_token=${HF_TOKEN} \
--dry-run=client -o yaml | kubectl apply -n ${MLP_KUBERNETES_NAMESPACE} -f -
```

## Deploy model

```
kubectl apply -f it-model-deployment.yaml -n ml-team
```
