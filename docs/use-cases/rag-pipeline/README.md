## Introduction

This workflow outlines the technical architecture and processes behind a Virtual
Retail Assistant designed to provide intelligent and context-aware product
recommendations to online shoppers. It uses a technique called Retrieval
Augmented Generation (RAG) which leverages a combination of pre-trained large
language model, semantic search to retrieve relevant information from the
product catalog and provide answers based on the relevant information.

## Use Case in Business Context

In a retail context, RAG becomes crucial in scenarios where:

1. A significant influx of new products into the catalog renders the existing
   fine-tuned model outdated, and immediate retraining is infeasible due to
   time/resource constraints.
2. The fine-tuned Large Language Model (LLM) generates outputs (product
   recommendations) that are outside the scope of the retailer's actual product
   catalog, indicating model hallucination.
3. The LLM recommends products with low or depleted inventory, leading to
   potential customer dissatisfaction.

In these instances, RAG can improve the accuracy and relevance of LLM outputs by
grounding them in real-time or up-to-date external knowledge sources.

## RAG Architecture

The RAG pipeline orchestrates a combination of services which processes raw
data, generates the embeddings (text & images) and indexes into a vector
database. A backed service is made available to aggregate data from an
instruction-tuned model and the vector embeddings to return an enriched response
to the frontend.

![RAG Architecture][images/arch-rag-architecture-flow.png]

## Product Catalog Preparation

For this example, we used a
[pre-crawled dataset](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products)
consisting of 20,000 retail products. This product catalog serves as the central
repository of all available products, their attributes, and metadata. We
narrowed it down to clothing products, \~4500 products, that included both a
description and an image.

For further information about data preparation and cleaning, please check here:
[RAG: Data preprocessing](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/data-preprocessing/README.md)

## Product Catalog Onboarding

### Embeddings for Product search

In RAG for product search, embeddings play a crucial role. Embeddings are
vectors, a numerical representation of product descriptions and images,
capturing the semantic meaning and visual features, respectively. These
embeddings allow the system to perform semantic search, finding products that
are similar in meaning or appearance, even if they don't share exact keywords.

**Product Description Embeddings:**

- Textual descriptions of products are converted into embeddings.
- These embeddings capture the semantic meaning and context of the descriptions.
- When a user queries with a description, the system generates an embedding of
  the query and compares it to the product description embeddings.
- Products with the most similar embeddings are considered the most relevant.

**Product Image Embeddings:**

- Images of products are also converted into embeddings.
- These embeddings capture the visual features and characteristics of the
  images.
- When a user provides an image or a query related to visual features, the
  system generates an embedding of the image/query and compares it to the
  product image embeddings.
- Products with visually similar embeddings are considered the most relevant.

**Multimodal Embeddings:**

- Ideally, both text and image embeddings are used together to provide a more
  comprehensive understanding of the product.
- Multimodal embeddings combine information from both text and image, creating a
  unified representation.
- This allows for searches that consider both semantic meaning and visual
  appearance.

**Multimodal Embedding Models**

