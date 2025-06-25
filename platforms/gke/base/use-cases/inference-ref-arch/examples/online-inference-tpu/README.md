# Online Inference with Gemma on Google Kubernetes Engine (GKE) with TPUs

This guide demonstrates how to deploy and serve Gemma large language models
(LLMs) for online inference on Google Kubernetes Engine (GKE), specifically
leveraging Cloud TPUs. It showcases high-performance and scalable LLM serving
using various Gemma model sizes and their corresponding TPU v5e and v6e
topologies.

# Getting Started

Follow these steps to set up your environment and deploy Gemma inference
workloads on GKE with TPUs.

## Prerequisites

Before you begin, ensure the following are in place within your Google Cloud
project:

1. **Google Cloud APIs:** Enable the following essential APIs:

- Cloud TPU API

  You can enable them using the gcloud CLI:

  ```bash
  gcloud services enable tpu.googleapis.com
  ```

2. **TPU Quotas and Capacity:** Ensure your Google Cloud project has sufficient
   TPU quota for the desired TPU types and topologies. TPU capacity can be
   provisioned in different ways, each with its own pricing and availability
   characteristics:

   - On-Demand (Standard) Quota
   - Preemptible (Spot) Quota
   - Reservations (for Guaranteed Capacity)

- Checking Your Current Quota:

  You can view your current TPU quota usage and limits in the Google Cloud
  Console:

  1.  Go to the **IAM & Admin** section.
  2.  Select **Quotas & System Limits**.
  3.  In the filter bar, search for `Service: Cloud TPU API` or
      `Service: Compute Engine API`.
  4.  Look for quota names like:

  - `TPU v5 lite pod cores per project per zone` (for on-demand v5e)
  - `Preemptible TPU v5 lite pod cores per project per zone` (for preemptible
    v5e)
  - `TPU v6e cores per project per zone` (for on-demand v6e)
  - `Preemptible TPU v6e cores per project per zone` (for preemptible v6e)

3. **Region Configuration:** The GKE cluster is created by default in the
   us-central1 region. If your desired TPU quota is available in a different
   region, you must update the cluster region before deployment.

- Add the cluster_region variable in:
  `accelerated-platforms/platforms/gke/base/\_shared_config/cluster.auto.tfvars`
- Example:
  ```shell
  cluster_region = "us-east5" # Change to your preferred TPU region
  ```

## Deploy the Core Reference Architecture

This solution builds upon the foundational infrastructure provided by
[inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).

