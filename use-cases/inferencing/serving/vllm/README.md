# Distributed Inferencing on vLLM

In this guide, you will serve a fine-tuned Gemma large language model (LLM) using graphical processing units (GPUs) on Google Kubernetes Engine (GKE) with the vLLM serving framework. You can choose to swap the Gemma model with any other fine-tuned or instruction based model for inference on GKE.

There are three common strategies for inference on vLLM:

- Single GPU (no distributed inference) - If your model fits in a single GPU, you probably don't need to use distributed inference. Just use the single GPU to run the inference.
  
- Single-Node Multi-GPU (tensor parallel inference) - If your model is too large to fit in a single GPU, but it can fit in a single node with multiple GPUs, you can use tensor parallelism. The tensor parallel size is the number of GPUs you want to use. For example, if you need 4 GPUs, you can set the tensor parallel size to 4.

- Multi-Node Multi-GPU - It is a technique used to run very large language models (LLMs) that are too big to fit on a single GPU, or even a single machine with multiple GPUs. It involves distributing the model across multiple GPUs and multiple machines (nodes), allowing for parallel processing and faster inference times.


This guide uses `Single-Node Multi-GPU` method to serve the model that was fine-tuned in the previous guides.


# Choosing storage to load model weights

In order to serve a model on GKE, the model weights need to be download in the GKE container.
There are different ways to load the model weights in the container:

* Downlaod the model from Persisdent SSD disk - the model is loaded from a persistent disk.
* Download the model from GCS bucket - the model is loaded from a GCS bucket.
* Download the model from Hyperdisk ML  - the model is loaded from high throughput HyperdiskML.
* Use secondary boot disk - A disk can be preloaded with the model and be used as a secondary disk on the nodepools running the pods serving the model.

# Serving the model

In this guide, you will learn how to serve a model with vllm using the following storage options:

- **Persistent Disk** : Follow the [guide](./persistent-disk/README.md) to serve a model with vllm using persistent disk.

- **GCS** : Follow the [guide](./gcsfuse/README.md) to serve a model with vllm using GCSfuse download.

- **HyperdiskML** : Follow the [guide](./hyperdiskML/README.md) to serve a model with vllm using HyperdiskML.


