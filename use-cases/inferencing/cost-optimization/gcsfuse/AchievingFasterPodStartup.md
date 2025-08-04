# LLM Inference Optimization on GKE: Achieving faster Pod Startup with Google Cloud Storage

A key challenge in serving large language models (LLMs) is their sheer size.
With model weights often reaching hundreds of gigabytes, loading them into GPU
or TPU memory can be a major performance bottleneck. When running on Google
Kubernetes Engine (GKE), this delay directly impacts your ability to autoscale
workloads cost-effectively in response to demand.

Optimizing your storage strategy is critical for achieving the high throughput
needed for fast model loading. In this post, we’ll focus on a crucial metric:
Pod startup time. We will explore how combining Google Cloud Storage with
Anywhere Cache can significantly reduce the time from “Pod Scheduled” to “Pod
Ready,” enabling faster and more efficient LLM serving on GKE.

### The importance of fast Pod startup times

Pod startup time directly impacts several key areas of LLM online inference, for
example:

- **Scalability and cost**: Fast startup enables effective autoscaling (e.g.,
  Horizontal Pod Autoscaler), optimizing utilization of premium resources such
  as GPUs, TPUs, and local SSDs. Slow startup, in contrast, makes autoscaling
  infeasible and requires workloads to be configured to the peak, wasting
  expensive resources.
- **User experience:** for applications that require quick responses, like
  agents and chatbots, slow startup can translate to a noticeable delay or
  instability in the system for the end-user.

Slow Pod startup times can also impact development and offline (a.k.a. batch)
inference:

- **For development and experimentation:** Faster startup times allow for
  quicker testing and deployment of new model versions and configurations.
- **Offline inference:** Slow Pod startup doesn’t directly impact users'
  experience. However, it can increase overall workload costs, as it takes
  longer for expensive accelerators like GPUs and TPUs to start being used.

### **Loading LLMs weights into accelerators' memory**

