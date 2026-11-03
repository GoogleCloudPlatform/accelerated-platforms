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
                       [--namespace <ns>] [--no-gmp]

It combines:
  - the client-side golden signals of every inference-perf stage and client
    region (latency, throughput, errors, goodput),
  - the autoscaling timeline recorded by bench/record_scaling.py (HPA desired
    and current replicas, ready pods, queue metric, GPU nodes), and per-pod
    scale-out latency (created -> scheduled -> ready),
  - optionally, server-side time series from Google Cloud Managed Service for
    Prometheus (p90 TTFT and inter-token latency, queue depth, KV cache
    utilization, prefix cache hit rate, generated tokens/s, per region),
and writes report.md, CSV files, and charts (with matplotlib, if installed).
"""

import argparse
import collections
import csv
import datetime
import glob
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402


def ts(value):
    """Parses an RFC 3339 timestamp into epoch seconds."""
    if not value:
        return None
    value = value.rstrip("Z")
    if "." in value:
        head, frac = value.split(".", 1)
        value = f"{head}.{frac[:6]}"
    return datetime.datetime.fromisoformat(value).replace(tzinfo=datetime.timezone.utc).timestamp()


def fmt(v, digits=1):
    return analyze.fmt(v, digits)


def mmss(seconds):
    if seconds is None:
        return "–"
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def stage_windows(runs_dir):
    """Returns {stage: (start, end)} from inference-perf partial stage reports
    (earliest start and latest end over the client regions)."""
    windows = {}
    for path in glob.glob(os.path.join(runs_dir, "**", "inference-perf.partial.stage_*.yaml"), recursive=True):
        stage = int(path.rsplit("_", 1)[1].split(".")[0])
        with open(path) as f:
            t = json.load(f)["run"]["time"]
        start, end = ts(t["start"]), ts(t["end"])
        old = windows.get(stage)
        windows[stage] = (min(start, old[0]), max(end, old[1])) if old else (start, end)
    return windows


def load_recorder(path):
    by_region = collections.defaultdict(list)
    with open(path) as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                by_region[r["region"]].append(r)
    return dict(by_region)


def pod_latencies(records):
    """Last known state of every model server pod seen by the recorder, with
    its node's creation time."""
    pods, nodes = {}, {}
    for r in records:
        nodes.update(r.get("node_list") or {})
        for p in r.get("pod_list") or []:
            pods[p["name"]] = dict(pods.get(p["name"], {}), **{k: v for k, v in p.items() if v})
    rows = []
    for name, p in pods.items():
        created, scheduled, ready = ts(p.get("created")), ts(p.get("scheduled")), ts(p.get("ready"))
        node_created = ts(nodes.get(p.get("node"))) if p.get("node") else None
        rows.append({
            "pod": name,
            "node": p.get("node"),
            "created": created,
            "node_created": node_created,
            "scheduled": scheduled,
            "ready": ready,
            "wait_for_node_s": (scheduled - created) if (scheduled and created) else None,
            "new_node": bool(node_created and created and node_created > created),
            "start_to_ready_s": (ready - scheduled) if (ready and scheduled) else None,
            "created_to_ready_s": (ready - created) if (ready and created) else None,
        })
    return sorted(rows, key=lambda r: r["created"] or 0)


def scale_events(records):
    """Times at which the HPA's desired replica count changed."""
    events, last = [], None
    for r in records:
        d = r.get("hpa_desired")
        if d is not None and d != last:
            events.append((r["ts"], last, d))
            last = d
    return events


def first_time(records, predicate, after=0):
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
    "serving_pods": "count by (cluster) (max by (cluster, pod) (vllm:num_requests_running{SEL}))",
    "kv_cache_usage": "avg by (cluster) (max by (cluster, pod) (vllm:kv_cache_usage_perc{SEL}))",
    "prefix_hit_rate": "sum by (cluster) (rate(vllm:prefix_cache_hits_total{SEL}[2m])) / sum by (cluster) (rate(vllm:prefix_cache_queries_total{SEL}[2m]))",
    "gen_tokens_per_s": "sum by (cluster) (rate(vllm:generation_tokens_total{SEL}[2m]))",
    "success_rps": "sum by (cluster) (rate(vllm:request_success_total{SEL}[2m]))",
    # Per pod, to find when each new replica served its first request.
    "pod_success_rps": "sum by (cluster, pod) (rate(vllm:request_success_total{SEL}[1m]))",
}


