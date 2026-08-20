#!/bin/bash
# Validates the GKE environment, namespace, GCS bucket, and HF model using loaded env vars

# Ensure required variables are set
REQUIRED_VARS=("NAMESPACE" "HF_MODEL_ID" "RESULTS_BUCKET" "ACP_REPO_DIR" "RESOURCE_NAME_PREFIX" "PLATFORM_NAME" "APP_LABEL")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Environment variable '$var' is not set. Ensure the .env file is loaded."
        exit 1
    fi
done

echo "--- 1. Validating Cluster & Namespace ---"
kubectl cluster-info > /dev/null || { echo "Error: Cannot connect to GKE cluster."; exit 1; }
kubectl get ns "$NAMESPACE" > /dev/null || { echo "Error: Namespace '$NAMESPACE' does not exist."; exit 1; }
echo "✓ Cluster connection and Namespace '$NAMESPACE' verified."

echo "--- 2. Validating Hugging Face Secret ---"
SECRET_NAME="${RESOURCE_NAME_PREFIX}-${PLATFORM_NAME}-huggingface-hub-access-token-read"
echo "Checking Secret Manager for '$SECRET_NAME'..."
if gcloud secrets describe "$SECRET_NAME" > /dev/null 2>&1; then
    echo "✓ Secret '$SECRET_NAME' exists in Secret Manager."
else
    echo "Error: Secret '$SECRET_NAME' not found in Secret Manager."
    exit 1
fi

echo "--- 3. Validating GCS Bucket ---"
gcloud storage ls "gs://$RESULTS_BUCKET" > /dev/null 2>&1 || { echo "Error: Cannot access GCS bucket 'gs://$RESULTS_BUCKET'."; exit 1; }
echo "✓ GCS Bucket 'gs://$RESULTS_BUCKET' verified."

echo "--- 4. Validating Model Readiness ---"
echo "Finding pod with label app=$APP_LABEL in namespace '$NAMESPACE'..."
POD_NAME=$(kubectl get pods -n "$NAMESPACE" -l "app=$APP_LABEL" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ -z "$POD_NAME" ]; then
    echo "Error: No pod found with label app=$APP_LABEL in namespace '$NAMESPACE'."
    exit 1
fi
echo "✓ Found pod '$POD_NAME'."

echo "Checking health endpoint of '$POD_NAME'..."
if kubectl exec -n "$NAMESPACE" "$POD_NAME" -c inference-server -- curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ Model is up and running (health check passed)."
else
    echo "Error: Health check failed for pod '$POD_NAME'."
    exit 1
fi

echo "Environment validation complete."
