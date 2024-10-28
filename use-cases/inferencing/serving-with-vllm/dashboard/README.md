### Create a dashboard for Cloud Monitoring to view vLLM metrics

Cloud Monitoring provides an [importer](https://cloud.google.com/monitoring/dashboards/import-grafana-dashboards) that you can use to import dashboard files in the Grafana JSON format into Cloud Monitoring

*    Clone github repository

  ```sh
  cd
  git clone https://github.com/GoogleCloudPlatform/monitoring-dashboard-samples
  ```

*   Change to the directory for the dashboard importer:

  ```sh
  cd monitoring-dashboard-samples/scripts/dashboard-importer
  ```

The dashboard importer includes the following scripts:

- import.sh, which converts dashboards and optionally uploads the converted dashboards to Cloud Monitoring.
- upload.sh, which uploads the converted dashboards or any Monitoring dashboards to Cloud Monitoring. The import.sh script calls this script to do the upload.

*   Import the dashboard

  ```sh
  ./import.sh ${INFERENCE_DASHBOARD_DIR}/configs/grafana.json ${MLP_PROJECT_ID}
  ```

  When you use the import.sh script, you must specify the location of the Grafana dashboards to convert. The importer creates a directory that contains the converted dashboards and other information.

*   Go back to the infernece directory

  ```sh
  cd  ${INFERENCE_DIR}
  ```