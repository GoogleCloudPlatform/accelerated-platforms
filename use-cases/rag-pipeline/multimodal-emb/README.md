## Steps to deploy multi modal embedding model BLIP2
docker build -t multi_emb src/
docker tag multi_emb:latest gcr.io/gkebatchexpce3c8dcb/multi_emb:latest
docker push gcr.io/gkebatchexpce3c8dcb/multi_emb:latest
kubectl delete -f manifests/multimodal-embedding.yaml -n ml-team
kubectl apply -f manifests/multimodal-embedding.yaml -n ml-team
