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

REPO_DIR="${ACP_REPO_DIR}"
if [ -z "$REPO_DIR" ]; then
    REPO_DIR=$(cd "$(dirname "$0")/../../.." && pwd)
fi

echo "Available models (examples): google/gemma-4-31b-it, qwen/qwen3-32b"
echo "Available accelerators (examples): nvidia-h100, nvidia-h200, rtx-pro-6000, google-tpu-v6e"

# In a real scenario, this would read from a config or prompt the user.
# For now, we assume environment variables are set or we use defaults.

MODEL=${HF_MODEL_ID:-"google/gemma-4-31b-it"}
ACCELERATOR=${ACCELERATOR_TYPE:-"rtx-pro-6000"}
DEPLOYMENT_STRATEGY=${DEPLOYMENT_STRATEGY:-"optimized-baseline"}
MODEL_SERVER=${MODEL_SERVER:-"vllm"}

echo "Selected Model: $MODEL"
echo "Selected Accelerator: $ACCELERATOR"
echo "Deployment Strategy (Well-Lit Path): $DEPLOYMENT_STRATEGY"
echo "Model Server (Engine): $MODEL_SERVER"

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
    "nvidia-h200"|"h200") PREFIX="h200" ;;
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

if [ "$PREFIX" = "unknown" ]; then
    echo "ERROR: Unsupported accelerator: $ACCELERATOR. Allowed accelerators are: h100, h200, rtx-pro-6000, v6e." >&2
    exit 1
fi

if [ "$SUFFIX" = "custom" ]; then
    echo "ERROR: Unsupported model: $MODEL. Allowed models are: google/gemma-4-31b-it, qwen/qwen3-32b." >&2
    exit 1
fi


# Resolve overlay path based on platform, strategy, and model server
if [ "$PREFIX" = "v6e" ]; then
    OVERLAY_DIR="${REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-tpu/llmd-${DEPLOYMENT_STRATEGY}/${MODEL_SERVER}/${PREFIX}-${SUFFIX}"
else
    OVERLAY_DIR="${REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd-${DEPLOYMENT_STRATEGY}/${MODEL_SERVER}/${PREFIX}-${SUFFIX}"
fi

echo "=== Overlay Instructions ==="
if [ -d "$OVERLAY_DIR" ]; then
    echo "Instructions point to combining official llm-d base manifests with $OVERLAY_DIR overlay"
    echo "The final vLLM arguments are configured to use --model $MODEL"
else
    echo "ERROR: Overlay directory not found: $OVERLAY_DIR" >&2
    echo "Please ensure the model and accelerator combination is supported for the chosen strategy." >&2
    exit 1
fi

