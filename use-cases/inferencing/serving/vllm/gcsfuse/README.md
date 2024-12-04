# Distributed Inference and Serving with vLLM using GCS

This guide demonstrates how to serve a model with vllm using GCS. By the end of this guide, you should be able to perform the following steps:

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
  cd use-cases/inferencing/serving/vllm/gcsfuse
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

- Get credentials for the GKE cluster..

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

## Serve the model with vLLM

- Configure the environment.

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
  -i -e "s|V_IMAGE_NAME|${VLLM_IMAGE_NAME}|" \
  -i -e "s|V_KSA|${MLP_MODEL_SERVE_KSA}|" \
  manifests/model-deployment-${ACCELERATOR}.yaml
  ```

- Create the deployment.

  ```
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/model-deployment-${ACCELERATOR}.yaml
  ```

  ```
  deployment.apps/vllm-openai-gcs-l4 created
  service/vllm-openai-gcs-l4 created
  ```

- Watch the deployment until it is ready and available.

  ```sh
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} get deployment/vllm-openai-gcs-${ACCELERATOR} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  It can take 5+ minutes for the deployment to be ready and available.

  ```
  NAME                 READY   UP-TO-DATE   AVAILABLE   AGE
  vllm-openai-gcs-l4   1/1     1            1           XXX
  ```

## Serve the model through a web chat interface

- Configure the deployment

  ```sh
  git restore manifests/gradio.yaml
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
