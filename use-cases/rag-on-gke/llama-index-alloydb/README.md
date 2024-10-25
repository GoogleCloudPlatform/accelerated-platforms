# The RAG application

This application is using the LlamaIndex framework. 

## Extensions to LlamaIndex

In the file `query_alloydb.py` there are two extension classes defined. 

### The `AlloyDBNaiveRetriever` class

This class implements a `Retriever` that retrieves similar "facts" to the query string from alloydb using "cosine distance". 

You can specify the table(s), the column of embedding vectors and the column holding the "facts". You also need to specify the embedding function to use. This embedding function should be the same function used to create the embedding vector column from the "facts".

### The `AlloyDBNaieveLLM` class

This a trivial class that calls the in-database llm function to do inferencing on the prompt. 

## To use

### Prepare

- Apply all modules in `alloyDB`
- Create the `flipkart` table and the `flipkart_embedding` table

### Install

- run `make config` in this folder
  This will create a configmap holding the codes
- apply the `query-gradio.yaml`
