Build and push the Docker image:

Build: docker build -t rerank .

Tag: docker tag rerank:latest gcr.io/[YOUR_PROJECT_ID]/rerank:latest
docker tag rerank:latest gcr.io/gkebatchexpce3c8dcb/rerank:latest

Push: docker push gcr.io/[YOUR_PROJECT_ID]/rerank:latest
docker push gcr.io/gkebatchexpce3c8dcb/rerank:latest

Replace placeholders:
In rerank-job.yaml, replace the image name with your actual image.

kubectl apply -f rerank-job.yaml -n ml-team

kubectl get jobs 
kubectl get pods
