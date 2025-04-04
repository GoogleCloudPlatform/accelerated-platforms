# MLflow Inference pipeline

## Why use MLflow ?

MLflow streamlines ML workflows with robust versioning and dependency
management. Its Model Registry tracks model iterations, ensuring reproducibility
and controlled deployments. Experiment Tracking captures all experiment details,
promoting transparency. Dependency tracking automates environment capture,
guaranteeing consistent deployments and eliminating environment-related errors.

Deploying MLflow on Google Kubernetes Engine (GKE) enhances production-grade ML
deployments. GKE's managed Kubernetes service simplifies cluster management,
allowing teams to focus on model development.

MLflow's versioning combined with GKE's scalable, managed environment creates a
powerful, efficient, and reliable platform for deploying and managing production
ML models. This synergy simplifies MLOps, enhances reproducibility, and ensures
consistent deployments.

# Mlflow deployment on GKE

In MLflow, the "artifact registry" that is primarily used for storing model
deployments is called the MLflow Model Registry; it acts as a centralized
repository to manage and track different versions of your machine learning
models, allowing you to easily deploy them to various environments while keeping
track of which version is being used where.

## Deployment steps for MLflow on GKE

Important: To complete this tutorial, you will need to delete the initial
experimental MLflow deployment that is part of MLPlayground.

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
  cd use-cases/mlflow-deployment/create-db
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

## Build the container image for create database job.

- Build the container image using Cloud Build and push the image to Artifact
  Registry

  ```shell
  cd src
  git restore cloudbuild.yaml
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --region ${MLP_REGION} \
  --substitutions _DESTINATION=${MLP_MLFLOW_DB_SETUP_IMAGE}
  cd -
  ```

  It takes approximately 2 minutes for the build to complete.

## Configure the create-database job

git restore manifests/job-create-database.yaml sed \
-i -e "s|V_DB_ADMIN_KSA|${MLP_DB_ADMIN_KSA}|" \
-i -e "s|V_MLFLOW_DB_SETUP_IMAGE|${MLP_MLFLOW_DB_SETUP_IMAGE}|"
\
-i -e "s|V_DB_INSTANCE_URI|${MLP_DB_INSTANCE_URI}|" \
manifests/job-create-database.yaml

## Run the create-database job

- Create the database creation job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/job-create-database.yaml
  ```

  It takes approximately 1 minute for the job to complete.

- Watch the job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} get job/create-database | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'
  echo '\nLogs(last 10 lines):'
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs job/create-database --tail 10"
  ```

  ```
  NAME                  STATUS     COMPLETIONS   DURATION   AGE
  create-database   Complete   1/1           XXXXX      XXXXX
  ```

  It takes approximately 1 minutes for the job to complete.

- Check logs for any errors.

```
kubectl logs  create-database-XXXX -n ml-team
```

```
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connection pool created", "timestamp": 1743724348.0579753, "level": "INFO", "runtime": 4981.638719}
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connecting to db 'postgres' as user 'wi-mlp-mlflow-prod-db-admin@gkebatchenv3a4ec43f.iam'", "timestamp": 1743724348.0581832, "level": "INFO", "runtime": 4981.846764}
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' dropped (if existed)", "timestamp": 1743724348.705331, "level": "INFO", "runtime": 5628.994754}
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' creation initiated", "timestamp": 1743724349.3212118, "level": "INFO", "runtime": 6244.875518}
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' creation verified", "timestamp": 1743724349.3237712, "level": "INFO", "runtime": 6247.434572}
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connector closed", "timestamp": 1743724349.3288069, "level": "INFO", "runtime": 6252.470507}
{"name": "__main__", "thread": 140149397920640, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' creation successful.", "timestamp": 1743724349.3289633, "level": "INFO", "runtime": 6252.626789}
```

- ML flow backend store

  Mlflow needs an artifact store to store the mlflow deployment artifacts. A GCS
  bucket has already been created as part of MLP Playground.

  Validate that this GCS bucket exists in your project.

  ```shell
  gcloud storage buckets describe gs://${MLP_MLFLOW_ARTIFACT_LOCATION}
  ```

## Build the MLflow container image:

- Build the container image using Cloud Build and push the image to Artifact
  Registry

  ```shell
  cd mlflow
  git restore cloudbuild.yaml
  sed -i -e "s|^serviceAccount:.*|serviceAccount: projects/${MLP_PROJECT_ID}/serviceAccounts/${MLP_BUILD_GSA}|" cloudbuild.yaml
  gcloud beta builds submit \
  --config cloudbuild.yaml \
  --gcs-source-staging-dir gs://${MLP_CLOUDBUILD_BUCKET}/source \
  --project ${MLP_PROJECT_ID} \
  --region ${MLP_REGION} \
  --substitutions _DESTINATION=${MLP_MLFLOW_DB_SETUP_IMAGE}
  cd -
  ```

## Deploy the image on the MLPlayground cluster.

```shell
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f manifests/deployment.yaml
```

It takes approximately 5 minutes for the deployment to complete.


## Check if the MLflow dashboard is available

```shelll


```