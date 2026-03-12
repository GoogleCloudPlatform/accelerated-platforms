# Data Preparation

A processed Flipkart product catalog is used as input data to generate prompts
in preparation for fine-tuning. The prompts are generated using
[Llama 3.1 on Vertex AI](https://console.cloud.google.com/vertex-ai/publishers/meta/model-garden/llama-3.1-405b-instruct-maas).
The output is a data set that can be used to fine-tune the base model.

Depending on the infrastructure you provisioned, the data preparation step takes
approximately 1 hour and 40 minutes.

## Pre-requisites

- The
  [GKE Training reference implementation](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
  is deployed and configured in your repository.

  - The
    [model_fine_tuning](/platforms/gke/base/use-cases/training-ref-arch/terraform/model_fine_tuning/README.md)
    terraservice is deployed and configured.

## Before you begin

- A bucket containing the processed data from the
  [Distributed Data Processing with Ray on GKE](/docs/platforms/gke/base/use-cases/training-ref-arch/model-fine-tuning/data-preparation.md)

- Ensure that that Llama 3.1 on Vertex API is available in your regions.

## Preparation

> [!NOTE]  
> This guide is designed to be run on
> [Cloud Shell](https://cloud.google.com/shell) as it has all of the most of the
> required tools preinstalled.

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/_shared_config/scripts/set_environment_variables.sh"
  ```

- Accept Llama 3.1 on Vertex AI license agreement terms

  ```shell
  echo -e "\nhttps://console.cloud.google.com/vertex-ai/publishers/meta/model-garden/llama-3.1-405b-instruct-maas\n"
  ```

  1. Accept the license terms for the Llama 3.1 model
  1. On the Llama 3.1 on Vertex AI model card, click the blue `ENABLE` button

## Build the container image

- Build the container image using Cloud Build and push the image to Artifact
  Registry

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/model_fine_tuning/images/data_preparation && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Run the job

- Configure the job

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/data-preparation/gemma-it/configure.sh"
  ```

- Create the job

  ```shell
  kubectl --namespace=${mft_kubernetes_namespace} apply --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/data-preparation/gemma-it/job.yaml"
  ```

- Once the Job is completed, the prepared datasets are stored in Google Cloud
  Storage.

  ```sh
  gcloud storage ls gs://${mft_data_bucket_name}/dataset/output
  ```

- Delete the job.

  ```sh
  kubectl --namespace=${mft_kubernetes_namespace} delete --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/data-preparation/gemma-it/job.yaml"
  ```

## Observability

By default, both GKE and the workloads you run expose metrics and logs in Google
Cloud's Observability suite. You can view this information from the Cloud
Observability console or the GKE Observability page.

For more information about infrastructure and application metrics, see
[View observability metrics](https://cloud.google.com/kubernetes-engine/docs/how-to/view-observability-metrics).

You may want to perform the following tasks specifically for the data
preparation use case described in this example.

### Monitor the job

In the Google Cloud console, go to the
[Kubernetes Engine](https://console.cloud.google.com/kubernetes) page. Under the
`Resource Management` menu on the left side, click `Workloads`. From there, you
can filter the workloads by cluster name and namespaces. The `Observability` tab
provides system level metric views such as `Overview`, `CPU`, and `Memory`. If
you click the job name like `data-prep`, you can see the job details like the
following page:

![monitor-job](/docs/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/images/monitor-job.png)

At the bottom of the page, you can see the status of the managed pods by the
job. If your job is having trouble running, the `EVENTS` and `LOGS` tabs will
provide more insight. You can also adjust the time windows or open the
`Container logs` and `Audit logs` for additional information.

### View the logs

To gain insight into your workload quickly, you can filter and tweak the log
queries to view only the relevant logs. You can do so in the `Logs Explorer`.
One fast way to open the Logs Explorer and have the query pre-populated is to
click the `View in Logs Explorer` button on the right side of the `LOGS` tab
once you are on the `Job details` page.

When the link is opened, you should see something like the following:

![log-explorer-query](/docs/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/images/log-explorer-query.png)

The Logs Explorer provides many nice features besides tweaking your log query in
the `Query` field. For example, if you want to know which steps the job has
completed, you can run the following query based on
[the source code](src/dataprep.py#L318):

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

As another example, if you want to know how many prompts are generated in a
specific time window, you can do something like the following:

- Look for the log entries from the code associated with the prompt generation.
  In this example, the `Content generated` log entry is produced each time a
  prompt is generated.
- You can click the `Similar entries`, which automatically updates the log query
  for you and lists all `Content generated` entries.
- Adjust the timeline in the middle of the page and zoom in/out. You will see
  how many log entries are ingested during a specific time window, such as 30
  seconds. That number should be the same as the number of prompts generated by
  the code.

### Log Analytics

You can also use
[Log Analytics](https://cloud.google.com/logging/docs/analyze/query-and-view) to
analyze your logs. After it is enabled, you can run SQL queries to gain insight
from the logs. The result can also be charted. For example, you can click the
`Analyze results` link on the Logs Explorer page and open the Log Analytics page
with a converted SQL query. The chart and table you view can also be added to a
dashboard.

![log-analytics](/docs/use-cases/model-fine-tuning-pipeline/data-preparation/gemma-it/images/log-analytics.png)

## Notes

The raw
[pre-crawled public dataset](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products),
[license](https://creativecommons.org/licenses/by-sa/4.0/).
