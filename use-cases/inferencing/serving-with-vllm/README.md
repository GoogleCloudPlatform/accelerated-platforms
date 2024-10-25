# Distributed Inferencing on vLLM

There are three common strategies for inference on vLLM:

*   Single GPU (no distributed inference)
  
*   Single-Node Multi-GPU (tensor parallel inference)
  
*   Multi-Node Multi-GPU

In this guide, you will serve a fine-tuned Gemma large language model (LLM) using
graphical processing units (GPUs) on Google Kubernetes Engine (GKE) with the vLLM
 serving framework with the above mentioned deployment strategies.
 You can choose to swap the Gemma model with any other fine-tuned
 or instruction based model for inference on GKE.

*   Single GPU (no distributed inference) - If your model fits in a single GPU, you  don’t need to use distributed inference. Just use the single GPU to run the inference.

*   Single-Node Multi-GPU (tensor parallel inference) - If your model is too
large to fit in a single GPU, but it can fit in a single node with multiple GPUs,
you can use tensor parallelism. The tensor parallel size is the number of GPUs
you want to use. For example, if you need 4 GPUs, you can set the tensor parallel
size to 4.

By the end of this guide, you should be able to perform the following steps:

*   Create a Persistent Disk for the LLM model weights

*   Deploy a vLLM container to your cluster to host your model

*   Use vLLM to serve the fine-tuned Gemma model

*   View Production metrics for your model serving

*   Use custom metrics and Horizontal Pod Autoscaler (HPA) to scale your model

## Prerequisites

*   This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md).
If you are using a different environment the scripts and manifest will
need to be modified for that environment.

*   A bucket containing the fine-tuned model from the [Fine-tuning example](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md)

## Preparation

