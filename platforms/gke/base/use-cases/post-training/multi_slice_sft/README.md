# Multi-Slice Supervised Fine-Tuning (SFT) for Qwen3-14B on GKE TPU v6e

This directory contains production-ready Kubernetes manifests and scripts for converting PyTorch Hugging Face weights to MaxText Orbax format and running 64-chip Pathways-enabled Supervised Fine-Tuning (SFT) for `Qwen/Qwen3-14B` on GKE.

---

## 📁 Directory Structure

- **`convert_job.yaml`**: Kubernetes `Job` manifest for high-memory CPU checkpoint conversion (PyTorch $\rightarrow$ MaxText Orbax).
- **`convert_checkpoint.py`**: Python conversion script for programmatically invoking MaxText `to_maxtext`.
- **`sft_job.yaml`**: Production `PathwaysJob` custom resource manifest for 64-chip TPU v6e SFT execution.

---

## 🛠️ Step 1: Base Checkpoint Conversion (CPU High-Memory)

Conversion for 14B+ parameter models requires high CPU memory (`120Gi`) to avoid PyTorch/XLA driver conflicts and OOM eviction.

```bash
kubectl apply -f convert_job.yaml
```

- **Output Path**: `gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models/qwen3_14b_fresh_v023/0/items`
- **Memory Allocated**: `120Gi` CPU RAM
- **Execution Engine**: `JAX_PLATFORMS=cpu`

---

## 🚀 Step 2: 64-Chip Pathways SFT Execution (`PathwaysJob`)

The SFT training workload runs on a 64-chip TPU v6e slice (`2x4` per host across 8 hosts) using Pathways.

```bash
kubectl apply -f sft_job.yaml
```

### ⚙️ Critical Configuration Rules

1. **Pathways Setup**:
   ```bash
   export JAX_PLATFORMS=proxy
   export JAX_BACKEND_TARGET=grpc://127.0.0.1:29000
   export ENABLE_PATHWAYS_PERSISTENCE=1
   ```

2. **XLA Layer Scanning (`scan_layers=True`)**:
   - Reduces compilation HBM memory usage from **43.02 GB HBM** down to **~12 GB HBM**, eliminating TPU HBM OOM errors on 32GB TPU v6e chips.

3. **MaxText 0.2.3 Positional Argument**:
   - Positional argument 1 MUST point to `${MAXTEXT_PKG_DIR}/configs/post_train/sft.yml`.

4. **PathwaysJob Naming Limit**:
   - PathwaysJob resource name MUST be short (e.g. `pw-sft-14b`, < 15 bytes) to satisfy Kubernetes 63-byte coordinator label limits (`jobset.sigs.k8s.io/coordinator`).

---

## 📊 Verification & Logs

Check PathwaysJob resource and pod status:
```bash
kubectl get pathwaysjob -n rl-kr-single-grpo-single-host
kubectl get pods -n rl-kr-single-grpo-single-host
```

View training logs:
```bash
kubectl logs -f job/pw-sft-14b -c sft-trainer -n rl-kr-single-grpo-single-host
```
