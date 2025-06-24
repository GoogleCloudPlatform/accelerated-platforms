# Online Inference with Gemma on Google Kubernetes Engine (GKE) with TPUs

This example demonstrates how to deploy and serve Gemma models for online
inference on Google Kubernetes Engine (GKE) leveraging Cloud TPUs. It showcases
high-performance and scalable LLM serving using various Gemma model sizes and
corresponding TPU v5e and v6e topologies.

## Prerequisites

Before proceeding, ensure you have the following prerequisites in place:

- **TPU Quotas:** Ensure your Google Cloud project has sufficient TPU quota for
  the desired TPU types and topologies. You may need to
  [request additional quota](https://www.google.com/search?q=https://cloud.google.com/docs/quotas%23requesting_additional_quota).
  - Ensure **TPU v5e** quota is available.
  - Ensure **TPU v6e** quota is available.
- **Enabled APIs:** Enable the following Google Cloud APIs in your project:

  - Cloud TPU API

## Deploy the reference architecture

This reference architecture builds on top of the infrastructure that the
[inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
provides, and follows the best practices that the reference implementations
establishes. To deploy this reference architecture, do the following:

1.  Deploy the
    [inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)

    After you deploy the reference architecture instances, continue following
    this document.

2.  Create
    [Hugging Face Account token](/platforms/gke/base/core/huggingface/initialize/README.md)

3.  Get access to the Gemma models by signing the consent agreement:

- For Gemma:

  1. Access the
     [model consent page on Kaggle.com](https://www.kaggle.com/models/google/gemma).

  1. Verify consent using your Hugging Face account.

  1. Accept the model terms.

4. Set the environment variables

```shell
source ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
```

6. Source GKE cluster credentials

```shell
gcloud container clusters get-credentials ${cluster_name} \
--dns-endpoint \
--location="${cluster_region}" \
--project="${cluster_project_id}"
```

7. Create KSA

```shell
export WORKLOAD_KSA="default"
#kubectl create serviceaccount $WORKLOAD_KSA --namespace $WORKLOAD_NAMESPACE
```

8. Add GCS bucket access permision to workload KSA

```shell
export ROLE_NAME="roles/storage.objectAdmin"

export cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")

gcloud storage buckets add-iam-policy-binding gs://"${huggingface_hub_models_bucket_name}" --member "principal://iam.googleapis.com/projects/${cluster_project_number}/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/${WORKLOAD_NAMESPACE}/sa/${WORKLOAD_KSA}" --role "${ROLE_NAME}"
```

## Deploy the online inference workloads

- To deploy Gemma 1B (TPU v5e 1x1) inference service

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-1b-tpu-v5e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```

- To deploy Gemma 4B (TPU v5e 2x2) inference service

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-4b-tpu-v5e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```

- To deploy Gemma 27B (1K context window on TPU v5e) inference service

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-27b-tpu-v5e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```

- To deploy Gemma 27B (16K context window on TPU v6e) inference service

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-27b-tpu-v6e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```
