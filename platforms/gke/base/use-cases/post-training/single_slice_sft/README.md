# MaxText v0.2.3 Single-Slice SFT (Supervised Fine-Tuning) Production Bundle

This directory contains the production-ready Python runner script, Kubernetes Job manifest, and instructions for running **Single-Slice Supervised Fine-Tuning (SFT)** on Google Cloud TPU v6e using MaxText 0.2.3.

---

## 📁 File Structure

1. **`convert_checkpoint.py`**: Standalone Python script to convert Hugging Face `Llama-3.1-8B-Instruct` safetensors to MaxText NNX format.
2. **`convert_job.yaml`**: Kubernetes Job manifest for running LLaMA 3.1 8B Instruct model conversion.
3. **`train.py`**: Standalone Python runner script for MaxText single-host SFT (`sft_train`).
4. **`train_job.yaml`**: Eviction-protected Kubernetes Job manifest targeting reserved TPU v6e chips.
5. **`README.md`**: Guide for model conversion, training deployment, monitoring, and checkpoint inspection.

---

## 🚀 Step 1: Model Conversion (HuggingFace -> MaxText)

Run the conversion job to transform Hugging Face `meta-llama/Llama-3.1-8B-Instruct` safetensors into MaxText NNX format:

```bash
kubectl apply -f convert_job.yaml
```

Track conversion status and logs:
```bash
kubectl logs -f job/convert-llama3-1-8b-instruct-to-maxtext -n rl-kr-single-grpo-single-host
```

---

## 🚀 Step 2: Deploy Single-Slice SFT Training

Submit the SFT training job to your Kubernetes cluster:

```bash
kubectl apply -f train_job.yaml
```

Track real-time training loss & perplexity metrics:
```bash
kubectl logs -f job/maxtext-sft-v6e-8c -n rl-kr-single-grpo-single-host
```

---

## 📊 Viewing TensorBoard Metrics
TensorBoard events are written directly to Cloud Storage during training:
```bash
tensorboard --logdir=gs://<YOUR_BUCKET>/llama3-8b-sft-run1/tensorboard/
```

---

## 💾 Output Checkpoints
Checkpoints are saved in Orbax format under:
`gs://<YOUR_BUCKET>/llama3-8b-sft-run1/checkpoints/`