1. **Deploy the Inference Reference Implementation:** Navigate to and follow the
   instructions in the main
   [inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
   guide. This step sets up the necessary GKE cluster, network, and other core
   components. After successfully deploying the reference architecture
   instances, return to this document to continue.

2. **Create Hugging Face Account Token:** Your VLLM deployment will need access
   to Hugging Face models. Follow the steps to create and configure a Hugging
   Face token:
   [Hugging Face Token Setup Guide](/platforms/gke/base/core/huggingface/initialize/README.md).

3. **Gain Access to Gemma Models:** To download and use Gemma models, you must
   accept their terms and conditions on Kaggle.com:
   - Access the Gemma
     [model consent page on Kaggle.com](https://www.kaggle.com/models/google/gemma).
   - Verify your consent using your Hugging Face account credentials.
   - Accept the model terms.

## Prepare Environment Variables and Kubeconfig

These steps set up your local shell environment to interact with your GKE
cluster and manage resources.

1. Set Core Environment Variables:

```shell
set -o allexport
source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
set +o allexport
```

2. Source GKE Cluster Credentials: Configure kubectl to connect to your newly
   deployed GKE cluster.

```shell
gcloud container clusters get-credentials ${cluster_name} \
--dns-endpoint \
--location="${cluster_region}" \
--project="${cluster_project_id}"
```

3. Define Kubernetes Service Account (KSA) Variable:

```shell
export WORKLOAD_KSA="default"
```

4. Add GCS Bucket Access Permission to Workload KSA Grant your Kubernetes
   Service Account the necessary IAM permissions to access the GCS bucket where
   your Hugging Face models are stored.

```shell
export ROLE_NAME="roles/storage.objectAdmin"

export cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")

gcloud storage buckets add-iam-policy-binding gs://"${huggingface_hub_models_bucket_name}" --member "principal://iam.googleapis.com/projects/${cluster_project_number}/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/${WORKLOAD_NAMESPACE}/sa/${WORKLOAD_KSA}" --role "${ROLE_NAME}"
```

# Deploy the Online Inference Workloads

You are now ready to deploy your Gemma inference services to GKE. Each command
below deploys a specific Gemma model size with its corresponding TPU topology.

**Important**: These commands use envsubst to replace variables like
\${WORKLOAD_NAMESPACE}, \${WORKLOAD_KSA}, and
\${huggingface_hub_models_bucket_name} within the Kubernetes YAML manifests.
Ensure these environment variables are correctly set and exported in your
current shell session before running.

## **Gemma 1B (TPU v5e 1x1)**

Deploy the Gemma 3 1B IT model, on a single TPU v5e chip.

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-1b-tpu-v5e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```

### Test Gemma 1B Inference (Port Forwarding & cURL)

Once the Gemma 1B deployment is complete and the pod is running, you can test
the inference service by port-forwarding the ClusterIP service to your local
machine and sending a curl request.

1. **Verify Pod Status:** Wait for your VLLM pod to transition to Running and
   Ready status. This may take several minutes as the model downloads and
   initializes on the TPU.

```bash
kubectl get pods -n "${WORKLOAD_NAMESPACE}" -l app=vllm-tpu-gemma-3-1b-it

```

2. **Verify Service Status:** Confirm that your ClusterIP service is deployed.

```bash
kubectl get service -n "${WORKLOAD_NAMESPACE}" vllm-service-gemma-3-1b-it
```

Look for output similar to:

```bash
NAME                         TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)    AGE
vllm-service-gemma-3-1b-it   ClusterIP   X.X.X.X     <none>        8000/TCP   5m
```

3. **Establish Port Forwarding:** Open a new terminal window and run the
   following command. This will forward traffic from your local machine's port
   8000 to the service's port 8000 within the cluster.

```bash

kubectl port-forward service/vllm-service-gemma-3-1b-it 8000:8000 -n "${WORKLOAD_NAMESPACE}"
```

You should see output indicating that the forwarding is active:

```bash
Forwarding from 127.0.0.1:8000 -> 8000
Handling connection for 8000
```

Keep this terminal window open as long as you want to access the service
locally.

4. **Test with curl:** In a separate terminal window (where port-forwarding is
   NOT running), send a curl request to your locally forwarded endpoint.

Example for Chat Completion (if using a chat-tuned model and
/v1/chat/completions):

```bash

curl -X POST -H "Content-Type: application/json" \
     -d '{
           "model": "google/gemma-3-1b-it",
           "messages": [
             {"role": "user", "content": "Tell me a short story about a brave knight and a dragon."}
           ],
           "max_tokens": 100,
           "temperature": 0.7
         }' \
     http://localhost:8000/v1/chat/completions
```

5. **Clean Up Port Forwarding:** Once you are done testing, simply close the
   terminal window where kubectl port-forward is running.

## **Gemma 4B (TPU v5e 2x2)**

Deploy the Gemma 3 4B IT model, leveraging a 2x2 TPU v5e podslice (4 chips).

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-4b-tpu-v5e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```

## **Gemma 27B (1K context window on TPU v5e)**

Deploy the Gemma 27B model (with a 1K context window), using TPU v5e, 2\*4
topology (8 chips).

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-27b-tpu-v5e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```

## **Gemma 27B (16K context window on TPU v6e)**

Deploy the Gemma 27B model (with a 16K context window), utilizing TPU v6e for
higher performance.

```shell
envsubst <${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/vllm-gemma3-27b-tpu-v6e.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE}
apply -f -
```
