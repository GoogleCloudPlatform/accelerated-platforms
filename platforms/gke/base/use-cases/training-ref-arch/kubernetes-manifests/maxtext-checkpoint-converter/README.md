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
   source platforms/gke/base/use-cases/training-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh
   ```

2. **Configure the GKE manifest variables**:

   ```bash
   platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/maxtext-checkpoint-converter/configure_checkpoint_converter.sh
   ```

3. **Deploy the CPU Conversion Job**:
   ```bash
   kubectl apply -k platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter
   ```

---

## 2. Manifest Customization

You can customize the conversion settings by modifying
`platforms/gke/base/use-cases/training-ref-arch/kubernetes-manifests/maxtext-checkpoint-converter/checkpoint-converter/templates/converter.tpl.env`
before running the configuration script:

- `BASE_OUTPUT_DIRECTORY`: The Cloud Storage bucket destination directory.
- `HF_MODEL_PATH`: The Hugging Face repo name containing the base instruct model
  (e.g. `meta-llama/Llama-3.1-8B-Instruct`).
- `USE_PATHWAYS`: Enables/disables Pathways for the conversion job (e.g. `0` or
  `1`). Default is `0`.

---

## 3. Monitoring the Conversion Job

You can track the live progress of the conversion job via `kubectl`:

```bash
# Get the pod name
kubectl get pods -n ${sft_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name}

# View logs in real-time
kubectl logs -f -l app=maxtext-checkpoint-converter -n ${sft_cpu_maxtext_checkpoint_converter_kubernetes_namespace_name}
```

Once completed, your model checkpoints will be stored under:
`gs://${huggingface_hub_models_bucket_name}/maxtext-checkpoint-converter-output/`
