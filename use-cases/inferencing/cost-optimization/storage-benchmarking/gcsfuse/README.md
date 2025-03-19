# Use GCS to store model and GCSFuse to download

In this guide, you will run inference of llama 70B model twice. In the first
run, the model will be stored in a flat GCS bucket and you will use GCSFuse
without any fine tuning to download the model from the bucket and start
inference. In the second run, the model will be stored in a hierarchical GCS
bucket and you will fine-tune GCSFuse configurations to download the model from
the bucket and start inference.

The goal of this guide is to demonstrate performance improvement in the model
load time and pod startup time when using fine-tuned configurations with
GCSFuse.

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.

- Follow [these instructions](/use-cases/prerequisites/storage-benchmarking.md)
  to download the Llama-3.3-70B-Instruct model into GCS bucket.

## Preparation

- Clone the repository.

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```sh
  cd use-cases/inferencing/cost-optimization/storage-benchmarking/gcsfuse
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster.

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

- Configure the environment.

  | Variable      | Description                                                                    | Example                   |
  | ------------- | ------------------------------------------------------------------------------ | ------------------------- |
  | ACCELERATOR   | Type of GPU accelerator to use (a100, h100, l4)                                | a100                      |
  | MODEL_NAME    | The name of the model folder in the root of the GCS model bucket               | meta-llama                |
  | MODEL_VERSION | The name of the version folder inside the model folder of the GCS model bucket | Meta-Llama-3-70B-Instruct |

  ```sh
  ACCELERATOR="a100"
  MODEL_NAME="meta-llama"
  MODEL_VERSION="Meta-Llama-3-70B-Instruct"
  ```

## Serve the model with vLLM with no tuning

- Configure the deployment.

  ```
  VLLM_IMAGE_NAME="vllm/vllm-openai:v0.6.6.post1"
  ```

  ```sh
  git restore manifests/model-deployment-${ACCELERATOR}-dws.yaml
  sed \
  -i -e "s|V_MODEL_BUCKET|${MLP_STORAGE_BENCHMARK_FLAT_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  -i -e "s|V_IMAGE_NAME|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_KSA|${MLP_STORAGE_BENCHMARKING_KSA}|" \
  manifests/model-deployment-${ACCELERATOR}-dws.yaml
  ```

- Create the provisioning request and the deployment.

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/provisioning-request-${ACCELERATOR}.yaml
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/model-deployment-${ACCELERATOR}-dws.yaml
  ```

  You will see the output similar to the following:

  ```
  podtemplate/a100-storage-benchmark created
  provisioningrequest.autoscaling.x-k8s.io/a100-storage-benchmark created
  deployment.apps/vllm-openai-gcs-llama33-70b-a100 created
  service/vllm-openai-gcs-llama33-70b-a100 created
  ```

  > Note : It may take a few minutes before the provisioning request is accepted
  > and the resources are provisioned. The deployment will be started as soon as
  > the resources are provisioned.

- Check the status of the provisioning request, once the `PROVISIONED` column
  shows `True`, the deployment will start.

  ```sh
  watch -n 5 kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get provisioningrequest a100-storage-benchmark
  ```

- When the deployment has started, watch the it until it is ready and available.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/vllm-openai-gcs-llama33-70b-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 20+ minutes for the deployment to be ready and available.

  ```
  NAME                              READY   UP-TO-DATE   AVAILABLE    AGE
  vllm-openai-gcs-llama33-70b-a100   1/1     1            1           XXXXX
  ```

## Calculate pod startup time

- Install bc in CloudShell

  ```sh
  sudo apt-get install bc
  ```

