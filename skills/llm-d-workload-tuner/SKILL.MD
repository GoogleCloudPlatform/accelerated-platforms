---
name: llm-d-workload-tuner
description: This is an experimental Skill. It automatically tunes GKE vLLM inference server parameters and resources based on workload profiles specified in the benchmark configs.
version: 0.1.0
allowed-tools: python3
mcp-servers: []
---

# LLM-D Workload Tuner Skill

Follow these instructions to run the workload optimizer and optionally apply the tuned vLLM parameters and GKE node resource requirements.

## 1. Terminology & Variables

This skill utilizes the following core variables:

- `SPEC` (passed via `--spec` flag): The target GKE routing specification/strategy overlay name (e.g., `optimized-baseline`, `precise-prefix-cache-routing`, `predicted-latency-routing`). It defines which subdirectory under GKE manifests will be read and patched.
- `Workload Profile`: The benchmark workload specification file (e.g., `chatbot_synthetic.yaml.in`, `agentic_code_generation.yaml.in`) which defines the load-testing prompt distributions and sequence limits.

## 2. Prerequisites

- Review the target workload characteristics and configurations in the reference guide: [llm-d-workload-profiles.md](references/llm-d-workload-profiles.md).
- Ensure you know the path to your llm-d-benchmark directory. The benchmarking files `config.json` (defining sequence lengths) and `inference-perf.yaml` (defining stages and model servers) come from the specific llm-d-benchmark workload profile chosen and must exist under the target benchmarking directories.
- Know the target accelerator type (e.g., `rtx-pro-6000`, `nvidia-h100`, or `v6e` TPU)
- Deployment strategy spec name (e.g., `precise-prefix-cache-routing`, `optimized-baseline`, or `predicted-latency-routing`). You must explicitly supply the target spec name using the `--spec` flag.

## 3. Running the Tuner

To compute optimal sizing (Tensor Parallelism size, maximum model length limits, memory margins, and chunked prefill). Note that the `--spec` parameter is required:

- **Command Format:**

  ```bash
  python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
      [--config <path_to_config.json>] \
      --perf-yaml <path_to_inference-perf.yaml> \
      --accelerator-type <accelerator_name> \
      --spec <spec_name>
  ```

- **Example (Dry Run):**
  ```bash
  python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
      --perf-yaml llm-d-benchmark/workload/profiles/inference-perf/chatbot_synthetic.yaml.in \
      --accelerator-type rtx-pro-6000 \
      --spec precise-prefix-cache-routing
  ```

## 4. Applying the Tuned Configuration

Confirm the GKE cluster name, region and reservation (if ANY) and then use the `--apply` flag to commit the calculated tuning configs directly to the GKE deployment overlays.

- **Command:**
  ```bash
  python3 "${ACP_REPO_DIR}/skills/llm-d-workload-tuner/scripts/tune_workload.py" \
      --perf-yaml llm-d-benchmark/workload/profiles/inference-perf/chatbot_synthetic.yaml.in \
      --accelerator-type rtx-pro-6000 \
      --spec precise-prefix-cache-routing \
      --apply
  ```

When `--apply` is set, the tuner:

1. Updates `runtime.env` inside the GKE overlay directory (e.g., setting `TENSOR_PARALLEL_SIZE`, `MAX_MODEL_LEN`).
2. Patches `patch-nodeselector.yaml` to request matching GPU / TPU counts on nodes.
3. Patches `patch-resources.yaml` to configure container GPU / TPU limit settings.
4. Patches `patch-tuner-args.yaml` to configure the optimal arguments for the vLLM container.
5. **Verifies and logs the parameter diff:** Always review the printed `=== Configuration Gap Analysis ===` output to see exactly which parameters were tuned from the baseline deployment in this repo.

## 5. Verification

After deploying the tuned stack, verify:

- That the baseline diff output matches the expected transitions.
- That vLLM deployment specs match the calculated values:
  ```bash
  kubectl get deployment -n <namespace> -l app=vllm -o jsonpath='{.items[0].spec.template.spec.containers[0].args}'
  ```
- Check if the user want to execute benchmark then call llm-d-benchmarking skill and pass the workload profile and endpoint url to it:
  ```bash
  "${ACP_REPO_DIR}/skills/llm-d-benchmarking/scripts/run_benchmark.sh" <workload_profile_name> <endpoint_url> [namespace] [model_name]
  ```
- That benchmarking config are automatically bundled to GCS bucket along with the performance metrics
