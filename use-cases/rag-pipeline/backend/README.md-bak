# Deploy backend application in GKE

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project ${MLP_PROJECT_ID}
```

## Build the image and deploy the application

```
docker build -t gcr.io/${MLP_PROJECT_ID}/rag-backend:latest src/
docker push gcr.io/${MLP_PROJECT_ID}/rag-backend:latest
kubectl delete -f manifests/rag-backend-deployment-cpu.yaml -n ${MLP_KUBERNETES_NAMESPACE}
kubectl apply -f  manifests/rag-backend-deployment-cpu.yaml -n ${MLP_KUBERNETES_NAMESPACE}
kubectl get pods -n ${MLP_KUBERNETES_NAMESPACE}
```

## Testing as a job: Run backend application job in GKE

```
docker build -t gcr.io/${MLP_PROJECT_ID}/rag-backend:latest src/
docker push gcr.io/${MLP_PROJECT_ID}/rag-backend:latest
kubectl delete -f manifests/rag-backend-job.yaml -n ${MLP_KUBERNETES_NAMESPACE}
kubectl apply -f  manifests/rag-backend-job.yaml -n ${MLP_KUBERNETES_NAMESPACE}
kubectl get pods -n ${MLP_KUBERNETES_NAMESPACE}
kubectl logs -n ${MLP_KUBERNETES_NAMESPACE} rag-backend-job-xxxxx
```
