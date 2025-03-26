<TODO> Re-write to address the deployment artifacts only

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

## Key GKE benefits include:

**Scalability and Resilience**: Auto-scaling and inherent resilience ensure high
availability and handle varying workloads. **Containerization and
Reproducibility**: Docker containerization ensures consistent environments
across all stages. **Simplified Management**: GKE's managed nature simplifies
deployment and integrates seamlessly with GCP services. **Resource Efficiency**:
Optimized container orchestration reduces infrastructure costs. Security: Robust
security features protect MLflow deployments. **GCP Integration**: Seamless
integration with services like Cloud Storage and BigQuery facilitates end-to-end
pipelines. **MLOps Simplification**: GKE and MLflow together provides a strong
base for MLops practices.

Essentially, MLflow's versioning combined with GKE's scalable, managed
environment creates a powerful, efficient, and reliable platform for deploying
and managing production ML models. This synergy simplifies MLOps, enhances
reproducibility, and ensures consistent deployments.

# Mlflow deployment on GKE

In MLflow, the "artifact registry" that is primarily used for storing model
deployments is called the MLflow Model Registry; it acts as a centralized
repository to manage and track different versions of your machine learning
models, allowing you to easily deploy them to various environments while keeping
track of which version is being used where.

## Deployment Steps

Important: To complete this tutorial, you will need to delete the initial
experimental MLflow deployment that is part of MLplayground.

1. Clone the Config Sync manifest repository:

```sh

git clone <https://github.com/IshmeetMehta/mlp-configsync-mlflow.git>
```

Then, remove the MLflow deployment YAML file reference from the
`manifests/apps/ml-team/kustomization.yaml` from the cloned repository to
prevent Config Sync from deploying it to your MLPlayground cluster."

2. Create an artifact store to store the mlflow deployment artifacts as a GCS
   bucket.

```sh
gcloud artifacts repositories create mlflow-artifacts-prod \
    --repository-format=docker \
    --location=<region>
```

3. Create database `mflowdb` in the existing alloydb instance.

Build the image Deploy this image on gke

Alternatively, you can also follow these [instructions]() to create the
database.

4. Build the MLflow image:

5. Deploy the image on the MLplayground cluster.
