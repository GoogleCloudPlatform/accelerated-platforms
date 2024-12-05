# Retrieval Augment Generation

<TODO> Explain the RAG use case with architecture and flow

<TODO> Explain the use case here before submitting to main
Use case helps the the retailer suggest semantically similiar items from the product catalog if the product item user requested is out of stock or unavailable.

## Dataset

[This](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products) is a pre-crawled public dataset, taken as a subset of a bigger dataset (more than 5.8 million products) that was created by extracting data from [Flipkart](https://www.flipkart.com/), a leading Indian eCommerce store.

The dataset has product information such as id, name, brand, description, image urls, product specifications.

## Architecture

![RAG Architecture](./docs/arch-rag-components.png)

## Set up the environment

Here is what we need:

- Create the vector store database[`product catalog`] in alloyDB to store Product Catalog Information in a table[`clothes`].
- Host a [blip2 multimodal embeddings model](https://github.com/salesforce/LAVIS/blob/main/examples/blip_feature_extraction.ipynb) to generate the embeddings(text, image and multimodal)
- Using an ETL pipeline generate embeddings[text, image and multimodal] using the multimodal model and store them to the alloyDB vector store in a separate table.
- Host the instruction tuned [gemma-2b-it model](https://huggingface.co/google/gemma-2b-it) to generate prompt responses for the retail customers.
- Deploy the backend FAST API to interface with multimodal embeddings model, instruction tuned model and alloyDB vectore store to process user prompts and generate product recommendations based on user queries.
- Deploy the Frontend UI built-in [gradio](https://gradio.app/) to start the chatbot to receive end customers prompts which interacts with backend service to fulfill customer queries regarding the product catalog.

## Prerequisites

- Use the existing  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

## Preparation

#### Set variable for the ML playground environment

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/rag-pipeline
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

##<TODO> Remove this before merge to main

If you are developing on int-rag branch you need to terraform apply ML-platform again to create Networking objects for frontend so gateway can reach the frontend service.

# Deploy RAG Application Components

Steps:

## Deploy the Multimodal Model on the playground cluster
Deploy multimodal model on ML playground, follow the [README](/use-cases/rag-pipeline/embedding-models/multimodal-embedding/README.md)

## Deploy instruction tuned model on the playground cluster
Deploy instruction tuned model on ML playground, follow the [README](/use-cases/rag-pipeline/instruction-tuned-model/README.md)

## Create database `product_catalog` in alloyDB to import Product Catalog
Deploy database setup kubernetes job on the ML playground cluster, follow the [README](/use-cases/rag-pipeline/backend-application/README.md)

## Deploy the backend on the playground cluster

Deploy backend application on the ML playground cluster, follow the [README](/use-cases/rag-pipeline/backend/README.md)

## Deploy the frontend on the playground cluster

Deploy frontend application on the MLP playground cluster, follow the [README](/use-cases/rag-pipeline/frontend/README.md)