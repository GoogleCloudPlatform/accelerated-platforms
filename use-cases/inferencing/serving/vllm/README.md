# Distributed Inferencing on vLLM

In this guide, you will serve a fine-tuned Gemma large language model (LLM) using graphical processing units (GPUs) on Google Kubernetes Engine (GKE) with the vLLM serving framework. You can choose to swap the Gemma model with any other fine-tuned or instruction based model for inference on GKE.

There are three common strategies for inference on vLLM:

- Single GPU (no distributed inference) - If your model fits in a single GPU, you probably don't need to use distributed inference. Just use the single GPU to run the inference.
- Single-Node Multi-GPU (tensor parallel inference) - If your model is too large to fit in a single GPU, but it can fit in a single node with multiple GPUs, you can use tensor parallelism. The tensor parallel size is the number of GPUs you want to use. For example, if you need 4 GPUs, you can set the tensor parallel size to 4.

- Multi-Node Multi-GPU - It is a technique used to run very large language models (LLMs) that are too big to fit on a single GPU, or even a single machine with multiple GPUs. It involves distributing the model across multiple GPUs and multiple machines (nodes), allowing for parallel processing and faster inference times.

This guide uses `Single-Node Multi-GPU` method to serve the model that was fine-tuned in the previous guides.

## Choosing storage to load model weights

In order to serve a model on GKE, the model weights need to be download in the GKE container.
There are different ways to load the model weights in the container:

- Download the model from Persisdent SSD disk - the model is loaded from a persistent disk.
- Download the model from GCS bucket - the model is loaded from a GCS bucket.
- Download the model from Hyperdisk ML - the model is loaded from high throughput Hyperdisk ML.
- Use secondary boot disk - you can preloaded container image or data on a secondary boot disks of a GKE node that can help you start the inference faster. You can use Image streaming to allow your workloads to initialize without waiting for the entire image to download, which leads to significant improvements in initialization times.

## Serving the model

In this guide, you will learn how to serve a model with vllm using the following storage options:

- **Persistent Disk** : Follow the [guide](/use-cases/inferencing/serving/vllm/persistent-disk/README.md) to serve a model with vllm using persistent disk.
- **GCS** : Follow the [guide](/use-cases/inferencing/serving/vllm/gcsfuse/README.md) to serve a model with vllm using GCSfuse download.
- **Hyperdisk ML** : Follow the [guide](/use-cases/inferencing/serving/vllm/hyperdisk-ml/README.md) to serve a model with vllm using Hyperdisk ML.

## Operationalize the model

- [**vLLM Metrics**](/use-cases/inferencing/serving/vllm/metrics/README.md): vLLM exposes a number of metrics that can be used to monitor the health of the system.
- [**vLLM autoscaling with horizontal pod autoscaling (HPA)**](/use-cases/inferencing/serving/vllm/autoscaling/README.md): You can configure Horizontal Pod Autoscaler to scale your inference deployment based on relevant metrics.
- [**Benchmarking with Locust**](/use-cases/inferencing/benchmark/README.md): The model is ready to run a benchmark for inference.

## Utilizing the model

- [**Batch inference on GKE**](<(/use-cases/inferencing/batch-inference/README.md)>): Now that the model is deployed on GKE, you can run batch inference jobs against the model to generate predictions.