*   Clone the repository and change directory to the guide directory

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms/use-cases/inferencing/serving-with-vllm
  ```

*   Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific 
to your environment.

*   Set other variables for preparing inference manifests

  | Variable                             | Description                                                                                                                       | Example                                       |
  | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
  | ACCELERATOR                          | Type of GPU accelerator to use (l4, a100,  h100)                                                                                  | nvidia-l4                                     |
  | MODEL_ID                             | The name of the fine-tuned model in the GCS bucket                                                                                | model-gemma2-a100                             |  
  | MODEL_PATH                           | The directory inside the model folder in the GCS                                                                                  | experiment-a100-llamaprep                     |
  | IMAGE_NAME                           | Disk image created with model weights                                                                                             | gemma-model-weights-image                     |
  | DISK_NAME                            | Name of the persistent disk that will host the model                                                                              | model-weights-disk                            |
  | ZONE                                 | GCP zone where you have accelerators available. The zone must be in the region ${MLP_REGION}                                      | us-central1-a                                 |

```sh
ACCELERATOR=<ACCELERATOR> #nvidia-l4 or nvidia-tesla-a100 or nvidia-h100-80gb
MODEL_ID=<MODEL_ID>
MODEL_PATH=<MODEL_PATH>
IMAGE_NAME=<IMAGE_NAME>
DISK_NAME=<DISK_NAME>
ZONE=<ZONE> # choose the zone where you have the accelerator that you are using available.
```

*   Get Credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

*   Grant permission to kubernetes service account in cluster to access the storage
bucket to view model weights

  ```sh
  gcloud storage buckets add-iam-policy-binding "gs://${MLP_MODEL_BUCKET}" \
    --member "principal://iam.googleapis.com/projects/"${MLP_PROJECT_NUMBER}"/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${MLP_KUBERNETES_NAMESPACE}/sa/${MLP_SERVE_KSA}" \
    --role "roles/storage.objectViewer"
  ```

*   Update the bucket access level to uniform.

  ```sh
  gcloud storage buckets update "gs://${MLP_MODEL_BUCKET}"  --uniform-bucket-level-access
  ```

## Prepare loading the model to the GKE container

There are a few ways you can load the model efficiently in the GKE container for
inferencing:

*   Use SSD based Persistent disk.
*   Use GCS Fuse parallel dowload.
*   Use Hyperdisk ML.
*   Loading the model weight as an image from a secondary boot disk.
  
In this example, we will load the model from PD SSD.

## Downlaod the fine tuned model from GCS bucket to a persistent volume

Loading model weights from a Persistent Volume is a method to load models faster.
In GKE, Persistent Volumes backed by GCP Persistent Disks can
be mounted read-only simultaneously by multiple nodes(ReadOnlyMany), this allows
multiple pods access to the model weights from a
single volume.

*   Create a Persistent volume claim for the model weights

  ```sh
  sed -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|g" manifests/volume-prep/pvc-disk-image.yaml
  kubectl apply -f manifests/volume-prep/pvc-disk-image.yaml
  ```

*   Create a job for downloading the model from the GCS bucket to the volume
and review logs for successful
completion.

  ```sh
  sed -i -e "s|_YOUR_BUCKET_NAME_|${MLP_MODEL_BUCKET}|g" manifests/volume-prep/batch-job-download-model-on-pv-volume.yaml
  sed -i -e "s|_MODEL_ID_|${MODEL_ID}|g" manifests/volume-prep/batch-job-download-model-on-pv-volume.yaml
  sed -i -e "s|_MODEL_PATH_|${MODEL_PATH}|g" manifests/volume-prep/batch-job-download-model-on-pv-volume.yaml
  sed -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|g" manifests/volume-prep/batch-job-download-model-on-pv-volume.yaml
  sed -i -e "s|_KSA_|${MLP_SERVE_KSA}|g" manifests/volume-prep/batch-job-download-model-on-pv-volume.yaml
  kubectl create -f manifests/volume-prep/batch-job-download-model-on-pv-volume.yaml
  ```

*   Wait for the job to show completion.

  ```sh
  kubectl get jobs -n ${MLP_KUBERNETES_NAMESPACE}
  ```
Now, the model is downloaded to the persistent volume.

## Create a persistent disk with the image of the model

*   Fetch the Persistent volume name and disk ref to create a disk image

  ```sh
  PV_NAME="$(kubectl get pvc/block-pvc-model -n ${MLP_KUBERNETES_NAMESPACE} -o jsonpath='{.spec.volumeName}')"
  DISK_REF="$(kubectl get pv "$PV_NAME" -n ${MLP_KUBERNETES_NAMESPACE} -o jsonpath='{.spec.csi.volumeHandle}')"
  ```

*   Create a disk image

  ```sh
  gcloud compute images create ${IMAGE_NAME} --source-disk="$DISK_REF"
  ```

*   Create a peristent disk with the model image:

  ```sh
  gcloud compute disks create ${DISK_NAME} --size=1TiB \
  --type=pd-ssd --zone=${ZONE} --image=${IMAGE_NAME}
  ```


## Deploy a vLLM container serving the model on the GKE cluster

*   Replace the variables in the manifest and deploy the model.

  ```sh
  sed \
  -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|g" \
  -i -e "s|_KSA_|${MLP_SERVE_KSA}|g" \
  -i -e "s|_MODEL_ID_|${MODEL_ID}|g" \
  -i -e "s|_MODEL_PATH_|${MODEL_PATH}|g" \
  -i -e "s|_ACCELERATOR_|${ACCELERATOR}|g" \
  -i -e "s|_PROJECT_ID_|${MLP_PROJECT_ID}|g" \
  -i -e "s|_ZONE_|${ZONE}|g" \
  -i -e "s|_DISK_|${DISK_NAME}|g" \
  manifests/model-deployment.yaml
  kubectl  apply -f manifests/model-deployment.yaml
  ```

  
  Note: This guide assumes that you have the accelerator available in the zone you are using.
        The manifest creates a persistent volume and persistent volume claim to 
        use the model image on persistent disk and then deploys vLLM container using that
        persistent volume claim.

*   Check the logs for the following pattern that indicates that the model is ready 
to serve.
  
  ```sh
  INFO:     Started server process [1]
  INFO:     Waiting for application startup.
  INFO:     Application startup complete.
  INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
  ```

## Serve the deployed model through a web chat interface

- Deploy a gradio chat interface to view the model chat interface. [OPTIONAL]

  ```sh
    sed \
  -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|g" \
  -i -e "s|_MODEL_ID_|${MODEL_ID}|g" \
  -i -e "s|_MODEL_PATH_|${MODEL_PATH}|g" \
  manifests/gradio.yaml
  kubectl apply -f manifests/gradio.yaml
  ```
  TODO : Make the chat interfave avialable via IAP

### Production Metrics

vLLM exposes a number of metrics that can be used to monitor the health of the system. These metrics are exposed via the `/metrics` endpoint on the vLLM OpenAI compatible API server. These metrics can be scraped using Google Managed Promotheus.

*   Deploy the a monitoring pod that scrapes the vllm metrics and make them available in Cloud Monitoring.

  ```sh
    sed \
  -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|g" \
  manifests/pod-monitoring.yaml
  kubectl apply -f manifests/pod-monitoring.yaml
  ```

*   Wait for a minute andview the metrics in Cloud metrics

### View vLLM serving metrics for your model on GKE

You can configure monitoring of the metrics above using the [pod monitoring](https://cloud.google.com/stackdriver/docs/managed-prometheus/setup-managed#gmp-pod-monitoring)

  ```sh
  kubectl apply -f manifests/pod_monitoring.yaml
  ```

### Create a dashboard for Cloud Monitoring to view vLLM metrics

Cloud Monitoring provides an [importer](https://cloud.google.com/monitoring/dashboards/import-grafana-dashboards) that you can use to import dashboard files in the Grafana JSON format into Cloud Monitoring

1. Clone github repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/monitoring-dashboard-samples
  ```

