# GCS storage optimization

This guide will demonstrate two different methods to deploy the Llama 70B model
for inference using
[Cloud Storage FUSE](https://cloud.google.com/storage/docs/cloud-storage-fuse/overview)
via the Google Kubernetes Engine (GKE) Cloud Storage FUSE CSI driver. The first
method uses a standard, "flat" GCS bucket to store the model. The second method
utilizes a
[hierarchical namespace](https://cloud.google.com/storage/docs/hns-overview) GCS
bucket and tuned configuration.

> Note : By default, a GCS bucket is created as flat.

This guide aims to show how to improve model load time and pod startup time by
using tuned configurations with Cloud Storage FUSE.

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
  cd use-cases/inferencing/cost-optimization/gcsfuse/
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```sh
  set -o allexport
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  set +o allexport
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster.

  ```sh
  gcloud container clusters get-credentials ${MLP_CLUSTER_NAME} \
  --dns-endpoint \
  --location=${MLP_REGION} \
  --project=${MLP_PROJECT_ID}
  ```

- Configure the environment.

  | Variable      | Description                                                                    | Example                |
  | ------------- | ------------------------------------------------------------------------------ | ---------------------- |
  | ACCELERATOR   | Type of GPU accelerator to use (a100, h100, l4)                                | a100                   |
  | MODEL_NAME    | The name of the model folder in the root of the GCS model bucket               | meta-llama             |
  | MODEL_VERSION | The name of the version folder inside the model folder of the GCS model bucket | Llama-3.3-70B-Instruct |

  ```sh
  set -o nounset
  export ACCELERATOR="a100"
  export MODEL_NAME="meta-llama"
  export MODEL_VERSION="Llama-3.3-70B-Instruct"
  export VLLM_IMAGE_NAME="vllm/vllm-openai:v0.6.6.post1"
  set +o nounset
  ```

## Serve the model with vLLM with no tuning

- Configure the deployment.

  ```
  git restore manifests/model-deployment-${ACCELERATOR}-dws.yaml
  envsubst < manifests/model-deployment-${ACCELERATOR}-dws.yaml | sponge manifests/model-deployment-${ACCELERATOR}-dws.yaml
  ```

  > Ensure there are no bash: <ENVIRONMENT_VARIABLE> unbound variable error
  > messages.

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
  watch -n 5 kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get provisioningrequest ${ACCELERATOR}-storage-benchmark
  ```

- When the deployment has started, watch the it until it is ready and available.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/vllm-openai-gcs-llama33-70b-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 20+ minutes for the deployment to be ready and available.

  ```
  NAME                              READY   UP-TO-DATE   AVAILABLE    AGE
  vllm-openai-gcs-llama33-70b-a100  1/1     1            1           XXXXX
  ```

## Calculate pod startup time

- Run the following commands to get the model load time in seconds

  ```sh
  POD_NAME=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods -o json | jq -r --arg accelerator "$ACCELERATOR" ".items[] | select(.metadata.name | contains(\"vllm-openai-gcs-llama33-70b-$accelerator\")) | .metadata.name"`

  BEGIN_MODEL_DOWNLOAD_TIME=`kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} logs ${POD_NAME} -c "inference-server" | grep "^INFO.*Starting to load model"  | head -n 1 | awk '{print $2" "$3}' | xargs -I {} date -d "$(date +%Y)-{}" +%s%3N`

  ENDING_MODEL_DOWNLOAD_TIME=`kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} logs ${POD_NAME} -c "inference-server" | grep "^INFO.*Loading model weights took" | head -n 1 | awk '{print $2" "$3}' | xargs -I {} date -d "$(date +%Y)-{}" +%s%3N`

  MODEL_LOAD_TIME_WITHOUT_TUNING=$(((ENDING_MODEL_DOWNLOAD_TIME - BEGIN_MODEL_DOWNLOAD_TIME)/1000 ))

  echo "MODEL LOAD TIME WITHOUT TUNING - ${MODEL_LOAD_TIME_WITHOUT_TUNING}s"
  ```

  > Loading llama 70B model with GCSFuse and no tuning will typically take
  > around 1200 seconds.

- Run the following commands to get the pod startup time in seconds. This is the
  time taken by the pod to change from `PodScheduled` to `Ready` status.

  ```sh
  POD_SCHEDULED_TIME=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME" -o json | jq -r '.status.conditions[] | select(.type == "PodScheduled") | .lastTransitionTime' | date -f - +%s%3N`

  POD_READY_TIME=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME" -o json | jq -r '.status.conditions[] | select(.type == "Ready") | .lastTransitionTime' | date -f - +%s%3N`

  POD_STARTUP_TIME_WITHOUT_TUNING=$(((POD_READY_TIME - POD_SCHEDULED_TIME)/1000 ))

  echo "POD STARTUP TIME WITHOUT TUNING - ${POD_STARTUP_TIME_WITHOUT_TUNING}s"
  ```

## Serve the model with vLLM with tuning

- Configure the deployment

  ```
  git restore manifests/model-deployment-tuned-${ACCELERATOR}-dws.yaml
  envsubst < manifests/model-deployment-tuned-${ACCELERATOR}-dws.yaml | sponge manifests/model-deployment-tuned-${ACCELERATOR}-dws.yaml
  ```

  > Ensure there are no bash: <ENVIRONMENT_VARIABLE> unbound variable error
  > messages.

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

  MODEL_LOAD_TIME_WITH_TUNING=$(((ENDING_MODEL_DOWNLOAD_TIME_TUNED - BEGIN_MODEL_DOWNLOAD_TIME_TUNED)/1000 ))

  echo "MODEL LOAD TIME WITH TUNING - ${MODEL_LOAD_TIME_WITH_TUNING}s"
  ```

  > Loading llama 70B model with GCSFuse with tuned configurations will
  > typically take around 35 seconds.

- Run the following commands to get the pod startup time in seconds. This is the
  time taken by the pod to change from `PodScheduled` to `Ready` status.

  ```sh
  POD_SCHEDULED_TIME_TUNED=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME_TUNED" -o json | jq -r '.status.conditions[] | select(.type == "PodScheduled") | .lastTransitionTime' | date -f - +%s%3N`

  POD_READY_TIME_TUNED=`kubectl --namespace "${MLP_MODEL_SERVE_NAMESPACE}" get pods "$POD_NAME_TUNED" -o json | jq -r '.status.conditions[] | select(.type == "Ready") | .lastTransitionTime' | date -f - +%s%3N`

  POD_STARTUP_TIME_WITH_TUNING=$(((POD_READY_TIME_TUNED - POD_SCHEDULED_TIME_TUNED)/1000 ))

  echo "POD STARTUP TIME WITH TUNING - ${POD_STARTUP_TIME_WITH_TUNING}s"
  ```

## Conclusion

Look at the pod startup time with and without tuning by running these commands
in cloudShell:

```sh
echo $POD_STARTUP_TIME_WITHOUT_TUNING

echo $POD_STARTUP_TIME_WITH_TUNING
```

The pod startup time is approximately 20 minutes, but with tuning it can be
reduced to around 3 minutes. GCSFuse can further decrease startup time by
enabling faster downloads of model weights, which is especially beneficial for
large models with weights exceeding several GBs.
