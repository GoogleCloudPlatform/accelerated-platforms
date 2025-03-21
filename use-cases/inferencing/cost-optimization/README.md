# Inference Cost Optimization

Running inference for large language models can be expensive. Often, this cost
goes even higher based on your requirements. For example, if your requirement is
to reduce the latency in starting up inference, it may need advanced
accelerators on high end virtual machines with expansive storage options. Often,
there is confusion in choosing the right accelerator , virtual machine and
storage options when if comes to running the large language models. The goal of
this guide is to provide the cost efficient and high performant ways to run
inference for llama models.

## Choosing accelerator, machine and storage

Google Cloud provides different types of accelerators, GPUs(L4, A100, H100) and
TPUs and storage options(GCS, Parallelstore, Hyperdisk ML, Persistent Disk) that
covers end to end requirements for running large language models in cost
efficient fashion.

Typically, the type and the number of accelerators that will be used in your
inference is decided based on the size of your model. For example, if you want
to run llama 70B model which has weights of about 132GB, you will need at least
8 nvidia-l4 or 4 nvidia-tesla-a100 or 2 nvidia-a100-80gb to run inference.
However, you can use additional accelerators to achieve faster model load time
and serving e.g use 8 nvidia-tesla-a100 instead of 4.

Different VM types provide different number of GPUs, GPU memory, vCPU, VM memory
and network bandwidth. You can choose the VM once you have decided what and how
many accelerators you want to use to run inference. For example, if you decide
to use 8 nvidia-l4 GPUs to serve llama 70B model, you can use g2-standard-96
which is the only machine type that provides 8 nvidia-l4 in G2 machine series.
You can configuration of different machine types at [Google Cloud GPU Machine
types documentation][gpus]

The storage option is a key factor in determining the cost and performance of
your inference along with the accelerator. This is because the model is loaded
from storage into GPU memory to run inference. The more throughput a storage
provides, the faster will be the model load time and shorter will be the
inference start up time and Time To First Token. On Google Cloud, the storage
can be zonal, regional or multi-regional. This means if you use a zonal storage
and decide to run inference workload in 3 different zones, you will need three
instance of the storage in each of those zones. Therefore, it becomes critical
to choose the storage option wisely to optimize the cost.

## Storage benchmarking

In the [storage-benchmarking][storage-benchmarking] guide, we demonstrate how
you can fine tune the different storage options to achieve the best performance
with an estimated cost. This will help you asses you if a given storage type is
a fit for you or not.

---

[gpus]: https://cloud.google.com/compute/docs/gpus
[storage-benchmarking]: storage-benchmarking/README.md
