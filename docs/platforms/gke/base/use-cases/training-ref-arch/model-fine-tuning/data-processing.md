# Distributed Data Processing with Ray on GKE

## Dataset

[This](https://www.kaggle.com/datasets/PromptCloudHQ/flipkart-products) is a
pre-crawled public dataset,
[license](https://creativecommons.org/licenses/by-sa/4.0/), taken as a subset of
a bigger dataset (more than 5.8 million products) that was created by extracting
data from [Flipkart](https://www.flipkart.com/), a leading Indian eCommerce
store.

## Architecture

![data-processing](/docs/use-cases/model-fine-tuning-pipeline/data-processing/ray/images/data-processing-ray-workflow.png)

## Data processing steps

The dataset has product information such as id, name, brand, description, image
urls, product specifications.

In the following section, you will run a GKE job to perform data preprocessing.
The GKE job will run a python script named `preprocessing_finetuning.py` that
does the following:

- Read the csv from Cloud Storage
- Clean up the product description text
- Extract image urls, validate and download the images into Google Cloud Storage
- Cleanup & extract attributes as key-value pairs
- Uploads the processed data as a csv file to Google Cloud Storage

The data processing step takes approximately 18-20 minutes.

## Pre-requisites

- The
  [GKE Training reference implementation](/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)
  is deployed and configured in your repository.

  - The
    [model_fine_tuning](/platforms/gke/base/use-cases/training-ref-arch/terraform/model_fine_tuning/README.md)
    terraservice is deployed and configured.

## Before you begin

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

- Ensure your
  [Kaggle API token](/platforms/gke/base/core/kaggle/initialize/README.md) has
  been added to Secret Manager.

## Preparation

> [!NOTE]  
> This guide is designed to be run on
> [Cloud Shell](https://cloud.google.com/shell) as it has all of the most of the
> required tools preinstalled.

### Download the dataset

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/_shared_config/scripts/set_environment_variables.sh"
  ```

- Install the `kaggle` API package.

  ```shell
  pip install --upgrade "kaggle==1.8.2"
  ```

- Download the dataset from Kaggle.

  ```shell
  kaggle datasets download \
  --unzip \
  --wp \
  PromptCloudHQ/flipkart-products
  ```

- Upload the dataset to the Google Cloud Storage bucket.

  ```shell
  gcloud storage cp "flipkart_com-ecommerce_sample.csv" "gs://${kaggle_bucket_name}/datasets/PromptCloudHQ/flipkart-products/flipkart_com-ecommerce_sample.csv" && \
  rm flipkart_com-ecommerce_sample.csv
  ```

- Verify the dataset CSV file.

  ```shell
  gcloud storage ls --long "gs://${kaggle_bucket_name}/datasets/PromptCloudHQ/flipkart-products/flipkart_com-ecommerce_sample.csv"
  ```

- Verify the Hugging Face Hub **Read** access token secret.

  ```shell
  secret_version_found=$(gcloud secrets versions list "${huggingface_hub_access_token_read_secret_manager_secret_name}" --project="${huggingface_secret_manager_project_id}" 2>/dev/null | grep "enabled" | wc -l)
  echo
  if [[ ${secret_version_found} == 0 ]]; then
    echo "ERROR: Hugging Face Hub read token secret '${huggingface_hub_access_token_read_secret_manager_secret_name}' version is missing or not enabled! Please add the token to the secret."
  else
    echo "Hugging Face Hub read token secret '${huggingface_hub_access_token_read_secret_manager_secret_name}' version found."
  fi
  ```

- Verify Check Kaggle API token secret.

  ```shell
  secret_version_found=$(gcloud secrets versions list "${kaggle_api_token_secret_manager_secret_name}" --project="${kaggle_secret_manager_project_id}" 2>/dev/null | grep "enabled" | wc -l)
  echo
  if [[ ${secret_version_found} == 0 ]]; then
    echo "ERROR: Kaggle API token secret '${kaggle_api_token_secret_manager_secret_name}' version is missing or not enabled! Please add the token to the secret."
  else
    echo "Kaggle API token secret '${kaggle_api_token_secret_manager_secret_name}' version found."
  fi
  ```

- Verify dataset CSV file.

  ```shell
  gcloud storage ls gs://${kaggle_bucket_name}/datasets/PromptCloudHQ/flipkart-products/flipkart_com-ecommerce_sample.csv
  ```

- Get credentials for the GKE cluster

  ```shell
  ${cluster_credentials_command}
  ```

## Build the container image

- Build container image using Cloud Build and push the image to Artifact
  Registry

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/terraform/model_fine_tuning/images/data_processing && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Run the job

- Configure the job

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/data-processing/ray/configure.sh"
  ```

- Create the job

  ```shell
  kubectl --namespace=${mft_kubernetes_namespace} apply --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/data-processing/ray/job.yaml"
  ```

- Monitor the execution in Ray Dashboard. You can run the following command to
  get the dashboard endpoint:

  ```shell
  echo -e "\n${mft_kubernetes_namespace} Ray dashboard: ${mft_endpoint_ray_dashboard_url}\n"
  ```

- From the Ray Dashboard, view the following about the jobs:

  - Jobs -> Running Job ID
    - See the Tasks/actors overview for Running jobs
    - See the Task Table for a detailed view of task and assigned node(s)
  - Cluster -> Node List
    - See the Ray actors running on the worker process

- You can check the job status from the GKE console or
  [query the logs](#log-query-sample) in the
  [Logs Explorer](https://console.cloud.google.com/logs). Once the Job is
  completed, both the prepared dataset as a CSV and the images are stored in
  Google Cloud Storage.

  ```shell
  gcloud storage ls gs://${mft_data_bucket_name}/flipkart_preprocessed_dataset/flipkart.csv
  gcloud storage ls gs://${mft_data_bucket_name}/flipkart_images
  ```

> For additional information about developing using this codebase see the
> [Developer Guide](DEVELOPER.md)

> For additional information about converting you code from a notebook to run as
> a Job on GKE see the [Conversion Guide](CONVERSION.md)

- Delete the job.

  ```sh
  kubectl --namespace=${mft_kubernetes_namespace} delete --filename="${ACP_REPO_DIR}/platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/model-fine-tuning/data-processing/ray/job.yaml"
  ```

## Observability

By default, both GKE and the workloads you run expose metrics and logs in Google
Cloud's Observability suite. You can view that information either from the Cloud
Observability console or the GKE Observability page.

For more information about infrastructure and application metrics, see
[View observability metrics](https://cloud.google.com/kubernetes-engine/docs/how-to/view-observability-metrics).

Specifically for the data processing use case described in this example, you can
perform observability using both the **Ray Dashboard** (for real-time cluster
and job metrics) and **Google Cloud Logging** (for log searching and SQL
analytics).

### Ray Dashboard

The
[Ray Dashboard](https://docs.ray.io/en/latest/ray-observability/getting-started.html)
provides real-time observability into Ray cluster resources, submitted jobs,
actor pools, and Ray Data streaming execution.

#### Accessing the Dashboard

Run the following command to print the Ray Dashboard endpoint URL:

```shell
echo -e "\n${mft_kubernetes_namespace} Ray dashboard: ${mft_ray_dashboard_namespace_endpoint}\n"
```

Alternatively, you can port-forward the service to your local machine:

```shell
kubectl --namespace ${mft_kubernetes_namespace} port-forward svc/ray-cluster-kuberay-head-svc 8265:8265
```

#### Key Observability Views

- **Jobs Tab**: Monitor active and completed Ray Job submissions, view
  entrypoint status (`SUCCEEDED`, `RUNNING`), duration, and tail live driver
  logs.
- **Ray Data Tab**: Visualize the dataset execution graph (`ReadCSV` ->
  `MapBatches` -> `Write`), monitor operator throughput, and check object store
  memory usage.
- **Actors Tab**: Inspect the `PreprocessingActor` pool state, worker node
  placement, and active worker tasks.
- **Cluster Tab**: View real-time CPU, RAM, and Object Store Memory utilization
  across Head and Worker nodes.

### Cloud Logging

#### Log query sample

In the Google Cloud console, go to the
[Logs Explorer](https://console.cloud.google.com/logs) page to run your queries.

- Find when the data processing job started and finished. You may need to adjust
  the time window in the UI or use
  [timestamp](https://cloud.google.com/logging/docs/view/logging-query-language)
  in the query:

  ```
  labels."k8s-pod/app"="data-processing"
  resource.type="k8s_container"
  "Started" OR "Finished"
  severity=INFO
  ```

  ![Logs Explorer - Job Started/Finished](/docs/use-cases/model-fine-tuning-pipeline/data-processing/ray/images/logs-explorer-started-finished.png)

- Find all error logs for the job:

  ```
  labels."k8s-pod/app"="data-processing"
  resource.type="k8s_container"
  severity=ERROR
  ```

- Search for specific errors from the `textPayload` using a regex expression:

  ```
  labels."k8s-pod/app"="data-processing"
  resource.type="k8s_container"
  textPayload =~ "WARNING - ray_worker_node_id.+Failed to (download|upload) image"
  ```

  ![Logs Explorer - Failed Image Downloads](/docs/use-cases/model-fine-tuning-pipeline/data-processing/ray/images/logs-explorer-failed-downloads.png)

You can narrow down the results by adding extra filters, such as using
additional labels. For more GKE query samples, you can read
[Kubernetes-related queries](https://cloud.google.com/logging/docs/view/query-library#kubernetes-filters).


### Log Analytics

You can also use
[Log Analytics](https://cloud.google.com/logging/docs/log-analytics#analytics)
to
[analyze your logs](<(https://cloud.google.com/logging/docs/analyze/query-and-view)>).
If your log buckets are not upgraded for Log Analytics, you need to upgrade them
first. After the log buckets are upgraded, you can run SQL queries to gain
insight from the newly ingested logs. The query results can also be charted. For
example, the following query returns the `Image not found` error and chart the
result:

```sql
WITH
  logs AS (
  SELECT
    *
  FROM
    `[Your Project Id].global._Default._AllLogs` )
SELECT
  timestamp,
  severity,
  text_payload,
  proto_payload,
  json_payload
FROM
  logs
WHERE
  SAFE.STRING(logs.labels["k8s-pod/app"]) = "data-processing"
  AND logs.resource.type= "k8s_container"
  AND logs.text_payload IS NOT NULL
  AND REGEXP_CONTAINS(logs.text_payload, "WARNING - ray_worker_node_id.+Failed to (download|upload) image")
ORDER BY
  timestamp DESC,
  insert_id DESC
LIMIT
  10000
```

You should see output like the following:
![use-log-based-metrics](/docs/use-cases/model-fine-tuning-pipeline/data-processing/ray/images/log-analytics-data-processing.png)
