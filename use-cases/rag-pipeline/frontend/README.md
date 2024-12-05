## Frontend application deployment

# Getting Started

## Prepare the environment

You have an existing [ML Playground cluster](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/platforms/gke-aiml/playground) in a Google Cloud Project.

## Set the default environment variables:

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project $MLP_PROJECT_ID
```

## Build the frontend container image container image

```
#<TODO> change it to main branch before merge
git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git
cd rag-pipeline/frontend
```

Update the location where you would like to store the container images in the ```cloud build yaml`` and kick off the build: 

Create the artifact repostiory(if it not already exists) to store the container images:

```
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="RAG artifacts repository"
```

```
cd src
gcloud builds submit . 
```

## Deploy the frontend RAG application

Update manifests/frontend_gradio_deployment.yaml file with absolute path to of the frontend image (container registry) and GPU resource allocations as needed. 

Now, deploy frontend application:

```sh
    export BACKEND_SERVICE_ENDPOINT="http://rag-backend.ml-team:8000/generate_product_recommendations/"
```

```sh
  sed \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_BACKEND_SERVICE_ENDPOINT|${BACKEND_SERVICE_ENDPOINT}|" \
  manifests/frontend_gradio_deployment.yaml
  ```

```sh
kubectl apply -f manifests/frontend_gradio_deployment.yaml -n {MLP_KUBERNETES_NAMESPACE}
```

## Test pod deployment for frontend RAG application
Validations: 
kubectl get po -n {MLP_KUBERNETES_NAMESPACE}


└─⪧ kubectl get svc -n {MLP_KUBERNETES_NAMESPACE}
NAME              TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)          AGE


## Retrieve the fronend URL endpoint 

```sh
echo {MLP_FRONTEND_RAG_NAMESPACE_ENDPOINT}
```
Open the Front end application in browser using URL value retrieved above.