# vLLM Metrics

vLLM exposes a number of metrics that can be used to monitor the health of the system. These metrics are exposed via the `/metrics` endpoint on the vLLM OpenAI compatible API server. These metrics can be scraped using Google Managed Prometheus (GMP) and made available in [Cloud Metrics](https://console.cloud.google.com/monitoring/metrics-explorer). For more details, see [pod monitoring with Google managed prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus/setup-managed#gmp-pod-monitoring).

## Prerequisites

- This guide was developed to be run on the [playground AI/ML platform](/platforms/gke-aiml/playground/README.md). If you are using a different environment the scripts and manifest will need to be modified for that environment.
- A model is deployed using one of the vLLM guides
  - [Serving the mode using vLLM and GCSFuse](/use-cases/inferencing/serving/vllm/gcsfuse/README.md)
  - [Serving the mode using vLLM and HyperdiskML](/use-cases/inferencing/serving/vllm/hyperdiskML/README.md)
  - [Serving the mode using vLLM and Persistent Disk](/use-cases/inferencing/serving/vllm/persistent-disk/README.md)


## Preparation

- Clone the repository and change directory to the guide directory

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory

  ```
  cd use-cases/inferencing/serving/vllm/metrics
  METRICS_DIR=$(pwd)
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

## Deploy the PodMonitoring resource

- Configure the environment

  | Variable        | Description                                   | Example  |
  | --------------- | --------------------------------------------- | -------- |
  | ACCELERATOR     | Type of GPU accelerator used (l4, a100, h100) | l4       |
  | V_MODEL_STORAGE | Type of storage used for the model (gcs, pd)  | pd       |


  ```sh
  ACCELERATOR=l4
  MODEL_STORAGE=pd
  ```

- Configure the resource

  ```sh
  sed \
  -i -e "s|V_ACCELERATOR|${ACCELERATOR}|" \
  -i -e "s|V_MODEL_STORAGE|${MODEL_STORAGE}|" \
  manifests/pod-monitoring.yaml
  ```

- create the resource

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/pod-monitoring.yaml
  ```

## View the metrics

- Make several requests to your model to populate metrics

- Wait a minute for the metrics to populate, then you can view the metrics in the Metrics explorer
  - Go to the [Metrics explorer](https://console.cloud.google.com/monitoring/metrics-explorer)
  - Click the **Select a metric** dropdown near the upper left of the screen
  - Select **Prometheus Target**
  - Select **Vllm**, you should now see a list of the available metrics.
  - Select **Prometheus/vllm:avg_generation_throughput_toks_per_s/gauge**
  - Click **Apply**
  - Click **Add filter** in the **Filter** text box
  - Under **Resource labels** select **cluster**
  - For the **value** select the name of your cluster
  - You should now see the metrics for your cluster

## Create a dashboard

Cloud Monitoring provides an [importer](https://cloud.google.com/monitoring/dashboards/import-grafana-dashboards) that you can use to import dashboard files in the Grafana JSON format into Cloud Monitoring

- Clone the repository

  ```sh
  git clone https://github.com/GoogleCloudPlatform/monitoring-dashboard-samples
  ```

- Change to the directory for the dashboard importer:

  ```sh
  cd monitoring-dashboard-samples/scripts/dashboard-importer
  ```

- The dashboard importer includes the following scripts:

  - `import.sh`, which converts dashboards and optionally uploads the converted dashboards to Cloud Monitoring.
  - `upload.sh`, which uploads the converted dashboards or any Monitoring dashboards to Cloud Monitoring. The `import.sh` script calls this script to do the upload.

- Import the dashboard

  ```sh
  ./import.sh ${METRICS_DIR}/grafana/vllm.json ${MLP_PROJECT_ID}
  ```

- A link to the dashboard will be output by the script, open the link to view the dashboard
