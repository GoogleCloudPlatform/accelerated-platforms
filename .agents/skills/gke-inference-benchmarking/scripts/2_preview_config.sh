#!/bin/bash
# Previews the Kustomize configuration for benchmarking

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-env-file>"
    exit 1
fi

ENV_FILE="$1"
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: Environment file '$ENV_FILE' not found."
    exit 1
fi

echo "Sourcing environment variables from $ENV_FILE..."
source "$ENV_FILE"

# Ensure required variables are set
REQUIRED_VARS=("NAMESPACE" "HF_MODEL_ID" "RESULTS_BUCKET" "ACP_REPO_DIR" "RESOURCE_NAME_PREFIX" "PLATFORM_NAME" "APP_LABEL" "TOKENIZER_ID")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: Environment variable '$var' is not set."
        exit 1
    fi
done

# Infer ACCELERATOR from namespace
if [[ "$NAMESPACE" == *"-tpu"* ]]; then
    export ACCELERATOR="TPU"
else
    export ACCELERATOR="GPU"
fi

echo "--- Running configure_benchmark.sh ---"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm/configure_benchmark.sh"

echo "--- Previewing Kustomize Output ---"
kustomize build "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/inference-perf-bench/vllm"
