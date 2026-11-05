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

"""Breaks down model server startup time per Pod.

Each input directory contains:

  pods.json      kubectl get pods -o json       (the model server Pods)
  nodes.json     kubectl get nodes -o json
  events.json    kubectl get events -o json     (namespace events; Pod events
                                                 expire after 1 hour by default)
  markers.json   {"apply_epoch_s": ..., "first_ok_via_gateway_epoch_s": ..., "arm": "..."}
  logs/<pod>.log optional model server logs (kubectl logs --timestamps works best)

and the script writes startup.csv (one row per Pod) and startup.md (per Pod
and per arm) to --out. Python 3 standard library only.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
from datetime import datetime, timezone
from typing import Any

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
LOG_TS = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2}))\s"
)
NUM = r"([0-9]+(?:\.[0-9]+)?)"

# vLLM startup log lines. Every pattern is case-insensitive and matched against
# each line with ANSI colors removed; the last match wins (the current
# container instance after a restart). Several spellings are listed because
# vLLM rewords these messages between releases.
LOG_PATTERNS = {
    "weights_load_s": [
        rf"Loading weights took\s+{NUM}\s*s",
    ],
    "model_load_s": [
        rf"Model loading took\s+[0-9.]+\s*[GM]i?B(?:\s+memory)?\s+and\s+{NUM}\s*s",
        rf"Loading model weights took\s+[0-9.]+\s*[GM]i?B\s+and\s+{NUM}\s*s",
        rf"Model loading took\s+{NUM}\s*s",
    ],
    "dynamo_transform_s": [
        rf"Dynamo bytecode transform time:\s*{NUM}\s*s",
    ],
    "torch_compile_s": [
        rf"torch\.compile takes\s+{NUM}\s*s\s+in total",
        rf"torch\.compile took\s+{NUM}\s*s",
        rf"Compiling a graph for dynamic shape takes\s+{NUM}\s*s",
    ],
    "cuda_graph_s": [
        rf"Graph capturing finished in\s+{NUM}\s*s",
        rf"CUDA graph capturing finished in\s+{NUM}\s*s",
        rf"Capturing CUDA graphs?.*?took\s+{NUM}\s*s",
    ],
    "engine_init_s": [
        rf"init engine \(profile, create kv cache, warmup model\) took\s+{NUM}\s*s",
        rf"init engine.*?took\s+{NUM}\s*s",
    ],
    "kv_cache_tokens": [
        r"GPU KV cache size:\s*([0-9,]+)\s*tokens",
    ],
}
LOG_EVENTS = {
    "app_startup_complete": re.compile(r"Application startup complete", re.IGNORECASE),
}
COMPILED = {
    k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in LOG_PATTERNS.items()
}
GO_DURATION = re.compile(r"([0-9]+(?:\.[0-9]+)?)(h|ms|us|µs|ns|m|s)")
GO_UNITS = {
    "h": 3600.0,
    "m": 60.0,
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "µs": 1e-6,
    "ns": 1e-9,
}
PULLED = re.compile(
    r'Successfully pulled image "([^"]+)" in ([0-9hmsuµn.]+)(?: \(([0-9hmsuµn.]+) including waiting\))?'
)
PRESENT = re.compile(r'Container image "([^"]+)" already present on machine')

COLUMNS = [
    "source",
    "arm",
    "pod",
    "node",
    "node_provisioned",
    "restarts",
    "apply_to_scheduled_s",
    "apply_to_node_created_s",
    "node_created_to_ready_s",
    "node_ready_to_scheduled_s",
    "scheduled_to_initialized_s",
    "image_pull_s",
    "image_pull_incl_wait_s",
    "images_cached",
    "container_start_to_ready_s",
    "container_start_to_app_startup_s",
    "weights_load_s",
    "model_load_s",
    "dynamo_transform_s",
    "torch_compile_s",
    "cuda_graph_s",
    "engine_init_s",
    "kv_cache_tokens",
    "apply_to_ready_s",
]


def parse_ts(value: str | int | float | None) -> float | None:
    """RFC 3339 (with up to nanosecond fractions) to epoch seconds."""
    if not value:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$",
        value.strip(),
    )
    if not m:
        return None
    base, frac, tz = m.groups()
    dt = datetime.fromisoformat(base + ((tz or "Z").replace("Z", "+00:00"))).astimezone(
        timezone.utc
    )
    return dt.timestamp() + (float(frac) if frac else 0.0)


def go_duration(text: str | None) -> float | None:
    if not text:
        return None
    total, matched = 0.0, False
    for num, unit in GO_DURATION.findall(text):
        total += float(num) * GO_UNITS[unit]
        matched = True
    return total if matched else None


def diff(end: float | None, start: float | None) -> float | None:
    return None if end is None or start is None else round(end - start, 3)


def load_json(path: str, default: Any = None) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def items(doc: Any) -> list[dict[str, Any]]:
    if doc is None:
        return []
    return doc.get("items", []) if isinstance(doc, dict) else list(doc)


def condition_time(obj: dict[str, Any], ctype: str) -> float | None:
    for c in (obj.get("status") or {}).get("conditions") or []:
        if c.get("type") == ctype and c.get("status") == "True":
            return parse_ts(c.get("lastTransitionTime"))
    return None


def event_fields(ev: dict[str, Any]) -> dict[str, Any]:
    """Normalizes core/v1 and events.k8s.io/v1 Events."""
    obj = ev.get("involvedObject") or ev.get("regarding") or {}
    ts = (
        parse_ts(ev.get("eventTime"))
        or parse_ts(ev.get("firstTimestamp"))
        or parse_ts(ev.get("deprecatedFirstTimestamp"))
        or parse_ts(ev.get("lastTimestamp"))
        or parse_ts((ev.get("metadata") or {}).get("creationTimestamp"))
    )
    return {
        "kind": obj.get("kind"),
        "name": obj.get("name"),
        "field_path": obj.get("fieldPath") or "",
        "reason": ev.get("reason") or "",
        "message": ev.get("message") or ev.get("note") or "",
        "ts": ts,
    }


def image_pulls(
    pod_name: str, events: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Per container image pull durations from Pulling/Pulled events.

    Uses the duration in the kubelet's Pulled message when present (it excludes
    queueing behind other pulls), and Pulled - Pulling event times otherwise.
    Preserves an initial cold pull duration even if a subsequent container
    restart logs a cached "already present on machine" Pulled event.
    """
    pulls: dict[str, dict[str, Any]] = {}
    for ev in events:
        if (
            ev["kind"] != "Pod"
            or ev["name"] != pod_name
            or ev["reason"] not in ("Pulling", "Pulled")
        ):
            continue
        m = re.search(r"\{(.+)\}", ev["field_path"])
        container = m.group(1) if m else ev["field_path"] or "?"
        p = pulls.setdefault(
            container,
            {
                "pulling": None,
                "pulled": None,
                "pull_s": None,
                "wait_s": None,
                "cached": False,
            },
        )
        if ev["reason"] == "Pulling":
            p["pulling"] = (
                ev["ts"]
                if p["pulling"] is None
                else min(p["pulling"], ev["ts"] or p["pulling"])
            )
        elif ev["reason"] == "Pulled":
            p["pulled"] = ev["ts"]
            if (mm := PULLED.search(ev["message"])) is not None:
                dur = go_duration(mm.group(2))
                wait_dur = go_duration(mm.group(3)) if mm.group(3) else dur
                p["pull_s"] = (
                    dur if p["pull_s"] is None else max(p["pull_s"], dur or 0.0)
                )
                p["wait_s"] = (
                    wait_dur
                    if p["wait_s"] is None
                    else max(p["wait_s"], wait_dur or 0.0)
                )
                p["cached"] = False
            elif PRESENT.search(ev["message"]):
                if p["pull_s"] is None:
                    p["pull_s"], p["wait_s"], p["cached"] = 0.0, 0.0, True
    for p in pulls.values():
        if p["pull_s"] is None and p["pulling"] is not None and p["pulled"] is not None:
            p["pull_s"] = p["wait_s"] = round(p["pulled"] - p["pulling"], 3)
    return pulls


