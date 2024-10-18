# Retrieval Augment Generation

We have come to a point in the solution where we can use the fine-tuned model to run as a chatbot.
Now, we can extend that model to use for different retail use cases for the end customers.

## Retail chat bot use case

<TODO> Explain the use case here before submitting to main
Use case helps the the retailer suggest semantically similiar items from the product catalog if the product item user requested is out of stock or unavailable.

## Dataset

[This](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products) is a pre-crawled public dataset, taken as a subset of a bigger dataset (more than 5.8 million products) that was created by extracting data from [Flipkart](https://www.flipkart.com/), a leading Indian eCommerce store.

The dataset has product information such as id, name, brand, description, image urls, product specifications.

## Architecture

![RAG Architecture](arch-rag-components.png)

## Set up the environment

Here is what we need:

- Create the vector store database in alloyDB to store Product Catalog Information in a table.
- Add ml-integration suite to alloyDB. This helps alloyDB to call out the multimodal embeddings model to request text and image embeddings.
- Host a [blip2 multimodal embeddings model](https://github.com/salesforce/LAVIS/blob/main/examples/blip_feature_extraction.ipynb) to generate the embeddings(text and image)
- Using an ETL pipeline generate text embeddings using the multimodal model and store them to the alloyDB vector store in a separate table.
- Host the fine tuned model developed using model-finetuned pipeline.
- Host the pre-trained gemma2 model to generate prompt responses for the retail customers.
- Deploy the backend API in [llamaIndex](https://www.llamaindex.ai/) to interface with multimodal embeddings model and fine tuned model via alloyDB vectore store to process user prompts and generate appropriate responses.
- Deploy the Frontend UI built-in [gradio](https://gradio.app/) to start the chatbot to receive end customers prompts.

## Prerequisites

- Use the existing  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.

- Host the fine tuned model developed using [ model-finetuned pipeline](/platforms/use-cases/model-finetuned/README.md)

## Preparation

#### Set vars

```
<TODO> Clean up the vars before submitting to main
PROJECT_ID=your-project-id>
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
V_MODEL_BUCKET=<model-artifacts-bucket>
MLP_DATA_BUCKET=<dataset-bucket>
CLUSTER_NAME=<your-gke-cluster>
NAMESPACE=ml-team
KSA=<k8s-service-account>
HF_TOKEN=<your-Hugging-Face-account-token>
MODEL_ID=<your-model-id>
REGION=<your-region>
IMAGE_NAME=<your-image-name>
DISK_NAME=<your-disk-name>
ZONE=<your-disk-zone>
ACCELERATOR_TYPE=<accelerator_type> # nvidia-l4 | nvidia-tesla-a100
```

#### Configuration

- Download the flipkart processed CSV file to your local environment to function as your Product Catalog.

    ```
    <TODO: Make this location publicly accessible>
    gcloud storage cp gs://flipkart-dataset-rag/flipkart_processed_dataset/flipkart.csv .
    ```
  - Alternatively, you can use the processed dataset from your earlier [data preprocessing job](https://github.com/GoogleCloudPlatform/accelerated-platforms/tree/llamaindex-for-rag/use-cases/model-fine-tuning-pipeline/data-processing/ray)

## Create alloyDB and import Product Catalog

#### Create AlloyDB cluster using terraform modules

 Add your Google Project ID to the terraform config to create alloyDB cluster.

```shell
   git clone https://github.com/GoogleCloudPlatform/accelerated-platforms
   cd accelerated-platforms
   # TODO: remove the next line when merge to main
   git checkout llamaindex-for-rag
   cd use-cases/rag-on-gke/alloyDB
   terraform init
   terraform plan
   terraform apply
```

#### Import Product Catalog to the alloyDB instance

TODO: Convert this paragraph to a python code running in GKE

Database is ready to import the dataset.You can follow the [Import CSV to alloyDB ](https://cloud.google.com/alloydb/docs/connect-psql)
instructions.

The default terraform configuration creates VPC network name ```simple-adb```

- Create a Compute Engine VM that can connect to AlloyDB instances using private services access in this VPC.
- A VPC network in the Google Cloud project that you are using must already be configured for private services access to AlloyDB.

Get the IP address of the AlloyDB primary instance where your database is located  and ssh to machine.

```
gcloud compute ssh --project=PROJECT_ID --zone=ZONE VM_NAME
```

Copy the CSV file to the client host's local file system

```
gcloud storage cp gs://flipkart-dataset-rag/flipkart_processed_dataset/flipkart.csv .
```

Run the psql client tool and then, at the psql prompt, connect to the database.

```
psql -h <IP_ADDRESS> -U postgres -d postgres

```

Generate DDL for the table from the CSV file

```
echo "create table flipkart ("; head -n 1 flipkart.csv  |sed 's/,/ text\n,/g; $s/$/ text/';echo ");"
```

Alternatively you can use the following command to generate the DDL for the flipkart table.

```
create table flipkart (
uniq_id text
,product_name text
,description text
,brand text
,image text
,image_uri text
,attributes text
,c0_name text
,c1_name text
,c2_name text
,c3_name text
,c4_name text
,c5_name text
,c6_name text
,c7_name text
);
```

Import from CSV file

Delete any existing data in flipkart table

```
truncate table flipkart; 
```

Import flipkart Product Catalog from CSV file

```
\copy flipkart from 'flipkart.csv' WITH (FORMAT CSV, HEADER)
```
You should see following records being copied to the flipkarttable. 

```
postgres=> \copy flipkart from 'flipkart.csv' WITH (FORMAT CSV, HEADER)
COPY 19981
```

Create the embedding table to store text and image embeddings.
Later on, we would use the [google_ml_integration extension](https://cloud.google.com/alloydb/docs/ai#generate_embeddings_and_text_predictions) in alloyDB to access and utilize machine learning models directly within your AlloyDB environment.

```
truncate table flipkart_embeded; -- clear existing data from the table
insert into flipkart_embeded select uniq_id, google_ml.embedding_text(description) from flipkart ;
```
## Deploy the ML playground and finetuned gemma2 model

You can use a previously deployed version of the fine tuned model that you created using [model-finetuned pipeline](/platforms/use-cases/model-finetuned/README.md).

Alternatively, you can use below steps:

<TODO> Check with Aaron if the fine tuned image can be made publicly accessible.


## Deploy the Multimodal Model on the playground cluster


## Deploy pre-trained model gemma2 on the playground cluster


## Create ml-integration functions in AlloyDB

The [Google Ml Integration](https://cloud.google.com/alloydb/docs/ai/invoke-predictions)
makes the ML services callable from inside the database, so that ML inferencing 
services can be integrated with the SQL queries.

![RAG With_Database](arch-alloydb-rag.png)

Why we are using this approach to generate embeddings:

- It gives us an option to deploy any custom or OSS embedding model on GKE.
- Applications can interface with database to generate and store embeddings as a single source of truth. 
- It helps create custom functions in sql to generate, store and retrieve embeddings.

The ml-integration.sql script provided in `ml-integration/assets` file will create the following ml functions in the AlloyDB:

- `vllm_completion` This function allows you to call fine-tuned model for inference.

- `gemma2_completion` This function allows you to call a pretrained gemma2 2B   model for inference

- `google_ml.embedding_text` This function allows you to call the "blip2" model forcalls the "blip2" model for generating text embeddings only.

- `google_ml.multimodal_embedding` This function calls the "blip2" model for 
  generating multi-model embedding: text, image, and combined embedding

To create the ml-integration functions, set these environment variables and then
connect to the database using `psql` and run the script.

These environment variables help set the endpoint urls of the custom or OSS embedding models hosted in your enviorment.

```bash
export FINETUNE_MODEL_EP=<FINE-TUNED-MODEL-URL>
export PRETRAINED_MODEL_EP=<PRE-TRAINED-MODEL-URL>
export EMBEDDING_ENDPOINT=<EMBEDDING-MODEL-URL>
```

```
psql <your-connection-string> -f ml-integration/assets/ml-integration.sql
```

## Run ETL pipeline for embedding generation

- 