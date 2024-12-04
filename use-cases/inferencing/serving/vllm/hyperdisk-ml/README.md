# Distributed Inference and Serving with vLLM using Hyperdisk ML

This guide demonstrates how to serve a model with vllm using Hyperdisk ML.

Hyperdisk ML is a high performance storage solution that can be used to scale out your applications. It provides high aggregate throughput to many virtual machines concurrently, making it ideal if you want to run AI/ML workloads that need access to large amounts of data. When enabled in read-only-many mode, you can use Hyperdisk ML to accelerate the loading of model weights by up to 11.9X relative to loading directly from a model registry.

By the end of this guide, you should be able to perform the following steps:

- Create a Hyperdisk ML for the LLM model weights
- Deploy a vLLM container to your cluster to host your model
- Use vLLM to serve the fine-tuned Gemma model

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A bucket containing the fine-tuned model from the [Fine-tuning example](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md)

## Preparation

- Clone the repository.

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```sh
  cd use-cases/inferencing/serving/vllm/hyperdisk-ml
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- Get credentials for the GKE cluster.

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

## Prepare the Hyperdisk ML

Loading model weights from a PersistentVolume is a method to load models faster. In GKE, PersistentVolumes backed by Google Cloud Hyperdisk ML can be mounted read-only simultaneously by multiple nodes (ReadOnlyMany), this allows multiple pods access to the model weights from a single volume.

- Configure the environment.

  | Variable             | Description                                                                                  | Example                                     |
  | -------------------- | -------------------------------------------------------------------------------------------- | ------------------------------------------- |
  | ACCELERATOR          | Type of GPU accelerator to use (a100, h100, l4)                                              | l4                                          |
  | GCE_HYPERDISKML_NAME | Name of the Hyperdisk ML that will host the model                                            | <unique_id>-vllm-model-weights-hdml-${ZONE} |
  | GCE_IMAGE_NAME       | Disk image created with model weights                                                        | <unique_id>-vllm-model-weights-hdml-${ZONE} |
  | MODEL_NAME           | The name of the model folder in the root of the GCS model bucket                             | model-gemma2                                |
  | MODEL_VERSION        | The name of the version folder inside the model folder of the GCS model bucket               | experiment                                  |
  | ZONE                 | GCP zone where you have accelerators available. The zone must be in the region ${MLP_REGION} | us-central1-a                               |

  ```sh
  ACCELERATOR=l4
  MODEL_NAME=model-gemma2
  MODEL_VERSION=experiment
  ZONE=us-central1-a
  ```

  ```ssh
  GCE_HYPERDISKML_NAME=${MLP_UNIQUE_IDENTIFIER_PREFIX}-vllm-model-weights-hdml-${ZONE}
  GCE_IMAGE_NAME=${MLP_UNIQUE_IDENTIFIER_PREFIX}-vllm-model-weights-hdml-${ZONE}
  ```

### Download the model from GCS to a PersistentVolume (PV)

- Create a PersistentVolumeClaim (PVC) for the model weights.

  ```sh
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} apply -f manifests/volume-prep/downloads-persistent-volume-claim.yaml
  ```

  ```
  persistentvolumeclaim/vllm-models-hdml created
  ```

- Configure the job to download the model from the GCS bucket to the PersistentVolume (PV).

  ```sh
  git restore manifests/volume-prep/job.yaml
  sed \
  -i -e "s|V_KSA|${MLP_MODEL_OPS_KSA}|" \
  -i -e "s|V_MODEL_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|g" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  manifests/volume-prep/job.yaml
  ```

- Create the job.

  ```
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} create -f manifests/volume-prep/job.yaml
  ```

  ```
  job.batch/model-downloader-hdml created
  ```

  It takes approximately 10 minutes for the job to complete.

- Once the job has started, you can check the logs for the progress of the download.

  ```sh
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} logs job/model-downloader-hdml
  ```

  If you get the following error, wait a moment and retry as the pod is still initializing:

  ```
  Defaulted container "model-downloader" out of: model-downloader, gke-gcsfuse-sidecar (init)
  Error from server (BadRequest): container "model-downloader" in pod "model-downloader-hdml-XXXXX" is waiting to start: PodInitializing
  ```

  If the download is still in progress you should see something similar to:

  ```
  ...<skipped output>...

  Allocating group tables: done
  Writing inode tables: done
  Creating journal (###### blocks): done
  Writing superblocks and filesystem accounting information: done

  ```

  When the download is complete you should see something similar to:

  ```
  ...<skipped output>...

  Allocating group tables: done
  Writing inode tables: done
  Creating journal (###### blocks): done
  Writing superblocks and filesystem accounting information: done


  total ##K
  drwxr-xr-x 3 root root 4.0K MMM DD HH:MM .
  drwxr-xr-x 4 root root 4.0K MMM DD HH:MM ..
  drwxr-xr-x 3 root root 4.0K MMM DD HH:MM experiment
  total ##G
  drwxr-xr-x 3 root root #### MMM DD HH:MM .
  drwxr-xr-x 3 root root #### MMM DD HH:MM ..
  -rw-r--r-- 1 root root #### MMM DD HH:MM README.md
  drwxr-xr-x 4 root root #### MMM DD HH:MM checkpoint-#####
  -rw-r--r-- 1 root root #### MMM DD HH:MM config.json
  -rw-r--r-- 1 root root #### MMM DD HH:MM generation_config.json
  -rw-r--r-- 1 root root #### MMM DD HH:MM model-00001-of-00004.safetensors
  -rw-r--r-- 1 root root #### MMM DD HH:MM model-00002-of-00004.safetensors
  -rw-r--r-- 1 root root #### MMM DD HH:MM model-00003-of-00004.safetensors
  -rw-r--r-- 1 root root #### MMM DD HH:MM model-00004-of-00004.safetensors
  -rw-r--r-- 1 root root #### MMM DD HH:MM model.safetensors.index.json
  -rw-r--r-- 1 root root #### MMM DD HH:MM special_tokens_map.json
  -rw-r--r-- 1 root root #### MMM DD HH:MM tokenizer.json
  -rw-r--r-- 1 root root #### MMM DD HH:MM tokenizer_config.json
  ```

- You can also watch the job till it is complete.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get job/model-downloader-hdml | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'"
  ```

  ```
  NAME                    STATUS    COMPLETIONS   DURATION   AGE
  model-downloader-hdml   Complete  1/1           XXXXX      XXXXX
  ```

  Now, the model is downloaded to the persistent volume.

### Create a Hyperdisk ML

- Fetch the Persistent volume name and disk ref to create a disk image.

  ```sh
  PV_NAME="$(kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get pvc/vllm-models -o jsonpath='{.spec.volumeName}')"
  GCE_HYPERDISKML_REF="$(kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get pv/${PV_NAME} -o jsonpath='{.spec.csi.volumeHandle}')"
  echo "PV_NAME=${PV_NAME}"
  echo "GCE_HYPERDISKML_REF=${GCE_HYPERDISKML_REF}"
  ```

  ```
  PV_NAME=pvc-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
  GCE_DISK_REF=projects/XXXXXXXXXX/zones/us-central1-X/disks/pvc-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
  ```

- Create a Compute Engine image.

  ```sh
  gcloud compute images create ${GCE_IMAGE_NAME} \
  --project="${MLP_PROJECT_ID}" \
  --source-disk="${GCE_HYPERDISKML_REF}"
  ```

  It takes approximately 3 minutes to create the Compute Engine image.

  ```
  Created [https://www.googleapis.com/compute/v1/projects/XXXXXXXXXX/global/images/XXXXXXXXXX-vllm-model-weights-hdml-us-central1-a].
  NAME                                              PROJECT              FAMILY  DEPRECATED  STATUS
  XXXXXXXXXX-vllm-model-weights-hdml-us-central1-a  XXXXXXXXXX                               READY
  ```

- Create a Hyperdisk ML from the image.

  > Ensure the appropriate zone based on cluster node location and GPU availability.

  ```sh
  gcloud compute disks create ${GCE_HYPERDISKML_NAME} \
  --access-mode="READ_ONLY_MANY" \
  --image="${GCE_IMAGE_NAME}" \
  --size="1TiB" \
  --project="${MLP_PROJECT_ID}" \
  --type="hyperdisk-ml" \
  --zone="${ZONE}"
  ```

  It takes approximately 2 minutes to create the Disk image.

  ```
  WARNING: Some requests generated warnings:
  - Disk size: '1024 GB' is larger than image size: '100 GB'. You might need to resize the root repartition manually if the operating system does not support automatic resizing. See https://cloud.google.com/compute/docs/disks/add-persistent-disk#resize_pd for details.

  NAME                                              ZONE           SIZE_GB  TYPE          STATUS
  XXXXXXXXXX-vllm-model-weights-hdml-us-central1-a  us-central1-a  1024     hyperdisk-ml  READY

  The Hyperdisk ML is created with default throughput limit of 24,576 MB/s. You can adjust the throughput limit based on the underlying VM to achieve higher speed in loading the model.
  ```

### Create the PersistentVolumeClaim (PVC) and PersistentVolume (PV) for serving

- Configure the PersistentVolume.

  ```sh
  VOLUME_HANDLE="projects/${MLP_PROJECT_ID}/zones/${ZONE}/disks/${GCE_HYPERDISKML_NAME}"
  echo "VOLUME_HANDLE=${VOLUME_HANDLE}"
  ```

  ```
  git restore manifests/volume-prep/persistent-volume.yaml
  sed \
  -i -e "s|V_VOLUME_HANDLE|${VOLUME_HANDLE}|" \
  -i -e "s|V_ZONE|${ZONE}|" \
  manifests/volume-prep/persistent-volume.yaml
  ```

- Create the PersistentVolume

  > PersistentVolumes are cluster-wide resources, meaning they do not belong to any specific namespace.

  ```
  kubectl apply -f manifests/volume-prep/persistent-volume.yaml
  ```

  ```
  persistentvolume/vllm-model-weights-hdml-1024gb-us-central1-a created
  ```

- Configure the PersistentVolumeClaim

  ```sh
  git restore manifests/volume-prep/persistent-volume-claim.yaml
  sed \
  -i -e "s|V_ZONE|${ZONE}|" \
  manifests/volume-prep/persistent-volume-claim.yaml
  ```

- Create the PersistentVolumeClaim

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/volume-prep/persistent-volume-claim.yaml
  ```

  ```
  persistentvolumeclaim/vllm-model-weights-hdml-1024gb-us-central1-a-ro created
  ```

## Serve the model with vLLM

- Configure the deployment.

  ```
  VLLM_IMAGE_NAME="vllm/vllm-openai:v0.6.3.post1"
  ```

  ```sh
  git restore manifests/model-deployment-${ACCELERATOR}.yaml
  sed \
  -i -e "s|V_MODEL_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
  -i -e "s|V_VLLM_IMAGE_URL|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_ZONE|${ZONE}|" \
  manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment.

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/model-deployment-${ACCELERATOR}.yaml
  ```

  ```
  deployment.apps/vllm-openai-hdml-l4 created
  service/vllm-openai-hdml-l4 created
  ```

- Watch the deployment until it is ready and available.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/vllm-openai-hdml-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 5+ minutes for the deployment to be ready and available.

  ```
  NAME                  READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-openai-hdml-l4   1/1     1            1           XXX
  ```

## Serve the model through a web chat interface

- Configure the deployment

  ```sh
  git restore manifests/gradio.yaml
  sed \
  -i -e "s|V_ACCELERATOR|${ACCELERATOR}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|g" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|g" \
  manifests/gradio.yaml
  ```

- Create the deployment

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/gradio.yaml
  ```

  ```
  deployment.apps/gradio created
  service/gradio-svc created
  ```

- Watch the deployment until it is ready and available.

  ```
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/gradio | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 1 minute for the deployment to be ready and available.

  ```
  NAME     READY   UP-TO-DATE   AVAILABLE   AGE
  gradio   1/1     1            1           XXs
  ```

- Run the following command to output the URL for the the chat interface.

  ```sh
  echo -e "\nGradio chat interface: ${MLP_GRADIO_MODEL_OPS_ENDPOINT}\n"
  ```

- Open the chat interface in your browser.

- Enter the following prompt in the **Type a message...** text box and click **Submit**.

  ```
  I'm looking for comfortable cycling shorts for women, what are some good options?
  ```

  You should see a response similar to:

  ```
  Gritstones Solid Women's Cycling Shorts are a great option, they're comfortable, have a great price point, and are available in various colors
  Product Name: Gritstones Solid Women's Cycling Shorts
  Product Category: Sports
  Product Details:
  • Number of Contents in Sales Package: Pack of 3
  • Fabric: Cotton, Lycra
  • Type: Cycling Shorts
  • Pattern: Solid
  • Ideal For: Women's
  • Style Code: GSTPBLK119_Multicolor
  ```

## What's next

Now that the model is deployed, there are several steps you can take to operationalize and utilize the model.

- [vLLM Metrics](/use-cases/inferencing/serving/vllm/metrics/README.md)
- [vLLM autoscaling with horizontal pod autoscaling (HPA)](/use-cases/inferencing/serving/vllm/autoscaling/README.md)
- [Benchmarking with Locust](/use-cases/inferencing/benchmark/README.md)
- [Batch inference on GKE](/use-cases/inferencing/batch-inference/README.md)