def parse_log(path: str) -> dict[str, Any]:
    out: dict[str, Any] = {k: None for k in LOG_PATTERNS}
    out.update({k: None for k in LOG_EVENTS})
    if not path or not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = ANSI.sub("", raw.rstrip("\n"))
            m = LOG_TS.match(line)
            line_ts = parse_ts(m.group(1)) if m else None
            for key, patterns in COMPILED.items():
                for pat in patterns:
                    if (mm := pat.search(line)) is not None:
                        value = mm.group(1).replace(",", "")
                        out[key] = (
                            int(value) if key == "kv_cache_tokens" else float(value)
                        )
                        break
            for key, pat in LOG_EVENTS.items():
                if line_ts is not None and pat.search(line):
                    out[key] = line_ts
    return out


def pick_container(pod: dict[str, Any], name_hint: str) -> dict[str, Any] | None:
    statuses = (pod.get("status") or {}).get("containerStatuses") or []
    if not statuses:
        return None
    for s in statuses:
        if name_hint and s.get("name") == name_hint:
            return s
    for s in statuses:
        if "vllm" in (s.get("name") or "") or "vllm" in (s.get("image") or ""):
            return s
    return statuses[0]


def get_started(status: dict[str, Any] | None) -> str | None:
    if not status:
        return None
    state = status.get("state") or {}
    for key in ("running", "terminated"):
        if state.get(key, {}).get("startedAt"):
            return state[key]["startedAt"]
    return None


