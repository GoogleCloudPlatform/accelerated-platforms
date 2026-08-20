#!/bin/bash
# Executes the benchmarking job and verifies results in GCS

# Ensure required variables are set
REQUIRED_VARS=("NAMESPACE" "RESULTS_BUCKET" "ACP_REPO_DIR")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Environment variable '$var' is not set. Ensure the .env file is loaded."
        exit 1
    fi
done

MANIFEST_DIR="${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm"

echo "--- 1. Executing Benchmarking Job ---"
kubectl apply --kustomize "$MANIFEST_DIR" || { echo "Error: Failed to apply benchmarking manifests."; exit 1; }

# Find the newly created job
JOB_NAME=$(kubectl get jobs -n "$NAMESPACE" -o custom-columns=NAME:.metadata.name --no-headers | grep "inference-perf")

if [ -z "$JOB_NAME" ]; then
    echo "Error: Could not identify the inference-perf job in namespace '$NAMESPACE'."
    exit 1
fi

echo "Benchmarking job '$JOB_NAME' submitted. Waiting for completion..."
kubectl wait --for=condition=complete --timeout=1200s job/"$JOB_NAME" -n "$NAMESPACE" || {
    echo "Error: Job timed out or failed. Fetching logs..."
    kubectl logs job/"$JOB_NAME" -n "$NAMESPACE"
    exit 1
}
echo "✓ Benchmarking job completed."

echo "--- 2. Verifying Results in GCS ---"
echo "Checking bucket gs://$RESULTS_BUCKET for output files..."
sleep 10 # Buffer time for GCS flush

RESULTS_FILE=$(gcloud storage ls "gs://$RESULTS_BUCKET/**" | grep "\.json" | tail -n 1)

if [ -n "$RESULTS_FILE" ]; then
    echo "✓ Success! Benchmarking results found:"
    echo "$RESULTS_FILE"
else
    echo "Error: Benchmarking job completed, but no JSON results were found in gs://$RESULTS_BUCKET."
    exit 1
fi
