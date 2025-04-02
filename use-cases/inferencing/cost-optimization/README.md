# Inference Cost Optimization

Running inference for large language models (LLMs) can be expensive and costs
can increase due to specific requirements. For example, reducing inference
startup latency may require advanced accelerators on high-end virtual machines
with extensive storage options. Choosing the right combination of accelerator,
virtual machine, and storage options for running large language models can be
complicated. The goal of this guide is to provide cost-efficient and
high-performance methods for running Llama model inference.

## Choosing accelerator, machine and storage

Google Cloud offers a variety of accelerators, including
[Graphics Processing Units (GPUs)](https://cloud.google.com/gpu) and
[Tensor Processing Units (TPUs)](https://cloud.google.com/tpu) model, as well as
[storage options](https://cloud.google.com/products/storage) such as Google
Cloud Storage (GCS), Parallelstore, Hyperdisk ML, and Persistent Disk. These
comprehensive options enable cost-effective operation of large language models
for various requirements.

The number and type of accelerators needed for inference is typically determined
by the size of your model. For instance, running a
[Llama](https://www.llama.com/) 70B model, which has weights of roughly 132GB,
requires a minimum of eight NVIDIA L4 GPUs, four NVIDIA A100 40GB GPUs, or two
NVIDIA A100 80GB GPUs. However, using additional accelerators, such as using
eight NVIDIA A100 40GB instead of four, can result in faster model loading times
and improved inference.

The number of GPUs, amount of GPU memory, vCPU, memory, and network bandwidth
are all factors that vary across different virtual machine types. After deciding
on the type and quantity of accelerators required for inference, you can select
the appropriate VM family and type. For example, if you need eight NVIDIA L4
GPUs to serve the Llama 70B model, in the G2 instances the `g2-standard-96`
machine type is the only one that can accommodate this requirement. For an
overview of the different GPU VMs that are available on Compute Engine, see the
[GPU Machine types](https://cloud.google.com/compute/docs/gpus) documentation.

The storage and accelerator that you choose are key factors that affect the cost
and performance of your inference. To run inference, the model must be loaded
from storage into GPU memory. Thus, storage throughput affects model load time,
inference start-up time, and time to first token (TTFT). Google Cloud storage
can be zonal, regional, or multi-regional. If you use zonal storage and run
inference workloads in three different zones, you will need three instances of
storage, one in each of the zones. Choosing the right storage option is critical
for cost optimization.

## Storage optimization

In the
[GCS storage optimization](/use-cases/inferencing/cost-optimization/gcsfuse/README.md)
guide, we demonstrate how you can tune GCS to achieve the best cost performance.
