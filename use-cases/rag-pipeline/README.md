# Retrieval Augment Generation

This solution implements a Retrieval Augmented Generation (RAG) pipeline to enhance product recommendations in an e-commerce setting, specifically addressing the challenge of out-of-stock or unavailable items. When a customer searches for a product that's not currently available, the RAG pipeline uses advanced semantic search capabilities to identify and suggest similar items from the catalog. This approach not only improves the customer experience by providing relevant alternatives but also helps reduce lost sales and potentially increases average order value.

**Here's how it works:**

Understanding Customer Intent: The system analyzes the customer's search query (e.g., "blue cotton t-shirt") to understand the key attributes and features they are looking for.

**Semantic Search:** Instead of relying on exact keyword matches, the RAG pipeline leverages a vector database to perform semantic search. This means it can identify products that are semantically similar to the customer's query, even if they don't share the exact same words.

**Generating Recommendations:** Based on the semantic similarity scores, the system generates a list of relevant product recommendations. These might include:

**Cosine Simlarity:** Cosine similarity measures how similar two items are by looking at the angle between their vector representations.

Cosine: Cosine is a mathematical function that tells you how much two vectors point in the same direction. If they point in the same direction, the cosine similarity is 1. If they point in opposite directions, it's -1.
In simple terms:

High cosine similarity: The items are very similar.

Low cosine similarity: The items are not very similar.

This is really useful in things like:

Finding similar documents: Like finding articles that are on the same topic.

Recommending products: Suggesting items that you might like based on what you've liked before.

Image recognition: Identifying images that are similar to each other.

**_Exact Matches (if available):_** Similar blue cotton t-shirts in different sizes or styles.

**_Near Matches:_** Other blue t-shirts (different materials), cotton t-shirts in other colors, or even other blue cotton clothing items like shirts or sweaters.

**_Ranking and Presentation:_** The recommendations are ranked based on relevance and presented to the customer in a clear and appealing way, encouraging them to continue shopping.

## Dataset

