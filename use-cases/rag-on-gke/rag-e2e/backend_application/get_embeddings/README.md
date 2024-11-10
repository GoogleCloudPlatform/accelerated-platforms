## Steps to fetch text, image & multi modal embeddings from GKE deployment BLIP2 end point

docker build -t get-emb-job .
docker tag get-emb-job:latest gcr.io/gkebatchexpce3c8dcb/get-emb-job:latest
docker push gcr.io/gkebatchexpce3c8dcb/get-emb-job:latest
kubectl delete -f get-emb-job.yaml -n ml-team
kubectl apply -f get-emb-job.yaml -n ml-team
