#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Script to choose model/accelerator and validate custom compute class

echo "Available models (examples): google/gemma-4-31b-it, Qwen/Qwen3-32B-Instruct"
echo "Available accelerators (examples): nvidia-h100, rtx-pro-6000, google-tpu-v6e"

# In a real scenario, this would read from a config or prompt the user.
# For now, we assume environment variables are set or we use defaults.

MODEL=${HF_MODEL_ID:-"google/gemma-4-31b-it"}
ACCELERATOR=${ACCELERATOR_TYPE:-"rtx-pro-6000"}
DEPLOYMENT_STRATEGY=${DEPLOYMENT_STRATEGY:-"vllm"}

echo "Selected Model: $MODEL"
echo "Selected Accelerator: $ACCELERATOR"
echo "Deployment Strategy: $DEPLOYMENT_STRATEGY"

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
    "nvidia-h100"|"h100") PREFIX="h100" ;;
    "rtx-pro-6000") PREFIX="rtx-pro-6000" ;;
    "google-tpu-v6e"|"tpu-v6e"|"v6e") PREFIX="v6e" ;;
    *) PREFIX="unknown" ;;
esac

# Determine directory suffix from model
SUFFIX=""
case "$MODEL" in
    "google/gemma-4-31b-it"|"google/gemma-4-31b") SUFFIX="gemma-4-31b-it" ;;
    "Qwen/Qwen3-32B-Instruct"|"Qwen/Qwen3-32B"|"qwen/qwen3-32b") SUFFIX="qwen3-32b" ;;
    *) SUFFIX="custom" ;;
esac

# Resolve overlay path based on platform and deployment strategy
if [ "$PREFIX" = "v6e" ]; then
    # In GKE base reference implementation, TPU overlays use strategy folder overlays
    if [ "$DEPLOYMENT_STRATEGY" = "vllm" ]; then
        # Default optimized baseline
        OVERLAY_DIR="platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-optimized-baseline/vllm/${PREFIX}-${SUFFIX}"
    else
        OVERLAY_DIR="platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-${DEPLOYMENT_STRATEGY}/vllm/${PREFIX}-${SUFFIX}"
    fi
else
    if [ "$DEPLOYMENT_STRATEGY" = "vllm" ]; then
        OVERLAY_DIR="platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd-optimized-baseline/vllm/${PREFIX}-${SUFFIX}"
    else
        OVERLAY_DIR="platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd-${DEPLOYMENT_STRATEGY}/vllm/${PREFIX}-${SUFFIX}"
    fi
fi

echo "=== Overlay Instructions ==="
if [ "$PREFIX" != "unknown" ] && [ "$SUFFIX" != "custom" ] && [ -d "$OVERLAY_DIR" ]; then
    echo "Instructions point to combining official llm-d base manifests with $OVERLAY_DIR overlay"
    echo "The final vLLM arguments are configured to use --model $MODEL"
else
    echo "Instructions point to combining official llm-d base manifests with custom model overlay"
    echo "The final vLLM arguments are configured to use --model $MODEL"
fi

