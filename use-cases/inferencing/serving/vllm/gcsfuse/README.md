# Distributed Inferencing on vLLM using GCS

This guide demonstrates how to serve a model with vllm using GCS. By the end of this guide, you should be able to perform the following steps:

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
  cd use-cases/inferencing/serving/vllm/gcsfuse
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

## Serve the model with vLLM

- Configure the environment

  | Variable      | Description                                                                    | Example      |
  | ------------- | ------------------------------------------------------------------------------ | ------------ |
  | ACCELERATOR   | Type of GPU accelerator to use (a100, h100, l4)                                | l4           |
  | MODEL_NAME    | The name of the model folder in the root of the GCS model bucket               | model-gemma2 |
  | MODEL_VERSION | The name of the version folder inside the model folder of the GCS model bucket | experiment   |

  ```sh
  ACCELERATOR="l4"
  MODEL_NAME="model-gemma2"
  MODEL_VERSION="experiment"
  ```

- Configure the deployment

  ```
  VLLM_IMAGE_NAME="vllm/vllm-openai:v0.6.3.post1"
  ```

  ```sh
  sed \
  -i -e "s|V_MODEL_BUCKET|${MLP_MODEL_BUCKET}|" \
  -i -e "s|V_MODEL_NAME|${MODEL_NAME}|" \
  -i -e "s|V_MODEL_VERSION|${MODEL_VERSION}|" \
  -i -e "s|V_IMAGE_NAME|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
  manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Wait for the deployment to be ready

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} wait --for=condition=ready --timeout=900s pod --selector app=vllm-openai-gcs-${ACCELERATOR}
  ```

## Serve the model through a web chat interface

- Configure the deployment

  ```sh
  sed \
  -i -e "s|V_ACCELERATOR|${ACCELERATOR}|g" \
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

You can configure Horizontal Pod Autoscaling to scale your inference deployment based on relevant metrics. Follow the instructions in the [vLLM autoscaling with horizontal pod autoscaling (HPA)](/use-cases/inferencing/serving/vllm/autoscaling/README.md) guide to scale your deployed model.

## Run a benchmark for inference

The model is ready to run the benchmark for inference job, follow [Benchmarking with Locust](/use-cases/inferencing/benchmark/README.md) to run inference benchmarking on the

## Run Batch inference on GKE

Once a model has completed fine-tuning and is deployed on GKE , you can run batch inference on it. Follow the instructions in [batch-inference readme](/use-cases/inferencing/batch-inference/README.md) to run batch inference.
