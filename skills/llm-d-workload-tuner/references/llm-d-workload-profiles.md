# LLM-D Workload Profiles Reference Guide

This reference details the different benchmarking workload profiles defined in
the
[Upstream LLM-D Benchmark Repository](https://github.com/llm-d/llm-d-benchmark/tree/main/workload/profiles/inference-perf)
and describes their recommended vLLM and GKE tuning configurations.

---

## Workload Profiles & Recommended Tuning Configurations

| Profile Name                                     | Description                                   | Characteristics                                                             | Recommended Tuning Config                                                                                               |
| :----------------------------------------------- | :-------------------------------------------- | :-------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- |
| **`chatbot_synthetic`** / **`interactive-chat`** | Standard multi-turn dialogue simulation.      | Moderate input prompts, moderate generation outputs, high token overlap.    | **EPP Prefix Cache:** Enable prefix caching (`--enable-prefix-caching=True`), set high `--gpu-memory-utilization=0.95`. |
| **`code_coder`** / **`code-gen-bench`**          | Code generation assistant simulation.         | Large input context (e.g. codebase context files), long output code blocks. | **Quantized Model (FP8/FP4):** Reduces base model weight size to reserve VRAM space for large output generation memory. |
| **`search_synthetic`**                           | Multi-document search / retrieval evaluation. | Prefill-heavy. Very large input sequences, short single-token output.       | **High Cache Block Size:** Increase block size to match prefill context bounds and maximize initial context cache hits. |
| **`offline_batch`**                              | Batch dataset processing (non-interactive).   | High concurrency, throughput prioritized over latency.                      | **High Max Model Len:** Maximize batch sizes and set memory utilization to `0.90` to maximize compute density.          |
