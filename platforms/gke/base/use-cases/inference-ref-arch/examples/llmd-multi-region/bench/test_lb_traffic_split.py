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

"""Unit tests for lb_traffic_split.py."""

from __future__ import annotations

import contextlib
import datetime
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lb_traffic_split  # noqa: E402

UTC = datetime.timezone.utc


def entry(timestamp: str, latency_s: float, region: str, scope: str) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "httpRequest": {"latency": f"{latency_s}s"},
        "resource": {"labels": {"region": region, "backend_scope": scope}},
    }


ENTRIES = [
    entry("2026-10-30T07:01:00.500Z", 0.5, "us-central1", "us-central1-a"),
    # Queued for a minute: it ended after <end> but started before it.
    entry("2026-10-30T07:10:30Z", 60, "us-central1", "europe-west2-b"),
    # Started before <start> / after <end>.
    entry("2026-10-30T06:59:50Z", 1, "us-central1", "us-central1-a"),
    entry("2026-10-30T07:12:00Z", 1, "us-central1", "us-central1-a"),
    # Logged with a UTC offset.
    entry("2026-10-30T09:05:00.25+02:00", 0.25, "us-central1", "us-central1-c"),
]


class ParseTimeTest(unittest.TestCase):
    def test_offsets_and_fractions(self) -> None:
        self.assertEqual(
            lb_traffic_split.parse_time("2026-10-30T12:00:00.25Z"),
            lb_traffic_split.parse_time("2026-10-30T14:00:00.25+02:00"),
        )
        self.assertEqual(
            lb_traffic_split.parse_time("2026-10-30T07:28:19.5+00:00"),
            datetime.datetime(2026, 10, 30, 7, 28, 19, 500000, tzinfo=UTC),
        )
        self.assertEqual(
            lb_traffic_split.parse_time("2026-10-30T07:28:19.123456789Z").microsecond,
            123457,
        )

    def test_datetimes(self) -> None:
        naive = datetime.datetime(2026, 10, 30, 7, 0)
        offset = datetime.datetime(
            2026, 10, 30, 9, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
        )
        self.assertEqual(lb_traffic_split.parse_time(naive), naive.replace(tzinfo=UTC))
        self.assertEqual(lb_traffic_split.parse_time(offset), naive.replace(tzinfo=UTC))

    def test_rejects_invalid_timestamps(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid RFC 3339 timestamp"):
            lb_traffic_split.parse_time("30/10/2026 07:00")

    def test_log_filter(self) -> None:
        flt = lb_traffic_split.build_log_filter(
            "mr-map", "2026-10-30T07:00:00Z", "2026-10-30T08:10:00Z"
        )
        self.assertIn('resource.labels.url_map_name="mr-map"', flt)
        self.assertIn('httpRequest.requestUrl=~"/v1/(chat/)?completions"', flt)
        self.assertIn('timestamp>="2026-10-30T07:00:00Z"', flt)
        self.assertIn('timestamp<="2026-10-30T08:10:00Z"', flt)


class MainTest(unittest.TestCase):
    def run_main(
        self, entries: list[dict[str, Any]], *extra: str
    ) -> tuple[int, str, str, list[str]]:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(entries), stderr=""
        )
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(
                lb_traffic_split.subprocess, "run", return_value=completed
            ) as run,
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = lb_traffic_split.main(
                [
                    "lb_traffic_split.py",
                    "my-project",
                    "mr-map",
                    "2026-10-30T07:00:00Z",
                    "2026-10-30T07:10:00Z",
                    *extra,
                ]
            )
        return rc, out.getvalue(), err.getvalue(), run.call_args.args[0]

    def test_counts_requests_by_start_time(self) -> None:
        rc, out, err, cmd = self.run_main(ENTRIES)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        self.assertEqual(cmd[:3], ["gcloud", "logging", "read"])
        self.assertIn('timestamp<="2026-10-30T07:20:00.000000Z"', cmd[3])
        self.assertIn("--order=asc", cmd)
        self.assertIn("--limit=100000", cmd)
        self.assertEqual(cmd[cmd.index("--project") + 1], "my-project")
        self.assertIn("3 requests started between", out)
        self.assertIn("| us-central1 | us-central1 | 2 | 66.7% |", out)
        self.assertIn("| us-central1 | europe-west2 | 1 | 33.3% |", out)

    def test_completion_grace(self) -> None:
        _rc, out, _err, cmd = self.run_main(ENTRIES, "--completion-grace-s", "0")
        self.assertIn('timestamp<="2026-10-30T07:10:00.000000Z"', cmd[3])
        self.assertIn("3 requests started between", out)

    def test_warns_when_the_log_query_is_truncated(self) -> None:
        _rc, _out, err, cmd = self.run_main(ENTRIES, "--limit", "5")
        self.assertIn("--limit=5", cmd)
        self.assertIn("WARNING: gcloud logging read returned --limit=5 entries", err)

    def test_buckets(self) -> None:
        _rc, out, _err, _cmd = self.run_main(ENTRIES, "--bucket-seconds", "300")
        self.assertIn("Per 300 s bucket of request start times", out)
        self.assertIn("| 0 | 2 | 0% | 100% |", out)
        self.assertIn("| 1 | 1 | 100% | 0% |", out)

    def test_stages_from_partial_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp)
            (reports / "inference-perf.partial.stage_0.yaml").write_text(
                "run:\n  time:\n    start: 2026-10-30T07:00:00Z\n"
                "    end: 2026-10-30T07:05:00Z\n",
                encoding="utf-8",
            )
            (reports / "inference-perf.partial.stage_1.yaml").write_text(
                json.dumps(
                    {
                        "run": {
                            "time": {
                                "start": "2026-10-30T07:05:00.1Z",
                                "end": "2026-10-30T07:10:00Z",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            _rc, out, _err, _cmd = self.run_main(ENTRIES, "--stages-from", str(reports))
        self.assertIn("Per inference-perf stage", out)
        self.assertIn("| 0 | 2 | 0% | 100% |", out)
        self.assertIn("| 1 | 1 | 100% | 0% |", out)


if __name__ == "__main__":
    unittest.main()
