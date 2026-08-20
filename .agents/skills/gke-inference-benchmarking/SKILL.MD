---
name: gke-inference-benchmarking
description: Automates Hugging Face model inference performance benchmarking on GKE following the accelerated-platforms reference architecture using environment configuration files.
version: 0.2.0
allowed-tools: kubectl gcloud kustomize curl cat source
---

# GKE Inference Benchmarking Skill

This skill guides the agent through the complete process of deploying a GKE cluster, downloading and serving a Hugging Face model, validating the environment, and running performance benchmarks.

## 1. Cluster Deployment & Workspace Setup

1.  **Cluster Creation**: If a cluster is not already available, deploy one using the reference architecture scripts (e.g., `deploy-standard.sh`) in `platforms/gke/base/use-cases/inference-ref-arch/terraform/`.
    - _Tip_: Customize the `platform_name` in `platforms/gke/base/_shared_config/platform.auto.tfvars` before deployment.
2.  **Workspace Setup**: Create a dedicated directory for the run (e.g., `acp-bench-test-##`) and a configuration file named `bench-test-##.env`.
3.  **Load Configuration**: Sourcfe the `.env` file to load variables like `NAMESPACE`, `HF_MODEL_ID`, `RESULTS_BUCKET`, `RESOURCE_NAME_PREFIX`, `PLATFORM_NAME`, and `APP_LABEL`.

## 2. Model Download & Serving Deployment

Before benchmarking, the model must be available in GCS and served by an inference server.

1.  **Download Model**: Configure and run the Hugging Face model downloader job to transfer weights from Hugging Face to your GCS bucket.
2.  **Provision K8s Resources**: Run Terraform in the appropriate directory (e.g., `online_tpu` or `online_gpu`) to create the namespace, service accounts, and IAM bindings.
3.  **Deploy Inference Server**: Configure and apply the vLLM manifests for the specific model and accelerator. Wait until the deployment is fully `Ready` (e.g., `3/3` containers running).

## 3. Environment & Model Validation

Run `scripts/1_validate_env.sh` to ensure the environment is ready for benchmarking:

- **Cluster connection**: Verifies `kubectl` access and namespace existence.
- **Secret Manager**: Verifies that the HF token secret exists in Secret Manager without exposing its value.
- **GCS Bucket**: Verifies access to the results bucket.
- **Model Readiness**: Verifies that the model endpoint is responding to health checks (via `kubectl exec` to the pod's health endpoint).

## 4. Configuration Preview

Run `scripts/2_preview_config.sh <path-to-env-file>` to generate and preview the Kustomize manifests for the benchmarking job. Verify that the generated Job points to the correct service endpoint and results bucket.

## 5. Benchmarking Execution

Run `scripts/3_execute_and_verify.sh` to trigger the job:

1.  **Apply**: Submit the benchmarking job to GKE.
2.  **Monitor**: Watch the status of the benchmarking Job until completion.
3.  **Verify**: Confirm that the output JSON results files are securely stored in the target GCS bucket.

## 6. Troubleshooting

- **Pending Pods**: Check for unfulfilled node selectors or GPU/TPU quota limits (e.g., Invalid Reservation errors).
- **Secret Missing**: Verify the secret exists in Secret Manager with the name `${RESOURCE_NAME_PREFIX}-${PLATFORM_NAME}-huggingface-hub-access-token-read`.
