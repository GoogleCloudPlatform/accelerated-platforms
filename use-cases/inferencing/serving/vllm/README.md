# Distributed Inference and Serving with vLLM

In these guides, you will serve a fine-tuned Gemma large language model (LLM) using graphical processing units (GPUs) on Google Kubernetes Engine (GKE) with the vLLM serving framework.
You can choose to swap the Gemma model with any other model for inference and serving on GKE.

When to use distributed inference and the common practice and strategies available:

- **Single GPU** (non distributed inference): If the model fits in a single GPU, you probably don't need to use distributed inference. Just use the single GPU to run the inference.
- **Single-Node, Multi-GPU** (tensor parallel inference): If the model is too large to fit in a single GPU, but it can fit in a single node with multiple GPUs, you can use tensor parallelism.
- **Multi-Node, Multi-GPU** (tensor parallel plus pipeline parallel inference): If your model is too large to fit in a single node, you can use tensor parallel together with pipeline parallelism.
  It involves distributing the model across multiple GPUs and multiple machines (nodes), allowing for parallel processing and faster inference times.

These guides use `Single-Node, Multi-GPU` method to serve the model.

## Choosing storage to load model weights

In order to serve a model on GKE, the model weights need to be available. There are different ways to load the model weights in the container:

- GCS bucket: The model is loaded from a GCS bucket.
- Hyperdisk ML: The model is loaded from a high throughput Hyperdisk ML volume.
- Persistent Disk: The model is loaded from a persistent disk volume.

These methods can also make use of Image streaming to allow your workloads to startup without waiting for the entire image to download, which can lead to decreased workload startup latency.
One step further would be to use a Secondary Boot Disk to preloaded container images and model data on the GKE node, further decreasing workload startup latency and model loading times.

## Serving the model

These guides walk through how to serve a model with vLLM using the specific storage option:

- [**Google Cloud Storage (GCS)**](/use-cases/inferencing/serving/vllm/gcsfuse/README.md): Serve a model with vLLM using GCSfuse.
- [**Hyperdisk ML**](/use-cases/inferencing/serving/vllm/hyperdisk-ml/README.md): Serve a model with vLLM using Hyperdisk ML.
- [**Persistent Disk**](/use-cases/inferencing/serving/vllm/persistent-disk/README.md): Serve a model with vLLM using persistent disk.

## Operationalize the model

Once the model is being served, these guides walk through how to further operationalize the model:

- [**vLLM Metrics**](/use-cases/inferencing/serving/vllm/metrics/README.md): vLLM exposes a number of metrics that can be used to monitor the health of the system.
- [**vLLM autoscaling with horizontal pod autoscaling (HPA)**](/use-cases/inferencing/serving/vllm/autoscaling/README.md): You can configure Horizontal Pod Autoscaler to scale your inference deployment based on relevant metrics.
- [**Benchmarking with Locust**](/use-cases/inferencing/benchmark/README.md): The model is ready to run a benchmark for inference.

## Utilizing the model

This guides walk through how to utilize the model:

- [**Batch inference on GKE**](/use-cases/inferencing/batch-inference/README.md): Now that the model is deployed on GKE, you can run batch inference jobs against the model to generate predictions.
