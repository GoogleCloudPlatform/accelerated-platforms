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

![GCSFuse Pod Startup Time](/docs/use-cases/inferencing/cost-optimization/gcsfuse/GCSFusePodStartupTime.png)

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