def gmp_query_range(project, query, start, end, step, token):
    url = (f"https://monitoring.googleapis.com/v1/projects/{project}/location/global/prometheus/api/v1/query_range?"
           + urllib.parse.urlencode({"query": query, "start": f"{start:.0f}", "end": f"{end:.0f}", "step": f"{step}s"}))
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    out = {}
    for series in data.get("data", {}).get("result", []):
        key = series["metric"].get("cluster", "?")
        if "pod" in series["metric"]:
            key = f"{key}/{series['metric']['pod']}"
        out[key] = [(float(t), float(v)) for t, v in series["values"] if v not in ("NaN", "+Inf", "-Inf")]
    return out


def gmp_all(project, cluster_regex, namespace, start, end, step=30):
    token = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True,
                           check=True).stdout.strip()
    # One series per pod: GKE automatic application monitoring (job gke-ac-*).
    sel = f'{{cluster=~"{cluster_regex}",namespace="{namespace}",job=~"gke-ac-.*"}}'
    return {name: gmp_query_range(project, q.replace("{SEL}", sel), start, end, step, token)
            for name, q in GMP_QUERIES.items()}


def first_serving(gmp):
    """{pod: first time its request success rate was above zero}."""
    out = {}
    for key, pts in (gmp.get("pod_success_rps") or {}).items():
        pod = key.split("/", 1)[-1]
        t = next((t for t, v in pts if v > 0), None)
        if t is not None:
            out[pod] = t
    return out


def mean_in(points, start, end):
    vals = [v for t, v in points if start <= t <= end]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def region_of_cluster(cluster, keys):
    for k in keys:
        if cluster.endswith(k):
            return k
    return cluster


