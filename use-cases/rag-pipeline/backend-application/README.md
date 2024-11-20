# Deploy backend application in GKE
docker build -t rag-backend:latest src/
docker tag rag-backend:latest gcr.io/gkebatchexpce3c8dcb/rag-backend:latest
docker push gcr.io/gkebatchexpce3c8dcb/rag-backend:latest
kubectl delete -f manifests/rag-backend-deployment-cpu.yaml -n ml-team
kubectl apply -f  manifests/rag-backend-deployment-cpu.yaml -n ml-team
kubectl get pods -n ml-team

## Testing as a job: Run backend application job in GKE
docker build -t rag-backend:latest src/
docker tag rag-backend:latest gcr.io/gkebatchexpce3c8dcb/rag-backend:latest
docker push gcr.io/gkebatchexpce3c8dcb/rag-backend:latest
kubectl delete -f manifests/rag-backend-job.yaml -n ml-team
kubectl apply -f  manifests/rag-backend-job.yaml -n ml-team
kubectl get pods -n ml-team
kubectl logs -n ml-team rag-backend-job-xxxxx
