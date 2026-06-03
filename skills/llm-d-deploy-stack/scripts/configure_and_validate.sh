#!/bin/bash
# Script to choose model/accelerator and validate custom compute class

echo "Available models (examples): google/gemma-3-1b-it, Qwen/Qwen3-Coder-480B-A35B-Instruct"
echo "Available accelerators (examples): nvidia-l4, nvidia-h100"

# In a real scenario, this would read from a config or prompt the user.
# For now, we assume environment variables are set or we use defaults.

MODEL=${HF_MODEL_ID:-"google/gemma-3-1b-it"}
ACCELERATOR=${ACCELERATOR_TYPE:-"nvidia-l4"}

echo "Selected Model: $MODEL"
echo "Selected Accelerator: $ACCELERATOR"

echo "Checking for custom compute class for $ACCELERATOR..."
# This command lists compute classes, we should check if one matches our accelerator.
kubectl get customcomputeclasses

# Example check (naive):
if kubectl get customcomputeclasses | grep -q "$ACCELERATOR"; then
    echo "Valid custom compute class found."
else
    echo "Warning: No custom compute class explicitly matching $ACCELERATOR found. Please ensure it exists."
fi

# Determine directory prefix from accelerator
PREFIX=""
case "$ACCELERATOR" in
    "nvidia-l4") PREFIX="l4" ;;
    "nvidia-h100") PREFIX="h100" ;;
    "nvidia-h200") PREFIX="h200" ;;
    "rtx-pro-6000") PREFIX="rtx-pro-6000" ;;
    *) PREFIX="unknown" ;;
esac

# Determine directory suffix from model
SUFFIX=""
case "$MODEL" in
    "google/gemma-3-1b-it") SUFFIX="gemma-3-1b-it" ;;
    "Qwen/Qwen3-Coder-32B-Instruct") SUFFIX="qwen3-32b" ;;
    *) SUFFIX="custom" ;;
esac

OVERLAY_DIR="platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/${PREFIX}-${SUFFIX}"

echo "=== Overlay Instructions ==="
if [ "$PREFIX" != "unknown" ] && [ "$SUFFIX" != "custom" ] && [ -d "$OVERLAY_DIR" ]; then
    echo "Instructions point to combining official llm-d base manifests with $OVERLAY_DIR overlay"
    echo "The final vLLM arguments are configured to use --model $MODEL"
else
    echo "Instructions point to combining official llm-d base manifests with custom model overlay"
    echo "The final vLLM arguments are configured to use --model $MODEL"
fi

