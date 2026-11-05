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

"""Compares inference-perf v0.7.0 results across experiment arms.

Reads the run directories written by scripts/run-benchmark.sh:

  <dir>/.../<arm>/<workload>/run.json
  <dir>/.../<arm>/<workload>/<client>/client.json
  <dir>/.../<arm>/<workload>/<client>/reports/stage_<N>_lifecycle_metrics.json
  <dir>/.../<arm>/<workload>/<client>/reports/summary_lifecycle_metrics.json

and writes stages.csv, summary.csv, aggregate.csv, relative.csv, report.md and, when
matplotlib is installed, PNG charts to --out.

Python 3 standard library only; matplotlib is optional.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

STAGE_FILE = re.compile(r"^stage_(\d+)_lifecycle_metrics\.json$")
RFC3339_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)
LATENCIES = {
    "ttft": "time_to_first_token",
    "tpot": "time_per_output_token",
    "itl": "inter_token_latency",
    "e2e": "request_latency",
}
PERCENTILES = ("p50", "p90", "p99")

STAGE_COLUMNS = (
    [
        "run_id",
        "arm",
        "workload",
        "client",
        "target",
        "stage",
        "requested_qps",
        "achieved_qps",
        "completed_rps",
    ]
    + ["successes", "failures", "error_rate"]
    + [f"{m}_{p}_ms" for m in LATENCIES for p in PERCENTILES]
    + [
        "output_tokens_per_s",
        "input_tokens_per_s",
        "goodput_rps",
        "goodput_pct",
        "slo_attainment_pct",
    ]
)
SUMMARY_COLUMNS = [
    "run_id",
    "arm",
    "workload",
    "client",
    "target",
    "stages",
    "max_qps_p90_ttft_slo",
    "max_qps_p90_ttft_tpot_slo",
    "max_goodput_rps",
    "max_output_tokens_per_s",
    "total_successes",
    "total_failures",
]
RELATIVE_METRICS = [
    ("ttft_p50_ms", "lower"),
    ("ttft_p90_ms", "lower"),
    ("tpot_p90_ms", "lower"),
    ("itl_p90_ms", "lower"),
    ("e2e_p90_ms", "lower"),
    ("output_tokens_per_s", "higher"),
    ("goodput_rps", "higher"),
]


def load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_rfc3339_epoch(value: str | None) -> float | None:
    """Parses an RFC 3339 timestamp with arbitrary fractional digits to UTC epoch seconds.

    Returns None for a missing (empty) value and raises ValueError for a
    malformed one.
    """
    if not value:
        return None
    m = RFC3339_RE.match(value.strip())
    if not m:
        raise ValueError(f"invalid RFC 3339 timestamp: {value!r}")
    base, frac, tz = m.groups()
    tz_str = (tz or "Z").replace("Z", "+00:00")
    dt = datetime.fromisoformat(base + tz_str).astimezone(timezone.utc)
    return dt.timestamp() + (float(frac) if frac else 0.0)


def epoch_seconds(value: Any) -> float | None:
    """Converts a timestamp to UTC epoch seconds.

    Accepts epoch seconds, RFC 3339 strings, and datetimes (PyYAML parses
    unquoted YAML timestamps into datetimes; naive ones are UTC).
    """
    if isinstance(value, datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.timestamp()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        return parse_rfc3339_epoch(value)
    return None


def get(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict) or d.get(k) is None:
            return None
        d = d[k]
    return d


def percentile(summary: Any, p: str) -> float | None:
    """Reads a percentile from an inference-perf `summarize()` dict.

    inference-perf names the 50th percentile "median" and the others p<N>.
    """
    if not isinstance(summary, dict):
        return None
    if p == "p50":
        return summary.get("median", summary.get("p50"))
    return summary.get(p)


def ms(seconds: float | None) -> float | None:
    return None if seconds is None else seconds * 1000.0


def parse_stage(report: dict[str, Any]) -> dict[str, Any]:
    """Flattens one stage_<N>_lifecycle_metrics.json into a row."""
    load = report.get("load_summary") or {}
    succ = report.get("successes") or {}
    fail = report.get("failures") or {}
    n_ok = int(succ.get("count") or 0)
    n_fail = int(fail.get("count") or 0)
    total = n_ok + n_fail
    all_failed = total > 0 and n_ok == 0

    completed_rps = get(succ, "throughput", "requests_per_sec")
    output_tok_s = get(succ, "throughput", "output_tokens_per_sec")
    input_tok_s = get(succ, "throughput", "input_tokens_per_sec")
    goodput = succ.get("goodput_metrics") or {}
    goodput_rps = goodput.get("request_goodput")
    goodput_pct = goodput.get("goodput_percentage")
    good = goodput.get("good_requests")

    row: dict[str, Any] = {
        "requested_qps": load.get("requested_rate"),
        "achieved_qps": load.get("achieved_rate"),
        "completed_rps": (
            0.0 if (all_failed and completed_rps is None) else completed_rps
        ),
        "successes": n_ok,
        "failures": n_fail,
        "error_rate": (n_fail / total) if total else None,
        "output_tokens_per_s": (
            0.0 if (all_failed and output_tok_s is None) else output_tok_s
        ),
        "input_tokens_per_s": (
            0.0 if (all_failed and input_tok_s is None) else input_tok_s
        ),
    }
    for short, name in LATENCIES.items():
        summary = get(succ, "latency", name)
        for p in PERCENTILES:
            row[f"{short}_{p}_ms"] = ms(percentile(summary, p))
    row["goodput_rps"] = 0.0 if (all_failed and goodput_rps is None) else goodput_rps
    row["goodput_pct"] = 0.0 if (all_failed and goodput_pct is None) else goodput_pct
    if good is not None and total:
        row["slo_attainment_pct"] = 100.0 * good / total
    elif all_failed:
        row["slo_attainment_pct"] = 0.0
    else:
        row["slo_attainment_pct"] = None
    return row


def find_client_dirs(roots: list[str]):
    """Yields (client_dir, reports_dir, run_meta, client_meta) for every client with reports."""
    seen: set[str] = set()
    for root in roots:
        for dirpath, _dirnames, filenames in os.walk(root):
            if "summary_lifecycle_metrics.json" not in filenames and not any(
                STAGE_FILE.match(f) for f in filenames
            ):
                continue
            reports = os.path.realpath(dirpath)
            client_dir = (
                os.path.dirname(reports)
                if os.path.basename(reports) == "reports"
                else reports
            )
            if client_dir in seen:
                continue
            seen.add(client_dir)
            run_dir = os.path.dirname(client_dir)
            run_meta = (
                load_json(os.path.join(run_dir, "run.json"))
                if os.path.exists(os.path.join(run_dir, "run.json"))
                else {}
            )
            client_json = os.path.join(client_dir, "client.json")
            client_meta = load_json(client_json) if os.path.exists(client_json) else {}
            yield client_dir, reports, run_meta, client_meta


def load_partial_report(path: str) -> dict[str, Any]:
    """Loads an inference-perf partial stage report (inference-perf.partial.stage_<N>.yaml).

    inference-perf writes these files as YAML. JSON (a subset of YAML) is parsed
    with the standard library, so PyYAML is only imported for YAML content.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        doc = json.loads(text)
    except ValueError:
        import yaml

        doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a mapping, got {type(doc).__name__}")
    return doc


