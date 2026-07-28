# Cloud TPU v6e MaxText GRPO RL Training & Evaluation User Guide

This guide provides step-by-step instructions for running Group Relative Policy
Optimization (GRPO) Reinforcement Learning (RL) training, monitoring live
metrics, and executing checkpoint evaluations on GKE using 8x Cloud TPU v6e
slices.

---

## Quick Reference Workflow

```mermaid
flowchart TD
    Setup["1. Environment & Secret Setup"] --> Convert["2. One-Time Model Conversion"]
    Convert --> Train["3. Launch GRPO RL Training Job"]
    Train --> Monitor["4. Monitor Logs & TensorBoard"]
    Train --> Eval["5. Launch Checkpoint Evaluation Job"]
    Eval --> Results["6. Inspect GSM8K Accuracy & Outputs"]
```

---

## 1. Prerequisites & Environment Setup

### 1.1 Set Environment Variables

```bash
export PROJECT_ID="accelerated-platforms-dev"
export REGION="us-east5"
export CLUSTER_NAME="rl-kr-single"
export NAMESPACE="rl-kr-single-grpo-single-host"
export GCS_BUCKET="gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models"

# Configure kubectl context
gcloud container clusters get-credentials ${CLUSTER_NAME} --location=${REGION} --project=${PROJECT_ID}
```

### 1.2 Create Namespace & Hugging Face Secret

```bash
kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic hf-secret \
  --from-literal=token=${HF_TOKEN} \
  -n ${NAMESPACE} \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## 2. Step 1: One-Time HuggingFace Model Conversion

Before starting RL training, convert the base HuggingFace weights into MaxText Orbax format. Running this on CPU nodes preserves valuable TPU resources:

```bash
# Configure the CPU checkpoint converter
export HF_MODEL_ID="meta-llama/Llama-3.1-8B-Instruct"
platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/configure_checkpoint_converter.sh

# Deploy the CPU Conversion Job
kubectl apply -k platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter
```

### Monitor Model Conversion:

```bash
kubectl logs -f -l app=maxtext-checkpoint-converter -n ${NAMESPACE}
```

_Outputs will be saved to `${GCS_BUCKET}/maxtext-checkpoint-converter-output/`._

---

## 3. Step 2: Launch GRPO RL Training Job

Deploy the 150-step GRPO RL training job onto an 8-chip Cloud TPU v6e slice
(`v6e-2x4`):

```bash
kubectl apply -k platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-tpu-maxtext-grpo-single-host/v6e-2x4-llama-3-1-8b-instruct/
```

---

## 4. Step 3: Monitor Training Logs & Telemetry

### 4.1 View Live Pod Logs

```bash
kubectl logs -f -l app=maxtext-grpo -n ${NAMESPACE}
```

### 4.2 Check Saved Checkpoints in GCS

```bash
gcloud storage ls ${GCS_BUCKET}/llama_checkpoint_converted/v6e-*/checkpoints/actor/
```

### 4.3 Launch TensorBoard Dashboard

```bash
tensorboard --logdir=${GCS_BUCKET}/llama_checkpoint_converted/v6e-*/tensorboard
```

---

## 5. Step 4: Launch Dedicated Checkpoint Evaluation Job

To evaluate a specific checkpoint (e.g. Checkpoint 50) without interrupting
training, deploy the dedicated evaluation job onto a second TPU slice:

```bash
# 1. Apply updated eval script ConfigMap
kubectl create configmap eval-script-ckpt50 \
  --from-file=eval.py=container-images/tpu/rl-tpu-maxtext-grpo-single-host/src/eval.py \
  -n ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -

# 2. Launch Evaluation Job
kubectl apply -f platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/rl-tpu-maxtext-grpo-single-host/eval-job-ckpt50.yaml
```

---

## 6. Step 5: Inspect Evaluation Results & Reasoning Outputs

### 6.1 Monitor Evaluation Logs

```bash
kubectl logs -f -l app=grpo-eval-ckpt50 -n ${NAMESPACE}
```

### 6.2 View Extracted Prompt Completions & Scores

```bash
gcloud storage cat ${GCS_BUCKET}/llama_checkpoint_converted/eval_results_50/eval-ckpt-50/debug_rl_logs/*.txt | head -n 40
```

### 6.3 Compute Average Reward Score Across Test Dataset

```bash
gcloud storage cat ${GCS_BUCKET}/llama_checkpoint_converted/eval_results_50/eval-ckpt-50/debug_rl_logs/*.txt \
  | grep "Reward Score:" \
  | awk '{sum+=$3; count++} END {print "Total Evaluated Prompts: " count "\nAverage Reward Accuracy: " sum/count*100 "%"}'
```

---

## 7. Key Architecture Rules & Troubleshooting

1. **Ephemeral Storage Limits:** Always maintain
   `requests.ephemeral-storage: 30Gi` and `limits.ephemeral-storage: 80Gi` in
   job manifests to accommodate OpenXLA AOT compilation files on `/tmp`.
2. **Workload Identity:** Ensure all Job manifests specify
   `serviceAccountName: rl-kr-single-grpo-single-host-sa`.
3. **Decoupled Execution:** Keep `eval_interval=0` during training to avoid TPU
   VFIO device lock collisions (`/dev/vfio/0: Device or resource busy`).
