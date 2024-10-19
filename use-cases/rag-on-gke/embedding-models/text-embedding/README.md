## Sentence Transformers serving

see original [paper](https://arxiv.org/abs/1908.10084) 
and [source](https://github.com/UKPLab/sentence-transformers#application-examples)

# Getting Started

## List of Models for Best Sentence Embeddings (taken from [source](https://github.com/UKPLab/sentence-transformers/blob/master/README.md))

## Prepare the environment

Set the default environment variables:
```
gcloud config set project PROJECT_ID
export PROJECT_ID=$(gcloud config get project)
```

## Build Sentence Transformer embedding container image
Go go cloud shell, Clone the repo:
```
git clone 
cd rag-on-gke/embedding-models/text-embedding
```

Update the location where you would like to store the container images and kick off the build: 

```
gcloud builds submit . 
```
## Deploy the embedding model
Update embeddings.yaml file, with proper image path, and GPU resource allocations. A sample embeddings.yaml has been provided for your reference.

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
              nvidia.com/gpu: "1"
            requests:
              cpu: "2"
              memory: "8Gi"
              nvidia.com/gpu: "1"
```
then Run the following command to deploy embeddings model:
```
kubectl apply -f embeddings.yaml

```
Validations: 
kubectl get po


└─⪧ kubectl get svc
NAME              TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)          AGE


## curl tests against Embedding model
```
curl SVC_IP:8080/embed -X POST \
-d '{"inputs":"What is Deep Learning?"}' \
-H 'Content-Type: application/json'
```

## requirements
```text
sentence_transformers>=2.7.0
Flask
requests
waitress
```

# References

https://github.com/UKPLab/sentence-transformers

https://arxiv.org/abs/1908.10084