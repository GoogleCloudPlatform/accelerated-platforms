# Benchmark harness

This directory benchmarks the two experiment arms (plain vLLM and llm-d) behind
the cross-region internal Application Load Balancer (`MR_GLOBAL_LB=terraform` by
default, or the GKE multi-cluster Inference Gateway when
`MR_GLOBAL_LB=mc-gateway`). It uses
[inference-perf](https://github.com/kubernetes-sigs/inference-perf) **v0.7.0**,
pinned by digest in `MR_INFERENCE_PERF_IMAGE` in `mr.env`. One client Job runs
in each client region, and every client sends requests to the internal VIP of
the load balancer in the region that you choose.

| Path                               | Purpose                                                                                                                                  |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `../terraform/bench/`              | Results bucket and IAM for the client Jobs                                                                                               |
| `../scripts/bench-lib.sh`          | Benchmark settings (`MR_BENCH_*`) and helpers                                                                                            |
| `../scripts/deploy-bench-infra.sh` | Applies or destroys `terraform/bench`                                                                                                    |
| `../scripts/run-benchmark.sh`      | Runs one arm x one workload on every client region and collects results                                                                  |
| `workloads/*.yaml.tmpl`            | inference-perf configuration templates                                                                                                   |
| `manifests/job.yaml.tmpl`          | Client Job template (runs `entrypoint.py` from the ConfigMap)                                                                            |
| `entrypoint.py`                    | Client container wrapper: Cloud Storage tokenizer staging + `/tmp/bench-ready` -> `/tmp/bench-go` barrier                                |
| `analyze.py`                       | Compares runs: CSV, Markdown, optional PNG charts                                                                                        |
| `startup_report.py`                | Model server startup breakdown per Pod and per arm                                                                                       |
| `record_scaling.py`                | Polls regional HPA, Deployment, Pod, and GPU node state during scale-out                                                                 |
| `scale_report.py`                  | Summarizes and plots client golden signals, HPA metrics, and GMP server data (including active `serving_pods` filtered by `--pod-regex`) |
| `lb_traffic_split.py`              | Attributes requests to backend regions from Cloud Logging load-balancer logs                                                             |
| `setup_report.py`                  | Renders `timings/<run>.jsonl` stage durations as Markdown                                                                                |
| `test_*.py`, `testdata/`           | Unit tests (`unittest`) with synthetic fixtures (alongside `../scripts/test_*.py`)                                                       |

## Prerequisites

- The regional clusters and the cross-region internal load balancer
  (`deploy-arm.sh` / `set-route.sh`, using `terraform/global_lb` by default or
  `MR_GLOBAL_LB=mc-gateway`) are deployed, and the regional VIPs serve the
  OpenAI API on port 80 with the model name `${MR_SERVED_MODEL_NAME}`.
- The namespace `${MR_NAMESPACE}` and the Kubernetes service account
  `${MR_NAMESPACE}` exist in every client cluster. `run-benchmark.sh` checks
  this.
- `mr_gateway_vip <gateway> <region_key>` in `scripts/lib.sh` prints the
  load-balancer VIP for a region.
- The client Pods can reach Cloud Storage (and Hugging Face through Cloud NAT
  only when a custom `MR_BENCH_TOKENIZER` differs from `MR_HF_MODEL_ID`). When
  `MR_BENCH_TOKENIZER` matches `MR_HF_MODEL_ID` (the default), `entrypoint.py`
  in the client container copies all non-weight files (`<= 64 MiB`) under
  `gs://<models-bucket>/${MR_MODEL_PATH}/` into `/cache/tokenizer` with Workload
  Identity and fails fast if no tokenizer marker file is found, avoiding
  unauthenticated Hugging Face requests or gated-model `401` failures. When more
  than one client region runs (`MR_BENCH_SYNC_START=auto`, bounded by
  `MR_BENCH_SYNC_TIMEOUT_S=900`), `run-benchmark.sh` waits until every regional
  Pod writes `/tmp/bench-ready` before creating `/tmp/bench-go` in parallel so
  Stage 0 starts together across regions.
- The `${MR_NAMESPACE}-bench-cpu` ComputeClass (default `llm-mr-bench-cpu`)
  exists. Both `deploy-arm.sh` and `run-benchmark.sh` (when the default
  `MR_BENCH_COMPUTE_CLASS` is used) apply it from
  `manifests/common/compute-class-bench.tpl.yaml`, prioritizing on-demand 8-vCPU
  shapes across four families (`n4-standard-8` -> `c4-standard-8` ->
  `n2-standard-8` -> `e2-standard-8`) so a single-family stockout doesn't block
  client Jobs. To use the default node pool instead, set
  `MR_BENCH_COMPUTE_CLASS=""`. On-demand capacity is used instead of Spot so
  that a preemption doesn't end a run.

## Deploy the benchmark infrastructure

```bash
scripts/deploy-bench-infra.sh           # or: scripts/deploy-bench-infra.sh destroy
```

The script creates the following resources:

- The bucket
  `${MR_PROJECT_ID}-${MR_RESOURCE_NAME_PREFIX}-${MR_ENVIRONMENT_NAME}-bench`, in
  the region of the config cluster. The bucket uses uniform bucket-level access,
  enforced public access prevention, `force_destroy`, and deletes objects after
  30 days.
- IAM for the Workload Identity principal of the client Jobs. The principal is
  the same in every cluster because of namespace sameness:
  `principal://iam.googleapis.com/projects/<PROJECT_NUMBER>/locations/global/workloadIdentityPools/<PROJECT_ID>.svc.id.goog/subject/ns/<MR_NAMESPACE>/sa/<MR_NAMESPACE>`.
  The principal gets these roles:
  - `roles/storage.objectUser` on the bucket.
  - `roles/storage.legacyBucketReader` on the bucket. Before uploading,
    inference-perf v0.7.0 calls `storage.Client().lookup_bucket()`
    ([gcs.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/client/filestorage/gcs.py)),
    which needs `storage.buckets.get`.
  - `roles/monitoring.viewer` on the project, for the optional Managed
    Prometheus metrics.

## Run a benchmark

Before you run a benchmark, point the load balancer at the arm that you want to
measure with `scripts/set-route.sh` (or `deploy-arm.sh`; in `mc-gateway` mode,
`set-route.sh` updates the `HTTPRoute`). The `--arm` value is only a label. For
automated A/B sweeps across arms and modes, use `scripts/run-experiment.sh` or
`scripts/run-skew-experiment.sh` (`--region-capacity-inflight`,
`--capacity-mode-inflight`, `--region-capacity-qps`, `--capacity-mode-qps`).

```bash
export MR_RUN_ID=20261030-ab1          # share one run ID across arms and workloads
scripts/set-route.sh --backend baseline
scripts/run-benchmark.sh --arm vllm --workload shared-prefix
scripts/run-benchmark.sh --arm vllm --workload chat
scripts/set-route.sh --backend ppcr
scripts/run-benchmark.sh --arm llmd --workload shared-prefix
scripts/run-benchmark.sh --arm llmd --workload chat
python3 bench/analyze.py "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}" --baseline-arm vllm \
  --out "${MR_RESULTS_DIR}/runs/${MR_RUN_ID}/analysis"
```

| Option                 | Default                     | Meaning                                                                                                                                                     |
| ---------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--arm <label>`        | required                    | Arm label, `[a-z0-9-]`, at most 30 characters                                                                                                               |
| `--workload <name>`    | required                    | `shared-prefix` or `chat`                                                                                                                                   |
| `--clients "<keys>"`   | `MR_REGION_KEYS`            | Regions that run a client Job; all clients run concurrently                                                                                                 |
| `--gateway <name>`     | `llm-mr-gateway`            | Gateway whose VIPs the clients use                                                                                                                          |
| `--target-region <t>`  | `local`                     | `local`: each client uses its own region's VIP. `cross`: each client uses the next region in `MR_REGION_KEYS`. `<key>`: every client uses that region's VIP |
| `--qps "<rates>"`      | `MR_BENCH_QPS`              | Request rate per client for each stage                                                                                                                      |
| `--stage-duration <s>` | `MR_BENCH_STAGE_DURATION_S` | Duration of each stage                                                                                                                                      |
| `--force`              | off                         | Deletes existing local and Cloud Storage results for the same run, arm, and workload first                                                                  |
| `--dry-run`            | off                         | Renders manifests and `run.json` without contacting a cluster                                                                                               |

For each client, the script does the following:

1. Renders the configuration, ConfigMap, and Job manifests.
1. Applies them with `mr_kubectl`.
1. With more than one client region (`MR_BENCH_SYNC_START=auto` or `true`),
   waits until every client Pod has staged its tokenizer (`/tmp/bench-ready`),
   then releases Stage 0 in all of them at once (`/tmp/bench-go`, bounded by
   `MR_BENCH_SYNC_TIMEOUT_S`).
1. Waits until the Job completes or fails. The Job's `activeDeadlineSeconds`
   bounds the wait. If `MR_BENCH_JOB_TIMEOUT_S` isn't set, the deadline is 900 s
   plus `MR_BENCH_SYNC_TIMEOUT_S` plus, per stage, the stage duration, the
   interval, and 120 s of teardown grace.
1. Saves the Job, Pod, and event JSON and the container logs.
1. Downloads the reports with `gcloud storage cp -r`.
1. Deletes the Job and the ConfigMap. The rendered manifests are kept.

Each step is timed with `mr_stage` and recorded in `MR_TIMINGS_FILE`.

inference-perf skips an upload when the object already exists. To keep a stale
prefix from silently mixing results from different runs, the script refuses to
reuse a prefix unless you pass `--force`.

### Result layout

Cloud Storage:
`gs://<bucket>/runs/<MR_RUN_ID>/<arm>/<workload>/<client>/<report files>`

Local, under `${MR_RESULTS_DIR}/runs/<MR_RUN_ID>/<arm>/<workload>/`:

```text
run.json                    run metadata (see below)
<client>/client.json        client region, target region, VIP, base URL, seed, Job, status, Pod image IDs
<client>/manifests/         config.yaml, 00-configmap.yaml, 10-job.yaml (as applied)
<client>/logs/              harness.log, job.json, pods.json, events.json, <pod>.log
<client>/reports/           inference-perf reports (copied from Cloud Storage)
```

`run.json` records the run ID, arm, workload, gateway, target mode, clients
(with their targets and VIPs), start and end epochs, the Git commit and dirty
flag of `ACP_REPO_DIR`, every pinned image or chart (inference-perf, vLLM, llm-d
ref, and router chart with its digest), model settings, load settings, SLOs,
workload parameters, and the timings file.

## Workloads

Both workloads use the completion API with streaming and `ignore_eos: true`.
Every request generates exactly its requested number of output tokens, so both
arms do the same decode work. Arrivals are Poisson by default
(`MR_BENCH_LOAD_TYPE=constant` is also supported), and each stage runs
`MR_BENCH_STAGE_DURATION_S` seconds at one rate from `MR_BENCH_QPS`, with
`MR_BENCH_STAGE_INTERVAL_S` seconds between stages. Rates are per client: with
two client regions, the total offered load is twice the stage rate.

### `shared-prefix`

This workload uses `data.type: shared_prefix`. It has `num_groups` system
prompts, each `system_prompt_len` tokens long, and each shared by
`num_prompts_per_group` requests that have distinct `question_len`-token
questions. Prompts are shuffled across groups with a seeded RNG. This is the
case where prefix-cache aware routing should win.

Defaults: 64 groups x 64 prompts, a 2048-token system prompt, a 256-token
question, and 256 output tokens. The defaults are sized for Qwen3-32B in BF16 on
one 96 GB GPU per replica, with two replicas per region:

- Qwen3-32B KV cache: 2 (K and V) x 64 layers x 8 KV heads x 128 x 2 bytes = 256
  KiB per token.
- At `--gpu-memory-utilization 0.90`, about 20 GiB remains after the 61 GiB of
  weights and the activations, which is about 80k tokens per replica. Confirm
  the real value in the vLLM log line `GPU KV cache size: N tokens`;
  `startup_report.py` extracts it.
- One client's prefix working set is 64 x 2048 = 131k tokens. That is more than
  one replica holds, but about 65k tokens per replica when prefix-aware routing
  partitions the groups across the two replicas.
- One client sends 4,096 distinct prompts. The default sweep sends (1+2+3+4+6+8)
  x 60 = 1,440 requests, so no full prompt repeats; only prefixes are shared.

With `MR_BENCH_SEED_PER_CLIENT=true` (the default), client _i_ uses seed
`MR_BENCH_SEED + i`. Clients in different regions then have different system
prompts. Set it to `false` to give every region the same corpus, for example to
study cross-region cache reuse after spillover.

### `chat` (control)

This workload uses `data.type: random`. Prompts are random vocabulary tokens
with no deliberate sharing. Input lengths follow a normal distribution (mean
2304, standard deviation 512, clamped to 256 through 8192), so the mean input
matches the shared-prefix workload. Output is fixed at 256 tokens, and 4,096
lengths are sampled. The `random` generator supports only the completion API
([random_datagen.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/datagen/synthetic/random_datagen.py),
`get_supported_apis`). That is also why both workloads use
`api.type: completion`.

## inference-perf v0.7.0 schema used

The schema was verified against the source at tag `v0.7.0`. Every model is a
`StrictBaseModel` with `extra="forbid"`
([common.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/common.py)),
so unknown keys are rejected. The rendered configurations of both workloads,
with and without GMP, were validated with `read_config()` from that tag.

| Field                                                                                                                                   | Value                                                                                                                                  | Source (v0.7.0)                                                                                                                                        |
| --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `api.type`                                                                                                                              | `completion`                                                                                                                           | [apis/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/apis/config.py) `APIType`                         |
| `api.streaming`                                                                                                                         | `true` (enables TTFT, TPOT, ITL)                                                                                                       | same                                                                                                                                                   |
| `server.type`, `server.model_name`, `server.base_url`, `server.ignore_eos`                                                              | `vllm`, `${MR_SERVED_MODEL_NAME}`, `http://<VIP>:80`, `true`                                                                           | [client/modelserver/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/client/modelserver/config.py)       |
| `tokenizer.pretrained_model_name_or_path`                                                                                               | `${MR_BENCH_TOKENIZER}`                                                                                                                | [utils/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/utils/config.py)                                 |
| `load.type`                                                                                                                             | `poisson` or `constant`                                                                                                                | [loadgen/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/loadgen/config.py) `LoadType`                  |
| `load.stages[].rate`, `load.stages[].duration`                                                                                          | per stage (`StandardLoadStage`: `rate` > 0 QPS, `duration` > 0 s)                                                                      | same                                                                                                                                                   |
| `load.interval`                                                                                                                         | seconds between stages                                                                                                                 | same                                                                                                                                                   |
| `load.num_workers`, `load.worker_max_concurrency`, `load.request_timeout`, `load.base_seed`                                             | 4, 128, 600, seed                                                                                                                      | same                                                                                                                                                   |
| `data.type: shared_prefix`, `data.shared_prefix.{num_groups, num_prompts_per_group, system_prompt_len, question_len, output_len, seed}` | see above. `num_groups` and `num_prompts_per_group` are also accepted as `num_unique_system_prompts` and `num_users_per_system_prompt` | [datagen/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/datagen/config.py) `SharedPrefix`              |
| `data.type: random`, `data.input_distribution` and `data.output_distribution` `{min, max, mean, std_dev, total_count}`                  | see above. `total_count` is required by the random generator                                                                           | `DataConfig`, [common.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/common.py) `Distribution`                |
| `report.request_lifecycle.{summary, per_stage, per_request, percentiles}`                                                               | `true`, `true`, `false`, `[1, 5, 10, 25, 50, 75, 90, 95, 99, 99.9]`                                                                    | [reportgen/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/reportgen/config.py)                         |
| `report.goodput.constraints.{ttft, tpot}`                                                                                               | SLOs in seconds                                                                                                                        | same, `GoodputConfig`                                                                                                                                  |
| `report.prometheus.{summary, per_stage}`                                                                                                | `true`, `true` (used only when `metrics` is set)                                                                                       | same                                                                                                                                                   |
| `storage.local_storage.path`, `storage.google_cloud_storage.{bucket_name, path}`                                                        | `/reports`, the bench bucket, `runs/<run>/<arm>/<workload>/<client>`                                                                   | [client/filestorage/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/client/filestorage/config.py)       |
| `metrics.type: prometheus`, `metrics.prometheus.{google_managed, scrape_interval, filters}`                                             | optional (`MR_BENCH_GMP=true`): `true`, 15, `['namespace="<ns>"']`. Exactly one of `url` or `google_managed` is allowed                | [client/server_metrics/config.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/config/client/server_metrics/config.py) |

The container image runs `python inference_perf/main.py --config_file <file>`
from `/workspace`
([Dockerfile](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/Dockerfile)).
The Job runs `entrypoint.py` (mounted with `/config/config.yaml` from the
ConfigMap), which rewrites `tokenizer.pretrained_model_name_or_path` to
`/cache/tokenizer` when staged from Cloud Storage, coordinates the optional
`/tmp/bench-ready` -> `/tmp/bench-go` cross-region barrier, and execs
`inference_perf/main.py --config_file /tmp/config.yaml`. The Job runs as a
non-root user with a read-only root file system; `HOME` and `HF_HOME` point to
an `emptyDir`.

With GMP enabled, inference-perf queries
`https://monitoring.googleapis.com/v1/projects/<ADC project>/location/global/prometheus`
with Application Default Credentials. It adds `model_name='<model>'` to the
filters for vLLM metrics such as `vllm:time_to_first_token_seconds`,
`vllm:kv_cache_usage_perc`, and `vllm:prefix_cache_hits`. The query aggregates
every model server Pod in the namespace in every region. The metrics come from
GKE automatic application monitoring, which the core platform enables.

### Reports consumed

Report file names come from `ReportGenerator.generate_reports` in
[reportgen/base.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/reportgen/base.py):

- `summary_lifecycle_metrics.json`, `stage_<N>_lifecycle_metrics.json`,
  `config.yaml`. In Cloud Storage, `config.yaml` holds JSON, because
  [gcs.py](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/inference_perf/client/filestorage/gcs.py)
  always writes `json.dumps`.
- With GMP: `summary_prometheus_metrics.json` and
  `stage_<N>_prometheus_metrics.json`.

Each lifecycle report is a `ResponsesSummary` with the following fields. Times
are in seconds, and percentiles come from `summarize()`: `mean`, `min`, `max`,
`median` (the 50th percentile), and `p<N>` for the other percentiles (`p90`,
`p99`, `p99.9`).

| Field                                                                                            | Meaning                                                                                                                  |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| `load_summary.requested_rate` / `achieved_rate`                                                  | Stage rate and achieved send rate (requests / send duration). Per stage only                                             |
| `successes.count`, `failures.count`, `failures.by_label`                                         | Request outcomes                                                                                                         |
| `successes.latency.time_to_first_token`                                                          | TTFT: first streamed token - request start                                                                               |
| `successes.latency.time_per_output_token`                                                        | TPOT: (last token - first token) / (output tokens - 1), per request                                                      |
| `successes.latency.inter_token_latency`                                                          | ITL: distribution of every gap between consecutive tokens, over all requests                                             |
| `successes.latency.request_latency`                                                              | End-to-end latency                                                                                                       |
| `successes.throughput.{requests_per_sec, input_tokens_per_sec, output_tokens_per_sec}`           | Successful requests and tokens / (last end - first start)                                                                |
| `successes.goodput_metrics.{request_goodput, goodput_percentage, good_requests, total_requests}` | Requests that met every configured constraint, per second and as a percentage of successes (`calculate_goodput_metrics`) |

Metric definitions:
[metrics.md](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/docs/metrics.md).
Report structure:
[reports.md](https://github.com/kubernetes-sigs/inference-perf/blob/v0.7.0/docs/reports.md).

## SLOs and derived metrics

| Name                        | Definition                                                                                                                                                       |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SLO                         | `MR_BENCH_SLO_TTFT_S=2` (TTFT <= 2 s) and `MR_BENCH_SLO_TPOT_S=0.1` (TPOT <= 100 ms), per request. These are written to `report.goodput.constraints` at run time |
| goodput (`goodput_rps`)     | inference-perf `request_goodput` of the stage: successful requests that met both SLOs, divided by the stage's wall time                                          |
| `goodput_pct`               | inference-perf `goodput_percentage`: good / successful requests                                                                                                  |
| `slo_attainment_pct`        | good / (successful + failed) requests, so failures count against attainment                                                                                      |
| `error_rate`                | failures / (successes + failures)                                                                                                                                |
| `max_qps_p90_ttft_slo`      | Highest stage rate such that it and every lower stage have p90 TTFT <= `--slo-ttft` and `error_rate <= --max-error-rate` (default `0.05`)                        |
| `max_qps_p90_ttft_tpot_slo` | Same, with p90 TPOT <= `--slo-tpot` also required                                                                                                                |

Goodput is computed per request by inference-perf, so it always uses the SLO
that was configured at run time.
`analyze.py --slo-ttft/--slo-tpot/--max-error-rate` only change the max-QPS
columns. Stages with 100% failed requests (`n_ok == 0`, `total > 0`) retain
`0.0` throughput and goodput rather than being dropped as missing data. The
report warns when the runtime and analysis SLOs differ, or when cross-region
`stage_0` start times diverge by more than 5 s.

## analyze.py

```bash
python3 bench/analyze.py <run dirs...> [--out DIR] [--baseline-arm vllm] [--arms llmd]
                         [--slo-ttft 2.0] [--slo-tpot 0.1] [--max-error-rate 0.05]
                         [--no-charts]
```

The script searches the directories recursively for client report directories.
It reads `run.json` and `client.json` when they're present, and otherwise infers
the run, arm, workload, and client from the path. It writes the following files:

- `stages.csv`: one row per (run, arm, workload, client, stage). Columns:
  requested, achieved, and completed QPS; successes, failures, and error rate;
  TTFT, TPOT, ITL, and E2E p50, p90, and p99 in ms; output and input tokens/s;
  goodput.
- `summary.csv`: one row per (run, arm, workload, client). Columns: max QPS
  within SLO, max goodput, max output tokens/s, and totals.
- `aggregate.csv`: per (run, arm, workload, stage, requested_qps), summed over
  client regions. Columns: `stage`, throughput, goodput, and the worst client's
  p90 (preserving total-outage stages and keeping repeated-rate stages
  distinct).
- `relative.csv`: each candidate arm vs `--baseline-arm`, matched on (workload,
  client, QPS); repeated runs are averaged. Columns: % change of TTFT p50 and
  p90, TPOT, ITL, and E2E p90, output tokens/s, goodput; the error-rate change
  in percentage points; % change of max QPS within SLO.
- `report.md`: all of the above as Markdown tables.
- PNG charts, when matplotlib is installed: p90 TTFT vs QPS with the SLO line,
  output tokens/s vs QPS, and goodput vs QPS, per workload.

## startup_report.py

```bash
python3 bench/startup_report.py <dir> [<dir>...] [--out DIR] [--pod-regex REGEX] [--container NAME]
```

Each input directory contains:

| File             | Content                                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| `pods.json`      | `kubectl get pods -o json` for the model server Pods                                                              |
| `nodes.json`     | `kubectl get nodes -o json`                                                                                       |
| `events.json`    | `kubectl get events -o json` for the namespace. Capture it within an hour of the apply, because Pod events expire |
| `markers.json`   | `{"apply_epoch_s": <epoch>, "first_ok_via_gateway_epoch_s": <epoch>, "arm": "<label>"}`                           |
| `logs/<pod>.log` | Optional `kubectl logs --timestamps <pod> -c <vllm container>`                                                    |

The script writes `startup.csv` (per Pod), `startup.md`, and
`startup_summary.json` (per arm) to `--out`. The default output directory is the
input directory.

| Column                                                                            | Derived from                                                                                                                                                                                                                                                                                     |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `apply_to_scheduled_s`                                                            | `PodScheduled` condition - `apply_epoch_s` (or the Pod creation time)                                                                                                                                                                                                                            |
| `node_provisioned`                                                                | The node was created after the Pod, so the autoscaler provisioned it for this Pod                                                                                                                                                                                                                |
| `apply_to_node_created_s`, `node_created_to_ready_s`, `node_ready_to_scheduled_s` | Node `creationTimestamp` and `Ready` condition, for provisioned nodes                                                                                                                                                                                                                            |
| `scheduled_to_initialized_s`                                                      | `Initialized` - `PodScheduled`: init container image pulls and init containers                                                                                                                                                                                                                   |
| `image_pull_s`, `image_pull_incl_wait_s`, `images_cached`                         | `Pulling` and `Pulled` events for every container. Uses the kubelet duration in `Successfully pulled image "..." in X (Y including waiting)`, or `Pulled - Pulling` when that's missing (retaining the maximum real pull across restarts). `already present on machine` counts as 0 s and cached |
| `container_start_to_ready_s`                                                      | Model server container `state.running.startedAt` to the Pod `Ready` condition: model load, compile, warmup, and readiness probe                                                                                                                                                                  |
| `container_start_to_app_startup_s`                                                | Container start to the `Application startup complete` log line (needs `--timestamps`)                                                                                                                                                                                                            |
| `weights_load_s`                                                                  | `Loading weights took X seconds`                                                                                                                                                                                                                                                                 |
| `model_load_s`                                                                    | `Model loading took X GiB [memory] and Y seconds`, `Loading model weights took X GB and Y seconds`                                                                                                                                                                                               |
| `dynamo_transform_s`, `torch_compile_s`                                           | `Dynamo bytecode transform time: X s`, `torch.compile takes X s in total`, `Compiling a graph for dynamic shape takes X s`                                                                                                                                                                       |
| `cuda_graph_s`                                                                    | `Graph capturing finished in X secs`                                                                                                                                                                                                                                                             |
| `engine_init_s`                                                                   | `init engine (profile, create kv cache, warmup model) took X seconds`                                                                                                                                                                                                                            |
| `kv_cache_tokens`                                                                 | `GPU KV cache size: N tokens`                                                                                                                                                                                                                                                                    |
| `apply_to_ready_s`                                                                | Pod `Ready` - apply                                                                                                                                                                                                                                                                              |
| per arm: `apply_to_all_pods_ready_s`, `apply_to_first_ok_via_gateway_s`           | Last Pod `Ready` - apply, and `first_ok_via_gateway_epoch_s` - apply                                                                                                                                                                                                                             |

Log patterns are case-insensitive, ignore ANSI colors, and accept several vLLM
wordings. When a pattern matches more than once, the last match wins (the
current container after a restart).

## Tests

```bash
python3 -m unittest discover -s bench -p "test_*.py" -v
python3 -m unittest discover -s scripts -p "test_*.py" -v
scripts/run-benchmark.sh --arm test --workload shared-prefix --dry-run   # renders manifests only
```

## Settings reference

Every setting is defined in `scripts/bench-lib.sh` and can be overridden in the
environment.

| Variable                                                                              | Default                      | Purpose                                                                                           |
| ------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------- |
| `MR_BENCH_GATEWAY`, `MR_BENCH_GATEWAY_PORT`                                           | `llm-mr-gateway`, `80`       | Load-balancer VIP lookup name and port                                                            |
| `MR_BENCH_TOKENIZER`                                                                  | `MR_HF_MODEL_ID`             | Tokenizer ID (copied from the regional Cloud Storage model bucket when equal to `MR_HF_MODEL_ID`) |
| `MR_BENCH_SYNC_START`, `MR_BENCH_SYNC_TIMEOUT_S`                                      | `auto`, `900`                | Cross-region Stage 0 start barrier (`auto` enables when >1 client region runs)                    |
| `MR_BENCH_COMPUTE_CLASS`                                                              | `${MR_NAMESPACE}-bench-cpu`  | Client node selector (`""` to omit)                                                               |
| `MR_BENCH_CPU`, `MR_BENCH_MEMORY`                                                     | `4`, `8Gi`                   | Client requests and limits (Guaranteed QoS)                                                       |
| `MR_BENCH_JOB_TIMEOUT_S`                                                              | derived                      | Job `activeDeadlineSeconds`                                                                       |
| `MR_BENCH_LOAD_TYPE`                                                                  | `poisson`                    | `poisson` or `constant`                                                                           |
| `MR_BENCH_QPS`                                                                        | `1 2 3 4 6 8`                | Stage rates per client                                                                            |
| `MR_BENCH_STAGE_DURATION_S`, `MR_BENCH_STAGE_INTERVAL_S`                              | `60`, `10`                   | Stage length and pause between stages                                                             |
| `MR_BENCH_NUM_WORKERS`, `MR_BENCH_WORKER_MAX_CONCURRENCY`                             | `MR_BENCH_CPU`, `128`        | inference-perf worker processes and in-flight requests per worker                                 |
| `MR_BENCH_REQUEST_TIMEOUT_S`                                                          | `600`                        | Per-request timeout                                                                               |
| `MR_BENCH_SEED`, `MR_BENCH_SEED_PER_CLIENT`                                           | `42`, `true`                 | Prompt and arrival seeds                                                                          |
| `MR_BENCH_SLO_TTFT_S`, `MR_BENCH_SLO_TPOT_S`                                          | `2`, `0.1`                   | SLOs for goodput                                                                                  |
| `MR_BENCH_SP_NUM_GROUPS`, `MR_BENCH_SP_PROMPTS_PER_GROUP`                             | `64`, `64`                   | shared-prefix corpus                                                                              |
| `MR_BENCH_SP_SYSTEM_PROMPT_LEN`, `MR_BENCH_SP_QUESTION_LEN`, `MR_BENCH_SP_OUTPUT_LEN` | `2048`, `256`, `256`         | shared-prefix token lengths                                                                       |
| `MR_BENCH_CHAT_INPUT_{MEAN,STD_DEV,MIN,MAX}`                                          | `2304`, `512`, `256`, `8192` | chat input length distribution                                                                    |
| `MR_BENCH_CHAT_OUTPUT_LEN`, `MR_BENCH_CHAT_NUM_PROMPTS`                               | `256`, `4096`                | chat output length and sample count                                                               |
| `MR_BENCH_GMP`, `MR_BENCH_GMP_SCRAPE_INTERVAL_S`                                      | `false`, `15`                | Optional Managed Prometheus server metrics                                                        |