1. Change to the directory for the dashboard importer:

  ```sh
  cd monitoring-dashboard-samples/scripts/dashboard-importer
  ```

The dashboard importer includes the following scripts:

- import.sh, which converts dashboards and optionally uploads the converted dashboards to Cloud Monitoring.
- upload.sh, which uploads the converted dashboards or any Monitoring dashboards to Cloud Monitoring. The import.sh script calls this script to do the upload.

1. Import the dashboard

  ```sh
  ./import.sh ./configs/grafana.json ${MLP_PROJECT_ID}
  ```

  When you use the import.sh script, you must specify the location of the Grafana dashboards to convert. The importer creates a directory that contains the converted dashboards and other information.

### Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , its ready to run batch Inference pipeline.
In this example of batch inference pipeline, we would first send prompts to the hosted fine-tuned model and then validate the results based on ground truth.

#### Prepare your environment

*   Setup Workload Identity Federation access to read/write to the bucket for the inference batch data set


 ```sh
  gcloud storage buckets add-iam-policy-binding "gs://${MLP_PREDICTION_BUCKET}" \
    --member "principal://iam.googleapis.com/projects/"${MLP_PROJECT_NUMBER}"/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${MLP_KUBERNETES_NAMESPACE}/sa/${MLP_SERVE_KSA}" \
    --role "roles/storage.objectUser"
  
  gcloud storage buckets add-iam-policy-binding "gs://${MLP_PREDICTION_BUCKET}" \
    --member "principal://iam.googleapis.com/projects/"${MLP_PROJECT_NUMBER}"/locations/global/workloadIdentityPools/${MLP_PROJECT_ID}.svc.id.goog/subject/ns/${MLP_KUBERNETES_NAMESPACE}/sa/${MLP_SERVE_KSA}" \
    --role "roles/storage.legacyBucketWriter"

  ```

#### Build the image of the source and execute batch inference job

*   Build container image using Cloud Build and push the image to Artifact Registry. 

```sh
cd src
sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
gcloud beta builds submit \
--config cloudbuild.yaml \
--gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
--project ${MLP_PROJECT_ID} \
--substitutions _DESTINATION=${MLP_SERVE_IMAGE}
cd ..
```

*   Set variables

```sh
DATASET_OUTPUT_PATH=/dataset/output
EVAL_MODEL_PATH=/data/models/${MODEL_ID}/${MODEL_PATH}
ENDPOINT="http://vllm-openai:8000/v1/chat/completions" # The modle endpoint
```

*   Create an output directory to store the predictions in the bucket

```sh
gcloud storage folders create --recursive gs://MLP_PREDICTION_BUCKET/DATASET_OUTPUT_PATH

```

*   Replace variables in inference job manifest and deploy the job
```sh
sed -i -e "s|_IMAGE_URL_|${MLP_SERVE_IMAGE}|" \
    -i -e "s|_KSA_|${MLP_SERVE_KSA}|" \
    -i -e "s|_BUCKET_|${MLP_PREDICTION_BUCKET}|" \
    -i -e "s|_MODEL_PATH_|${EVAL_MODEL_PATH}|" \
    -i -e "s|_DATASET_OUTPUT_PATH_|${DATASET_OUTPUT_PATH}|" \
    -i -e "s|_ENDPOINT_|${ENDPOINT}|" \
    -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|" \
    model-eval.yaml
kubectl apply -f model-eval.yaml
```

You can review predictions result in file named `predictions.txt` under /dataset/output folder in the bucket. Sample file has been added to the repository.
The job will take approx 45 mins to execute.

### Run benchmarks for inference

