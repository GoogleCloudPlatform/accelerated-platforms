# Llama 3.1 8B GRPO Training on GKE (TPU v5e)

This repository contains a production-ready, end-to-end Reinforcement Learning (GRPO) pipeline for fine-tuning Llama 3.1 8B on Google Kubernetes Engine (GKE) using TPU v5e-8 slices.

It integrates **MaxText** (for FSDP model training), **vLLM** (for high-throughput rollout generation), and **Tunix** (the RL bridge).

## 🚀 Quick Start & Prerequisites

1. **Hugging Face Token:** You must have access to the Meta Llama 3.1 weights. Ensure your `HF_TOKEN` environment variable is set in the Kubernetes Secrets.
2. **Hardware:** This configuration is strictly tuned for a **TPU v5e-8** topology.
3. **Storage:** The container requires local ephemeral storage (or a mounted SSD) at `/workspace` to handle the 16GB checkpoint conversions.

## 🛠️ How to Deploy and Run

### 1. Deploy the MLflow Tracking Server

Before starting the training job, you must spin up the MLflow service so the training pod has somewhere to send its metrics and artifacts.

```bash
kubectl apply -f mlflow.yaml

```

_(Note: This uses a `ClusterIP` configuration, meaning the dashboard is kept completely internal and secure inside our GKE cluster. The training pod will automatically discover it at `mlflow-service:5000`)_.

### 2. Build and Push the Training Image

```bash
docker build -t your-registry/maxtext-grpo:latest .
docker push your-registry/maxtext-grpo:latest

```

### 3. Submit the GKE Training Job

```bash
kubectl apply -f job.yaml

```

### 4. Tail the Logs

```bash
kubectl logs -f job/maxtext-grpo-job

```

---

## 📊 Viewing Metrics (MLflow & TensorBoard)

MaxText uses a custom C++ backend that logs directly to a local TensorBoard folder. To make this visible to the team, the `train.py` script automatically zips this folder and attaches it to **MLflow** as an artifact when the run completes.

### Accessing the MLflow UI

Because MLflow is running securely inside the cluster, you need to port-forward it to your local machine to view the dashboard:

1. **Port-forward the MLflow Service:**

```bash
kubectl port-forward svc/mlflow-service 5000:5000

```

2. **Open your Browser:**
   Navigate to `http://localhost:5000`
3. **View the Run Data:**

- Go to the `MaxText-RL-GRPO` experiment.
- Click on your specific run (e.g., `Llama3.1-8B-grpo`).
- Scroll down to the **Artifacts** section. You will see the `tensorboard_logs` folder attached there.

### Live Tracking (During Training)

If you want to watch the loss curves in real-time _before_ the job finishes and uploads to MLflow, you can port-forward TensorBoard directly from the running pod:

```bash
kubectl exec -it job/maxtext-grpo-job -- tensorboard --logdir /workspace/rl_llama3_output --host 0.0.0.0 --port 6006
kubectl port-forward job/maxtext-grpo-job 6006:6006

```
