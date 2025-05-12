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
  cd use-cases/mlflow-inference-pipeline/mlflow-deployment/
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
  cd create-db/src
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

```shell
set -o nounset
export DB_ADMIN_KSA="${MLP_DB_ADMIN_KSA}"
export DB_INSTANCE_URI= "${MLP_DB_INSTANCE_URI}"
export DB_USER_IAM="${MLP_DB_USER_IAM}"
export MLFLOW_DB_SETUP_IMAGE= "${MLP_MLFLOW_DB_SETUP_IMAGE}"
set +o nounset
```

> Ensure there are no `bash: <ENVIRONMENT_VARIABLE> unbound variable` error
> messages.

```shell
git restore create-db/manifests/job-create-database.yaml
envsubst < create-db/manifests/job-create-database.yaml | sponge create-db/manifests/job-create-database.yaml
```

## Run the create-database job

- Create the database creation job.

  ```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f create-db/manifests/job-create-database.yaml
  cd -
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
  create-database       Complete   1/1           XXXXX      XXXXX
  ```

  It takes approximately 1 minutes for the job to complete.

- Check logs for any errors.

```
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Log level set to 'INFO' via LOG_LEVEL env var", "timestamp": 1744226224.1897552, "level": "INFO", "runtime": 4898.694859}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connection pool created for database 'postgres'", "timestamp": 1744226224.5151405, "level": "INFO", "runtime": 5224.080303}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connecting to database 'postgres' as user 'wi-xxxx-user@xxxx.iam'", "timestamp": 1744226224.5153522, "level": "INFO", "runtime": 5224.292105}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' dropped (if existed)", "timestamp": 1744226225.1793787, "level": "INFO", "runtime": 5888.3185}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' creation initiated", "timestamp": 1744226225.820661, "level": "INFO", "runtime": 6529.600795}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connection pool created for database 'mlflowdb'", "timestamp": 1744226225.822039, "level": "INFO", "runtime": 6530.978479}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connecting to database 'mlflowdb' as user 'wi-xxxx-user@xxxx.iam'", "timestamp": 1744226225.8222442, "level": "INFO", "runtime": 6531.183811}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' creation verified", "timestamp": 1744226226.1060863, "level": "INFO", "runtime": 6815.025777}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connector closed", "timestamp": 1744226226.1147602, "level": "INFO", "runtime": 6823.699854}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Database 'mlflowdb' creation successful.", "timestamp": 1744226226.1149092, "level": "INFO", "runtime": 6823.848818}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connection pool created for database 'mlflowdb'", "timestamp": 1744226226.1501238, "level": "INFO", "runtime": 6859.063597}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Granting ALL privileges on schema 'public' of database 'mlflowdb' to user 'wi-xxxx-user@xxxx.iam'", "timestamp": 1744226226.150347, "level": "INFO", "runtime": 6859.286788}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connecting to database 'mlflowdb' as user ''wi-xxxx-user@xxxx.iam'", "timestamp": 1744226226.1509507, "level": "INFO", "runtime": 6859.890375}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Successfully granted ALL privileges on schema 'public' of database 'mlflowdb' to user 'wi-xxxx-user@xxxx.iam'", "timestamp": 1744226226.8060656, "level": "INFO", "runtime": 7515.005285}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Connector closed", "timestamp": 1744226226.8080332, "level": "INFO", "runtime": 7516.973029}
{"name": "__main__", "thread": 135677854571392, "threadName": "MainThread", "processName": "MainProcess", "process": 1, "message": "Permissions granted to user 'wi-xxxx-user@xxxxx.iam' on database 'mlflowdb'.", "timestamp": 1744226226.8089216, "level": "INFO", "runtime": 7517.86128}
```

- MLflow backend store

  Mlflow needs an artifact store to store the deployment artifacts. A GCS bucket
  has already been created as part of MLP Playground.

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
  --substitutions _DESTINATION=${MLP_MLFLOW_IMAGE}
  cd -
  ```

## Deploy the image on the MLPlayground cluster.

- Configure the deployment file for MLflow

```shell
set -o nounset
export MLFLOW_KSA="${MLP_MLFLOW_KSA}"
export DB_INSTANCE_URI="${MLP_DB_INSTANCE_URI}"
export MLFLOW_ARTIFACT_LOCATION="${MLP_MLFLOW_ARTIFACT_LOCATION}"
export MLFLOW_DATABASE_URI="${MLP_MLFLOW_DATABASE_URI}"
export MLFLOW_IMAGE="${MLP_MLFLOW_IMAGE}"
set +o nounset
```

> Ensure there are no `bash: <ENVIRONMENT_VARIABLE> unbound variable` error
> messages.

```shell
git mlflow/manifests/deployment.yaml
envsubst < mlflow/manifests/deployment.yaml | sponge mlflow/manifests/deployment.yaml
```

```shell
kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} apply -f mlflow/manifests/deployment.yaml
```

It takes approximately 5 minutes for the deployment to complete.

## Check if the MLflow dashboard is available

```shell
  kubectl --namespace ${MLP_KUBERNETES_NAMESPACE} logs mlflow-tracking-XXXX --tail 10"
```
