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

"""Summarizes the stage timings recorded by scripts/lib.sh (mr_stage).

Usage: setup_report.py <timings.jsonl> [<timings.jsonl> ...]

For every (scope, stage) pair the last successful record wins, so re-running a
failed stage replaces its earlier attempt. The report shows each stage, the
per-scope totals, and the wall-clock span of the whole run (regions run in
parallel, so the span is shorter than the sum of the stages).
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from typing import Any


def load(paths: list[str]) -> list[dict[str, Any]]:
    records = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def fmt(seconds: float | int) -> str:
    rounded = int(round(float(seconds)))
    sign = "-" if rounded < 0 else ""
    m, s = divmod(abs(rounded), 60)
    h, m = divmod(m, 60)
    return f"{sign}{h:d}:{m:02d}:{s:02d}" if h else f"{sign}{m:d}:{s:02d}"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    records = load(argv[1:])
    latest: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
    failures = []
    for r in records:
        key = (r["scope"], r["stage"])
        if r["status"] == "ok":
            latest.pop(key, None)
            latest[key] = r
        else:
            failures.append(r)

    if not latest:
        print("No successful stages recorded.")
        return 1

    run_ids = sorted({r["run_id"] for r in latest.values()})
    print(f"# Stage timings ({', '.join(run_ids)})\n")
    print("| Scope | Stage | Duration | Start (UTC epoch) |")
    print("| --- | --- | ---: | ---: |")
    for (scope, stage), r in sorted(
        latest.items(), key=lambda kv: kv[1]["start_epoch_s"]
    ):
        print(
            f"| {scope} | {stage} | {fmt(r['duration_s'])} | {r['start_epoch_s']:.0f} |"
        )

    print("\n## Totals per scope\n")
    print("| Scope | Sum of stages | Wall-clock span |")
    print("| --- | ---: | ---: |")
    scopes: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for (scope, _), r in latest.items():
        scopes.setdefault(scope, []).append(r)
    for scope, rs in scopes.items():
        total = sum(r["duration_s"] for r in rs if not r["stage"].endswith("_total"))
        span = max(r["end_epoch_s"] for r in rs) - min(r["start_epoch_s"] for r in rs)
        print(f"| {scope} | {fmt(total)} | {fmt(span)} |")

    all_rs = list(latest.values())
    span = max(r["end_epoch_s"] for r in all_rs) - min(
        r["start_epoch_s"] for r in all_rs
    )
    print(f"\n**End-to-end wall-clock span of recorded stages:** {fmt(span)}")
    if failures:
        print(
            f"\n_{len(failures)} failed attempt(s) were recorded and superseded or still pending:_"
        )
        for r in failures:
            print(
                f"- {r['scope']} / {r['stage']}: exit {r.get('exit_code', '?')} after {fmt(r['duration_s'])}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
