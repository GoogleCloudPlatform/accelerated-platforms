# vLLM Metrics

vLLM exposes a number of metrics that can be used to monitor the health of the system. These metrics are exposed via the `/metrics` endpoint on the vLLM OpenAI compatible API server. These metrics can be scraped using Google Managed Prometheus (GMP) and made available in [Cloud Metrics](https://console.cloud.google.com/monitoring/metrics-explorer). For more details, see [pod monitoring with Google managed prometheus](https://cloud.google.com/stackdriver/docs/managed-prometheus/setup-managed#gmp-pod-monitoring).

## Prerequisites

- A model is deployed using one of the vLLM guides
  - [Distributed Inference and Serving with vLLM using GCSFuse](/use-cases/inferencing/serving/vllm/gcsfuse/README.md)
  - [Distributed Inference and Serving with vLLM using Hyperdisk ML](/use-cases/inferencing/serving/vllm/hyperdisk-ml/README.md)
  - [Distributed Inference and Serving with vLLM using Persistent Disk](/use-cases/inferencing/serving/vllm/persistent-disk/README.md)

## Preparation

- Clone the repository and change directory to the guide directory.

  ```sh
  git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
  cd accelerated-platforms
  ```

- Change directory to the guide directory.

  ```
  cd use-cases/inferencing/serving/vllm/metrics
  METRICS_DIR=$(pwd)
  ```

- Ensure that your `MLP_ENVIRONMENT_FILE` is configured.

  ```sh
  cat ${MLP_ENVIRONMENT_FILE} && \
  source ${MLP_ENVIRONMENT_FILE}
  ```

## Deploy the PodMonitoring resource

- Configure the environment.

  > Set the environment variables based on the accelerator and model storage type used to serve the model.
  > The default values below are set for NVIDIA L4 GPUs and persistent disk.

  | Variable      | Description                                        | Example |
  | ------------- | -------------------------------------------------- | ------- |
  | ACCELERATOR   | Type of GPU accelerator used (a100, h100, l4)      | l4      |
  | MODEL_STORAGE | Type of storage used for the model (gcs, hdml, pd) | pd      |

  ```sh
  ACCELERATOR="l4"
  MODEL_STORAGE="pd"
  ```

- Configure the PodMonitoring resource.

  ```sh
  git restore manifests/pod-monitoring.yaml
  sed \
  -i -e "s|V_ACCELERATOR|${ACCELERATOR}|" \
  -i -e "s|V_MODEL_STORAGE|${MODEL_STORAGE}|" \
  manifests/pod-monitoring.yaml
  ```

- Create the PodMonitoring resource.

  ```sh
  kubectl --namespace ${MLP_MODEL_SERVE_NAMESPACE} apply -f manifests/pod-monitoring.yaml
  ```

  ```
  podmonitoring.monitoring.googleapis.com/vllm-inference-XXX-XXX created
  ```

## View the metrics

- Make several requests to your model to populate metrics, you can use the previously deployed chat interface.

  ```sh
  echo -e "\nGradio chat interface: ${MLP_GRADIO_MODEL_OPS_ENDPOINT}\n"
  ```

- Wait for the metrics to populate, then they can be viewed in the Metrics explorer.

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

Cloud Monitoring provides an [importer](https://cloud.google.com/monitoring/dashboards/import-grafana-dashboards) that you can use to import dashboard files in the Grafana JSON format into Cloud Monitoring.

- Clone the repository.

  ```sh
  git clone https://github.com/GoogleCloudPlatform/monitoring-dashboard-samples
  ```

- Change to the directory for the dashboard importer.

  ```sh
  cd monitoring-dashboard-samples/scripts/dashboard-importer
  ```

- The dashboard importer includes the following scripts:

  - `import.sh`, which converts dashboards and optionally uploads the converted dashboards to Cloud Monitoring.
  - `upload.sh`, which uploads the converted dashboards or any Monitoring dashboards to Cloud Monitoring. The `import.sh` script calls this script to do the upload.

- Import the dashboard. When prompted, answer `y`

  ```sh
  ./import.sh ${METRICS_DIR}/grafana/vllm.json ${MLP_PROJECT_ID}
  ```

  ```
  Converting: vLLM
  ✓ vLLM converted successfully

  Conversion of /XXXXXXXXXX/XXXXXXXXXX/XXXXXXXXXX/accelerated-platforms/use-cases/inferencing/serving/vllm/metrics/grafana/vllm.json complete. Conversion Report located at: reports/YYYY-MM-DD/HH:MM:SS/report.json


  To upload these dashboard(s) manually, you can run:
  ./upload.sh reports/YYYY-MM-DD/HH:MM:SS/ <PROJECT_ID>

  Conversion complete. Proceeding to upload...

  Now running: ./upload.sh reports/YYYY-MM-DD/HH:MM:SS/ <PROJECT_ID>

  Uploading 1 dashboard(s) from a directory with the following args:
  Directory: reports/YYYY-MM-DD/HH:MM:SS/
  Project: <PROJECT_ID>

  The following are your dashboards:
  - vllm.json

  Would you like to continue? (y/n) y
  ```

  ```
  ✓ vllm.json successfully uploaded:
  https://console.cloud.google.com/monitoring/dashboards/builder/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX?project=<PROJECT_ID>

  Upload log created in reports/YYYY-MM-DD/HH:MM:SS/upload_HH:MM:SS.txt

  Need to troubleshoot? Please visit:
  https://github.com/GoogleCloudPlatform/monitoring-dashboard-samples/tree/master/scripts/dashboard-importer/README.md#troubleshooting
  ```

- A link to the dashboard will be output by the script, or navigate to the [Monitoring Dashboards](https://console.cloud.google.com/monitoring/dashboards) page in the console and look for the **vLLM** Custom dashboard.

## What's next

- [vLLM autoscaling with horizontal pod autoscaling (HPA)](/use-cases/inferencing/serving/vllm/autoscaling/README.md)
- [Benchmarking with Locust](/use-cases/inferencing/benchmark/README.md)
- [Batch inference on GKE](/use-cases/inferencing/batch-inference/README.md)
