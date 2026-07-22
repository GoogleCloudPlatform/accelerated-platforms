#!/usr/bin/env python3
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

import argparse
import csv
import json
import os
import sys
from functools import reduce


def deep_get(d: dict, path_list: list, default=None):
    try:
        return reduce(lambda c, k: c[k], path_list, d)
    except (KeyError, TypeError, IndexError):
        return default


REQ_PRE = "results.request_performance.aggregate"
SES_PRE = "results.session_performance.sessions"

_METRICS_RAW = {
    "output_tps": f"{REQ_PRE}.throughput.output_token_rate.mean",
    "request_qps": f"{REQ_PRE}.throughput.request_rate.mean",
    "total_tps": f"{REQ_PRE}.throughput.total_token_rate.mean",
    "total_requests": f"{REQ_PRE}.requests.total",
    "failures": f"{REQ_PRE}.requests.failures",
    "session_rate_qps": f"{SES_PRE}.session_rate.mean",
    "events_per_session_mean": f"{SES_PRE}.events_per_session.mean",
    "events_cancelled_per_session_mean": f"{SES_PRE}.events_cancelled_per_session.mean",
    "input_tokens_per_session_mean": f"{SES_PRE}.input_tokens_per_session.mean",
    "output_tokens_per_session_mean": f"{SES_PRE}.output_tokens_per_session.mean",
    "total_sessions": f"{SES_PRE}.total",
    "failed_sessions": f"{SES_PRE}.failed",
    **{
        f"ttft_{k}_s": f"{REQ_PRE}.latency.time_to_first_token.{k}"
        for k in ["mean", "p50", "p99"]
    },
    **{
        f"tpot_{k}_s": f"{REQ_PRE}.latency.time_per_output_token.{k}"
        for k in ["mean", "p99"]
    },
    **{
        f"itl_{k}_s": f"{REQ_PRE}.latency.inter_token_latency.{k}"
        for k in ["mean", "p99"]
    },
    **{f"e2e_{k}_s": f"{REQ_PRE}.latency.request_latency.{k}" for k in ["mean", "p99"]},
    **{
        f"session_duration_{k}_s": f"{SES_PRE}.session_duration.{k}"
        for k in ["mean", "p50", "p99"]
    },
}
METRICS = {k: v.split(".") for k, v in _METRICS_RAW.items()}


def main():
    parser = argparse.ArgumentParser(
        description="Extract key metrics from standard benchmark report to CSV."
    )
    parser.add_argument("--input", required=True, help="Path to input report JSON file")
    parser.add_argument("--output", required=True, help="Path to output CSV file")
    args = parser.parse_args()

    print(f"Extracting CSV from {args.input} to {args.output}...")
    try:
        with open(args.input, encoding="utf-8") as f:
            report = json.load(f)
    except Exception as e:
        sys.exit(f"Error loading report file: {e}")

    # Compress row extraction logic
    row = {
        "treatment": "default",
        "source_file": os.path.basename(args.input),
        "input_len_mean": deep_get(
            report, f"{REQ_PRE}.requests.input_length.mean".split(".")
        ),
        "output_len_mean": deep_get(
            report, f"{REQ_PRE}.requests.output_length.mean".split(".")
        ),
        "tool": deep_get(report, ["scenario", "load", "standardized", "tool"], ""),
        "rate_qps": deep_get(
            report, ["scenario", "load", "standardized", "rate_qps"], ""
        )
        or "",
        **{col: deep_get(report, path) for col, path in METRICS.items()},
    }

    fieldnames = (
        ["treatment", "source_file"]
        + list(METRICS.keys())
        + ["input_len_mean", "output_len_mean", "tool", "rate_qps"]
    )

    try:
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerow(row)
        print("CSV extraction successful.")
    except Exception as e:
        sys.exit(f"Error writing CSV file: {e}")


if __name__ == "__main__":
    main()
