# Distributed Inferencing on vLLM using Persistent disk

This guide demonstrates how to serve a model with vllm using hyperdiskML. By the end of this guide, you should be able to perform the following steps:

- Create a hyperdiskML for the LLM model weights
- Deploy a vLLM container to your cluster to host your model
- Use vLLM to serve the fine-tuned Gemma model
- View Production metrics for your model serving
- Use custom metrics and Horizontal Pod Autoscaler (HPA) to scale your model

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A bucket containing the fine-tuned model from the [Fine-tuning example](/use-cases/model-fine-tuning-pipeline/fine-tuning/pytorch/README.md)

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/inferencing/serving/vllm/hyperdiskML
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

## Prepare the HyperdiskML

Loading model weights from a PersistentVolume is a method to load models faster. In GKE, PersistentVolumes backed by Google Cloud hyperdiskML can be mounted read-only simultaneously by multiple nodes (ReadOnlyMany), this allows multiple pods access to the model weights from a single volume.

- Configure the environment

  | Variable       | Description                                                                                  | Example                                |
  | -------------- | -------------------------------------------------------------------------------------------- | -------------------------------------- |
  | ACCELERATOR    | Type of GPU accelerator to use (l4, a100, h100)                                              | l4                                     |
  | GCE_HYPERDISKML_NAME  | Name of the hyperdiskML that will host the model                                         | <unique_id>-vllm-model-weights-${ZONE} |
  | GCE_IMAGE_NAME | Disk image created with model weights                                                        | <unique_id>-vllm-model-weights-${ZONE} |
  | MODEL_NAME     | The name of the model folder in the root of the GCS model bucket                             | model-gemma2                           |
  | MODEL_VERSION  | The name of the version folder inside the model folder of the GCS model bucket               | experiment                             |
  | ZONE           | GCP zone where you have accelerators available. The zone must be in the region ${MLP_REGION} | us-central1-a                          |

  ```sh
  ACCELERATOR=l4
  MODEL_NAME=model-gemma2
  MODEL_VERSION=experiment
  ZONE=us-central1-a
  ```

  ```ssh
  GCE_HYPERDISKML_NAME=${MLP_UNIQUE_IDENTIFIER_PREFIX}-vllm-model-weights-${ZONE}
  GCE_IMAGE_NAME=${MLP_UNIQUE_IDENTIFIER_PREFIX}-vllm-model-weights-${ZONE}
  ```

### Download the model from GCS to a PersistentVolume (PV)

- Create a PersistentVolumeClaim (PVC) for the model weights

  ```sh
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} apply -f manifests/volume-prep/downloads-persistent-volume-claim.yaml
  ```