- Run the following commands to get the model load time in seconds

  ```sh
  POD_NAME=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods -o json | jq -r --arg accelerator "$ACCELERATOR" ".items[] | select(.metadata.name | contains(\"vllm-openai-gcs-llama33-70b-$accelerator\")) | .metadata.name"`

  BEGIN_MODEL_DOWNLOAD_TIME=`kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} logs ${POD_NAME} -c "inference-server" | grep "^INFO.*Starting to load model"  | head -n 1 | awk '{print $2" "$3}' | xargs -I {} date -d "$(date +%Y)-{}" +%s%3N`

  ENDING_MODEL_DOWNLOAD_TIME=`kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} logs ${POD_NAME} -c "inference-server" | grep "^INFO.*Loading model weights took" | head -n 1 | awk '{print $2" "$3}' | xargs -I {} date -d "$(date +%Y)-{}" +%s%3N`

  MODEL_LOAD_TIME_WITHOUT_TUNING=`echo "($ENDING_MODEL_DOWNLOAD_TIME - $BEGIN_MODEL_DOWNLOAD_TIME)/1000" | bc`

  echo "MODEL LOAD TIME WITHOUT TUNING - ${MODEL_LOAD_TIME_WITHOUT_TUNING}"
  ```

  > Loading llama 70B model with GCSFuse and no tuning will typically take
  > around 1200 seconds.

- Run the following commands to get the pod startup time in seconds. This is the
  time taken by the pod to change from `PodScheduled` to `Ready` status.

  ```sh
  POD_SCHEDULED_TIME=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME" -o json | jq -r '.status.conditions[] | select(.type == "PodScheduled") | .lastTransitionTime' | date -f - +%s%3N`

  POD_READY_TIME=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME" -o json | jq -r '.status.conditions[] | select(.type == "Ready") | .lastTransitionTime' | date -f - +%s%3N`

  POD_STARTUP_TIME_WITHOUT_TUNING=`echo "($POD_READY_TIME - $POD_SCHEDULED_TIME)/1000" | bc`

  echo "POD STARTUP TIME WITHOUT TUNING - ${POD_STARTUP_TIME_WITHOUT_TUNING}s"
  ```

## Serve the model with vLLM with tuning

- Configure the deployment.

  ```sh
  git restore manifests/model-deployment-tuned-${ACCELERATOR}-dws.yaml
  sed \
  -i -e "s|V_MODEL_BUCKET|${MLP_STORAGE_BENCHMARK_HIERARCHICAL_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  -i -e "s|V_IMAGE_NAME|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_KSA|${MLP_STORAGE_BENCHMARKING_KSA}|" \
  manifests/model-deployment-tuned-${ACCELERATOR}-dws.yaml
  ```

- Create the provisioning request and the deployment

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/provisioning-request-tuned-${ACCELERATOR}.yaml
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/model-deployment-tuned-${ACCELERATOR}-dws.yaml
  ```

  You will see the output similar to the following:

  ```
  podtemplate/a100-storage-benchmark-tuned created
  provisioningrequest.autoscaling.x-k8s.io/a100-storage-benchmark-tuned created
  deployment.apps/vllm-openai-gcs-tuned-llama33-70b-a100 created
  service/vllm-openai-gcs-tuned-llama33-70b-a100 created
  ```

  > Note : It may take a few minutes before the provisioning request is accepted
  > and the resources are provisioned. The deployment will be started as soon as
  > the resources are provisioned.

- Check the status of the provisioning request, once the `PROVISIONED` column
  shows `True`, the deployment will start.

  ```sh
  watch -n 5 kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get provisioningrequest a100-storage-benchmark-tuned
  ```

- Once the deployment has started, watch it until it is ready and available.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/vllm-openai-gcs-tuned-llama33-70b-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 3+ minutes for the deployment to be ready and available.

  ```
  NAME                                     READY   UP-TO-DATE   AVAILABLE    AGE
  vllm-openai-gcs-tuned-llama33-70b-a100   1/1     1            1           XXXXX
  ```

## Calculate pod startup time

- Run the following commands to get the model load time in seconds

  ```sh
  POD_NAME_TUNED=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods -o json | jq -r --arg accelerator "$ACCELERATOR" ".items[] | select(.metadata.name | contains(\"vllm-openai-gcs-tuned-llama33-70b-$accelerator\")) | .metadata.name"`

  BEGIN_MODEL_DOWNLOAD_TIME_TUNED=`kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} logs ${POD_NAME_TUNED} -c "inference-server" | grep "^INFO.*Starting to load model"  | head -n 1 | awk '{print $2" "$3}' | xargs -I {} date -d "$(date +%Y)-{}" +%s%3N`

  ENDING_MODEL_DOWNLOAD_TIME_TUNED=`kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} logs ${POD_NAME_TUNED} -c "inference-server" | grep "^INFO.*Loading model weights took" | head -n 1 | awk '{print $2" "$3}' | xargs -I {} date -d "$(date +%Y)-{}" +%s%3N`

  MODEL_LOAD_TIME_WITH_TUNING=`echo "($ENDING_MODEL_DOWNLOAD_TIME_TUNED - $BEGIN_MODEL_DOWNLOAD_TIME_TUNED)/1000" | bc`

  echo "MODEL LOAD TIME WITH TUNING - ${MODEL_LOAD_TIME_WITH_TUNING}s"
  ```

  > Loading llama 70B model with GCSFuse with tuned configurations will
  > typically take around 40 seconds.

- Run the following commands to get the pod startup time in seconds. This is the
  time taken by the pod to change from `PodScheduled` to `Ready` status.

  ```sh
  POD_SCHEDULED_TIME_TUNED=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME_TUNED" -o json | jq -r '.status.conditions[] | select(.type == "PodScheduled") | .lastTransitionTime' | date -f - +%s%3N`

  POD_READY_TIME_TUNED=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME_TUNED" -o json | jq -r '.status.conditions[] | select(.type == "Ready") | .lastTransitionTime' | date -f - +%s%3N`

  POD_STARTUP_TIME_WITH_TUNING=`echo "($POD_READY_TIME_TUNED - $POD_SCHEDULED_TIME_TUNED)/1000" | bc`

  echo "POD STARTUP TIME WITH TUNING - ${POD_STARTUP_TIME_WITH_TUNING}s"
  ```

## Conclusion

Look at the pod startup time with and without tuning by running these commands
in cloudShell:

```sh
echo $POD_STARTUP_TIME_WITHOUT_TUNING

echo $POD_STARTUP_TIME_WITH_TUNING
```

The pod startup time without fine-tuning will be around 20 minutes and with
fine-tuning, it will be around 3 mins. GCSFuse can facilitate faster download of
the model weights and reduces the time to startup inference server. You will see
good improvements with large models which have weights over several GBs.
