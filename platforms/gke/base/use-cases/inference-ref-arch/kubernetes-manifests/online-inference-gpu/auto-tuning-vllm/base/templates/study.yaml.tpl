study:
  name: "${HF_MODEL_NAME}_optimization"
  storage_file: "/shared/db/tuning.db"
logging:
  file_path: "/tmp/results/auto-tune-vllm-logs"
  log_level: "INFO"
results:
  dir: "/tmp/results"
optimization:
  approach: "multi_objective"
  max_concurrent_trials: 1
  objectives:
    - metric: "output_tokens_per_second"
      direction: "maximize"
      percentile: "median"
    - metric: "time_to_first_token_ms"
      direction: "minimize"
      percentile: "p95"
  sampler: "nsga2"
  n_trials: 50
static_parameters:
  tensor_parallel_size: 1
  enable_chunked_prefill: true
benchmark:
  benchmark_type: "guidellm"
  model: "/gcs/${HF_MODEL_ID}"
  max_seconds: 600
  dataset: null  # Use synthetic data
  prompt_tokens: 4096
  output_tokens: 128
parameters:
  gpu_memory_utilization:
    enabled: true
    min: 0.88
    max: 0.94
  max_num_batched_tokens:
    enabled: true
    min: 4096
    max: 65536
  kv_cache_dtype:
    enabled: true
    options: ["auto", "fp8"]
  max_num_seqs:
    enabled: true
    min: 1
    max: 64
