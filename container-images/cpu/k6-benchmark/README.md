# k6 Benchmark Image

This container image packages [k6](https://k6.io/) load testing tool with
specific scripts to benchmark Machine Learning inference workloads.

It is designed to run in environments like Google Kubernetes Engine (GKE) to
generate consistent, reproducible load against target endpoints and output
granular metrics to a JSONL file for further analysis. It also includes a Python
script (`extract_metrics.py`) that can be run manually to process the k6 output
and generate a price/performance report.

## Usage

You can run this container image via Docker or deploy it as a Job in a
Kubernetes cluster.

### Environment Variables

The container accepts the following optional environment variables for metric
output naming and processing:

- `ACCELERATOR_NAME`: A string representing the target hardware (e.g., `l4`,
  `a100`, `v5p`). If not provided, it defaults to `accelerator-not-set`.
- `NODE_HOURLY_COST`: The hourly cost of the underlying node in USD. Used by the
  automatic metric extraction script to compute cost per 1k images. Defaults to
  `0.0`.

The default benchmark script (`k6-diffusers-flux-2-klein-4b.js`) expects the
following environment variables:

- `TARGET_URL`: The full URL of the inference endpoint to test (e.g.,
  `http://model-service:8000/generate`).
- `BATCH_SIZE`: The batch size to request in the payload (default: `1`).
- `VUS`: The number of concurrent Virtual Users to simulate (default: `1`).

### Running via Docker

Set the k6 script to run by setting the `CMD` to point to the script path when
starting the container:

```bash
# Example: running a different script mounted into the container
docker run --rm \
  -e ACCELERATOR_NAME="custom" \
  -v $(pwd)/custom-script.js:/app/custom-script.js \
  -v $(pwd)/output:/output \
  k6-benchmark:latest /app/your-k6-script.js
```

The k6 output will be saved in the mapped `/output` directory on your host. The
filename will be dynamically generated in the format:
`<name-of-k6-script>-<ACCELERATOR_NAME>-<experiment-start-timestamp>.jsonl`. For
For example: `k6-diffusers-flux-2-klein-4b-l4-20260417T120000Z.jsonl`.

#### Supported Benchmarks

The following benchmark scripts are included:

- **`/app/k6-diffusers-flux-2-klein-4b.js`**: Benchmark the FLUX.2-klein-4B
  image generation model.

## Metrics Extraction

The extraction script (`extract_metrics.py`) can be run manually after the
benchmark finishes to generate a price/performance report.

The extraction script calculates throughput (Images/sec) and latencies (p50,
p95, p99) strictly from the `benchmark` scenario, and automatically fetches
corresponding on-node telemetry (Peak VRAM, Avg GPU Utilization) from Google
Cloud Monitoring if the dependencies are installed and it is running on Google
Cloud.

To ensure accurate hardware metrics when multiple deployments are running in the
same project, the script can filter by pod, namespace, or node. If the `--pod`
argument is omitted, the script automatically uses the `deployment_name`
(extracted from the `TARGET_URL` hostname) as a prefix to filter for relevant
pods.

### Script Arguments

- `--file`: Path to the k6 `.jsonl` output file (Required).
- `--output-csv`: Path to the output CSV file where aggregated results are
  stored (Optional, default: `k6-benchmark.csv`).
- `--hourly-cost`: The hourly cost of the underlying GKE node in USD. If set to
  `0.0`, a warning is emitted and cost metrics will be `0.0` (Optional, default:
  `0.0`).
- `--project-id`: Google Cloud Project ID to query DCGM metrics via Cloud
  Monitoring. If omitted, the script dynamically fetches the project ID from the
  Google Cloud Metadata server (Optional).
- `--pod`: Filter metrics by a specific pod name. If omitted, the script
  automatically uses the `deployment_name` (derived from the `TARGET_URL`
  hostname) as a prefix filter to match all relevant pods in the deployment
  (Optional).
- `--namespace`: Filter metrics by a specific namespace (Optional).
- `--node`: Filter metrics by a specific node name (Optional).
- `--vram-metric`: The Prometheus metric string for VRAM usage (Default:
  `prometheus.googleapis.com/DCGM_FI_DEV_FB_USED/gauge`).
- `--util-metric`: The Prometheus metric string for GPU utilization (Default:
  `prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge`).
