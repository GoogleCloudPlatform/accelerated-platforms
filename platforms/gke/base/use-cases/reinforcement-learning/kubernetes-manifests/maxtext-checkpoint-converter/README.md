# CPU-based MaxText Checkpoint Converter User Guide

This guide provides instructions for deploying a cheap, one-time CPU-based GKE
Job to convert Hugging Face model checkpoints (e.g. Llama-3.1) into MaxText
Orbax format.

Running this step on CPU nodes saves significant costs and preserves your
valuable TPU resources for actual model training.

---

## 1. Quick Start Workflow

1. **Source the environment variables**:

   ```bash
   source platforms/gke/base/use-cases/reinforcement-learning/terraform/_shared_config/scripts/set_environment_variables.sh
   ```

2. **Set your Model Variables**:

   Specify the Hugging Face Model ID and corresponding MaxText model name:

   ```bash
   # Example: Qwen3-30B-A3B
   export HF_MODEL_ID="Qwen/Qwen3-30B-A3B-Instruct-2507"
   export MODEL_NAME="qwen3-30b-a3b"

   # Example: Gemma 3 4B
   # export HF_MODEL_ID="google/gemma-3-4b-it"
   # export MODEL_NAME="gemma3-4b"

   # Example: LLaMA 3.1 8B
   # export HF_MODEL_ID="meta-llama/Llama-3.1-8B-Instruct"
   # export MODEL_NAME="llama3.1-8b"
   ```

3. **Configure the GKE manifest variables**:

   ```bash
   platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/configure_checkpoint_converter.sh
   ```

4. **Deploy the CPU Conversion Job**:
   ```bash
   kubectl apply -k platforms/gke/base/use-cases/reinforcement-learning/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter
   ```

---

## 2. Supported Model Mappings Reference

| Model Architecture   | Hugging Face Repo (`HF_MODEL_ID`)   | MaxText Name (`MODEL_NAME`) | Multimodal (`USE_MULTIMODAL`) |
| :------------------- | :---------------------------------- | :-------------------------- | :---------------------------: |
| **Gemma 3 4B**       | `google/gemma-3-4b-it`              | `gemma3-4b`                 |    `True` (auto-detected)     |
| **Gemma 3 12B**      | `google/gemma-3-12b-it`             | `gemma3-12b`                |    `True` (auto-detected)     |
| **Gemma 3 27B**      | `google/gemma-3-27b-it`             | `gemma3-27b`                |    `True` (auto-detected)     |
| **Qwen 3 30B MoE**   | `Qwen/Qwen3-30B-A3B-Instruct-2507`  | `qwen3-30b-a3b`             |            `False`            |
| **Qwen 3 4B**        | `Qwen/Qwen3-4B-Instruct-2507`       | `qwen3-4b`                  |            `False`            |
| **LLaMA 3.1 8B**     | `meta-llama/Llama-3.1-8B-Instruct`  | `llama3.1-8b`               |            `False`            |
| **LLaMA 3.1 70B**    | `meta-llama/Llama-3.1-70B-Instruct` | `llama3.1-70b`              |            `False`            |
| **DeepSeek V3 671B** | `deepseek-ai/DeepSeek-V3`           | `deepseek3-671b`            |            `False`            |

---

## 3. Monitoring the Conversion Job

You can track the live progress of the conversion job via `kubectl`:

```bash
# Get the pod name
kubectl get pods -n ${rl_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name}

# View logs in real-time
kubectl logs -f -l app=maxtext-checkpoint-converter -n ${rl_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name}
```

Once completed, your model checkpoints will be stored under:
`gs://${huggingface_hub_models_bucket_name}/${MODEL_NAME}/`
