#!/usr/bin/env python3
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Reports a scale-out experiment (scripts/run-scale-experiment.sh).

Usage: scale_report.py --runs <results/runs/<run>/<arm>> --recorder <recorder.jsonl>
                       --out <dir> [--project <id>] [--cluster-regex <re>]
                       [--namespace <ns>] [--pod-regex <re>]
                       [--gmp-json <path> | --no-gmp]

It combines:
  - the client-side golden signals of every inference-perf stage and client
    region (latency, throughput, errors, goodput),
  - the autoscaling timeline recorded by bench/record_scaling.py (HPA desired
    and current replicas, ready pods, queue metrics, GPU nodes), and per-pod
    scale-out latency (created -> scheduled -> ready),
  - optionally, server-side time series from Google Cloud Managed Service for
    Prometheus (p90 TTFT and inter-token latency, queue depth, KV cache
    utilization, prefix cache hit rate, generated tokens/s, per region),
and writes report.md, CSV files, and charts (with matplotlib, if installed).
"""

from __future__ import annotations

import argparse
import collections
import glob
import itertools
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402

PALETTE: tuple[str, ...] = (
    "tab:blue",
    "tab:orange",
    "tab:green",
    "tab:red",
    "tab:purple",
    "tab:brown",
    "tab:pink",
    "tab:olive",
    "tab:cyan",
)


def ts(value: Any) -> float | None:
    """Epoch seconds, RFC 3339 string, or datetime to UTC epoch seconds."""
    return analyze.epoch_seconds(value)


def fmt(v: Any, digits: int = 1) -> str:
    return analyze.fmt(v, digits)


def mmss(seconds: float | None) -> str:
    if seconds is None:
        return "–"
    rounded = int(round(seconds))
    sign = "-" if rounded < 0 else ""
    total = abs(rounded)
    return f"{sign}{total // 60}:{total % 60:02d}"


def _client_key_for_partial(path: str) -> str:
    """Client region key of a partial stage report (like analyze.collect)."""
    report_dir = os.path.dirname(os.path.abspath(path))
    client_dir = (
        os.path.dirname(report_dir)
        if os.path.basename(report_dir) == "reports"
        else report_dir
    )
    client_json = os.path.join(client_dir, "client.json")
    meta = analyze.load_json(client_json) if os.path.exists(client_json) else {}
    return str(meta.get("key") or os.path.basename(client_dir))


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def stage_windows_with_regions(
    runs_dir: str,
) -> tuple[dict[int, tuple[float, float]], dict[tuple[str, int], tuple[float, float]]]:
    """Returns ({stage: (start, end)}, {(client, stage): (start, end)})."""
    windows: dict[int, tuple[float, float]] = {}
    by_region: dict[tuple[str, int], tuple[float, float]] = {}
    for path in glob.glob(
        os.path.join(runs_dir, "**", "inference-perf.partial.stage_*.yaml"),
        recursive=True,
    ):
        stage = int(path.rsplit("_", 1)[1].split(".")[0])
        t = analyze.load_partial_report(path)["run"]["time"]
        start, end = ts(t.get("start")), ts(t.get("end"))
        if start is None or end is None:
            raise ValueError(f"{path}: run.time has no start or end")
        client = _client_key_for_partial(path)
        reg_old = by_region.get((client, stage))
        by_region[(client, stage)] = (
            (min(start, reg_old[0]), max(end, reg_old[1])) if reg_old else (start, end)
        )
        old = windows.get(stage)
        windows[stage] = (min(start, old[0]), max(end, old[1])) if old else (start, end)
    return windows, by_region


def load_recorder(path: str) -> dict[str, list[dict[str, Any]]]:
    by_region: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                by_region[r["region"]].append(r)
    return dict(by_region)


def pod_latencies(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last known state of every model server pod seen by the recorder, with its node's creation time."""
    pods: dict[str, dict[str, Any]] = {}
    nodes: dict[str, str] = {}
    for r in records:
        nodes.update(r.get("node_list") or {})
        for p in r.get("pod_list") or []:
            pods[p["name"]] = dict(
                pods.get(p["name"], {}), **{k: v for k, v in p.items() if v}
            )
    rows = []
    for name, p in pods.items():
        created, scheduled, ready = (
            ts(p.get("created")),
            ts(p.get("scheduled")),
            ts(p.get("ready")),
        )
        node_name = p.get("node")
        node_created = ts(nodes.get(node_name)) if node_name else None
        rows.append(
            {
                "pod": name,
                "node": node_name,
                "created": created,
                "node_created": node_created,
                "scheduled": scheduled,
                "ready": ready,
                "wait_for_node_s": (
                    (scheduled - created)
                    if (scheduled is not None and created is not None)
                    else None
                ),
                "new_node": bool(
                    node_created is not None
                    and created is not None
                    and node_created > created
                ),
                "start_to_ready_s": (
                    (ready - scheduled)
                    if (ready is not None and scheduled is not None)
                    else None
                ),
                "created_to_ready_s": (
                    (ready - created)
                    if (ready is not None and created is not None)
                    else None
                ),
            }
        )
    return sorted(rows, key=lambda r: r["created"] or 0)


