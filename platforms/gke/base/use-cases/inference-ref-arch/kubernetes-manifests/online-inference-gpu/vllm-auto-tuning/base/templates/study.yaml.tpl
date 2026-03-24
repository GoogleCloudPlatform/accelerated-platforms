study.yaml: |
  study:
    name: "${HF_MODEL_NAME}_optimization"
    storage_file: "/shared/db/tuning.db"
  logging:
    file_path: "/tmp/results/auto-tune-vllm-logs"
    log_level: "INFO"
  results:
    dir: "/tmp/results"
  optimization:
    # Advanced multi-objective: Optimize throughput vs Time-To-First-Token
    approach: "multi_objective"
    max_concurrent_trials: 1
    objectives:
      - metric: "output_tokens_per_second"  # Maximize throughput
        direction: "maximize"
        percentile: "median"
      - metric: "time_to_first_token_ms"  # Minimize TTFT for responsiveness
        direction: "minimize"
        percentile: "p95"  # Focus on worst-case TTFT
    sampler: "nsga2"  # Best for multi-objective optimization
    n_trials: 50
  static_parameters:
    tensor_parallel_size: 1       # Use 1 GPU for all trials
    enable_chunked_prefill: true  # Always enable chunked prefill
  benchmark:
    benchmark_type: "guidellm"
    model: "/gcs/${HF_MODEL_ID}"
    max_seconds: 600
    dataset: null  # Use synthetic data
    prompt_tokens: 4096
    output_tokens: 128

  logging:
    file_path: "/tmp/auto-tune-vllm-logs"
    log_level: "INFO"

  parameters:
    gpu_memory_utilization:
      enabled: true
      min: 0.88
      max: 0.94
    # The Prefill Engine (Crucial for heavy input)
    max_num_batched_tokens:
      enabled: true
      min: 4096
      max: 65536 # Pushing high for massive prefill throughput
    # FP8 KV Cache (Native Ada Support)
    kv_cache_dtype:
      enabled: true
      options: ["auto", "fp8"]
    # Max Sequences
    max_num_seqs:
      enabled: true
      min: 1
      max: 64  # Prefill heavy usually means fewer but larger requests