def _read_stage0_start(reports_dir: str) -> float | None:
    """Reads the Stage 0 start time from inference-perf.partial.stage_0.yaml, if present."""
    partial_path = os.path.join(reports_dir, "inference-perf.partial.stage_0.yaml")
    if not os.path.exists(partial_path):
        return None
    start = get(load_partial_report(partial_path), "run", "time", "start")
    return epoch_seconds(start)


def collect(
    roots: list[str], skew_warn_seconds: float = 5.0
) -> tuple[list[dict[str, Any]], list[str]]:
    stages: list[dict[str, Any]] = []
    notes: list[str] = []
    stage0_starts: dict[tuple[str, str, str], list[tuple[float, str]]] = defaultdict(
        list
    )
    for client_dir, reports, run_meta, client_meta in find_client_dirs(roots):
        parts = client_dir.split(os.sep)
        ident = {
            "run_id": run_meta.get("run_id") or (parts[-4] if len(parts) >= 4 else ""),
            "arm": run_meta.get("arm") or (parts[-3] if len(parts) >= 3 else ""),
            "workload": run_meta.get("workload")
            or (parts[-2] if len(parts) >= 2 else ""),
            "client": client_meta.get("key") or parts[-1],
            "target": client_meta.get("target_key", ""),
        }
        if run_meta.get("status") not in (None, "succeeded"):
            notes.append(f"{client_dir}: run status is {run_meta.get('status')!r}")
        if client_meta.get("status") not in (None, "succeeded"):
            notes.append(
                f"{client_dir}: client status is {client_meta.get('status')!r}"
            )
        s0_start = _read_stage0_start(reports)
        if s0_start is not None:
            stage0_starts[(ident["run_id"], ident["arm"], ident["workload"])].append(
                (s0_start, ident["client"])
            )
        files = sorted(
            (int(m.group(1)), f)
            for f in os.listdir(reports)
            if (m := STAGE_FILE.match(f))
        )
        if not files:
            notes.append(f"{client_dir}: no stage_<N>_lifecycle_metrics.json")
        for stage_id, name in files:
            row: dict[str, Any] = dict(ident, stage=stage_id)
            row.update(parse_stage(load_json(os.path.join(reports, name))))
            row["_slo"] = run_meta.get("slo")
            stages.append(row)

    for (run_id, arm, workload), entries in sorted(stage0_starts.items()):
        if len(entries) < 2:
            continue
        entries.sort()
        skew = entries[-1][0] - entries[0][0]
        if skew > skew_warn_seconds:
            notes.append(
                f"{run_id}/{arm}/{workload}: cross-region Stage 0 start skew is "
                f"{skew:.1f}s ({entries[0][1]} vs {entries[-1][1]})"
            )

    stages.sort(
        key=lambda r: (r["workload"], r["arm"], r["client"], r["run_id"], r["stage"])
    )
    return stages, notes


