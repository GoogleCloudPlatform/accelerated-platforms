## Frontend application deployment

# Getting Started

## Prepare the environment

You have an existing [ML Playground cluster](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/platforms/gke-aiml/playground) in a Google Cloud Project.

## Set the default environment variables:

```
PROJECT_ID=<your-project-id>
gcloud config set project $PROJECT_ID
```

## Build the frontend container image container image

```
#<TODO> change it to main branch before merge
git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git
cd rag-on-gke/frontend/src
```

Update the location where you would like to store the container images in the ```cloud build yaml`` and kick off the build: 

Create the artifact repostiory(if it not already exists) to store the container images:

```
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="RAG artifacts repository"
```

```
gcloud builds submit . 
```

## Deploy the embedding model

Update manifests/frontend_gradio_deployment.yaml file with absolute path to of the embedding model image (container registry) and GPU resource allocations as needed. 
A sample deployment.yaml has been provided for your reference.


Now, deploy frontend application:

```
NAMESPACE=ml-team
sed \
-i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
manifests/backend_deployment.yaml
kubectl apply -f manifests/backend_deployment.yaml -n $NAMESPACE
```

## Test the embedding model
Validations: 
kubectl get po -n $NAMESPACE


└─⪧ kubectl get svc
NAME              TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)          AGE


## Run the curl test for embedding models once backed in deployed
Using the sample image ```./t-shirt.jpg``` generate the image embedding
You can use the sample curl requests from ```curl_requests.txt```