We are using the OSS model
[BLIP2](https://github.com/salesforce/LAVIS/tree/main/projects/blip2), a
multimodal embedding model that specializes in converting text or images into
numerical vectors. BLIP-2 can support at least 768 dimensions. To know more
about the embedding model see original
[blog](https://blog.salesforceairesearch.com/blip-2/) and
[source](https://github.com/salesforce/LAVIS/tree/main/examples).

Several other open-source multimodal embedding models are available:
[CLIP](https://openai.com/index/clip/),
[ALIGN](https://research.google/blog/align-scaling-up-visual-and-vision-language-representation-learning-with-noisy-text-supervision/),
[OpenCLIP](https://github.com/mlfoundations/open_clip). The models differ in the
number of dimensions in the embeddings they generate. Common embedding
dimensions found in CLIP & OpenCLIP models are 512, but models with other
dimensions such as 1024 are also available.

It's important to remember that the number of dimensions in an embedding vector
can impact the model's performance and efficiency. Higher dimensions can capture
more information but may also increase computational costs and the risk of
overfitting.

The instructions to deploy BLIP2 on GKE for this RAG architecture can be found
here:
[RAG: Multimodal embedding model](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/embedding-models/multimodal-embedding/README.md)

### Database and the extensions

We are using
[AlloyDB](https://cloud.google.com/alloydb/docs?_gl=1*1reks4c*_up*MQ..&gclid=CjwKCAiA5pq-BhBuEiwAvkzVZX-P4LPefA7NZt0f1FzUSLyHIW40qvQyH-facZ4C21D5N6UXFTbxTBoCZqIQAvD_BwE&gclsrc=aw.ds),
a fully-managed, PostgreSQL-compatible database as the central database to host
the product catalog.

AlloyDB supports two key extensions for vector search and indexing:

- **Vector Extension:** This extension enables the storage and querying of
  vector embeddings. These embeddings are numerical representations of data,
  such as text and images, used for semantic search.
- [**ScaNN**](https://github.com/google-research/google-research/blob/master/scann/docs/algorithms.md)
  **Index:** The Scann Index extension facilitates efficient and scalable
  approximate nearest neighbor search on these vector embeddings, improving the
  speed and accuracy of retrieving relevant information.

The product catalog onboarding process utilizes a Kubernetes job to load the
Flipkart product catalog into the AlloyDB database named "product_catalog." This
job also creates columns within a table named "clothes" in the "product_catalog"
database to store text, image, and multimodal embeddings, and populates these
columns with the relevant data.

Large retailers will likely have millions of products in their catalog, so
synchronous onboarding procedures (i.e. generation of embeddings) are
impractical due to the sheer magnitude of data. Therefore, asynchronous
onboarding methodologies are essential.

The implementation of the product catalog onboarding can be found here:
[RAG: Database setup and initialization](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/alloy-db-setup/README.md)

## Backend Services

### Retrieval

The shopper's product search query is submitted via the
[Gradio](https://www.gradio.app/) chat interface and converted into embeddings
using an embedding service. Cosine similarity is then calculated to perform a
semantic search within the product catalog using the embeddings.

#### Cosine Similarity

Cosine similarity is a measure of similarity between two items. It calculates
the cosine of the angle between the vector representations of the two items.
Cosine is a mathematical function that indicates the degree to which two vectors
point in the same direction. A cosine similarity of 1 means the vectors point in
the same direction, while a cosine similarity of \-1 indicates they point in
opposite directions. In simpler terms, a high cosine similarity implies high
similarity between the items, and a low cosine similarity suggests low
similarity.

###

### Re-Rank

To enhance context awareness and improve the accuracy of recommendations, we are
utilizing LLMs. The retrieved product information is combined with the original
user query and used as input into the
[Gemma 2 2B Instruction Tuned](https://huggingface.co/google/gemma-2-2b-it) (IT)
model, which then re-ranks potential recommendations. The instruction tuned
model outperformed the
[Gemma 2 2B pre-trained](https://huggingface.co/google/gemma-2-2b) model when
provided with
[instructions](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/backend/src/prompt_helper.py#L42)
to re-rank the products. The team attempted to leverage the fine-tuned Gemma 2
9B IT from
[another use case](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/main/docs/use-cases/model-fine-tuning-pipeline)
with the same product catalog, but the model did not produce the desired
results. This was primarily because the model was fine-tuned for a different
purpose.

The instructions to deploy the Gemma 2 2B IT model on GKE is available here:
[RAG: Instruction tuned model](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/instruction-tuned-model/README.md)

In this RAG architecture the Retrieval and Re-Ranking approach is implemented as
a backend service using [FastAPI](https://github.com/fastapi), to interface with
multimodal embeddings model, instruction tuned model and AlloyDB vector store to
generate product recommendations based on user queries. The implementation
details can be found at:
[RAG: Backend Deployment](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/backend/README.md)

## Frontend

### Gradio

To provide a simplistic user interface for demonstration purposes, the Gradio
framework was chosen to showcase the three methods (text, image, text+image) to
interact with the implementation.

The implementation details are available here:
[RAG: Frontend deployment](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/int-rag/use-cases/rag-pipeline/frontend/README.md)

## Search Query and Response from RAG application

Below are a few sample search queries and product recommendations from our RAG
application.

### Text only search

![TEXT ONLY SEARCH][images/TextOnly.png]

### Image only search

![IMAGE ONLY SEARCH][images/ImageOnly.png]

### Text \+ Image search

![TEXT AND IMAGE SEARCH][images/TextAndImage.png]

### Analysis of Results

The quality of the master product catalog, user's query and/or uploaded image
are the main factors that influence product recommendations. The product
descriptions and image quality in the catalog affect the quality of the
embeddings, which directly impacts the recommendation. For instance, the text
only example has a more relevant product recommendation than the text \+ image.
This can happen when the product catalog doesn't have enough good quality images
and/or the user uploaded image is not matching the search query or of bad
quality.

The Gradio interface was intended for demonstration purposes, but has room for
enhancements to improve user experiences. The output results would typically be
used as data for an application or service.

The implemented user interface assumes the input image is accessible to the
application in the Google Cloud Storage bucket. The response from the
instruction tuned model can be formatted in a backend service for a better user
experience. For easy comparison of recommended products, the product image from
the catalog can be displayed next to the product details in the response.
