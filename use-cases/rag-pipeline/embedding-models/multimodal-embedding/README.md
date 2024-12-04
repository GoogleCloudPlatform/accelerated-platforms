## Multimodal blip2 model

To know more about the embedding model see original [blog](https://blog.salesforceairesearch.com/blip-2/) and [source](https://github.com/salesforce/LAVIS/tree/main/examples)

# Getting Started

## Prepare the environment

You have an existing [ML Playground cluster](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/platforms/gke-aiml/playground) in a Google Cloud Project.

## Source your playground environment file to export variables required for the set up.

```
cat ${MLP_ENVIRONMENT_FILE}
source ${MLP_ENVIRONMENT_FILE}
gcloud config set project $MLP_PROJECT_ID
```

## Build the multimodal embedding model container image

```
#<TODO> change it to main branch before merge
git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git
cd rag-pipeline/embedding-models/multimodal
```

Update the location where you would like to store the container images in the ```cloud build yaml`` and kick off the build: 

Create the artifact repostiory to store the container images:

```
gcloud artifacts repositories create rag-artifacts --repository-format=docker --location=us --description="RAG artifacts repository"
```

```
cd src
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


  ```sh
  sed \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_MLP_DB_USER_KSA|${MLP_DB_USER_KSA}|" \
  manifests/embedding.yaml
  ```

## Test the embedding model
Validations: 
kubectl get po -n {MLP_KUBERNETES_NAMESPACE}


└─⪧ kubectl get svc
NAME              TYPE           CLUSTER-IP      EXTERNAL-IP    PORT(S)          AGE


## Run the curl test for embedding models 

Using the sample image ```./t-shirt.jpg``` to generate the image embedding
You can use the sample curl requests from ```curl_requests.txt```