def resolve_source_labels(dirs: list[str]) -> list[str]:
    """Computes unique source labels across input directories."""
    norm_dirs = [os.path.normpath(d) for d in dirs]
    basenames = [os.path.basename(d) for d in norm_dirs]
    if len(set(basenames)) == len(norm_dirs):
        return basenames
    abs_dirs = [os.path.abspath(d) for d in norm_dirs]
    common = os.path.commonpath(abs_dirs)
    return [os.path.relpath(d, common) for d in abs_dirs]


def analyze_dir(
    source_dir: str, args: argparse.Namespace, source_label: str | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pods = items(load_json(os.path.join(source_dir, "pods.json"), {}))
    nodes = {
        n["metadata"]["name"]: n
        for n in items(load_json(os.path.join(source_dir, "nodes.json"), {}))
    }
    events = [
        event_fields(e)
        for e in items(load_json(os.path.join(source_dir, "events.json"), {}))
    ]
    markers = load_json(os.path.join(source_dir, "markers.json"), {}) or {}
    apply_ts = parse_ts(markers.get("apply_epoch_s"))
    first_ok = parse_ts(markers.get("first_ok_via_gateway_epoch_s"))
    arm = markers.get("arm", "")
    source = source_label or os.path.basename(os.path.normpath(source_dir))
    pod_filter = re.compile(args.pod_regex) if args.pod_regex else None

    rows: list[dict[str, Any]] = []
    for pod in pods:
        name = pod["metadata"]["name"]
        if pod_filter and not pod_filter.search(name):
            continue
        created = parse_ts(pod["metadata"].get("creationTimestamp"))
        start = apply_ts if apply_ts is not None else created
        scheduled = condition_time(pod, "PodScheduled")
        initialized = condition_time(pod, "Initialized")
        ready = condition_time(pod, "Ready")
        node_name = (pod.get("spec") or {}).get("nodeName")
        node = (nodes.get(node_name) if node_name else None) or {}
        node_created = parse_ts((node.get("metadata") or {}).get("creationTimestamp"))
        node_ready = condition_time(node, "Ready") if node else None
        provisioned = (
            node_created is not None and created is not None and node_created >= created
        )
        main = pick_container(pod, args.container)
        restarts = sum(
            s.get("restartCount", 0)
            for s in (pod.get("status") or {}).get("containerStatuses") or []
        )
        container_started = parse_ts(get_started(main))

        pulls = image_pulls(name, events)
        pull_values = [p["pull_s"] for p in pulls.values() if p["pull_s"] is not None]
        wait_values = [p["wait_s"] for p in pulls.values() if p["wait_s"] is not None]

        log = parse_log(os.path.join(source_dir, "logs", f"{name}.log"))
        rows.append(
            {
                "source": source,
                "arm": arm,
                "pod": name,
                "node": node_name or "",
                "node_provisioned": provisioned if node_created is not None else None,
                "restarts": restarts,
                "apply_to_scheduled_s": diff(scheduled, start),
                "apply_to_node_created_s": (
                    diff(node_created, start) if provisioned else None
                ),
                "node_created_to_ready_s": (
                    diff(node_ready, node_created) if provisioned else None
                ),
                "node_ready_to_scheduled_s": (
                    diff(scheduled, node_ready) if provisioned else None
                ),
                "scheduled_to_initialized_s": diff(initialized, scheduled),
                "image_pull_s": round(sum(pull_values), 3) if pull_values else None,
                "image_pull_incl_wait_s": (
                    round(sum(wait_values), 3) if wait_values else None
                ),
                "images_cached": (
                    all(p["cached"] for p in pulls.values()) if pulls else None
                ),
                "container_start_to_ready_s": diff(ready, container_started),
                "container_start_to_app_startup_s": diff(
                    log["app_startup_complete"], container_started
                ),
                **{k: log[k] for k in LOG_PATTERNS},
                "apply_to_ready_s": diff(ready, start),
                "_ready": ready,
            }
        )
    non_null_readies = [r["_ready"] for r in rows if r["_ready"] is not None]
    summary = {
        "source": source,
        "arm": arm,
        "pods": len(rows),
        "pods_ready": len(non_null_readies),
        "apply_to_all_pods_ready_s": (
            diff(max(non_null_readies), apply_ts)
            if rows and len(non_null_readies) == len(rows)
            else None
        ),
        "apply_to_first_ok_via_gateway_s": diff(first_ok, apply_ts),
    }
    return rows, summary


def fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    return "\n".join(
        lines + ["| " + " | ".join(fmt(c) for c in r) + " |" for r in rows]
    )


def write_outputs(
    out_dir: str, rows: list[dict[str, Any]], summaries: list[dict[str, Any]]
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(
        os.path.join(out_dir, "startup.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.DictWriter(
            f, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n"
        )
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in COLUMNS})

    md = ["# Model server startup", "", "## Per arm", ""]
    md.append(
        md_table(
            [
                "source",
                "arm",
                "pods",
                "ready",
                "apply -> all Pods Ready (s)",
                "apply -> first OK via gateway (s)",
            ],
            [
                [
                    s["source"],
                    s["arm"],
                    s["pods"],
                    s["pods_ready"],
                    s["apply_to_all_pods_ready_s"],
                    s["apply_to_first_ok_via_gateway_s"],
                ]
                for s in summaries
            ],
        )
    )
    phases = [
        ("apply -> scheduled", "apply_to_scheduled_s"),
        ("node create -> Ready", "node_created_to_ready_s"),
        ("image pull", "image_pull_s"),
        ("scheduled -> initialized", "scheduled_to_initialized_s"),
        ("weights load", "weights_load_s"),
        ("model load", "model_load_s"),
        ("torch.compile", "torch_compile_s"),
        ("CUDA graphs", "cuda_graph_s"),
        ("engine init", "engine_init_s"),
        ("container start -> Ready", "container_start_to_ready_s"),
        ("apply -> Ready", "apply_to_ready_s"),
    ]
    md += ["", "## Phase medians (seconds)", ""]
    table = []
    for label, key in phases:
        for s in summaries:
            values = [
                r[key]
                for r in rows
                if r["source"] == s["source"]
                and r["arm"] == s["arm"]
                and r[key] is not None
            ]
            table.append(
                [
                    label,
                    s["source"],
                    s["arm"],
                    len(values),
                    statistics.median(values) if values else None,
                    max(values) if values else None,
                ]
            )
    md.append(md_table(["phase", "source", "arm", "pods", "median", "max"], table))
    md += ["", "## Per Pod (seconds)", ""]
    headers = [
        "pod",
        "node",
        "new node",
        "apply->sched",
        "node create->Ready",
        "pull",
        "sched->init",
        "start->Ready",
        "weights",
        "model load",
        "compile",
        "graphs",
        "engine init",
        "apply->Ready",
        "restarts",
    ]
    md.append(
        md_table(
            headers,
            [
                [
                    r["pod"],
                    r["node"],
                    r["node_provisioned"],
                    r["apply_to_scheduled_s"],
                    r["node_created_to_ready_s"],
                    r["image_pull_s"],
                    r["scheduled_to_initialized_s"],
                    r["container_start_to_ready_s"],
                    r["weights_load_s"],
                    r["model_load_s"],
                    r["torch_compile_s"],
                    r["cuda_graph_s"],
                    r["engine_init_s"],
                    r["apply_to_ready_s"],
                    r["restarts"],
                ]
                for r in rows
            ],
        )
    )
    md.append("")
    with open(os.path.join(out_dir, "startup.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(
        os.path.join(out_dir, "startup_summary.json"), "w", encoding="utf-8"
    ) as f:
        json.dump(summaries, f, indent=2)
        f.write("\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "dirs",
        nargs="+",
        help="directories with pods.json, nodes.json, events.json, markers.json",
    )
    p.add_argument(
        "--out",
        help="output directory (default: the only input directory, else ./startup)",
    )
    p.add_argument(
        "--pod-regex",
        default="",
        help="only include Pods whose name matches this regex",
    )
    p.add_argument(
        "--container",
        default="",
        help="model server container name (default: first container named or imaged *vllm*)",
    )
    args = p.parse_args(argv)

    labels = resolve_source_labels(args.dirs)
    rows, summaries = [], []
    for d, label in zip(args.dirs, labels):
        if not os.path.exists(os.path.join(d, "pods.json")):
            print(f"{d}: pods.json not found", file=sys.stderr)
            return 1
        r, s = analyze_dir(d, args, source_label=label)
        rows += r
        summaries.append(s)
    out = args.out or (args.dirs[0] if len(args.dirs) == 1 else "startup")
    write_outputs(out, rows, summaries)
    print(
        f"wrote {out}/startup.csv, startup.md, startup_summary.json ({len(rows)} Pods)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