The model is ready to run the benchmarks for inference job. We can run few performance tests using locust.
Locust is an open source performance/load testing tool for HTTP and other protocols.
You can refer to the documentation to [set up](https://docs.locust.io/en/stable/installation.html) locust locally or deploy as a container on GKE.

We have created a sample [locustfile](https://docs.locust.io/en/stable/writing-a-locustfile.html) to run tests against our model using sample prompts which we tried earlier in the exercise.
Here is a sample ![graph](./benchmarks/locust.jpg) to review.

*   Open Cloudshell

*   Install the locust library locally:

  ```sh
  pip3 install locust==2.29.1
  ```

*   Launch the benchmark python script for locust

  ```sh
  python benchmarks/locust.py $EVAL_MODEL_PATH
  ```

### Inference at Scale

There are different metrics available that could be used to scale your inference workloads
on GKE:

*   Server metrics: LLM inference servers vLLM provides workload-specific
performance metrics. GKE simplifies scraping of those metrics and autoscaling
the workloads based on these server-level metrics. You can use these metrics to
gain visibility into performance indicators like batch size, queue size, and
decode latencies.
In case of vLLM, [production metrics class](https://docs.vllm.ai/en/latest/serving/metrics.html)
exposes a number of useful metrics which GKE can use to horizontally scale
inference workloads.

```sh
vllm:num_requests_running - Number of requests currently running on GPU.
vllm:num_requests_waiting - Number of requests waiting to be processed
```

*   GPU metrics:

```none
GPU Utilization (DCGM_FI_DEV_GPU_UTIL) - Measures the duty cycle, which is the 
amount of time that the GPU is active.

GPU Memory Usage (DCGM_FI_DEV_FB_USED) - Measures how much GPU memory is being 
used at a given point in time. This is useful for workloads that implement
dynamic allocation of GPU memory.
```

*   CPU metrics: Since the inference workloads primarily rely on GPU resources,
we don't recommend CPU and memory utilization as the only indicators of the
amount of resources a job consumes. Therefore, using CPU metrics alone for
 autoscaling can lead to suboptimal performance and costs.

HPA is an efficient way to ensure that your model servers scale appropriately
with load. Fine-tuning the HPA settings is the primary way to align your 
provisioned hardware cost with traffic demands to achieve your inference server
performance goals.

We recommend setting these HPA configuration options:

*   Stabilization window: Use this HPA configuration option to prevent rapid
replica count changes due to fluctuating metrics. Defaults are 5 minutes for
scale-down (avoiding premature downscaling) and 0 for scale-up (ensuring responsiveness).
Adjust the value based on your workload's volatility and your preferred responsiveness.

*   Scaling policies: Use this HPA configuration option to fine-tune the scale-up
and scale-down behavior. You can set the "Pods" policy limit to specify the
absolute number of replicas changed per time unit, and the "Percent" policy
limit to specify by the percentage change.

For more details, see Horizontal pod autoscaling in the Google Cloud Managed 
Service for Prometheus [documentation](https://cloud.google.com/kubernetes-engine/docs/horizontal-pod-autoscaling).

Pre-requisites:

1. GKE cluster running inference workload as shown in previous examples.
2. Export the metrics from the vLLM server to Cloud Monitoring as shown in enable monitoring section.

We have couple of options to scale the inference workload on GKE using the HPA 
and custom metrics adapter.

1. Scale pod on the same node as the existing inference workload.
2. Scale pod on the other nodes in the same node pool as the existing inference workload.

#### Prepare your environment to autoscale with HPA metrics

Install the Custom Metrics Adapter. This adapter makes the custom metric that you 
exported to Cloud Monitoring visible to the HPA. For more details, see HPA 
in the [Google Cloud Managed Service for Prometheus documentation](https://cloud.google.com/stackdriver/docs/managed-prometheus/hpa).

1. The following example command shows how to install the adapter:

  ```sh
  kubectl apply -f kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/k8s-stackdriver/master/custom-metrics-stackdriver-adapter/deploy/production/adapter_new_resource_model.yaml
  ```

1. Set up the custom metric-based HPA resource. Deploy an HPA resource that is 
based on your preferred custom metric.

Here is a sample ![metrics graph](./manifests/inference-scale/cloud-monitoring-metrics-inference.png) to review.

Select **ONE** of the options below `Queue-depth` or `Batch-size` to configure the HPA resource in your manifest:

> NOTE: Adjust the appropriate target values for `vllm:num_requests_running` or `vllm:num_requests_waiting` in the yaml file.

- Queue-depth

  ```sh
  sed -i -e "s/_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}" hpa-vllm-openai-queue-size.yaml

  kubectl apply -f manifests/inference-scale/hpa-vllm-openai-queue-size.yaml
  ```

- Batch-size

  ```sh
  sed -i -e "s/_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}" hpa-vllm-openai-batch-size.yaml

  kubectl apply -f manifests/inference-scale/hpa-vllm-openai-batch-size.yaml
  ```

> Note: Below is an example of the batch size HPA scale test below:

```sh
kubectl get hpa vllm-openai-hpa -n ${MLP_KUBERNETES_NAMESPACE} --watch
NAME              REFERENCE                TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
vllm-openai-hpa   Deployment/vllm-openai   0/10      1         5         1          6d16h
vllm-openai-hpa   Deployment/vllm-openai   13/10     1         5         1          6d16h
vllm-openai-hpa   Deployment/vllm-openai   17/10     1         5         2          6d16h
vllm-openai-hpa   Deployment/vllm-openai   12/10     1         5         2          6d16h
vllm-openai-hpa   Deployment/vllm-openai   17/10     1         5         2          6d16h
vllm-openai-hpa   Deployment/vllm-openai   14/10     1         5         2          6d16h
vllm-openai-hpa   Deployment/vllm-openai   17/10     1         5         2          6d16h
vllm-openai-hpa   Deployment/vllm-openai   10/10     1         5         2          6d16h
```

```sh
kubectl get pods -n ${MLP_KUBERNETES_NAMESPACE} --watch
NAME                           READY   STATUS      RESTARTS   AGE
gradio-6b8698d7b4-88zm7        1/1     Running     0          10d
model-eval-2sxg2               0/1     Completed   0          8d
vllm-openai-767b477b77-2jm4v   1/1     Running     0          3d17h
vllm-openai-767b477b77-82l8v   0/1     Pending     0          9s
```

Pod scaled up
```sh
kubectl get pods -n ml-serve --watch
NAME                           READY   STATUS      RESTARTS   AGE
gradio-6b8698d7b4-88zm7        1/1     Running     0          10d
model-eval-2sxg2               0/1     Completed   0          8d
vllm-openai-767b477b77-2jm4v   1/1     Running     0          3d17h
vllm-openai-767b477b77-82l8v   1/1     Running     0          111s
```

The new pod is deployed on a node triggered by the cluster autoscaler.
> NOTE: The existing node where inference workload was deployed in this case had
only two GPUS. Hence a new node is required to deploy the copy pod of inference workload.

```sh
kubectl describe pods vllm-openai-767b477b77-82l8v -n ${MLP_KUBERNETES_NAMESPACE}

Events:
  Type     Reason                  Age    From                                   Message
  ----     ------                  ----   ----                                   -------
  Warning  FailedScheduling        4m15s  gke.io/optimize-utilization-scheduler  0/3 nodes are available: 1 Insufficient ephemeral-storage, 1 Insufficient nvidia.com/gpu, 2 node(s) didn't match Pod's node affinity/selector. preemption: 0/3 nodes are available: 1 No preemption victims found for incoming pod, 2 Preemption is not helpful for scheduling.
  Normal   TriggeredScaleUp        4m13s  cluster-autoscaler                     pod triggered scale-up: [{https://www.googleapis.com/compute/v1/projects/gkebatchexpce3c8dcb/zones/us-east4-a/instanceGroups/gke-kh-e2e-l4-2-c399c5c0-grp 1->2 (max: 20)}]
  Normal   Scheduled               2m40s  gke.io/optimize-utilization-scheduler  Successfully assigned ml-serve/vllm-openai-767b477b77-82l8v to gke-kh-e2e-l4-2-c399c5c0-vvm9
  Normal   SuccessfulAttachVolume  2m36s  attachdetach-controller                AttachVolume.Attach succeeded for volume "model-weights-disk-1024gb-zone-a"
  Normal   Pulling                 2m29s  kubelet                                Pulling image "vllm/vllm-openai:v0.5.3.post1"
  Normal   Pulled                  2m25s  kubelet                                Successfully pulled image "vllm/vllm-openai:v0.5.3.post1" in 4.546s (4.546s including waiting). Image size: 5586843591 bytes.
  Normal   Created                 2m25s  kubelet                                Created container inference-server
  Normal   Started                 2m25s  kubelet                                Started container inference-server
```
