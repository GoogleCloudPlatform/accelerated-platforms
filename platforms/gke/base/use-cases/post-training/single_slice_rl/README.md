# MaxText v0.2.3 Single-Slice RL (GRPO) Production Bundle

This directory contains the complete, production-grade codebase for running **Single-Slice GRPO Reinforcement Learning** on Cloud TPU v6e using MaxText 0.2.3 and vLLM sampling.

---

## 📁 Repository Structure

1. **`convert_checkpoint.py`**: Python script to convert Hugging Face `Llama-3.1-8B-Instruct` safetensors to MaxText NNX format.
2. **`convert_job.yaml`**: Kubernetes Job manifest for model conversion.
3. **`train.py`**: Clean standalone RL training runner (`rl_train`).
4. **`train_job.yaml`**: Production Kubernetes Job manifest featuring GCS FUSE streaming to eliminate disk eviction.
5. **`eval.py`**: GSM8K math evaluation script with exact match and reasoning format verification.
6. **`eval_job.yaml`**: Kubernetes Job manifest to evaluate saved RL checkpoints.
7. **`README.md`**: Guide for running model conversion, GRPO training, evaluation, and checkpoint inspection.

---

## 🚀 Step 1: Model Conversion (HuggingFace -> MaxText)
```bash
kubectl apply -f convert_job.yaml
```

---

## 🚀 Step 2: Run Single-Slice GRPO RL Training
```bash
kubectl apply -f train_job.yaml
```

Track real-time GRPO training progress:
```bash
kubectl logs -f job/maxtext-rl-grpo-v6e-run8-gcsfuse -c grpo-trainer -n rl-kr-single-grpo-single-host
```

---

## 🚀 Step 3: Run Checkpoint Evaluation (GSM8K Test Split)
```bash
kubectl apply -f eval_job.yaml
```
