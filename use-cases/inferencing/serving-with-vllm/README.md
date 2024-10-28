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

* Save new variables in the environment variable file

   ```sh
   echo "MODEL_ID=${MODEL_ID}" >> ${MLP_ENVIRONMENT_FILE}
   echo "MODEL_PATH=${MODEL_PATH}" >> ${MLP_ENVIRONMENT_FILE}
   echo "INFERENCE_DIR=$(pwd)" >> ${MLP_ENVIRONMENT_FILE}
   echo "BATCH_INFERENCE_DIR=$(pwd)/batch-inference"  >> ${MLP_ENVIRONMENT_FILE}
   echo "INFERENCE_BENCHMARK_DIR=$(pwd)/benchmarks"  >> ${MLP_ENVIRONMENT_FILE}
   echo "INFERENCE_DASHBOARD_DIR=$(pwd)/dashboard"  >> ${MLP_ENVIRONMENT_FILE}
   echo "INFERENCE_SCALE_DIR=$(pwd)/inference-scale"  >> ${MLP_ENVIRONMENT_FILE}
   source ${MLP_ENVIRONMENT_FILE}
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

vLLM exposes a number of metrics that can be used to monitor the health of the system. These metrics are exposed via the `/metrics` endpoint on the vLLM OpenAI compatible API server. These metrics can be scraped using Google Managed Promotheus. For detials, see  [pod monitoring with Google managed prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus/setup-managed#gmp-pod-monitoring).

*   Deploy the a `PodMonitoring` resource that scrapes the vllm metrics and make them available in [Cloud Metrics](https://pantheon.corp.google.com/monitoring/metrics-explorer).

  ```sh
  sed \
  -i -e "s|_NAMESPACE_|${MLP_KUBERNETES_NAMESPACE}|g" \
  manifests/pod-monitoring.yaml
  kubectl apply -f manifests/pod-monitoring.yaml
  ```

*   Wait for a minute and view the metrics in Cloud metrics. Note, that some 
of the metrics will only be available when the model is used.
  
    *   Go to [metrics explorer](https://pantheon.corp.google.com/monitoring/metrics-explorer)
    *   Go to `Select  metric` > `Prometheus Target` > `vllm-inference` to view the metrics
    *   In the `Filter` box , set filter `cluster=<YOUR_CLUSTER_NAME>` to see the metrics related to your cluster.


### Create a dashboard for Cloud Monitoring to view vLLM metrics

You can create grafana dashboard with the vllm metrics. Follow the instructions on [dashboard readme][dashboard-readme].


### Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , you can run batch inference on it. Follow the instructions in [batch-inference readme](./batch-inference/README.md) to run batch inference.

### Run benchmarks for inference

The model is ready to run the benchmarks for inference job. Follow [benchmark readme](./benchmarks/README.md) to run inference benchmarks on our model.

### Inference at Scale

You can configure Horizontal Pod Autoscaler to scale your inference deployment based
on relevant metrics. Follow the instructions on [inference at scale reademe]
(./inference-scale/README.md) to scale your deployed model
.