Loading LLMs during Pod startup directly from sources like
[huggingface.co](http://huggingface.co) is slow and unreliable in production
environments, where network unpredictability and inconsistency can cause delays
and errors, making it unsuitable for applications that need fast and reliable
startup times.

Cloud Storage buckets, on the other hand, are a low-cost, high-throughput, and
reliable way to store your LLM models in Google Cloud. However, if not
configured properly, directly loading LLM weights from Cloud Storage into
accelerators' memory can be slow. For larger models in particular, the
traditional approach, in which open-source inference servers (e.g.
[vLLM](https://docs.vllm.ai/en/latest/),
[TGI](https://huggingface.co/docs/text-generation-inference/en/index), etc.)
read model files sequentially over the network through a mounted Cloud Storage
bucket as file systems (see the
[Cloud Storage Fuse CSI driver](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/cloud-storage-fuse-csi-driver)),
can be a bottleneck.

\*Note: Downloading models from Hugging Face into GCS buckets can be further
enhanced by optimizing data **hydration using
[this tutorial](https://gke-ai-labs.dev/docs/tutorials/storage/hf-gcs-transfer/).\***

We’re still in the early days of inference loading models over the network. To
help you achieve the most from your resources, we put together a guide on how to
use Cloud Storage Fuse to speed up reading LLMs from a Cloud Storage bucket
during Pod startup.

In the graph below, you can see how many seconds it takes for the
[Cloud Storage FUSE basic configuration](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/use-cases/inferencing/cost-optimization/gcsfuse/manifests/model-deployment-a100-dws.yaml)
(without any tuning) vs. the
[recommended configuration](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/use-cases/inferencing/cost-optimization/gcsfuse/manifests/model-deployment-tuned-a100-dws.yaml)
(with tuning). By implementing some key optimizations, the _GCSFuse \-
Recommended setup_ dramatically improved Pod startup time, showing **more than
7x less latency compared to a basic setup**. We achieved this by deploying the
[Llama-3.3-70B-Instruct](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
model served by
[vLLM](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html?ref=blog.mozilla.ai)
on a
[A2-highgpu-8g](https://cloud.google.com/compute/docs/accelerator-optimized-machines#a2-standard-vms)
node. And while different machine types have different performance (e.g., an
[A3-highgpu](https://cloud.google.com/compute/docs/accelerator-optimized-machines#a3-standard-vms)
machine family starts up inference Pods \~41% faster than the
[A2-highgpu](https://cloud.google.com/compute/docs/accelerator-optimized-machines#a2-standard-vms)),
we’ve seen equivalent improvements between the basic and recommended
configurations with different model sizes and machine types.

![][image1]

In the following section we discuss the optimizations we used in more detail.

### Cloud Storage Fuse recommended setup

This section assumes that once you store a version of your model in Cloud
Storage, its files never change — if your model requires an update, you will
store it in a different Cloud Storage folder or bucket.

Our recommended setup was created in such a way that you can use it **as-is** in
most LLM inference scenarios. Whether your use case is batch or serving, your
models are small or large, or you’re using entry-level or premium accelerators,
we recommend that you use the following optimizations:

1. **Create Cloud Storage buckets in the workload's region and enable
   hierarchical namespace:**

To improve read performance of your LLM, we recommend that you enable
[hierarchical namespace](https://cloud.google.com/storage/docs/hns-overview#key_features)
in your Cloud Storage bucket. Below is an example of how to create a
hierarchical bucket in region _us-central1_ using the _gcloud_ command.

```shell
gcloud storage buckets create gs://BUCKET_NAME \
  --location=us-central1 \
  --uniform-bucket-level-access \
  --enable-hierarchical-namespace
```

**Note:** If you use multi-regional buckets, you can improve your costs and
performance by enabling Anywhere Cache, as discussed in the next section.

2. **Enable parallel downloads and caching in Cloud Storage FUSE:**

The yaml snippets highlighted below show how to configure Cloud Storage FUSE to
download multiple files concurrently and to cache the downloaded data
indefinitely. For more details, see
[Optimize Cloud Storage FUSE CSI driver for GKE performance](https://cloud.google.com/kubernetes-engine/docs/how-to/cloud-storage-fuse-csi-driver-perf#parallel-download)
and the full content of the below snippet below in
[_model-deployment-a100-tuned.yaml_](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/use-cases/inferencing/cost-optimization/gcsfuse/manifests/model-deployment-tuned-a100-dws.yaml)
file.

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-openai-gcs-tuned-llama33-70b-a100
spec:
  ...
  template:
      annotations:
        gke-gcsfuse/volumes: "true"
        gke-gcsfuse/cpu-limit: "0"
        gke-gcsfuse/memory-limit: "0"
        gke-gcsfuse/ephemeral-storage-limit: "0"
      ...
      - name: inference-server
        ...
        volumeMounts:
        - name: gcsfuse
          mountPath: /gcs/${MODEL_NAME}/${MODEL_VERSION}/
          readOnly: true
      volumes:
      - name: gcsfuse
        csi:
          driver: gcsfuse.csi.storage.gke.io
          volumeAttributes:
            bucketName: ${GCS_BUCKET}
            mountOptions: "metadata-cache:ttl-secs:-1,metadata-cache:stat-cache-max-size-mb:-1,metadata-cache:type-cache-max-size-mb:-1,metadata-cache:negative-ttl-secs:0,file-cache:max-size-mb:-1,file-cache:cache-file-for-range-read:true,file-cache:enable-parallel-downloads:true,implicit-dirs,only-dir:${MODEL_NAME}/${MODEL_VERSION}/"
            skipCSIBucketAccessCheck: "true"
       ...
```

**Note**: Smart _mountOptions_ defaults are set from GKE version v1.33. So, if
you are deploying your workload in G2, A2, A3, A4, A4X, ct5l, ct5lp, ct5p, and
ct6e machine families, all you need to do is to configure _only-dir_ parameter

3. **Prefer RAM disk for Cloud Storage FUSE caching:**

[GPU](https://cloud.google.com/compute/docs/accelerator-optimized-machines) and
[TPU](https://cloud.google.com/tpu) machine families have a sizable amount of
CPU memory that is commonly not fully utilized by inference servers, resulting
in wasted resources. If that’s the case for you, you can leverage any unused RAM
as a high-speed cache for GCSFuse. Below you can see how to configure GCSFuse to
use RAM disk .

**Note:** The Cloud Storage FUSE cache is persistent, meaning the RAM used to
load the model is not recycled. So, if you can't afford to use RAM disk, we
highly recommend you use Local SSDs. There is no extra setup needed to configure
Cloud Storage FUSE to use Local SSDs on
[A2](https://cloud.google.com/compute/docs/accelerator-optimized-machines#a2-vms),
[A3](https://cloud.google.com/compute/docs/accelerator-optimized-machines#a3-vms),
and
[A4](https://cloud.google.com/compute/docs/accelerator-optimized-machines#a4-vms)
GPU machine families, meaning you can skip the yaml snippet below. For the
[G2](https://cloud.google.com/compute/docs/accelerator-optimized-machines#g2-vms)
machine family,
[you must attach Local SSDs during nodepool creation](https://cloud.google.com/kubernetes-engine/docs/how-to/persistent-volumes/local-ssd#node-pool).
For TPU machine families, there is no Local SSD option, so you must use the RAM
disk approach below.

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-openai-gcs-tuned-llama33-70b-a100
spec:
  replicas: 1
    ...
      volumes:
      - name: gke-gcsfuse-cache
        emptyDir:
          medium: Memory
      - name: gke-gcsfuse-tmp
        emptyDir:
          medium: Memory
      - name: gke-gcsfuse-buffer
        emptyDir:
          medium: Memory
```

4. **Prefetch the LLM model:**

To accelerate model loading further, instead of letting the inference server ask
Cloud Storage FUSE to download the model's files sequentially, you can prefetch
the model upfront by parallelizing files downloads in a separate container
(_fetch-safetensors_ in below snippet of yaml). While the inference server is
preparing to read the model from GCSFuse, the prefetching container downloads
the model from Cloud Storage directly into Cloud Storage FUSE Cache, ideally
using RAM disk as per the previous optimization. This achieves better
performance results for medium and large models.

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-openai-gcs-tuned-llama33-70b-a100
spec:
  replicas: 1
    ...
    spec:
      containers:
      - name: fetch-safetensors
        image: busybox
        command: ["/bin/sh", "-c"]
        args:
          - |
            echo "########### $(date) - Starting parallel-fetch-safetensors"
            find /gcs/${MODEL_NAME}/${MODEL_VERSION}/*safetensors -type f | xargs -I {} -P 15 sh -c 'echo "########### $(date) - Fetching: {}"; dd if={} of=/dev/null'
            echo "########### $(date) - Finished parallel-fetch-safetensors"
            sleep infinity
        volumeMounts:
        - name: gcsfuse
          mountPath: /gcs/${MODEL_NAME}/${MODEL_VERSION}/
          readOnly: true
```

**Note:** Cloud Storage FUSE plays an important role in this entire setup by
ensuring that if there's an initial slowness during the model prefetch, the
inference server doesn’t fail. In the absence of model files in the cache, they
will be read through the network.

### Anywhere Cache

Loading a model is a highly cacheable workload with high peak throughput
demands, and
[Anywhere Cache](https://cloud.google.com/storage/docs/anywhere-cache) is a
perfect fit for it\! Anywhere Cache provisions a zonal cache, colocated with
compute, that offers significant advantages — without the need to change
anything in your application:

- **Location flexibility:** When combined with a multi-region bucket, Anywhere
  Cache provides multi-region redundant storage that is co-located zonally for
  low latency and high throughput. Store once, and read anywhere within the
  region without complex data movement, while benefiting from performance
  acceleration.
- **Cost optimization**: Anywhere Cache has lower operation
  [charges](https://cloud.google.com/storage/pricing#anywhere-cache) on cached
  data, and it avoids multi-region data transfer fees. The
  [Anywhere Cache recommender](https://cloud.google.com/storage/docs/anywhere-cache-recommender)
  shows you how to create caches in bucket-zone pairs along with the associated
  potential cost savings.
- **Improved performance:** Caching frequently accessed model data closer to the
  GKE Pods reduces latency, leading to faster pod startup times.
- **High throughput:** Anywhere Cache is designed to support very high
  throughput
  ([up to 2.5TB/s](https://cloud.google.com/storage/quotas#anywhere-cache)),
  which is crucial for spinning up dozens of large LLMs pods at the same time.
- **Consistent performance:** Once data is cached, access times on cache hit
  become very consistent, eliminating the variability associated with network
  latency when accessing remote storage.

Below is an example of a gcloud command to create Anywhere Caches in zones zones
_us-central1-a_, _us-central1-b_, _us-central1-c_ for a given bucket. Note that
such cache instances use the maximum allowed time to live (ttl), which is 7
days.

```shell
BUCKET_NAME=<add-your-bucket-name-here>

# Create Anywhere Caches in zones us-central1-a, us-central1-b, us-central1-c
output=$(gcloud storage buckets anywhere-caches create gs://$BUCKET_NAME us-central1-a us-central1-b us-central1-c --ttl 604800s 2>&1)
op_ids=$(echo "$output" | grep -o "projects/_/buckets/$BUCKET_NAME/operations/[A-Za-z0-9_-]\+")

# Wait for the Anywhere Caches to be provisioned
for op_id in $op_ids; do
  echo "Waiting for operation: $op_id"
  while true; do
    if gcloud storage operations describe "$op_id" | grep -q "done: true"; then
      echo "Operation $op_id is complete."
      break
    else
      echo "Operation $op_id still in progress... checking again in 30 seconds."
      sleep 30
    fi
  done
done
echo "All operations are complete."
```

**Note:** The script will finish when Anywhere Cache is provided. It can take
several minutes.

### **Next steps**

Loading LLMs into your accelerators at Pod startup is an important way to ensure
the performance of your GKE-based inference workloads, and using Cloud Storage
and Cloud Storage FUSE is a way to do so reliably and cost-effectively. To see
for yourself, run these benchmarks by following this tutorial
[here](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/main/use-cases/inferencing/cost-optimization/gcsfuse/README.md).

[image1]:
  data:image/png;base64,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