[This](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products) is a pre-crawled public dataset, taken as a subset of a bigger dataset (more than 5.8 million products) that was created by extracting data from [Flipkart](https://www.flipkart.com/), a leading Indian eCommerce store.

The dataset has product information such as id, name, brand, description, image urls, product specifications.

# Data Preprocessing pipeline for RAG

<TODO> Data processing pipeline steps for RAG.

## Architecture

![RAG Architecture](./docs/arch-rag-architecture-flow.png)

This system provides relevant product suggestions to online shoppers by understanding their queries and searching a product catalog. It uses embeddings to represent user queries and products, leverages Scann for efficient similarity search, and employs an instruction-tuned LLM for refining results. The system retrieves relevant products from AlloyDB and presents them via a chat interface.

Let's break down the flow step-by-step:

1. **User Query:**

An online shopper initiates the process by entering a query through the Gradio Chat Interface. This query represents their need or request (e.g., "comfortable running shoes for women").

2. **Get Embeddings:**

The user's query is sent to the "Backend Application".
Within the Backend Application, the query is processed by an "Embedding Model Endpoint".

3. **Embedding Model Endpoint:**

This component hosts a blip2 multimodal embedding model that specializes in converting text(or images) into numerical vectors called "embeddings". These embeddings capture the semantic meaning of the query.
The Embedding Model Endpoint receives the query, performs the conversion, and returns the embedding vector.

4. **Get Embeddings (Continued):**

The Backend Application receives the embedding vector from the Embedding Model Endpoint.

5. **Scann Index:**

The backend application uses the received embedding vector to query a Scann Indexes built on embedding columns (text, image, or multimodal) within the AlloyDB clothes table. These embedding columns are populated by the Product Catalog Onboarding Job, representing product information as embedding vectors

Scann is a high-performance approximate nearest neighbor search library. It efficiently finds products with embedding vectors similar to the query's embedding vector.

6. **Fetch Similar Products:**

The backend system fetches the most similar products from the "AlloyDB" database, which stores the complete information in the "Product Catalog".
The system retrieves similar products from AlloyDB, including details like Name, Description, Category, Specifications, Product_ID, Brand, and image_uri. The retrieval is ordered by cosine similarity to the query embedding.

7. **Instruction Tuned Model Endpoint:**

These retrieved similar product information is then sent to an "Instruction Tuned Model Endpoint". This endpoint hosts a specific version of Gemini instruction tuned model(gemma-2b-it)[https://huggingface.co/google/gemma-2b-it] that's been trained with a focus on understanding and responding to instructions effectively. Instruction tuned model is provided with a specific instructions as a prompt to re-rank the search results.

8. **Re-Rank Search Results with LLM:**

The LLM re-ranks the search results based on relevance and prompt based instructions. This step ensures the most relevant products are presented to the user.

9. **Suggest Products:**

The Backend Application receives the re-ranked product list from the Instruction Tuned Model Endpoint.

This list is sent as Product Recommendations to the Gradio Chat Interface.

10. **Product Suggestions:**

The Gradio Chat Interface displays the product suggestions to the online shopper.

**Additional Components:**

The Product Catalog Onboarding Job handles the initial loading and ongoing updates of product information in AlloyDB, including building and maintaining the Scann Index to reflect catalog changes

### Setting up the RAG Pipeline deployment

This section outlines the steps to set up the Retrieval Augmented Generation (RAG) pipeline for product recommendations.

1. **Create the Vector Store:** Create the `product_catalog` database in [AlloyDB](https://cloud.google.com/alloydb/docs/introduction). This database will house the `clothes` table, which stores product catalog information.

2. **Deploy the Embedding Model:** Deploy the [Blip2 multimodal](https://github.com/salesforce/LAVIS/blob/main/examples/blip_feature_extraction.ipynb)embedding model. This model generates text, image, and multimodal embeddings for each product.

3. **Generate and Store Embeddings:** Use an ETL pipeline to generate embeddings (text, image, and multimodal) using the deployed Blip2 model. Store these embeddings in separate columns within the `clothes` table in AlloyDB.

4. **Deploy the Instruction-Tuned Model:** Deploy the [gemma-2b-it model](https://huggingface.co/google/gemma-2b-it). This model generates natural language responses and product recommendations based on user queries and retrieved product information.

5. **Deploy the Backend API:** Deploy the FastAPI backend. This API serves as the interface between the user interface, embedding model, instruction-tuned model, and the AlloyDB vector store. It processes user prompts and generates product recommendations.

6. **Deploy the Frontend UI:** Deploy the [gradio](https://gradio.app/) based frontend UI. This UI provides a chatbot interface for end-users to interact with the RAG pipeline and receive product recommendations.

## Prerequisites

- Use the existing [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

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

# Deploy RAG Application Components

This section outlines the steps to deploy the Retrieval Augmented Generation (RAG) pipeline to the playground cluster.The components should be deployed in the following order:

## Deploy the Multimodal Model on the playground cluster

Deploy multimodal model on ML playground, follow the [README](/use-cases/rag-pipeline/embedding-models/multimodal-embedding/README.md)

## Deploy instruction tuned model on the playground cluster

Deploy instruction tuned model on ML playground, follow the [README](/use-cases/rag-pipeline/instruction-tuned-model/README.md)

## Create database `product_catalog` in alloyDB to import Product Catalog

Deploy database setup kubernetes job on the ML playground cluster, follow the [README](/use-cases/rag-pipeline/alloy-db-setup/README.md)

## Deploy the backend on the playground cluster

Deploy backend application on the ML playground cluster, follow the [README](/use-cases/rag-pipeline/backend/README.md)

## Deploy the frontend on the playground cluster

Deploy frontend application on the MLP playground cluster, follow the [README](/use-cases/rag-pipeline/frontend/README.md)
