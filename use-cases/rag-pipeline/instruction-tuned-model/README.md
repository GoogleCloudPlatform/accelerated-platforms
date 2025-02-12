# Steps to deploy instruction tuned model

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.

## Preparation

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```sh
  cd use-cases/rag-pipeline/instruction-tuned-model
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

### HuggingFace access token

- Set `HF_TOKEN` to your HuggingFace access token. Go to
  https://huggingface.co/settings/tokens , click `Create new token` , provide a
  token name, select `Read` in token type and click `Create token`.

  ```
  HF_TOKEN=
  ```

- Create a Kubernetes secret with your HuggingFace token.

  ```sh
  kubectl create secret generic hf-secret \
  --from-literal=hf_api_token=${HF_TOKEN} \
  --dry-run=client -o yaml | kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply  -f -
  ```

## Deploy model

- Create the deployment.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/it-model-deployment.yaml
  ```

- Wait for the deployment to be ready.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} wait --for=condition=ready --timeout=900s pod -l app=rag-it-model
  ```

  When they deployment is ready you should see output similar to:

  ```output
  pod/rag-it-model-XXXXXXXXX-XXXXX condition met
  ```

- Verify the deployment with the curl job.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/curl.yaml
  ```

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/it-curl
  ```
