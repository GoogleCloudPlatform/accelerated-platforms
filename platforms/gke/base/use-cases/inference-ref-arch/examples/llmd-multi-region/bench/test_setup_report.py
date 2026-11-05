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

"""Unit tests for setup_report.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setup_report  # noqa: E402


def record(
    scope: str, stage: str, start: float, duration: float, status: str = "ok"
) -> dict[str, Any]:
    return {
        "run_id": "setup-1",
        "scope": scope,
        "stage": stage,
        "status": status,
        "start_epoch_s": start,
        "end_epoch_s": start + duration,
        "duration_s": duration,
        "exit_code": 0 if status == "ok" else 1,
    }


class FmtTest(unittest.TestCase):
    def test_formats_durations(self) -> None:
        self.assertEqual(setup_report.fmt(95), "1:35")
        self.assertEqual(setup_report.fmt(3661), "1:01:01")
        self.assertEqual(setup_report.fmt(-15), "-0:15")
        self.assertEqual(setup_report.fmt(-3661), "-1:01:01")
        self.assertEqual(setup_report.fmt(59.6), "1:00")


class MainTest(unittest.TestCase):
    def run_main(self, records: list[dict[str, Any]]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "timings.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(json.dumps(r) for r in records) + "\n\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = setup_report.main(["setup_report.py", path])
        return rc, out.getvalue()

    def test_last_successful_attempt_wins(self) -> None:
        rc, out = self.run_main(
            [
                record("region/usc1", "platform", 1000, 600),
                record("region/usc1", "model", 1600, 120, status="failed"),
                record("region/usc1", "model", 1800, 300),
                record("region/euw2", "platform", 1000, 900),
                record("global", "global_lb", 1900, 60),
            ]
        )
        self.assertEqual(rc, 0)
        self.assertIn("# Stage timings (setup-1)", out)
        self.assertIn("| region/usc1 | model | 5:00 | 1800 |", out)
        self.assertNotIn("| region/usc1 | model | 2:00 |", out)
        # usc1: 10:00 + 5:00 of stages over a 1000 -> 2100 span.
        self.assertIn("| region/usc1 | 15:00 | 18:20 |", out)
        self.assertIn("**End-to-end wall-clock span of recorded stages:** 18:20", out)
        self.assertIn("- region/usc1 / model: exit 1 after 2:00", out)

    def test_fails_without_successful_stages(self) -> None:
        rc, out = self.run_main([record("global", "fleet", 0, 5, status="failed")])
        self.assertEqual(rc, 1)
        self.assertIn("No successful stages recorded.", out)

    def test_usage(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = setup_report.main(["setup_report.py"])
        self.assertEqual(rc, 2)
        self.assertIn("Usage: setup_report.py", err.getvalue())


if __name__ == "__main__":
    unittest.main()
