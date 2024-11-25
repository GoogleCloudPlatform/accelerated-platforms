# Data Preparation

A processed Flipkart product catalog is used as input data to generate prompts in preparation for fine-tuning. The prompts are generated using [Llama 3.1 on Vertex AI](https://console.cloud.google.com/vertex-ai/publishers/meta/model-garden/llama-3.1-405b-instruct-maas). The output is a data set that can be used to fine-tune the base model.

Depending on the infrastructure you provisioned, the data preparation step takes approximately 1 hour and 40 minutes.

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A bucket containing the processed data from the [Data Processing example](/use-cases/model-fine-tuning-pipeline/data-processing/ray/README.md)

## Preparation

- Accept Llama 3.1 on Vertex AI license agreement terms

  ```sh
  echo -e "\nhttps://console.cloud.google.com/vertex-ai/publishers/meta/model-garden/llama-3.1-405b-instruct-maas\n"
  ```

  1. Accept the license terms for the Llama 3.1 model
  1. On the Llama 3.1 on Vertex AI model card, click the blue `ENABLE` button

- Clone the repository and change directory to the guide directory

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

  > You should see the various variables populated with the information specific to your environment.

### Vertex AI OpenAI endpoint variables

- Set `VERTEX_REGION` to Google Cloud region to use for the Vertex AI API OpenAI endpoint calls

  ```
  VERTEX_REGION=us-central1
  ```

  > The Llama 3.1 on Vertex API is in preview, it is only available in `us-central1`

## Data Preparation (Optional)

To execute this scenario without going through the [Data Processing example](/use-cases/model-fine-tuning-pipeline/data-processing/ray/README.md), we have a processed dataset that you can use.

Select a path between **Full dataset** and **Smaller dataset (subset)**. The smaller dataset is a quicker way to experience the pipeline, but it will produce a less than ideal fine-tuned model.

- If you would like to use the **Smaller dataset (subset)**, set the variable below.

  ```shell
  DATASET_SUBSET=-subset
  ```

- Download the Hugging Face CLI library

  ```shell
  pip3 install -U "huggingface_hub[cli]==0.26.2"
  ```

- Download the processed dataset CSV file from Hugging Face and copy it into the GCS bucket

  ```shell
  PROCESSED_DATA_REPO=gcp-acp/flipkart-preprocessed${DATASET_SUBSET}

  ${HOME}/.local/bin/huggingface-cli download --repo-type dataset ${PROCESSED_DATA_REPO} --local-dir ./temp

  gcloud storage cp ./temp/flipkart.csv \
    gs://${MLP_DATA_BUCKET}/flipkart_preprocessed_dataset/flipkart.csv && \

  rm ./temp/flipkart.csv
  ```

## Build the container image

- Build the container image using Cloud Build and push the image to Artifact Registry

  ```
  cd src
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --substitutions _DESTINATION=${MLP_DATA_PREPARATION_IMAGE}
  cd ..
  ```

## Run the job

- Get credentials for the GKE cluster

  ```sh
  gcloud container fleet memberships get-credentials ${MLP_CLUSTER_NAME} --project ${MLP_PROJECT_ID}
  ```

- Configure the job

  | Variable            | Description                                                                                                   | Example                          |
  | ------------------- | ------------------------------------------------------------------------------------------------------------- | -------------------------------- |
  | DATASET_INPUT_PATH  | The folder path of where the preprocessed flipkart data resides                                               | flipkart_preprocessed_dataset    |
  | DATASET_INPUT_FILE  | The filename of the preprocessed flipkart data                                                                | flipkart.csv                     |
  | DATASET_OUTPUT_PATH | The folder path of where the generated output data set will reside. This path will be needed for fine-tuning. | dataset/output                   |
  | PROMPT_MODEL_ID     | The Vertex AI model for prompt generation                                                                     | meta/llama-3.1-70b-instruct-maas |

  ```sh
  DATASET_INPUT_PATH="flipkart_preprocessed_dataset"
  DATASET_INPUT_FILE="flipkart.csv"
  DATASET_OUTPUT_PATH="dataset/output"
  PROMPT_MODEL_ID="meta/llama-3.1-70b-instruct-maas"
  ```

  ```sh
  sed \
  -i -e "s|V_IMAGE_URL|${MLP_DATA_PREPARATION_IMAGE}|" \
  -i -e "s|V_KSA|${MLP_DATA_PREPARATION_KSA}|" \
  -i -e "s|V_PROJECT_ID|${MLP_PROJECT_ID}|" \
  -i -e "s|V_DATA_BUCKET|${MLP_DATA_BUCKET}|" \
  -i -e "s|V_DATASET_INPUT_PATH|${DATASET_INPUT_PATH}|" \
  -i -e "s|V_DATASET_INPUT_FILE|${DATASET_INPUT_FILE}|" \
  -i -e "s|V_DATASET_OUTPUT_PATH|${DATASET_OUTPUT_PATH}|" \
  -i -e "s|V_PROMPT_MODEL_ID|${PROMPT_MODEL_ID}|" \
  -i -e "s|V_REGION|${VERTEX_REGION}|" \
  manifests/job.yaml
  ```

- Create the job

  ```sh
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job.yaml
  ```

- Once the Job is completed, the prepared datasets are stored in Google Cloud Storage.

  ```sh
  gcloud storage ls gs://${MLP_DATA_BUCKET}/${DATASET_OUTPUT_PATH}
  ```

## Observability

By default, both GKE and the workloads you run expose metrics and logs in Google Cloud's Observability suite. You can view this information from the Cloud Observability console or the GKE Observability page.

For more information about infrastructure and application metrics, see [View observability metrics](https://cloud.google.com/kubernetes-engine/docs/how-to/view-observability-metrics).

You may want to perform the following tasks specifically for the data preparation use case described in this example.

### Monitor the job

In the Google Cloud console, go to the [Kubernetes Engine](https://console.cloud.google.com/kubernetes) page. Under the `Resource Management` menu on the left side, click `Workloads`. From there, you can filter the workloads by cluster name and namespaces. The `Observability` tab provides system level metric views such as `Overview`, `CPU`, and `Memory`. If you click the job name like `data-prep`, you can see the job details like the following page:

![monitor-job](/docs/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/images/monitor-job.png)

At the bottom of the page, you can see the status of the managed pods by the job. If your job is having trouble running, the `EVENTS` and `LOGS` tabs will provide more insight. You can also adjust the time windows or open the `Container logs` and `Audit logs` for additional information.

### View the logs

To gain insight into your workload quickly, you can filter and tweak the log queries to view only the relevant logs. You can do so in the `Logs Explorer`. One fast way to open the Logs Explorer and have the query pre-populated is to click the `View in Logs Explorer` button on the right side of the `LOGS` tab once you are on the `Job details` page.

When the link is opened, you should see something like the following:

![log-explorer-query](/docs/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/images/log-explorer-query.png)

The Logs Explorer provides many nice features besides tweaking your log query in the `Query` field. For example, if you want to know which steps the job has completed, you can run the following query based on [the source code](src/dataprep.py#L318):

```shell
resource.type="k8s_container"
resource.labels.location="us-central1"
resource.labels.namespace_name="ml-team"
jsonPayload.message = (
"***Job Start***" OR
"Configure signal handlers" OR
"Prepare context for model prompt" OR
"Generate Q & A according" OR
"Generate Prompts for Gemma IT model" OR
"Upload prepared dataset into GCS" OR
"***Job End***")
```

As another example, if you want to know how many prompts are generated in a specific time window, you can do something like the following:

- Look for the log entries from the code associated with the prompt generation. In this example, the `Content generated` log entry is produced each time a prompt is generated.
- You can click the `Similar entries`, which automatically updates the log query for you and lists all `Content generated` entries.
- Adjust the timeline in the middle of the page and zoom in/out. You will see how many log entries are ingested during a specific time window, such as 30 seconds. That number should be the same as the number of prompts generated by the code.

### Log Analytics

You can also use [Log Analytics](https://cloud.google.com/logging/docs/analyze/query-and-view) to analyze your logs. After it is enabled, you can run SQL queries to gain insight from the logs. The result can also be charted. For example, you can click the `Analyze results` link on the Logs Explorer page and open the Log Analytics page with a converted SQL query. The chart and table you view can also be added to a dashboard.

![log-analytics](/docs/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/images/log-analytics.png)

## Notes

The raw [pre-crawled public dataset](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products), [license](https://creativecommons.org/licenses/by-sa/4.0/).