def meets(
    row: dict[str, Any],
    slo_ttft_ms: float,
    slo_tpot_ms: float,
    use_tpot: bool,
    max_error_rate: float = 0.05,
) -> bool:
    if (row.get("successes") or 0) <= 0:
        return False
    err = row.get("error_rate")
    if err is not None and err > max_error_rate:
        return False
    ttft = row.get("ttft_p90_ms")
    if ttft is None or ttft > slo_ttft_ms:
        return False
    if use_tpot:
        tpot = row.get("tpot_p90_ms")
        if tpot is None or tpot > slo_tpot_ms:
            return False
    return True


def max_qps_within_slo(
    rows: list[dict[str, Any]],
    slo_ttft_ms: float,
    slo_tpot_ms: float,
    use_tpot: bool,
    max_error_rate: float = 0.05,
) -> float | None:
    """Highest requested QPS such that it and every lower stage meet the SLO."""
    best = None
    for row in sorted(rows, key=lambda r: r["requested_qps"] or 0):
        if not meets(row, slo_ttft_ms, slo_tpot_ms, use_tpot, max_error_rate):
            break
        best = row["requested_qps"]
    return best


def summarize(
    stages: list[dict[str, Any]],
    slo_ttft_ms: float,
    slo_tpot_ms: float,
    max_error_rate: float = 0.05,
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = defaultdict(
        list
    )
    for r in stages:
        groups[(r["run_id"], r["arm"], r["workload"], r["client"], r["target"])].append(
            r
        )
    out = []
    for (run_id, arm, workload, client, target), rows in sorted(
        groups.items(), key=lambda kv: kv[0][1:4] + kv[0][:1]
    ):
        out.append(
            {
                "run_id": run_id,
                "arm": arm,
                "workload": workload,
                "client": client,
                "target": target,
                "stages": len(rows),
                "max_qps_p90_ttft_slo": max_qps_within_slo(
                    rows, slo_ttft_ms, slo_tpot_ms, False, max_error_rate
                ),
                "max_qps_p90_ttft_tpot_slo": max_qps_within_slo(
                    rows, slo_ttft_ms, slo_tpot_ms, True, max_error_rate
                ),
                "max_goodput_rps": max(
                    (r["goodput_rps"] for r in rows if r["goodput_rps"] is not None),
                    default=None,
                ),
                "max_output_tokens_per_s": max(
                    (
                        r["output_tokens_per_s"]
                        for r in rows
                        if r["output_tokens_per_s"] is not None
                    ),
                    default=None,
                ),
                "total_successes": sum(r["successes"] for r in rows),
                "total_failures": sum(r["failures"] for r in rows),
            }
        )
    return out


AGGREGATE_COLUMNS = [
    "run_id",
    "arm",
    "workload",
    "stage",
    "requested_qps",
    "clients",
    "completed_rps",
    "successes",
    "failures",
    "output_tokens_per_s",
    "goodput_rps",
    "worst_ttft_p90_ms",
    "worst_tpot_p90_ms",
]


def aggregate(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sums throughput over the client regions of each stage.

    Groups by (run_id, arm, workload, stage, requested_qps) so multi-stage runs
    with repeated QPS levels (for example, sustained scale-out hammers) keep
    each stage distinct rather than summing across stages. Percentiles can't be
    combined across clients, so only the worst client's p90 is reported; if any
    client region had 100% request failures in a stage, worst latency is None
    rather than masking the outage behind another region's latency.
    """
    groups: dict[tuple[str, str, str, int, Any], list[dict[str, Any]]] = defaultdict(
        list
    )
    for r in stages:
        groups[
            (r["run_id"], r["arm"], r["workload"], r["stage"], r["requested_qps"])
        ].append(r)

    def total(rows: list[dict[str, Any]], key: str) -> float | int | None:
        values = [r[key] for r in rows if r[key] is not None]
        return sum(values) if values else None

    def worst(rows: list[dict[str, Any]], key: str) -> float | None:
        if any(
            (r.get("failures") or 0) > 0 and (r.get("successes") or 0) == 0
            for r in rows
        ):
            return None
        values = [r[key] for r in rows if r[key] is not None]
        return max(values) if values else None

    out = []
    for (run_id, arm, workload, stage, qps), rows in sorted(
        groups.items(),
        key=lambda kv: (kv[0][2], kv[0][1], kv[0][0], kv[0][3], kv[0][4] or 0),
    ):
        out.append(
            {
                "run_id": run_id,
                "arm": arm,
                "workload": workload,
                "stage": stage,
                "requested_qps": qps,
                "clients": " ".join(sorted(r["client"] for r in rows)),
                "completed_rps": total(rows, "completed_rps"),
                "successes": total(rows, "successes"),
                "failures": total(rows, "failures"),
                "output_tokens_per_s": total(rows, "output_tokens_per_s"),
                "goodput_rps": total(rows, "goodput_rps"),
                "worst_ttft_p90_ms": worst(rows, "ttft_p90_ms"),
                "worst_tpot_p90_ms": worst(rows, "tpot_p90_ms"),
            }
        )
    return out


def mean(values: Any) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def relative(
    stages: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    baseline: str,
    candidates: list[str],
) -> list[dict[str, Any]]:
    """Relative change of each candidate arm vs the baseline arm.

    Rows are matched on (workload, client, requested QPS); repeated runs of the
    same arm are averaged first.
    """
    by_key: dict[tuple[str, str, str, Any], list[dict[str, Any]]] = defaultdict(list)
    for r in stages:
        by_key[(r["arm"], r["workload"], r["client"], r["requested_qps"])].append(r)
    out = []
    for (arm, workload, client, qps), rows in sorted(
        by_key.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][3] or 0, kv[0][0])
    ):
        if arm not in candidates:
            continue
        base_rows = by_key.get((baseline, workload, client, qps))
        if not base_rows:
            continue
        rec: dict[str, Any] = {
            "workload": workload,
            "client": client,
            "requested_qps": qps,
            "arm": arm,
            "baseline": baseline,
        }
        for metric, _better in RELATIVE_METRICS:
            b = mean(r[metric] for r in base_rows)
            c = mean(r[metric] for r in rows)
            rec[f"{metric}_baseline"] = b
            rec[f"{metric}_arm"] = c
            rec[f"{metric}_change_pct"] = (
                (100.0 * (c - b) / b)
                if (b is not None and b != 0 and c is not None)
                else None
            )
        b_err = mean(r["error_rate"] for r in base_rows)
        c_err = mean(r["error_rate"] for r in rows)
        rec["error_rate_change_pp"] = (
            (100.0 * (c_err - b_err))
            if (b_err is not None and c_err is not None)
            else None
        )
        out.append(rec)

    by_sum: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for s in summary:
        by_sum[(s["arm"], s["workload"], s["client"])].append(s)
    for (arm, workload, client), rows in sorted(
        by_sum.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])
    ):
        if arm not in candidates or (baseline, workload, client) not in by_sum:
            continue
        base = by_sum[(baseline, workload, client)]
        rec = {
            "workload": workload,
            "client": client,
            "requested_qps": "max-within-slo",
            "arm": arm,
            "baseline": baseline,
        }
        for metric in ("max_qps_p90_ttft_slo", "max_qps_p90_ttft_tpot_slo"):
            b = mean(r[metric] for r in base)
            c = mean(r[metric] for r in rows)
            rec[f"{metric}_baseline"] = b
            rec[f"{metric}_arm"] = c
            rec[f"{metric}_change_pct"] = (
                (100.0 * (c - b) / b)
                if (b is not None and b != 0 and c is not None)
                else None
            )
        out.append(rec)
    return out


def fmt(v: Any, digits: int = 1) -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "-"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def fmt_pct(v: float | None) -> str:
    return "-" if v is None else f"{v:+.1f}%"


def write_csv(
    path: str,
    rows: list[dict[str, Any]],
    columns: list[str] | tuple[str, ...] | None = None,
) -> None:
    if columns is None:
        cols: list[str] = []
        for r in rows:
            cols.extend(k for k in r if k not in cols)
        columns = cols
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=list(columns), extrasaction="ignore", lineterminator="\n"
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in columns})


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _distinct_clients(agg_rows: list[dict[str, Any]]) -> list[str]:
    return sorted({c for a in agg_rows for c in (a.get("clients") or "").split() if c})


def write_markdown(
    path: str,
    stages: list[dict[str, Any]],
    summary: list[dict[str, Any]],
    agg: list[dict[str, Any]],
    rel: list[dict[str, Any]],
    args: argparse.Namespace,
    notes: list[str],
    charts: list[str],
) -> None:
    out = [
        "# Benchmark comparison",
        "",
        f"SLO: p90 TTFT <= {args.slo_ttft * 1000:.0f} ms, p90 TPOT <= {args.slo_tpot * 1000:.0f} ms, "
        f"error rate <= {args.max_error_rate * 100:.1f}%. "
        "Goodput is the inference-perf `goodput_metrics.request_goodput` of each stage: requests per second "
        "that met the TTFT and TPOT constraints configured for the run (see run.json `slo`). "
        "Latencies are client-observed, in milliseconds.",
        "",
    ]
    if notes:
        out += ["> [!WARNING]"] + [f"> {n}" for n in notes] + [""]

    out += ["## Capacity within SLO", ""]
    out.append(
        md_table(
            [
                "workload",
                "arm",
                "client",
                "target",
                "max QPS (p90 TTFT)",
                "max QPS (p90 TTFT+TPOT)",
                "max goodput rps",
                "max out tok/s",
                "ok",
                "failed",
            ],
            [
                [
                    s["workload"],
                    s["arm"],
                    s["client"],
                    s["target"],
                    fmt(s["max_qps_p90_ttft_slo"]),
                    fmt(s["max_qps_p90_ttft_tpot_slo"]),
                    fmt(s["max_goodput_rps"], 2),
                    fmt(s["max_output_tokens_per_s"], 0),
                    str(s["total_successes"]),
                    str(s["total_failures"]),
                ]
                for s in summary
            ],
        )
    )
    clients = _distinct_clients(agg)
    if len(clients) == 1:
        single = clients[0]
        agg_heading = f"## Client region `{single}`"
        agg_blurb = f"Single-client-region run (`{single}`)."
        ttft_col = f"{single} TTFT p90"
        tpot_col = f"{single} TPOT p90"
    else:
        agg_heading = "## All client regions combined"
        agg_blurb = (
            "Throughput is summed over clients; latency is the worst client's p90."
        )
        ttft_col = "worst TTFT p90"
        tpot_col = "worst TPOT p90"

    out += [
        "",
        agg_heading,
        "",
        agg_blurb,
        "",
    ]
    out.append(
        md_table(
            [
                "workload",
                "arm",
                "stage",
                "QPS per client",
                "clients",
                "done rps",
                "ok",
                "failed",
                "out tok/s",
                "goodput rps",
                ttft_col,
                tpot_col,
            ],
            [
                [
                    a["workload"],
                    a["arm"],
                    str(a["stage"]),
                    fmt(a["requested_qps"]),
                    a["clients"],
                    fmt(a["completed_rps"], 2),
                    fmt(a["successes"]),
                    fmt(a["failures"]),
                    fmt(a["output_tokens_per_s"], 0),
                    fmt(a["goodput_rps"], 2),
                    fmt(a["worst_ttft_p90_ms"], 0),
                    fmt(a["worst_tpot_p90_ms"], 1),
                ]
                for a in agg
            ],
        )
    )
    out += ["", "## Per stage", ""]
    for workload in sorted({r["workload"] for r in stages}):
        out += [f"### {workload}", ""]
        out.append(
            md_table(
                [
                    "arm",
                    "client",
                    "stage",
                    "QPS",
                    "achieved",
                    "done rps",
                    "err %",
                    "TTFT p50/p90/p99",
                    "TPOT p50/p90/p99",
                    "ITL p50/p90/p99",
                    "E2E p50/p90/p99",
                    "out tok/s",
                    "in tok/s",
                    "goodput rps",
                ],
                [
                    [
                        r["arm"],
                        r["client"],
                        str(r["stage"]),
                        fmt(r["requested_qps"]),
                        fmt(r["achieved_qps"], 2),
                        fmt(r["completed_rps"], 2),
                        fmt(
                            None if r["error_rate"] is None else 100 * r["error_rate"],
                            2,
                        ),
                        "/".join(fmt(r[f"ttft_{p}_ms"], 0) for p in PERCENTILES),
                        "/".join(fmt(r[f"tpot_{p}_ms"], 1) for p in PERCENTILES),
                        "/".join(fmt(r[f"itl_{p}_ms"], 1) for p in PERCENTILES),
                        "/".join(fmt(r[f"e2e_{p}_ms"], 0) for p in PERCENTILES),
                        fmt(r["output_tokens_per_s"], 0),
                        fmt(r["input_tokens_per_s"], 0),
                        fmt(r["goodput_rps"], 2),
                    ]
                    for r in stages
                    if r["workload"] == workload
                ],
            )
        )
        out.append("")

    if rel:
        out += [
            f"## Relative change vs `{args.baseline_arm}`",
            "",
            "Negative is better for latencies; positive is better for throughput and goodput.",
            "",
        ]
        stage_rel = [r for r in rel if r["requested_qps"] != "max-within-slo"]
        if stage_rel:
            out.append(
                md_table(
                    ["workload", "client", "QPS", "arm"]
                    + [m for m, _ in RELATIVE_METRICS]
                    + ["err (pp)"],
                    [
                        [r["workload"], r["client"], fmt(r["requested_qps"]), r["arm"]]
                        + [fmt_pct(r[f"{m}_change_pct"]) for m, _ in RELATIVE_METRICS]
                        + [
                            (
                                "-"
                                if r["error_rate_change_pp"] is None
                                else f"{r['error_rate_change_pp']:+.2f}"
                            )
                        ]
                        for r in stage_rel
                    ],
                )
            )
            out.append("")
        cap_rel = [r for r in rel if r["requested_qps"] == "max-within-slo"]
        if cap_rel:
            out.append(
                md_table(
                    [
                        "workload",
                        "client",
                        "arm",
                        "max QPS (TTFT) base -> arm",
                        "change",
                        "max QPS (TTFT+TPOT) base -> arm",
                        "change",
                    ],
                    [
                        [
                            r["workload"],
                            r["client"],
                            r["arm"],
                            f"{fmt(r['max_qps_p90_ttft_slo_baseline'])} -> {fmt(r['max_qps_p90_ttft_slo_arm'])}",
                            fmt_pct(r["max_qps_p90_ttft_slo_change_pct"]),
                            f"{fmt(r['max_qps_p90_ttft_tpot_slo_baseline'])} -> {fmt(r['max_qps_p90_ttft_tpot_slo_arm'])}",
                            fmt_pct(r["max_qps_p90_ttft_tpot_slo_change_pct"]),
                        ]
                        for r in cap_rel
                    ],
                )
            )
            out.append("")

    if charts:
        out += (
            ["## Charts", ""]
            + [f"![{os.path.basename(c)}]({os.path.basename(c)})" for c in charts]
            + [""]
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def plot(stages: list[dict[str, Any]], out_dir: str, slo_ttft_ms: float) -> list[str]:
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return []
    charts = []
    specs = [
        ("ttft_p90_ms", "p90 TTFT (ms)", slo_ttft_ms),
        ("output_tokens_per_s", "output tokens/s", None),
        ("goodput_rps", "goodput (requests/s within SLO)", None),
    ]
    for workload in sorted({r["workload"] for r in stages}):
        rows = [r for r in stages if r["workload"] == workload]
        for metric, label, hline in specs:
            fig, ax = plt.subplots(figsize=(7, 4.5))
            series: dict[tuple[str, str, str], list[tuple[float, float]]] = defaultdict(
                list
            )
            for r in rows:
                if r["requested_qps"] is not None and r[metric] is not None:
                    series[(r["arm"], r["client"], r["run_id"])].append(
                        (r["requested_qps"], r[metric])
                    )
            if not series:
                plt.close(fig)
                continue
            multi_run = len({k[2] for k in series}) > 1
            for (arm, client, run_id), pts in sorted(series.items()):
                pts.sort()
                name = f"{arm} / {client}" + (f" / {run_id}" if multi_run else "")
                ax.plot(
                    [p[0] for p in pts], [p[1] for p in pts], marker="o", label=name
                )
            if hline is not None:
                ax.axhline(
                    hline, color="grey", linestyle="--", linewidth=1, label="SLO"
                )
            ax.set_xlabel("offered load per client (QPS)")
            ax.set_ylabel(label)
            ax.set_title(f"{workload}: {label}")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)
            path = os.path.join(out_dir, f"{workload}_{metric}.png")
            fig.tight_layout()
            fig.savefig(path, dpi=120)
            plt.close(fig)
            charts.append(path)
    return charts


def aggregate_chart_specs(
    clients: list[str], slo_ttft_ms: float
) -> tuple[list[tuple[str, str, float | None, bool]], str]:
    """Charts of plot_aggregate: ([(metric, label, SLO line, log scale)], x label).

    With a single client region, the labels name it instead of claiming to
    cover every region.
    """
    if len(clients) == 1:
        single = clients[0]
        return [
            ("goodput_rps", f"goodput, {single} (requests/s within SLO)", None, False),
            ("output_tokens_per_s", f"output tokens/s, {single}", None, False),
            (
                "worst_ttft_p90_ms",
                f"{single} p90 TTFT (ms, log scale)",
                slo_ttft_ms,
                True,
            ),
        ], f"offered load from {single} (QPS)"
    return [
        ("goodput_rps", "goodput, all regions (requests/s within SLO)", None, False),
        ("output_tokens_per_s", "output tokens/s, all regions", None, False),
        (
            "worst_ttft_p90_ms",
            "worst region p90 TTFT (ms, log scale)",
            slo_ttft_ms,
            True,
        ),
    ], "offered load per client region (QPS)"


def plot_aggregate(
    agg: list[dict[str, Any]], out_dir: str, slo_ttft_ms: float
) -> list[str]:
    """One line per arm across client regions (or single client region if only one)."""
    try:
        import matplotlib  # type: ignore[import-not-found]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-not-found]
    except ImportError:
        return []
    charts = []
    for workload in sorted({a["workload"] for a in agg}):
        rows = [a for a in agg if a["workload"] == workload]
        specs, xlabel = aggregate_chart_specs(_distinct_clients(rows), slo_ttft_ms)
        for metric, label, hline, log in specs:
            series: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
            for a in rows:
                if a["requested_qps"] is not None and a[metric] is not None:
                    series[(a["arm"], a["run_id"])].append(
                        (a["requested_qps"], a[metric])
                    )
            if not series:
                continue
            fig, ax = plt.subplots(figsize=(7, 4.5))
            multi_run = len({k[1] for k in series}) > 1
            for (arm, run_id), pts in sorted(series.items()):
                pts.sort()
                name = arm + (f" / {run_id}" if multi_run else "")
                ax.plot(
                    [q[0] for q in pts], [q[1] for q in pts], marker="o", label=name
                )
            if log:
                ax.set_yscale("log")
            if hline is not None:
                ax.axhline(
                    hline, color="grey", linestyle="--", linewidth=1, label="SLO"
                )
                ymin, ymax = ax.get_ylim()
                if ymax < hline * 1.35:
                    ax.set_ylim(ymin, hline * 1.35)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(label)
            ax.set_title(f"{workload}: {label}")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=8)
            path = os.path.join(out_dir, f"aggregate_{workload}_{metric}.png")
            fig.tight_layout()
            fig.savefig(path, dpi=120)
            plt.close(fig)
            charts.append(path)
    return charts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("dirs", nargs="+", help="run directories (searched recursively)")
    p.add_argument(
        "--out", default="analysis", help="output directory (default: ./analysis)"
    )
    p.add_argument(
        "--baseline-arm",
        default="vllm",
        help="arm that the other arms are compared to (default: vllm)",
    )
    p.add_argument(
        "--arms",
        default="",
        help="comma-separated candidate arms (default: every non-baseline arm)",
    )
    p.add_argument(
        "--slo-ttft",
        type=float,
        default=2.0,
        help="p90 TTFT SLO in seconds (default: 2.0)",
    )
    p.add_argument(
        "--slo-tpot",
        type=float,
        default=0.1,
        help="p90 TPOT SLO in seconds (default: 0.1)",
    )
    p.add_argument(
        "--max-error-rate",
        type=float,
        default=0.05,
        help="max error rate fraction allowed for max-QPS-within-SLO (default: 0.05)",
    )
    p.add_argument("--no-charts", action="store_true", help="don't write PNG charts")
    args = p.parse_args(argv)

    stages, notes = collect(args.dirs)
    if not stages:
        print(
            "no inference-perf stage reports found under: " + " ".join(args.dirs),
            file=sys.stderr,
        )
        return 1

    run_slos = {json.dumps(r["_slo"], sort_keys=True) for r in stages if r.get("_slo")}
    wanted = json.dumps(
        {"tpot_s": args.slo_tpot, "ttft_s": args.slo_ttft}, sort_keys=True
    )
    if run_slos and run_slos != {wanted}:
        notes.append(
            "goodput columns use the SLO configured at run time ("
            + ", ".join(sorted(run_slos))
            + "), "
            f"which differs from --slo-ttft/--slo-tpot ({wanted}); the max-QPS columns use the latter."
        )

    os.makedirs(args.out, exist_ok=True)
    slo_ttft_ms, slo_tpot_ms = args.slo_ttft * 1000, args.slo_tpot * 1000
    summary = summarize(stages, slo_ttft_ms, slo_tpot_ms, args.max_error_rate)
    arms = sorted({r["arm"] for r in stages})
    candidates = [
        a
        for a in (args.arms.split(",") if args.arms else arms)
        if a and a != args.baseline_arm
    ]
    rel = (
        relative(stages, summary, args.baseline_arm, candidates)
        if args.baseline_arm in arms
        else []
    )
    if args.baseline_arm not in arms:
        notes.append(
            f"baseline arm {args.baseline_arm!r} not found (arms: {', '.join(arms)}); no relative table."
        )

    write_csv(os.path.join(args.out, "stages.csv"), stages, STAGE_COLUMNS)
    write_csv(os.path.join(args.out, "summary.csv"), summary, SUMMARY_COLUMNS)
    agg = aggregate(stages)
    write_csv(os.path.join(args.out, "aggregate.csv"), agg, AGGREGATE_COLUMNS)
    write_csv(os.path.join(args.out, "relative.csv"), rel)
    charts = (
        []
        if args.no_charts
        else plot_aggregate(agg, args.out, slo_ttft_ms)
        + plot(stages, args.out, slo_ttft_ms)
    )
    write_markdown(
        os.path.join(args.out, "report.md"),
        stages,
        summary,
        agg,
        rel,
        args,
        notes,
        charts,
    )
    for n in notes:
        print("WARNING: " + n, file=sys.stderr)
    print(
        f"wrote {args.out}/report.md, stages.csv, summary.csv, aggregate.csv, relative.csv"
        + (f" and {len(charts)} charts" if charts else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