def scale_events(records: list[dict[str, Any]]) -> list[tuple[float, int | None, int]]:
    """Times at which the HPA's desired replica count changed."""
    events: list[tuple[float, int | None, int]] = []
    last: int | None = None
    for r in records:
        d = r.get("hpa_desired")
        if d is not None and d != last:
            events.append((r["ts"], last, d))
            last = d
    return events


def first_time(
    records: list[dict[str, Any]], predicate: Any, after: float = 0
) -> float | None:
    for r in records:
        if r["ts"] >= after and predicate(r):
            return r["ts"]
    return None


# ---------------------------------------------------------------------------
# Managed Service for Prometheus
# ---------------------------------------------------------------------------

GMP_QUERIES = {
    "ttft_p90_s": "histogram_quantile(0.9, sum by (le, cluster) (rate(vllm:time_to_first_token_seconds_bucket{SEL}[2m])))",
    "itl_p90_s": "histogram_quantile(0.9, sum by (le, cluster) (rate(vllm:inter_token_latency_seconds_bucket{SEL}[2m])))",
    "e2e_p90_s": "histogram_quantile(0.9, sum by (le, cluster) (rate(vllm:e2e_request_latency_seconds_bucket{SEL}[2m])))",
    "waiting": "sum by (cluster) (max by (cluster, pod) (vllm:num_requests_waiting{SEL}))",
    "running": "sum by (cluster) (max by (cluster, pod) (vllm:num_requests_running{SEL}))",
    # Pods with at least one request in progress.
    "serving_pods": "sum by (cluster) (max by (cluster, pod) (vllm:num_requests_running{SEL}) > bool 0)",
    "kv_cache_usage": "avg by (cluster) (max by (cluster, pod) (vllm:kv_cache_usage_perc{SEL}))",
    "prefix_hit_rate": "sum by (cluster) (rate(vllm:prefix_cache_hits_total{SEL}[2m])) / sum by (cluster) (rate(vllm:prefix_cache_queries_total{SEL}[2m]))",
    "gen_tokens_per_s": "sum by (cluster) (rate(vllm:generation_tokens_total{SEL}[2m]))",
    "success_rps": "sum by (cluster) (rate(vllm:request_success_total{SEL}[2m]))",
    # Per pod, to find when each new replica served its first request.
    "pod_success_rps": "sum by (cluster, pod) (rate(vllm:request_success_total{SEL}[1m]))",
}