- Configure the job to download the model from the GCS bucket to the PersistentVolume (PV)

  ```sh
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

- Once the job has started, you can check the pod logs for the progress of the download

  ```sh
  POD=$(kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get pods --no-headers --output custom-columns=":metadata.name" --selector app=model-downloader)
  kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} logs pod/${POD}
  ```

  If the download is still in progress you should see something similar to:

  ```
  ...<skipped output>...

  Allocating group tables: done
  Writing inode tables: done
  Creating journal (###### blocks): done
  Writing superblocks and filesystem accounting information: done

  ```

  If the download is complete you should see something similar to:

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

- Wait for the job to complete

  ```sh
  kubectl wait --namespace=${MLP_MODEL_OPS_NAMESPACE} --for=condition=complete --timeout=900s job/model-downloader && echo "complete" &
  kubectl wait --namespace=${MLP_MODEL_OPS_NAMESPACE} --for=condition=failed --timeout=900s job/model-downloader && echo "failed" && exit 1 &
  wait -n && pkill -f "kubectl wait --namespace=${MLP_MODEL_OPS_NAMESPACE}"
  ```

  ```
  job.batch/model-downloader condition met
  complete
  ```

  Now, the model is downloaded to the persistent volume.

### Create a HyperdiskML

- Fetch the Persistent volume name and disk ref to create a disk image

  ```sh
  PV_NAME="$(kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get pvc/vllm-models -o jsonpath='{.spec.volumeName}')"
  GCE_HYPERDISKML_REF="$(kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get pv/${PV_NAME} -o jsonpath='{.spec.csi.volumeHandle}')"
  echo "PV_NAME=${PV_NAME}"
  echo "GCE_HYPERDISKML_REF=${GCE_HYPERDISKML_REF}"
  ```

- Create a Compute Engine image

  ```sh
  gcloud compute images create ${GCE_IMAGE_NAME} \
  --source-disk="${GCE_HYPERDISKML_REF}"
  ```

- Create a HyperdiskML from the image

  ```sh
  gcloud compute disks create ${GCE_HYPERDISKML_NAME} \
  --image=${GCE_IMAGE_NAME} \
  --size=1TiB \
  --type=hyperdisk-ml \
  --zone=${ZONE} \
  --access-mode=READ_ONLY_MANY
  ```

  > Note: Ensure the appropriate zone based on cluster node location and GPU availability

The hyperdiskML is created with default throughput limit of 24,576 MB/s. You can adjust the througput limit based on the underlying VM to achieve higher speed in loading the model. 

### Create the PersistentVolumeClaim (PVC) and PersistentVolume (PV) for serving

- Configure the PersistentVolume

  ```sh
  VOLUME_HANDLE="projects/${MLP_PROJECT_ID}/zones/${ZONE}/disks/${GCE_HYPERDISKML_NAME}"
  echo "VOLUME_HANDLE=${VOLUME_HANDLE}"
  sed \
  -i -e "s|V_VOLUME_HANDLE|${VOLUME_HANDLE}|" \
  -i -e "s|V_ZONE|${ZONE}|" \
  manifests/volume-prep/persistent-volume.yaml
  ```

- Create the PersistentVolume

  ```
  kubectl apply -f manifests/volume-prep/persistent-volume.yaml
  ```

  > Note: PersistenVolumes are cluster-wide resources, meaning they do not belong to any specific namespace.

- Configure the PersistentVolumeClaim

  ```sh
  sed \
  -i -e "s|V_ZONE|${ZONE}|" \
  manifests/volume-prep/persistent-volume-claim.yaml
  ```

- Create the PersistentVolumeClaim

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/volume-prep/persistent-volume-claim.yaml
  ```

## Serve the model with vLLM

- Configure the deployment

  ```
  VLLM_IMAGE_NAME="vllm/vllm-openai:v0.6.3.post1"
  ```

  ```sh
  sed \
  -i -e "s|V_MODEL_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
  -i -e "s|V_VLLM_IMAGE_URL|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_ZONE|${ZONE}|" \
  manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Wait for the deployment to be ready

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} wait --for=condition=ready --timeout=900s pod --selector app=vllm-openai-pd-${ACCELERATOR}
  ```

## Serve the model through a web chat interface

- Configure the deployment

  ```sh
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

- Verify the deployment is ready

- Access the chat interface

  ```sh
  echo -e "\nGradio chat interface: ${MLP_GRADIO_MODEL_OPS_ENDPOINT}\n"
  ```

- Enter the following prompt in the chat text box to get the response from the model.

  ```
  I'm looking for comfortable cycling shorts for women, what are some good options?
  ```

## Metrics

vLLM exposes a number of metrics that can be used to monitor the health of the system. For more information about accessing these metrics see [vLLM Metrics](/use-cases/inferencing/serving/vllm/metrics/README.md).

## Autoscaling with horizontal pod autoscaling (HPA)

You can configure Horizontal Pod Autoscaler to scale your inference deployment based on relevant metrics. Follow the instructions in the [vLLM autoscaling with horizontal pod autoscaling (HPA)](/use-cases/inferencing/serving/vllm/autoscaling/README.md) guide to scale your deployed model.

## Run a benchmark for inference

The model is ready to run the benchmark for inference job, follow [Benchmarking with Locust](/use-cases/inferencing/benchmark/README.md) to run inference benchmarking on the model.

## Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , you can run batch inference on it. Follow the instructions in [batch-inference readme](/use-cases/inferencing/batch-inference/README.md) to run batch inference.
