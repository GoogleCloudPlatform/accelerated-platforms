# This is the base guide for implementing [llm-d Well-Lit Paths](https://llm-d.ai/docs/guides) on accelerated-platforms

## Intelligent Routing

### Optimized Baseline:

Strategies for handling the unique challenges of LLM request scheduling, moving
beyond traditional round-robin approaches. Try
[optimized-baseline well-lit path on accelerated-platforms](./llmd-optimized-baseline-vllm-with-hf-model.md).

### Predicted Latency-Based Routing:

Using online-trained machine learning models to predict latency and optimize
scheduling. Try
[predicted-latency-routing well-lit path on accelerated-platforms](./llmd-predicted-latency-routing-vllm-with-hf-model.md).

## Advanced KV-Cache Management

### Precise Prefix Cache Routing:

Near-real-time routing based on exact cache state published by model servers.
Try
[precise-prefix-cache-routing well-lit path on accelerated-platforms](./llmd-precise-prefix-cache-routing-vllm-with-hf-model.md).