def gmp_query_range(
    project: str,
    query: str,
    start: float,
    end: float,
    step: int,
    token: str,
) -> dict[str, list[tuple[float, float]]]:
    url = (
        f"https://monitoring.googleapis.com/v1/projects/{project}/location/global/prometheus/api/v1/query_range?"
        + urllib.parse.urlencode(
            {
                "query": query,
                "start": f"{start:.0f}",
                "end": f"{end:.0f}",
                "step": f"{step}s",
            }
        )
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    out: dict[str, list[tuple[float, float]]] = {}
    for series in data.get("data", {}).get("result", []):
        key = series["metric"].get("cluster", "?")
        if "pod" in series["metric"]:
            key = f"{key}/{series['metric']['pod']}"
        out[key] = [
            (float(t), float(v))
            for t, v in series["values"]
            if v not in ("NaN", "+Inf", "-Inf")
        ]
    return out


def gmp_all(
    project: str,
    cluster_regex: str,
    namespace: str,
    start: float,
    end: float,
    step: int = 30,
    pod_regex: str = ".*vllm.*",
) -> dict[str, dict[str, list[tuple[float, float]]]]:
    token = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # One series per pod: GKE automatic application monitoring (job gke-ac-*).
    sel = (
        f'{{cluster=~"{cluster_regex}",namespace="{namespace}",'
        f'pod=~"{pod_regex}",job=~"gke-ac-.*"}}'
    )
    return {
        name: gmp_query_range(project, q.replace("{SEL}", sel), start, end, step, token)
        for name, q in GMP_QUERIES.items()
    }


def load_gmp_json(path: str) -> dict[str, dict[str, list[tuple[float, float]]]]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        metric: {
            cluster: [(float(pt[0]), float(pt[1])) for pt in pts]
            for cluster, pts in (series or {}).items()
        }
        for metric, series in (raw or {}).items()
    }


def first_serving(
    gmp: dict[str, dict[str, list[tuple[float, float]]]],
) -> dict[str, float]:
    """{pod: first time its request success rate was above zero}."""
    out = {}
    for key, pts in (gmp.get("pod_success_rps") or {}).items():
        pod = key.split("/", 1)[-1]
        t = next((t for t, v in pts if v > 0), None)
        if t is not None:
            out[pod] = t
    return out


def mean_in(
    points: list[tuple[float, float]], start: float, end: float
) -> float | None:
    vals = [v for t, v in points if start <= t <= end]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def region_colors(keys: list[str]) -> dict[str, str]:
    """One chart color per region (the palette repeats past its length)."""
    return dict(zip(keys, itertools.cycle(PALETTE)))


def slo_ylim_top(ymax: float, slo: float) -> float:
    """Top of a y axis that keeps the SLO line visibly inside the chart."""
    return max(ymax, slo * 1.4)


def region_of_cluster(cluster: str, keys: list[str]) -> str:
    for k in keys:
        if cluster.endswith(k):
            return k
    return cluster


