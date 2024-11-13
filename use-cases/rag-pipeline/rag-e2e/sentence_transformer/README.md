docker build -t text_emb .
docker tag text_emb:latest gcr.io/gkebatchexpce3c8dcb/text_emb:latest
docker push gcr.io/gkebatchexpce3c8dcb/text_emb:latest
kubectl delete -f text-emb-job.yaml -n ml-team
kubectl apply -f text-emb-job.yaml -n ml-team