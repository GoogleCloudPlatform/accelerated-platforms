docker build -t retrieve .
docker tag retrieve:latest gcr.io/gkebatchexpce3c8dcb/retrieve:latest
docker push gcr.io/gkebatchexpce3c8dcb/retrieve:latest
kubectl delete -f retrieve-job.yaml -n ml-team
kubectl apply -f retrieve-job.yaml -n ml-team