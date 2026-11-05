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

"""Counts load balancer requests by entry region (forwarding rule) and serving
region (backend NEG) from the cross-region internal ALB request logs.

Usage: lb_traffic_split.py <project> <url_map_name> <start RFC3339> <end RFC3339>
                           [--bucket-seconds N | --stages-from <reports dir>]
                           [--completion-grace-s N] [--limit N]

It shows how much traffic the load balancing mode kept in the clients' region
and how much it sent to another region (spillover). With --bucket-seconds, it
also splits the window into buckets of N seconds of request start time (log
timestamp minus latency) from the first request (for example 60, the length of
one benchmark stage), to show how the split changes with the load. With
--stages-from, it uses the stage start and end times of an inference-perf
reports directory instead (runs/<run>/<arm>/<workload>/<client>/reports).
"""

from __future__ import annotations

import argparse
import collections
import datetime
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402

RFC3339_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})?$"
)


def parse_time(value: str | datetime.datetime) -> datetime.datetime:
    """Parses an RFC 3339 timestamp with arbitrary fractional digits and tz offset into UTC.

    Also accepts datetimes (PyYAML parses unquoted YAML timestamps into
    datetimes; naive ones are UTC).
    """
    if isinstance(value, datetime.datetime):
        aware = value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
        return aware.astimezone(datetime.timezone.utc)
    m = RFC3339_RE.match(value.strip())
    if not m:
        raise ValueError(f"Invalid RFC 3339 timestamp: {value!r}")
    base, frac, tz = m.groups()
    tz_str = (tz or "Z").replace("Z", "+00:00")
    dt = datetime.datetime.fromisoformat(base + tz_str).astimezone(
        datetime.timezone.utc
    )
    if frac:
        dt += datetime.timedelta(seconds=float(frac))
    return dt


def format_rfc3339(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def build_log_filter(url_map: str, start: str, query_end: str) -> str:
    return (
        'resource.type="internal_http_lb_rule" '
        f'AND resource.labels.url_map_name="{url_map}" '
        'AND httpRequest.requestUrl=~"/v1/(chat/)?completions" '
        f'AND timestamp>="{start}" AND timestamp<="{query_end}"'
    )


def main(argv: list[str] | None = None) -> int:
    args_list = sys.argv[1:] if argv is None else argv[1:]
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("project")
    p.add_argument("url_map")
    p.add_argument("start")
    p.add_argument("end")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--bucket-seconds", type=int, default=0)
    group.add_argument("--stages-from", default="")
    p.add_argument(
        "--completion-grace-s",
        type=int,
        default=600,
        help="extra seconds after <end> to query response completion logs for long requests (default: 600)",
    )
    p.add_argument("--limit", type=int, default=100000)
    args = p.parse_args(args_list)

    start_dt = parse_time(args.start)
    end_dt = parse_time(args.end)
    query_end_dt = end_dt + datetime.timedelta(seconds=max(0, args.completion_grace_s))
    log_filter = build_log_filter(
        args.url_map, format_rfc3339(start_dt), format_rfc3339(query_end_dt)
    )

    out = subprocess.run(
        [
            "gcloud",
            "logging",
            "read",
            log_filter,
            "--project",
            args.project,
            "--order=asc",
            "--format=json",
            f"--limit={args.limit}",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    entries = json.loads(out or "[]")
    if len(entries) >= args.limit:
        print(
            f"WARNING: gcloud logging read returned --limit={args.limit} entries; "
            "traffic split results are truncated.",
            file=sys.stderr,
        )

    counts: collections.Counter[tuple[str, str]] = collections.Counter()
    rows: list[tuple[datetime.datetime, str, str]] = []
    for e in entries:
        labels = e.get("resource", {}).get("labels", {})
        entry_region = labels.get("region", "?")
        scope = labels.get("backend_scope", "?")
        serving_region = scope.rsplit("-", 1)[0] if scope.count("-") >= 2 else scope
        # The log timestamp is when the response ended; filter & bucket by request start.
        latency = float(e.get("httpRequest", {}).get("latency", "0s").rstrip("s") or 0)
        started = parse_time(e.get("timestamp", args.start)) - datetime.timedelta(
            seconds=latency
        )
        if not (start_dt <= started <= end_dt):
            continue
        counts[(entry_region, serving_region)] += 1
        rows.append((started, entry_region, serving_region))

    total = sum(counts.values())
    print(f"{total} requests started between {args.start} and {args.end}")
    print("| entry region (VIP) | serving region | requests | share |")
    print("| --- | --- | ---: | ---: |")
    if total:
        for (entry_region, serving_region), n in sorted(counts.items()):
            print(
                f"| {entry_region} | {serving_region} | {n} | {100.0 * n / total:.1f}% |"
            )
    if args.bucket_seconds > 0 and rows:
        print_buckets(rows, args.bucket_seconds)
    if args.stages_from and rows:
        print_stages(rows, args.stages_from)
    return 0


def print_stages(
    rows: list[tuple[datetime.datetime, str, str]], reports_dir: str
) -> None:
    """Prints the split per inference-perf stage (its start and end times)."""
    stages = []
    for path in sorted(
        glob.glob(os.path.join(reports_dir, "inference-perf.partial.stage_*.yaml"))
    ):
        report = analyze.load_partial_report(path)
        index = int(path.rsplit("_", 1)[1].split(".")[0])
        t = report["run"]["time"]
        stages.append((index, parse_time(t["start"]), parse_time(t["end"])))
    stages.sort()
    counts: dict[int, collections.Counter[tuple[str, str]]] = {
        i: collections.Counter() for i, _, _ in stages
    }
    for started, entry_region, serving_region in rows:
        for i, begin, end in stages:
            if begin <= started <= end:
                counts[i][(entry_region, serving_region)] += 1
                break
    pairs = sorted({k for c in counts.values() for k in c})
    print()
    print(f"Per inference-perf stage ({reports_dir}):")
    print("| stage | requests | " + " | ".join(f"{a} → {b}" for a, b in pairs) + " |")
    print("| ---: | ---: | " + " | ".join("---:" for _ in pairs) + " |")
    for i, _, _ in stages:
        n = sum(counts[i].values())
        cells = " | ".join(
            f"{100.0 * counts[i][k] / n:.0f}%" if n else "–" for k in pairs
        )
        print(f"| {i} | {n} | {cells} |")


def print_buckets(
    rows: list[tuple[datetime.datetime, str, str]], bucket_seconds: int
) -> None:
    """Prints the share served by each region in each time bucket."""
    first = min(t for t, _, _ in rows)
    buckets: dict[int, collections.Counter[tuple[str, str]]] = collections.defaultdict(
        collections.Counter
    )
    for t, entry_region, serving_region in rows:
        index = int((t - first).total_seconds() // bucket_seconds)
        buckets[index][(entry_region, serving_region)] += 1
    pairs = sorted({k for b in buckets.values() for k in b})
    print()
    print(
        f"Per {bucket_seconds} s bucket of request start times, from the first request ({first.isoformat()}):"
    )
    print("| bucket | requests | " + " | ".join(f"{a} → {b}" for a, b in pairs) + " |")
    print("| ---: | ---: | " + " | ".join("---:" for _ in pairs) + " |")
    for index in sorted(buckets):
        b = buckets[index]
        n = sum(b.values())
        cells = " | ".join(f"{100.0 * b[k] / n:.0f}%" for k in pairs)
        print(f"| {index} | {n} | {cells} |")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
