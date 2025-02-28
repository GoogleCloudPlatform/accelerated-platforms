# RAG: Instruction tuned model

## Prerequisites

- This guide was developed to be run on the
  [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you
  are using a different environment the scripts and manifest will need to be
  modified for that environment.

## Preparation

- Clone the repository.

  ```shell
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```shell
  cd use-cases/rag-pipeline/instruction-tuned-model
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```shell
  cat ${MLP_ENVIRONMENT_FILE} && \
  set -o allexport && \
  source ${MLP_ENVIRONMENT_FILE} && \
  set +o allexport
  ```

  > You should see the various variables populated with the information specific
  > to your environment.

- Get credentials for the GKE cluster.

  ```shell
  gcloud container clusters get-credentials ${MLP_CLUSTER_NAME} \
  --dns-endpoint \
  --project=${MLP_PROJECT_ID} \
  --region=${MLP_REGION}
  ```

### HuggingFace access token

- Set `HF_TOKEN` to your HuggingFace access token. Go to
  https://huggingface.co/settings/tokens , click `Create new token`, provide a
  token name, select `Read` in token type and click `Create token`.

  ```shell
  HF_TOKEN=
  ```

- Create a Kubernetes secret with your HuggingFace token.

  ```shell
  kubectl create secret generic hf-secret \
  --from-literal=hf_api_token=${HF_TOKEN} \
  --dry-run=client -o yaml | kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply  -f -
  ```

## Deploy the model

- Create the deployment.

  ```
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/it-model-deployment.yaml
  ```

- Watch the deployment until it is ready and available.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_MODEL_OPS_NAMESPACE} get deployment/rag-it-model | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs  deployment/rag-it-model --tail 10"
  ```

  ```
  NAME           READY   UP-TO-DATE   AVAILABLE   AGE
  rag-it-model   1/1     1            1           XXXXX
  ```

## Verify the model

- Create the curl job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/curl.yaml
  ```

- Get the logs for the curl job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs --follow job/it-curl
  ```

  The output should be similar to:

  ```
  {"id":"chat-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX","object":"chat.completion","created":##########,"model":"google/gemma-2-2b-it","choices":[{"index":0,"message":{"role":"assistant","content":"You're in luck! There are tons of great cycling shorts for women out there. To help you find the perfect pair, I need a little more information about your needs and preferences. \n\n**Tell me about:**\n\n* **Your budget:** Are you looking for something affordable, mid-range, or high-end?\n* **Your riding style:** What type of cycling do you do? Road, mountain, gravel, triathlon, etc.?\n* **Your comfort priorities:** Do you prioritize chamois comfort, breathability, moisture-wicking, or something else?\n* **Your fit preferences:** Do you prefer a snug fit, a looser fit, or something in between?\n* **Your style preferences:** Do you want a specific color, pattern, or design?\n\n**Here are some popular brands known for their women's cycling shorts:**\n\n* **Specialized:** Known for their high-performance, technical shorts with excellent chamois.\n* **Pearl Izumi:** Offers a wide range of styles and features, including their popular \"Pro\" line.\n* **Castelli:** Italian brand known for their stylish and comfortable shorts.\n* **Rapha:** High-end brand with a focus on performance and style.\n* **","tool_calls":[]},"logprobs":null,"finish_reason":"length","stop_reason":null}],"usage":{"prompt_tokens":25,"total_tokens":281,"completion_tokens":256},"prompt_logprobs":null}
  ```
