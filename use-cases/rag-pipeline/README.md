# Steps

Run following commands in cloud shell

## Pre Req

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project ${MLP_PROJECT_ID}
```

## Setup the platform:

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

## Get Fleet credentials

```
gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
```

# Deploy RAG Architecture

- Deploy Multi modal embedding model in GKE, follow the [README](/use-cases/rag-pipeline/multimodal-emb/README.md)
- Build AlloyDB, follow the [README](/use-cases/rag-pipeline/alloy-db/README.md)
- Deploy instruction-tuned model in GKE, follow the [README](/use-cases/rag-pipeline/instruction-tuned-model-deployment/README.md)
- Deploy backend application in GKE, follow the [README](/use-cases/rag-pipeline/backend-application/README.md)
- Test the backend-application with the curl job

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/curl-job.yaml
  ```