def plot_timeline(out_dir, t0, windows, recorder, gmp, keys, stage_qps):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    panels = [("replicas", "model server replicas\n(solid: ready, dashed: HPA desired)"),
              ("queue", "HPA metric: waiting\nrequests per pod")]
    if gmp:
        panels += [("ttft", "p90 TTFT (s, server)"), ("tokens", "generated tokens/s")]
    fig, axes = plt.subplots(len(panels), 1, figsize=(10, 2.6 * len(panels)), sharex=True)
    colors = dict(zip(keys, ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple"]))
    for ax, (panel, label) in zip(axes, panels):
        for key in keys:
            recs = recorder.get(key, [])
            x = [(r["ts"] - t0) / 60 for r in recs]
            if panel == "replicas":
                ax.step(x, [r.get("deploy_ready") for r in recs], where="post", color=colors[key], label=key)
                ax.step(x, [r.get("hpa_desired") for r in recs], where="post", color=colors[key], linestyle="--", alpha=0.6)
            elif panel == "queue":
                ax.plot(x, [r.get("hpa_metric") for r in recs], color=colors[key], label=key)
            else:
                metric = "ttft_p90_s" if panel == "ttft" else "gen_tokens_per_s"
                for cluster, pts in (gmp.get(metric) or {}).items():
                    if region_of_cluster(cluster, keys) == key:
                        ax.plot([(t - t0) / 60 for t, _ in pts], [v for _, v in pts], color=colors[key], label=key)
        if panel == "ttft":
            ax.set_yscale("log")
            ax.axhline(2.0, color="grey", linestyle=":", linewidth=1)
        ax.set_ylabel(label, fontsize=8)
        ax.grid(alpha=0.3)
        for stage, (start, end) in sorted(windows.items()):
            ax.axvspan((start - t0) / 60, (end - t0) / 60, color="grey", alpha=0.06 if stage % 2 else 0.12)
    for stage, (start, _end) in sorted(windows.items()):
        axes[0].annotate(f"{stage_qps.get(stage, '?')} QPS", ((start - t0) / 60, axes[0].get_ylim()[1]),
                         fontsize=7, va="top")
    axes[0].legend(fontsize=8, loc="upper left")
    axes[-1].set_xlabel("minutes since the first stage started")
    fig.suptitle("Scale-out timeline per region (shaded: benchmark stages)")
    fig.tight_layout()
    path = os.path.join(out_dir, "scale_timeline.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return [path]


def plot_stages(out_dir, stages, keys, slo_ttft_ms):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for key in keys:
        rows = sorted((r for r in stages if r["client"] == key), key=lambda r: r["stage"])
        x = [r["stage"] for r in rows]
        axes[0].plot(x, [r["ttft_p90_ms"] for r in rows], marker="o", label=key)
        axes[1].plot(x, [r["goodput_rps"] for r in rows], marker="o", label=key)
        axes[2].plot(x, [r["output_tokens_per_s"] for r in rows], marker="o", label=key)
    axes[0].set_yscale("log")
    axes[0].axhline(slo_ttft_ms, color="grey", linestyle=":")
    for ax, title in zip(axes, ["p90 TTFT (ms, client)", "goodput (requests/s within SLO)", "output tokens/s"]):
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("stage")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    path = os.path.join(out_dir, "scale_stages.png")
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return [path]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", required=True)
    p.add_argument("--recorder", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--project")
    p.add_argument("--cluster-regex", default=".*")
    p.add_argument("--namespace", default="llm-mr")
    p.add_argument("--no-gmp", action="store_true")
    p.add_argument("--slo-ttft-ms", type=float, default=2000.0)
    args = p.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)

    stages, notes = analyze.collect([args.runs])
    windows = stage_windows(args.runs)
    recorder = load_recorder(args.recorder)
    keys = sorted(recorder) if recorder else sorted({r["client"] for r in stages})
    stage_qps = {r["stage"]: r["requested_qps"] for r in stages}
    t0 = min(w[0] for w in windows.values()) if windows else min(r["ts"] for rs in recorder.values() for r in rs)
    t_end = max(w[1] for w in windows.values()) if windows else max(r["ts"] for rs in recorder.values() for r in rs)

    gmp = {}
    if not args.no_gmp and args.project:
        try:
            gmp = gmp_all(args.project, args.cluster_regex, args.namespace, t0 - 120, t_end + 120)
        except Exception as e:  # report without server-side metrics
            notes.append(f"Managed Service for Prometheus query failed: {e}")

    lines = ["# Scale-out experiment", ""]
    lines += [f"Stages: " + ", ".join(f"{s}: {stage_qps.get(s)} QPS per client region, "
                                       f"{mmss(windows[s][0] - t0)}–{mmss(windows[s][1] - t0)}"
                                       for s in sorted(windows)), ""]

    # Client-side golden signals per stage and region.
    lines += ["## Client-side golden signals per stage", "",
              "| stage | QPS | client | achieved | done rps | errors | TTFT p50/p90/p99 (ms) | TPOT p90 (ms) | E2E p90 (s) | out tok/s | goodput rps |",
              "|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    for r in sorted(stages, key=lambda r: (r["stage"], r["client"])):
        lines.append(
            f"| {r['stage']} | {fmt(r['requested_qps'])} | {r['client']} | {fmt(r['achieved_qps'], 2)} | "
            f"{fmt(r['completed_rps'], 2)} | {r['failures']} | {fmt(r['ttft_p50_ms'], 0)}/{fmt(r['ttft_p90_ms'], 0)}/"
            f"{fmt(r['ttft_p99_ms'], 0)} | {fmt(r['tpot_p90_ms'])} | "
            f"{fmt(r['e2e_p90_ms'] / 1000 if r['e2e_p90_ms'] else None)} | {fmt(r['output_tokens_per_s'], 0)} | "
            f"{fmt(r['goodput_rps'], 2)} |")
    agg = collections.defaultdict(lambda: collections.defaultdict(float))
    worst = collections.defaultdict(float)
    for r in stages:
        a = agg[r["stage"]]
        for k in ("requested_qps", "completed_rps", "output_tokens_per_s", "goodput_rps", "successes", "failures"):
            a[k] += r[k] or 0
        worst[r["stage"]] = max(worst[r["stage"]], r["ttft_p90_ms"] or 0)
    lines += ["", "All client regions combined (sums; worst region's p90 TTFT):", "",
              "| stage | offered QPS | done rps | ok | errors | out tok/s | goodput rps | worst p90 TTFT (ms) |",
              "|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in sorted(agg):
        a = agg[s]
        lines.append(f"| {s} | {fmt(a['requested_qps'])} | {fmt(a['completed_rps'], 2)} | {int(a['successes'])} | "
                     f"{int(a['failures'])} | {fmt(a['output_tokens_per_s'], 0)} | {fmt(a['goodput_rps'], 2)} | "
                     f"{fmt(worst[s], 0)} |")
    analyze.write_csv(os.path.join(args.out, "stages.csv"), stages, analyze.STAGE_COLUMNS)

    # Autoscaling timeline.
    lines += ["", "## Autoscaling", "",
              "Times are relative to the start of the first stage.", "",
              "| region | HPA desired-replica changes | first time at max ready | max ready | max GPU nodes |",
              "|---|---|---:|---:|---:|"]
    pod_rows = []
    for key in keys:
        recs = recorder.get(key, [])
        events = scale_events(recs)
        max_ready = max((r.get("deploy_ready") or 0 for r in recs), default=0)
        t_max = first_time(recs, lambda r: (r.get("deploy_ready") or 0) >= max_ready) if max_ready else None
        changes = ", ".join(f"{mmss(t - t0)}: {a}→{b}" for t, a, b in events if a is not None) or "none"
        lines.append(f"| {key} | {changes} | {mmss(t_max - t0) if t_max else '–'} | {max_ready} | "
                     f"{max((r.get('gpu_nodes') or 0 for r in recs), default=0)} |")
        for row in pod_latencies(recs):
            row["region"] = key
            pod_rows.append(row)
    lines += ["", "Per pod (pods created during the run; `new node`: the pod waited for a GPU node that was "
              "created after it):", "",
              "| region | pod | created | new node | wait for node | scheduled → Ready | created → Ready | created → first request served |",
              "|---|---|---:|---|---:|---:|---:|---:|"]
    serving = first_serving(gmp)
    for r in pod_rows:
        r["first_served"] = serving.get(r["pod"])
        r["created_to_served_s"] = (r["first_served"] - r["created"]) if (r["first_served"] and r["created"]) else None
        if r["created"] and r["created"] >= t0 - 60:
            lines.append(f"| {r['region']} | `{r['pod'][-5:]}` | {mmss(r['created'] - t0)} | "
                         f"{'yes' if r['new_node'] else 'no'} | {mmss(r['wait_for_node_s'])} | "
                         f"{mmss(r['start_to_ready_s'])} | {mmss(r['created_to_ready_s'])} | "
                         f"{mmss(r['created_to_served_s'])} |")
    analyze.write_csv(os.path.join(args.out, "pods.csv"), pod_rows)

    # Server-side signals per stage.
    if gmp:
        lines += ["", "## Server-side signals per stage (Managed Service for Prometheus, means over the stage)", "",
                  "| stage | region | serving pods | waiting | running | KV cache use | prefix hit rate | gen tok/s | p90 TTFT (s) | p90 ITL (ms) |",
                  "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        clusters = sorted({c for name, m in gmp.items() if name != "pod_success_rps" for c in m})
        for s in sorted(windows):
            start, end = windows[s]
            for cluster in clusters:
                def m(name):
                    return mean_in(gmp.get(name, {}).get(cluster, []), start, end)
                kv, hit, itl = m("kv_cache_usage"), m("prefix_hit_rate"), m("itl_p90_s")
                lines.append(
                    f"| {s} | {region_of_cluster(cluster, keys)} | {fmt(m('serving_pods'))} | {fmt(m('waiting'))} | "
                    f"{fmt(m('running'))} | {fmt(kv * 100 if kv is not None else None)}% | "
                    f"{fmt(hit * 100 if hit is not None else None)}% | {fmt(m('gen_tokens_per_s'), 0)} | "
                    f"{fmt(m('ttft_p90_s'), 2)} | {fmt(itl * 1000 if itl is not None else None)} |")
        with open(os.path.join(args.out, "gmp.json"), "w") as f:
            json.dump(gmp, f)

    charts = plot_timeline(args.out, t0, windows, recorder, gmp, keys, stage_qps)
    charts += plot_stages(args.out, stages, keys, args.slo_ttft_ms)
    if charts:
        lines += ["", "## Charts", ""] + [f"![{os.path.basename(c)}]({os.path.basename(c)})" for c in charts]
    if notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    with open(os.path.join(args.out, "report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {args.out}/report.md, stages.csv, pods.csv" + (f" and {len(charts)} charts" if charts else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
