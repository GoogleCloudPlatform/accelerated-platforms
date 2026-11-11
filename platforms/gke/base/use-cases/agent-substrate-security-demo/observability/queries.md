# Canned PromQL & Cloud Logging Queries

> [!NOTE]
>
> **Provenance**: The three fleet dashboards under
> `observability/substrate-dashboards/` (`ate-e2e-latency-dashboard.json`,
> `ate-grpc-dashboard.json`, and `ate-snapshot-dashboard.json`) are adapted from
> [`github.com/ai-on-gke/substrate-gke`](https://github.com/ai-on-gke/substrate-gke)
> under the Apache-2.0 License, updated with
> `top_level_controller_name=~"atelet(-.*)?"` matchers.

Paste these queries into the Prometheus UI (`http://127.0.0.1:9090`,
port-forwarded on demand by
`./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh`
and
`python3 ./platforms/gke/base/use-cases/agent-substrate-security-demo/ui/mission_control.py`)
or into **Cloud Console -> Monitoring -> Metrics Explorer -> PromQL**. Agent
Substrate metric and label names contain dots, so they use UTF-8 quoted PromQL
syntax (`{"metric.name", ...}`). Points arrive 1–3 minutes after an operation.

Every query below is pinned to `cluster="agent-substrate-live"`, the default
`Option A` `CLUSTER_NAME` (for `Option B`, replace `agent-substrate-live` with
your `<prefix>-<platform>` cluster name such as `ate-prod`, or rewrite any
PromQL expression via
`python3 ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/promql_scope.py query "<CLUSTER_NAME>" '<promql>'`).
Because Google Cloud Managed Service for Prometheus is project-scoped, omitting
`cluster=` aggregates series across every cluster in the project.
`./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/dashboards.sh`
scopes all four Cloud Monitoring dashboards (PromQL queries, Cloud Monitoring
`timeSeriesFilter` heatmaps, and `ATESPACE` log panels) to your `CLUSTER_NAME`
automatically via `scripts/promql_scope.py`.

## Fleet Telemetry (Agent Substrate)

| Question                                                                                       | PromQL                                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Workers by state (`idle`, `partial`, `at_capacity`, `unschedulable`)                           | `sum by ("ate.worker.state") (avg by ("ate.workerpool.namespace", "ate.workerpool.name", "ate.worker.state", "ate.sandbox.class") ({"ate.workerpool.workers", "ate.workerpool.name"="agents", "ate.sandbox.class"!="unknown", cluster="agent-substrate-live"}))`                                  |
| Desired vs. ready workers                                                                      | `{"ate.workerpool.desired_workers", "ate.workerpool.name"="agents", cluster="agent-substrate-live"}` and `{"ate.workerpool.ready_workers", "ate.workerpool.name"="agents", cluster="agent-substrate-live"}`                                                                                       |
| Lifecycle operations per second                                                                | `sum by ("ate.actor.operation.name") (rate({"ate.actor.lifecycle.operation.duration_count", cluster="agent-substrate-live"}[2m]))`                                                                                                                                                                |
| Scheduler assignment outcomes (`no_capacity` indicates starvation)                             | `sum by ("ate.scheduler.outcome") (rate({"ate.scheduler.assignment.duration_count", cluster="agent-substrate-live"}[2m]))`                                                                                                                                                                        |
| Resume operation P95 latency                                                                   | `histogram_quantile(0.95, sum by (le, "ate.actor.operation.name") (rate({"ate.actor.lifecycle.operation.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                 |
| Restore duration by snapshot kind (`local` after suspend vs. `latest` from GCS after `revert`) | `sum by ("ate.snapshot.kind") (increase({"ate.actor.restore.duration_sum", "ate.snapshot.phase"="total", cluster="agent-substrate-live"}[1h])) / sum by ("ate.snapshot.kind") (increase({"ate.actor.restore.duration_count", "ate.snapshot.phase"="total", cluster="agent-substrate-live"}[1h]))` |
| Restore P95 latency by phase (`download`, `oci_unpack`, `worker_restore`, `total`)             | `histogram_quantile(0.95, sum by (le, "ate.snapshot.phase") (rate({"ate.actor.restore.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                                   |
| Checkpoint P95 latency by phase (`worker_checkpoint`, `persist`)                               | `histogram_quantile(0.95, sum by (le, "ate.snapshot.phase") (rate({"ate.actor.checkpoint.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                                |
| Image cache hit ratio                                                                          | `sum(rate({"ate.imagecache.requests", "ate.imagecache.outcome"="hit", cluster="agent-substrate-live"}[10m])) / sum(rate({"ate.imagecache.requests", "ate.imagecache.outcome"=~"hit\|miss", cluster="agent-substrate-live"}[10m]))`                                                                |
| Router requests by resume trigger (warm vs. resumed)                                           | `sum by ("ate.router.resume") (rate({"atenet.router.route.duration_count", top_level_controller_name="atenet-router", cluster="agent-substrate-live"}[2m]))`                                                                                                                                      |
| Router P95 latency (warm vs. resumed)                                                          | `histogram_quantile(0.95, sum by (le, "ate.router.resume") (rate({"atenet.router.route.duration_bucket", top_level_controller_name="atenet-router", cluster="agent-substrate-live"}[5m])))`                                                                                                       |
| Snapshot image sizes by template                                                               | `histogram_quantile(0.95, sum by (le, "ate.template.name") (rate({"atelet.snapshot.size_bucket", top_level_controller_name=~"atelet(-.*)?", "file.name"="pages.img", cluster="agent-substrate-live"}[10m])))`                                                                                     |
| Actor crashes total                                                                            | `sum({"ate.actor.crashes", cluster="agent-substrate-live"}) or vector(0)`                                                                                                                                                                                                                         |

## Split-Plane Gateway Telemetry (`gateway`)

| Question                                       | PromQL                                                                                                                                           |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Chat turns by outcome                          | `sum by (outcome) (rate(agent_gateway_chat_turns_total{cluster="agent-substrate-live"}[2m]))`                                                    |
| Gemini model request P95 latency               | `histogram_quantile(0.95, sum by (le, backend) (rate(agent_gateway_model_request_duration_seconds_bucket{cluster="agent-substrate-live"}[5m])))` |
| Model tokens per minute (`input` vs. `output`) | `sum by (direction) (rate(agent_gateway_model_tokens_total{cluster="agent-substrate-live"}[5m])) * 60`                                           |
| Tracked actors (`gateway`)                     | `max(agent_gateway_actors_tracked{cluster="agent-substrate-live"})`                                                                              |

## Cloud Logging Queries (Logs Explorer)

Correlate an actor's full lifecycle across workers and control-plane services:

```text
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
(labels."ate.actor.name"="gemini-agent" OR jsonPayload."ate.actor.name"="gemini-agent")
```

Inspect every container span sharing a `kubectl ate --trace` W3C `trace_id`:

```text
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
jsonPayload.trace_id="<32-hex-chars>"
```

Inspect an actor's stdout stream
(`kubectl ate logs actor gemini-agent -a security-demo`):

```text
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
resource.labels.namespace_name="agent-sandbox"
labels."ate.atespace"="security-demo"
labels."ate.actor.name"="gemini-agent"
```
