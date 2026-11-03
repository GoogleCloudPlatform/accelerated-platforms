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

It shows how much traffic the load balancing mode kept in the clients' region
and how much it sent to another region (spillover). With --bucket-seconds, it
also splits the window into buckets of N seconds of request start time (log
timestamp minus latency) from the first request (for example 60, the length of
one benchmark stage), to show how the split changes with the load. With
--stages-from, it uses the stage start and end times of an inference-perf
reports directory instead (runs/<run>/<arm>/<workload>/<client>/reports).
"""

import collections
import datetime
import glob
import json
import os
import subprocess
import sys


def main(argv):
    bucket_seconds = 0
    stages_dir = ""
    if len(argv) == 7 and argv[5] == "--bucket-seconds":
        bucket_seconds = int(argv[6])
        argv = argv[:5]
    elif len(argv) == 7 and argv[5] == "--stages-from":
        stages_dir = argv[6]
        argv = argv[:5]
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    project, url_map, start, end = argv[1:]
    log_filter = (
        'resource.type="internal_http_lb_rule" '
        f'AND resource.labels.url_map_name="{url_map}" '
        'AND httpRequest.requestUrl:"/v1/completions" '
        f'AND timestamp>="{start}" AND timestamp<="{end}"'
    )
    out = subprocess.run(
        ["gcloud", "logging", "read", log_filter, "--project", project, "--format=json", "--limit=100000"],
        check=True, capture_output=True, text=True,
    ).stdout
    entries = json.loads(out or "[]")
    counts = collections.Counter()
    rows = []
    for e in entries:
        labels = e.get("resource", {}).get("labels", {})
        entry_region = labels.get("region", "?")
        scope = labels.get("backend_scope", "?")
        serving_region = scope.rsplit("-", 1)[0] if scope.count("-") >= 2 else scope
        counts[(entry_region, serving_region)] += 1
        # The log timestamp is when the response ended; bucket by request start.
        latency = float(e.get("httpRequest", {}).get("latency", "0s").rstrip("s") or 0)
        started = parse_time(e.get("timestamp", start)) - datetime.timedelta(seconds=latency)
        rows.append((started, entry_region, serving_region))
    total = sum(counts.values())
    print(f"{total} requests between {start} and {end}")
    print("| entry region (VIP) | serving region | requests | share |")
    print("| --- | --- | ---: | ---: |")
    for (entry_region, serving_region), n in sorted(counts.items()):
        print(f"| {entry_region} | {serving_region} | {n} | {100.0 * n / total:.1f}% |")
    if bucket_seconds > 0 and rows:
        print_buckets(rows, bucket_seconds)
    if stages_dir and rows:
        print_stages(rows, stages_dir)
    return 0


def print_stages(rows, reports_dir):
    """Prints the split per inference-perf stage (its start and end times)."""
    stages = []
    for path in sorted(glob.glob(os.path.join(reports_dir, "inference-perf.partial.stage_*.yaml"))):
        # inference-perf writes JSON into these .yaml files (JSON is YAML).
        with open(path) as f:
            report = json.load(f)
        index = int(path.rsplit("_", 1)[1].split(".")[0])
        t = report["run"]["time"]
        stages.append((index, parse_time(t["start"]), parse_time(t["end"])))
    stages.sort()
    counts = {i: collections.Counter() for i, _, _ in stages}
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
        cells = " | ".join(f"{100.0 * counts[i][k] / n:.0f}%" if n else "–" for k in pairs)
        print(f"| {i} | {n} | {cells} |")


def parse_time(value):
    # RFC3339 with nanoseconds, for example 2026-10-30T07:28:19.123456789Z.
    value = value.rstrip("Z")
    if "." in value:
        head, frac = value.split(".", 1)
        value = f"{head}.{frac[:6]}"
    return datetime.datetime.fromisoformat(value).replace(tzinfo=datetime.timezone.utc)


def print_buckets(rows, bucket_seconds):
    """Prints the share served by each region in each time bucket."""
    first = min(t for t, _, _ in rows)
    buckets = collections.defaultdict(collections.Counter)
    for t, entry_region, serving_region in rows:
        index = int((t - first).total_seconds() // bucket_seconds)
        buckets[index][(entry_region, serving_region)] += 1
    pairs = sorted({k for b in buckets.values() for k in b})
    print()
    print(f"Per {bucket_seconds} s bucket of request start times, from the first request ({first.isoformat()}):")
    print("| bucket | requests | " + " | ".join(f"{a} → {b}" for a, b in pairs) + " |")
    print("| ---: | ---: | " + " | ".join("---:" for _ in pairs) + " |")
    for index in sorted(buckets):
        b = buckets[index]
        n = sum(b.values())
        cells = " | ".join(f"{100.0 * b[k] / n:.0f}%" for k in pairs)
        print(f"| {index} | {n} | {cells} |")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
