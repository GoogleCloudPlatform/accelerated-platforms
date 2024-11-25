## Steps to deploy multi modal embedding model BLIP2

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project ${MLP_PROJECT_ID}
```

```
docker build -t gcr.io/${MLP_PROJECT_ID}/multi_emb:latest src/
docker push gcr.io/${MLP_PROJECT_ID}/multi_emb:latest
kubectl delete -f manifests/multimodal-embedding.yaml -n ${MLP_KUBERNETES_NAMESPACE}
kubectl apply -f manifests/multimodal-embedding.yaml -n ${MLP_KUBERNETES_NAMESPACE}
```
