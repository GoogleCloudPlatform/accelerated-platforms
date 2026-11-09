# Canned queries

Paste these into the Prometheus UI (http://127.0.0.1:9090, port-forwarded
automatically by `./scripts/stage.sh` and `python3 ./ui/mission_control.py`) or
into Cloud Console -> Monitoring -> Metrics Explorer -> PromQL. Substrate's
metric and label names contain dots, so they are **quoted** (UTF-8 PromQL).
Points arrive 1-3 minutes after the action.

Every query is pinned to `cluster="agent-substrate-live"`, the default
`CLUSTER_NAME`. Managed Prometheus is per _project_, so without it a query also
counts any other cluster reporting there (your instructor's, or a second cluster
of your own). If your `CLUSTER_NAME` is different, change that matcher;
`./scripts/dashboards.sh` scopes all four Cloud Monitoring dashboards to your
`CLUSTER_NAME` automatically via `scripts/promql_scope.py`. `./scripts/stage.sh`
and `python3 ./ui/mission_control.py` automatically manage the local
port-forwards for `atenet-router` (`:8080`), `gateway` (`:8081`), and
`prometheus-ui` (`:9090`).

## The fleet (substrate)

| Question                                                                                                                                                                                                                            | PromQL                                                                                                                                                                                                                                                                                                                                |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| How many workers, in which state (`idle`, `partial`, `at_capacity`, `unschedulable`)? Every ateapi replica reports the whole pool, so take `max`, not `sum`. A worker running one of our actors is `partial` (actor slots, not CPU) | `max by ("ate.worker.state") ({"ate.workerpool.workers", "ate.workerpool.name"="agents", cluster="agent-substrate-live"})`                                                                                                                                                                                                            |
| Desired vs ready workers                                                                                                                                                                                                            | `{"ate.workerpool.desired_workers", "ate.workerpool.name"="agents", cluster="agent-substrate-live"}` and `{"ate.workerpool.ready_workers", "ate.workerpool.name"="agents", cluster="agent-substrate-live"}`                                                                                                                           |
| Lifecycle operations per second                                                                                                                                                                                                     | `sum by ("ate.actor.operation.name") (rate({"ate.actor.lifecycle.operation.duration_count", cluster="agent-substrate-live"}[2m]))`                                                                                                                                                                                                    |
| Did the scheduler find a free worker? (`no_capacity` = capacity starvation)                                                                                                                                                         | `sum by ("ate.scheduler.outcome") (rate({"ate.scheduler.assignment.duration_count", cluster="agent-substrate-live"}[2m]))`                                                                                                                                                                                                            |
| How slow is a resume? (P95)                                                                                                                                                                                                         | `histogram_quantile(0.95, sum by (le, "ate.actor.operation.name") (rate({"ate.actor.lifecycle.operation.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                                                     |
| Restore time by template                                                                                                                                                                                                            | `histogram_quantile(0.95, sum by (le, "ate.template.name") (rate({"ate.actor.restore.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                                                                        |
| Where does cold start go? (by phase: download, oci_unpack, worker_restore, ...)                                                                                                                                                     | `histogram_quantile(0.95, sum by (le, "ate.snapshot.phase") (rate({"ate.actor.restore.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                                                                       |
| Where does a suspend go? (by phase: worker_checkpoint, persist, ...)                                                                                                                                                                | `histogram_quantile(0.95, sum by (le, "ate.snapshot.phase") (rate({"ate.actor.checkpoint.duration_bucket", cluster="agent-substrate-live"}[5m])))`                                                                                                                                                                                    |
| Image cache hit ratio (a miss pays for the pull and unpack)                                                                                                                                                                         | `sum(rate({"ate.imagecache.requests", "ate.imagecache.outcome"="hit", cluster="agent-substrate-live"}[10m])) / sum(rate({"ate.imagecache.requests", "ate.imagecache.outcome"=~"hit\|miss", cluster="agent-substrate-live"}[10m]))`                                                                                                    |
| Which snapshot kind is being restored? (golden / latest / local)                                                                                                                                                                    | `sum by ("ate.snapshot.kind") (rate({"ate.actor.restore.duration_count", cluster="agent-substrate-live"}[5m]))`                                                                                                                                                                                                                       |
| Did requests hit a warm actor or trigger a resume?                                                                                                                                                                                  | `sum by ("ate.router.resume") (rate({"atenet.router.route.duration_count", top_level_controller_name="atenet-router", cluster="agent-substrate-live"}[2m]))`                                                                                                                                                                          |
| Router latency, warm vs resumed                                                                                                                                                                                                     | `histogram_quantile(0.95, sum by (le, "ate.router.resume") (rate({"atenet.router.route.duration_bucket", top_level_controller_name="atenet-router", cluster="agent-substrate-live"}[5m])))`                                                                                                                                           |
| Router requests by outcome (ok, no_capacity, timeout, ...)                                                                                                                                                                          | `sum by ("ate.router.outcome") (rate({"atenet.router.route.duration_count", top_level_controller_name="atenet-router", cluster="agent-substrate-live"}[2m]))`                                                                                                                                                                         |
| Snapshot image sizes by template (swap in `"file.name"` to see which file: gVisor's `pages.img`, a microVM `memory-ranges`)                                                                                                         | `histogram_quantile(0.95, sum by (le, "ate.template.name") (rate({"atelet.snapshot.size_bucket", cluster="agent-substrate-live"}[10m])))`                                                                                                                                                                                             |
| Actor CPU by template                                                                                                                                                                                                               | `sum by ("ate.template.name") (rate({"ate.actor.stats.cpu.time", cluster="agent-substrate-live"}[5m]))`                                                                                                                                                                                                                               |
| Actor memory (working set) by template                                                                                                                                                                                              | `sum by ("ate.template.name") ({"ate.actor.stats.memory.working_set", cluster="agent-substrate-live"})`                                                                                                                                                                                                                               |
| Crashes so far (a step up = a new crash)                                                                                                                                                                                            | `sum({"ate.actor.crashes", cluster="agent-substrate-live"}) or vector(0)` (0 on a healthy fleet, not "no data"). The running total, not `increase()`: each template's series is born at 1 on its first crash, and `increase()` needs a sample before that, so it misses exactly that crash. The total drops back when ateapi restarts |
| Is the controller keeping up?                                                                                                                                                                                                       | `max by ("controller") ({"workqueue_depth", cluster="agent-substrate-live"})`                                                                                                                                                                                                                                                         |
| ateapi gRPC errors                                                                                                                                                                                                                  | `sum by ("rpc.method") (rate({"rpc.server.call.duration_count", top_level_controller_name="ate-api-server", "rpc.response.status_code"!="OK", cluster="agent-substrate-live"}[5m]))`                                                                                                                                                  |

## Your app (gateway)

| Question                   | PromQL                                                                                                                                      |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Chat turns by outcome      | `sum by (outcome) (rate(workshop_chat_turns_total{cluster="agent-substrate-live"}[2m]))`                                                    |
| Model latency by backend   | `histogram_quantile(0.95, sum by (le, backend) (rate(workshop_model_request_duration_seconds_bucket{cluster="agent-substrate-live"}[5m])))` |
| Tokens per minute          | `sum by (direction) (rate(workshop_model_tokens_total{cluster="agent-substrate-live"}[5m])) * 60`                                           |
| Tracked actors (`gateway`) | `max(workshop_actors_tracked{cluster="agent-substrate-live"})`                                                                              |
| Actor suspends (5m)        | `sum(increase({"ate.actor.lifecycle.operation.duration_count", "ate.actor.operation.name"="suspend", cluster="agent-substrate-live"}[5m]))` |

## Logs (Cloud Console -> Logging -> Logs Explorer)

Substrate writes actor identity in two places. Records it writes _on the actor's
behalf_ (your agent's stdout, ateworker's `Actor restoring` /
`Actor checkpointing`) carry it in the label group, `labels."ate.*"`. Records a
component writes _about_ an actor (ateapi's `Actor state changed` and
`Actor crashed`, atelet's `Restore timing breakdown`, ateworker's
`Actor usage sampled`) carry the same keys flat in `jsonPayload`. A query for
one actor's whole story needs both.

One actor's history across workers and components, oldest first:

```
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
(labels."ate.actor.name"="gemini-agent" OR jsonPayload."ate.actor.name"="gemini-agent")
```

Every state change in the atespace (ateapi's record, the authoritative one):

```
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
jsonPayload.msg="Actor state changed"
jsonPayload."ate.atespace"="security-demo"
```

Why was that one resume slow? One record per restore, with every phase in
seconds:

```
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
jsonPayload.msg="Restore timing breakdown"
jsonPayload."ate.actor.name"="gemini-agent"
```

Which actor crashed? (the `ate.actor.crashes` metric can't say, it carries no
actor identity):

```
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
jsonPayload."ate.actor.state"="crashed"
```

Everything one request did, across ateapi, atelet, and ateworker. Use the ID
`kubectl ate --trace …` prints:

```
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
jsonPayload.trace_id="<32 hex chars>"
```

Your agent's own stdout (what
`kubectl ate logs actor gemini-agent -a security-demo` streams):

```
resource.type="k8s_container"
resource.labels.cluster_name="agent-substrate-live"
resource.labels.namespace_name="workshop"
labels."ate.atespace"="security-demo"
labels."ate.actor.name"="gemini-agent"
```