def plot_timeline(
    out_dir: str,
    t0: float,
    windows: dict[int, tuple[float, float]],
    recorder: dict[str, list[dict[str, Any]]],
    gmp: dict[str, dict[str, list[tuple[float, float]]]],
    keys: list[str],
    stage_qps: dict[int, Any],
    slo_ttft_ms: float = 2000.0,
) -> list[str]:
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return []

    has_running = any(
        r.get("hpa_running_average") is not None
        for recs in recorder.values()
        for r in recs
    )
    queue_label = (
        "HPA metrics per pod\n(solid: waiting, dotted: running)"
        if has_running
        else "HPA metric: waiting\nrequests per pod"
    )
    panels = [
        ("replicas", "model server replicas\n(solid: ready, dashed: HPA desired)"),
        ("queue", queue_label),
    ]
    if gmp:
        panels += [("ttft", "p90 TTFT (s, server)"), ("tokens", "generated tokens/s")]
    fig, axes = plt.subplots(
        len(panels), 1, figsize=(10, 2.6 * len(panels)), sharex=True
    )
    colors = region_colors(keys)
    slo_ttft_s = slo_ttft_ms / 1000.0

    for ax, (panel, label) in zip(axes, panels):
        for key in keys:
            recs = recorder.get(key, [])
            x = [(r["ts"] - t0) / 60 for r in recs]
            if panel == "replicas":
                ax.step(
                    x,
                    [r.get("deploy_ready") for r in recs],
                    where="post",
                    color=colors[key],
                    label=key,
                )
                ax.step(
                    x,
                    [r.get("hpa_desired") for r in recs],
                    where="post",
                    color=colors[key],
                    linestyle="--",
                    alpha=0.6,
                )
            elif panel == "queue":
                ax.plot(
                    x, [r.get("hpa_metric") for r in recs], color=colors[key], label=key
                )
                if has_running:
                    ax.plot(
                        x,
                        [r.get("hpa_running_average") for r in recs],
                        color=colors[key],
                        linestyle=":",
                        alpha=0.7,
                    )
            else:
                metric = "ttft_p90_s" if panel == "ttft" else "gen_tokens_per_s"
                for cluster, pts in (gmp.get(metric) or {}).items():
                    if region_of_cluster(cluster, keys) == key and pts:
                        ax.plot(
                            [(t - t0) / 60 for t, _ in pts],
                            [v for _, v in pts],
                            color=colors[key],
                            label=key,
                        )
        if panel == "ttft":
            ax.set_yscale("log")
            ax.axhline(
                slo_ttft_s,
                color="grey",
                linestyle=":",
                linewidth=1.2,
                label=f"SLO ({slo_ttft_s:g}s)",
            )
            ymin, ymax = ax.get_ylim()
            ax.set_ylim(ymin, slo_ylim_top(ymax, slo_ttft_s))
            ax.legend(fontsize=7, loc="upper right")
        ax.set_ylabel(label, fontsize=8)
        ax.grid(alpha=0.3)
        for stage, (start, end) in sorted(windows.items()):
            ax.axvspan(
                (start - t0) / 60,
                (end - t0) / 60,
                color="grey",
                alpha=0.06 if stage % 2 else 0.12,
            )
    for stage, (start, _end) in sorted(windows.items()):
        axes[0].annotate(
            f"{stage_qps.get(stage, '?')} QPS",
            ((start - t0) / 60, axes[0].get_ylim()[1]),
            fontsize=7,
            va="top",
        )
    axes[0].legend(fontsize=8, loc="upper left")
    axes[-1].set_xlabel("minutes since the first stage started")
    fig.suptitle("Scale-out timeline per region (shaded: benchmark stages)")
    fig.tight_layout()
    path = os.path.join(out_dir, "scale_timeline.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return [path]


def plot_stages(
    out_dir: str,
    stages: list[dict[str, Any]],
    keys: list[str],
    slo_ttft_ms: float,
) -> list[str]:
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return []
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    colors = region_colors(keys)
    metrics = ("ttft_p90_ms", "goodput_rps", "output_tokens_per_s")
    for key in keys:
        rows = sorted(
            (r for r in stages if r["client"] == key), key=lambda r: r["stage"]
        )
        for idx, metric in enumerate(metrics):
            pts = [(r["stage"], r[metric]) for r in rows if r.get(metric) is not None]
            if pts:
                axes[idx].plot(
                    [p[0] for p in pts],
                    [p[1] for p in pts],
                    marker="o",
                    color=colors[key],
                    label=key,
                )
    axes[0].set_yscale("log")
    axes[0].axhline(slo_ttft_ms, color="grey", linestyle=":", label="SLO")
    ymin, ymax = axes[0].get_ylim()
    axes[0].set_ylim(ymin, slo_ylim_top(ymax, slo_ttft_ms))
    for ax, title in zip(
        axes,
        ["p90 TTFT (ms, client)", "goodput (requests/s within SLO)", "output tokens/s"],
    ):
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("stage")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    path = os.path.join(out_dir, "scale_stages.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return [path]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--runs", required=True)
    p.add_argument("--recorder", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--project")
    p.add_argument("--cluster-regex", default=".*")
    p.add_argument("--namespace", default="llm-mr")
    p.add_argument("--pod-regex", default=".*vllm.*")
    p.add_argument(
        "--gmp-json",
        default="",
        help="load pre-fetched GMP series from JSON file instead of querying live",
    )
    p.add_argument("--no-gmp", action="store_true")
    p.add_argument("--slo-ttft-ms", type=float, default=2000.0)
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    stages, notes = analyze.collect([args.runs])
    windows, windows_by_region = stage_windows_with_regions(args.runs)
    recorder = load_recorder(args.recorder)
    keys = sorted(recorder) if recorder else sorted({r["client"] for r in stages})
    stage_qps = {r["stage"]: r["requested_qps"] for r in stages}
    t0 = (
        min(w[0] for w in windows.values())
        if windows
        else min(r["ts"] for rs in recorder.values() for r in rs)
    )
    t_end = (
        max(w[1] for w in windows.values())
        if windows
        else max(r["ts"] for rs in recorder.values() for r in rs)
    )

    gmp: dict[str, dict[str, list[tuple[float, float]]]] = {}
    if args.gmp_json:
        gmp = load_gmp_json(args.gmp_json)
    elif not args.no_gmp and args.project:
        try:
            gmp = gmp_all(
                args.project,
                args.cluster_regex,
                args.namespace,
                t0 - 120,
                t_end + 120,
                pod_regex=args.pod_regex,
            )
        except Exception as e:  # report without server-side metrics
            notes.append(f"Managed Service for Prometheus query failed: {e}")

    lines = ["# Scale-out experiment", ""]
    lines += [
        "Stages: "
        + ", ".join(
            f"{s}: {stage_qps.get(s)} QPS per client region, "
            f"{mmss(windows[s][0] - t0)}–{mmss(windows[s][1] - t0)}"
            for s in sorted(windows)
        ),
        "",
    ]

    # Client-side golden signals per stage and region.
    lines += [
        "## Client-side golden signals per stage",
        "",
        "| stage | QPS | client | achieved | done rps | errors | TTFT p50/p90/p99 (ms) | TPOT p90 (ms) | E2E p90 (s) | out tok/s | goodput rps |",
        "|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for r in sorted(stages, key=lambda r: (r["stage"], r["client"])):
        lines.append(
            f"| {r['stage']} | {fmt(r['requested_qps'])} | {r['client']} | {fmt(r['achieved_qps'], 2)} | "
            f"{fmt(r['completed_rps'], 2)} | {r['failures']} | {fmt(r['ttft_p50_ms'], 0)}/{fmt(r['ttft_p90_ms'], 0)}/"
            f"{fmt(r['ttft_p99_ms'], 0)} | {fmt(r['tpot_p90_ms'])} | "
            f"{fmt(r['e2e_p90_ms'] / 1000 if r['e2e_p90_ms'] is not None else None)} | {fmt(r['output_tokens_per_s'], 0)} | "
            f"{fmt(r['goodput_rps'], 2)} |"
        )
    by_stage: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for r in stages:
        by_stage[r["stage"]].append(r)

    lines += [
        "",
        "All client regions combined (sums; worst region's p90 TTFT):",
        "",
        "| stage | offered QPS | done rps | ok | errors | out tok/s | goodput rps | worst p90 TTFT (ms) |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for s in sorted(by_stage):
        s_rows = by_stage[s]
        any_region_dead = any(
            (r.get("failures") or 0) > 0 and (r.get("successes") or 0) == 0
            for r in s_rows
        )
        ttft_vals = [
            r["ttft_p90_ms"] for r in s_rows if r.get("ttft_p90_ms") is not None
        ]
        worst_ttft = (
            None if any_region_dead else (max(ttft_vals) if ttft_vals else None)
        )
        lines.append(
            f"| {s} | {fmt(sum(r['requested_qps'] or 0 for r in s_rows))} | "
            f"{fmt(sum(r['completed_rps'] or 0 for r in s_rows), 2)} | "
            f"{int(sum(r['successes'] or 0 for r in s_rows))} | "
            f"{int(sum(r['failures'] or 0 for r in s_rows))} | "
            f"{fmt(sum(r['output_tokens_per_s'] or 0 for r in s_rows), 0)} | "
            f"{fmt(sum(r['goodput_rps'] or 0 for r in s_rows), 2)} | "
            f"{fmt(worst_ttft, 0)} |"
        )
    analyze.write_csv(
        os.path.join(args.out, "stages.csv"), stages, analyze.STAGE_COLUMNS
    )

    # Autoscaling timeline.
    lines += [
        "",
        "## Autoscaling",
        "",
        "Times are relative to the start of the first stage.",
        "",
        "| region | HPA desired-replica changes | first time at max ready | max ready | max GPU nodes |",
        "|---|---|---:|---:|---:|",
    ]
    pod_rows = []
    for key in keys:
        recs = recorder.get(key, [])
        events = scale_events(recs)
        max_ready = max((r.get("deploy_ready") or 0 for r in recs), default=0)
        t_max = (
            first_time(recs, lambda r, m=max_ready: (r.get("deploy_ready") or 0) >= m)
            if max_ready
            else None
        )
        changes = (
            ", ".join(f"{mmss(t - t0)}: {a}→{b}" for t, a, b in events if a is not None)
            or "none"
        )
        lines.append(
            f"| {key} | {changes} | {mmss(t_max - t0) if t_max else '–'} | {max_ready} | "
            f"{max((r.get('gpu_nodes') or 0 for r in recs), default=0)} |"
        )
        for row in pod_latencies(recs):
            row["region"] = key
            pod_rows.append(row)
    lines += [
        "",
        "Per pod (pods created during the run; `new node`: the pod waited for a GPU node that was "
        "created after it):",
        "",
        "| region | pod | created | new node | wait for node | scheduled → Ready | created → Ready | created → first request served |",
        "|---|---|---:|---|---:|---:|---:|---:|",
    ]
    serving = first_serving(gmp)
    for r in pod_rows:
        r["first_served"] = serving.get(r["pod"])
        r["created_to_served_s"] = (
            (r["first_served"] - r["created"])
            if (r["first_served"] is not None and r["created"] is not None)
            else None
        )
        if r["created"] is not None and r["created"] >= t0 - 60:
            lines.append(
                f"| {r['region']} | `{r['pod'][-5:]}` | {mmss(r['created'] - t0)} | "
                f"{'yes' if r['new_node'] else 'no'} | {mmss(r['wait_for_node_s'])} | "
                f"{mmss(r['start_to_ready_s'])} | {mmss(r['created_to_ready_s'])} | "
                f"{mmss(r['created_to_served_s'])} |"
            )
    analyze.write_csv(os.path.join(args.out, "pods.csv"), pod_rows)

    # Server-side signals per stage.
    if gmp:
        lines += [
            "",
            "## Server-side signals per stage (Managed Service for Prometheus, means over the stage)",
            "",
            "| stage | region | serving pods | waiting | running | KV cache use | prefix hit rate | gen tok/s | p90 TTFT (s) | p90 ITL (ms) |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        clusters = sorted(
            {c for name, m in gmp.items() if name != "pod_success_rps" for c in m}
        )
        for s in sorted(windows):
            for cluster in clusters:
                reg = region_of_cluster(cluster, keys)
                start, end = windows_by_region.get((reg, s), windows[s])

                def m(
                    name: str, c: str = cluster, t_s: float = start, t_e: float = end
                ) -> float | None:
                    return mean_in(gmp.get(name, {}).get(c, []), t_s, t_e)

                kv, hit, itl = m("kv_cache_usage"), m("prefix_hit_rate"), m("itl_p90_s")
                lines.append(
                    f"| {s} | {reg} | {fmt(m('serving_pods'))} | {fmt(m('waiting'))} | "
                    f"{fmt(m('running'))} | {fmt(kv * 100 if kv is not None else None)}% | "
                    f"{fmt(hit * 100 if hit is not None else None)}% | {fmt(m('gen_tokens_per_s'), 0)} | "
                    f"{fmt(m('ttft_p90_s'), 2)} | {fmt(itl * 1000 if itl is not None else None)} |"
                )
        if not args.gmp_json:
            with open(os.path.join(args.out, "gmp.json"), "w", encoding="utf-8") as f:
                json.dump(gmp, f)

    charts = plot_timeline(
        args.out, t0, windows, recorder, gmp, keys, stage_qps, args.slo_ttft_ms
    )
    charts += plot_stages(args.out, stages, keys, args.slo_ttft_ms)
    if charts:
        lines += ["", "## Charts", ""] + [
            f"![{os.path.basename(c)}]({os.path.basename(c)})" for c in charts
        ]
    if notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(
        f"wrote {args.out}/report.md, stages.csv, pods.csv"
        + (f" and {len(charts)} charts" if charts else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
