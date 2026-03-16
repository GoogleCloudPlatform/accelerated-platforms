# Llama 3.1 8B GRPO Training on GKE (TPU v5e)

This repository contains a production-ready, end-to-end Reinforcement Learning
(GRPO) pipeline for a single-node smoke test of Llama 3.1 8B on Google
Kubernetes Engine (GKE) using a TPU v5e-8 slice.

It integrates **MaxText** (for FSDP model training), **vLLM** (for
high-throughput rollout generation), and **Tunix** (the RL bridge).

_Note: This script is currently configured as a single-batch smoke test. Scaling
up `rl.num_generations` or `per_device_batch_size` for a full training run
triggers an upstream Tunix API mismatch that requires a custom vLLM Monkey
Patch._

## 🚀 Quick Start & Environment Setup

### 1. Provision & Connect to the GKE Cluster

This pipeline is designed to run on the Accelerated Platforms training reference
architecture, which comes pre-configured with CCC and all necessary topology
routing.

If you do not already have a cluster running, follow the official infrastructure
provisioning guide to spin up a TPU v5e cluster: 👉
**[Accelerated Platforms GKE Training Architecture README](https://github.com/GoogleCloudPlatform/accelerated-platforms/blob/kr-rl/platforms/gke/base/use-cases/training-ref-arch/terraform/README.md)**

Once your cluster is up and running, fetch your cluster credentials (replace
with your actual cluster name and region/zone):

```bash
export PROJECT_ID="<YOUR_PROJECT_ID>"
gcloud config set project $PROJECT_ID
gcloud container clusters get-credentials <CLUSTER_NAME> --location <LOCATION>
```

### 2. Configure the Hugging Face Secret

You must have access to the Meta Llama 3.1 weights. The training job securely
pulls your token from a Kubernetes secret. Create it in your active namespace:

```bash
kubectl create secret generic hf-secret --from-literal=token="<YOUR_HF_TOKEN>"
```

### 3. Hardware & Storage Prerequisites

- **Hardware:** This configuration is strictly tuned for a **TPU v5e-8**
  topology.
- **Storage:** The container requires local ephemeral storage (or a mounted SSD)
  at `/workspace` to handle the 16GB checkpoint conversions.

---

## 🛠️ How to Deploy and Run

### 1. Deploy the MLflow Tracking Server

Before starting the training job, you must spin up the MLflow service so the
training pod has somewhere to send its metrics and artifacts.

```bash
kubectl apply -f mlflow.yaml
```

_(Note: This uses a `ClusterIP` configuration, meaning the dashboard is kept
completely internal and secure inside our GKE cluster. The training pod will
automatically discover it at `mlflow-service:5000`)_.

### 2. Build and Push the Training Image

```bash
docker build -t your-registry/maxtext-grpo:latest .
docker push your-registry/maxtext-grpo:latest
```

### 3. Submit the GKE Training Job

```bash
kubectl apply -f v5e-job.yaml
```

### 4. Tail the Logs

```bash
kubectl logs -f job/maxtext-grpo-job-v5e
```

---

## 📊 Viewing Metrics (MLflow & TensorBoard)

MaxText uses a custom C++ backend that logs directly to a local TensorBoard
folder. To make this visible to the team, the `train.py` script automatically
zips this folder and attaches it to **MLflow** as an artifact when the run
completes.

### Accessing the MLflow UI

Because MLflow is running securely inside the cluster, you need to port-forward
it to your local machine to view the dashboard:

1. **Port-forward the MLflow Service:**

```bash
kubectl port-forward svc/mlflow-service 5000:5000
```

2. **Open your Browser:** Navigate to `http://localhost:5000`
3. **View the Run Data:**

- Go to the `MaxText-RL-GRPO` experiment.
- Click on your specific run (e.g., `Llama3.1-8B-grpo`).
- Scroll down to the **Artifacts** section. You will see the `tensorboard_logs`
  folder attached there.

### Live Tracking (During Training)

If you want to watch the loss curves in real-time _before_ the job finishes and
uploads to MLflow, you can port-forward TensorBoard directly from the running
pod:

```bash
kubectl exec -it job/maxtext-grpo-job-v5e -- tensorboard --logdir /workspace/rl_llama3_output --host 0.0.0.0 --port 6006
kubectl port-forward job/maxtext-grpo-job-v5e 6006:6006
```

---

## ⚠️ Critical Architecture Notes & Patches (Do Not Remove)

Because we are bridging experimental research frameworks (MaxText/Tunix) with
open-source inference (vLLM), several runtime patches are applied in `train.py`
and the `Dockerfile`. **If you modify this pipeline, keep these constraints in
mind:**

### 1. The C++ Protobuf Shield

vLLM uses `os.fork()` for its background workers, which fatally crashes the C++
Protobuf engine loaded by JAX (`SIGABRT`).

- **The Fix:** We force Python protobufs and `spawn` multiprocessing at the
  absolute top of `train.py`.

### 2. JAX Version Pinning (`0.4.25`)

Newer versions of JAX strictly enforce `with_sharding_constraint` as an
assertion. Tunix currently violates this when mapping weights to vLLM, causing a
fatal mesh crash.

- **The Fix:** The `Dockerfile` explicitly pins `jax[tpu]==0.4.25` using the
  `--prerelease=allow` flag to grab the stable nightly drivers.

### 3. Memory & Mesh Tuning

To prevent vLLM from causing `RESOURCE_EXHAUSTED` (OOM) errors and starving
MaxText's FSDP optimizer:

- `rollout_tensor_parallelism=8`: Maps vLLM across all 8 chips.
- `hbm_utilization_vllm=0.4`: Restricts vLLM to 40% of the TPU memory.
- _Note:_ The `ici_tensor_parallelism` flag is intentionally omitted so MaxText
  defaults to FSDP for training.
