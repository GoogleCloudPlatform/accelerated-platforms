## Multimodal blip2 model

To know more about the embedding model see original [blog](https://blog.salesforceairesearch.com/blip-2/) and [source](https://github.com/salesforce/LAVIS/tree/main/examples)

# Getting Started

## Prepare the environment

You have an existing [ML Playground cluster](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/platforms/gke-aiml/playground) in a Google Cloud Project.

## Set the default environment variables:

```
PROJECT_ID=<your-project-id>
gcloud config set project $PROJECT_ID
```

## Build the multimodal embedding model container image

```
#<TODO> change it to main branch before merge
git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git
cd rag-on-gke/embedding-models/multimodal
```

Update the location where you would like to store the container images in the ```cloud build yaml`` and kick off the build: 

Create the artifact repostiory to store the container images:

```
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="My RAG artifacts repository"
```

```
gcloud builds submit . 
```

## Deploy the embedding model

Update embeddings.yaml file with absolute path to of the embedding model image (container registry) and GPU resource allocations as needed. 
A sample embeddings.yaml has been provided for your reference.

```
 nodeSelector:
        cloud.google.com/gke-accelerator: nvidia-tesla-t4
 ...
 ...       
 image: us-<region>-docker.pkg.dev/{PROJECT_ID}/gke-llm/sentence-transformer:latest #replace with your sentence transformer image path
        resources:
            limits:
              cpu: "2"
              memory: "8Gi"
              nvidia.com/gpu: "2"
            requests:
              cpu: "2"
              memory: "8Gi"
              nvidia.com/gpu: "2"
```

Now, deploy embeddings model:

```
kubectl apply -f embeddings.yaml

```
Validations: 
kubectl get po


└─⪧ kubectl get svc
NAME              TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)          AGE


## curl tests against Embedding model
