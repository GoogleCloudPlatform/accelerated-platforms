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

"""Unit tests for scale_report.py."""

from __future__ import annotations

import contextlib
import datetime
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scale_report  # noqa: E402

T0 = datetime.datetime(2026, 10, 30, 7, 0, tzinfo=datetime.timezone.utc)
E0 = T0.timestamp()


def rfc3339(offset_s: float) -> str:
    return (T0 + datetime.timedelta(seconds=offset_s)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def stage_report(qps: float, ok: int, failed: int, ttft_p90_s: float) -> dict[str, Any]:
    successes: dict[str, Any] = {"count": ok}
    if ok:
        successes["latency"] = {"time_to_first_token": {"p90": ttft_p90_s}}
        successes["throughput"] = {"requests_per_sec": ok / 60.0}
    return {
        "load_summary": {"requested_rate": qps, "achieved_rate": qps},
        "successes": successes,
        "failures": {"count": failed},
    }


def write_client(
    runs: Path,
    client: str,
    windows: list[tuple[float, float]],
    reports: list[dict[str, Any]],
) -> None:
    client_dir = runs / "shared-prefix" / client
    (client_dir / "reports").mkdir(parents=True)
    (client_dir / "client.json").write_text(json.dumps({"key": client}), "utf-8")
    for stage, ((start, end), report) in enumerate(zip(windows, reports)):
        reports_dir = client_dir / "reports"
        (reports_dir / f"stage_{stage}_lifecycle_metrics.json").write_text(
            json.dumps(report), "utf-8"
        )
        # YAML, as inference-perf writes it, with unquoted timestamps.
        (reports_dir / f"inference-perf.partial.stage_{stage}.yaml").write_text(
            f"run:\n  time:\n    start: {rfc3339(start)}\n    end: {rfc3339(end)}\n",
            "utf-8",
        )


class TimeTest(unittest.TestCase):
    def test_ts(self) -> None:
        self.assertEqual(scale_report.ts("2026-10-30T07:00:00Z"), E0)
        self.assertEqual(scale_report.ts("2026-10-30T02:00:00-05:00"), E0)
        self.assertAlmostEqual(
            scale_report.ts("2026-10-30T07:00:00.500000000Z") or 0.0, E0 + 0.5
        )
        self.assertEqual(scale_report.ts(T0), E0)
        self.assertEqual(scale_report.ts(E0), E0)
        self.assertIsNone(scale_report.ts(None))
        self.assertIsNone(scale_report.ts(""))

    def test_mmss(self) -> None:
        self.assertEqual(scale_report.mmss(95), "1:35")
        self.assertEqual(scale_report.mmss(-15), "-0:15")
        self.assertEqual(scale_report.mmss(-75), "-1:15")
        self.assertEqual(scale_report.mmss(None), "–")


class StageWindowsTest(unittest.TestCase):
    def test_windows_per_stage_and_per_region(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runs = Path(tmp)
            write_client(
                runs,
                "usc1",
                [(0, 60), (70, 130)],
                [stage_report(2.0, 120, 0, 0.5)] * 2,
            )
            write_client(
                runs,
                "euw2",
                [(300, 360), (370, 430)],
                [stage_report(2.0, 120, 0, 0.5)] * 2,
            )
            windows, by_region = scale_report.stage_windows_with_regions(str(runs))
        self.assertEqual(windows, {0: (E0, E0 + 360), 1: (E0 + 70, E0 + 430)})
        self.assertEqual(by_region[("usc1", 0)], (E0, E0 + 60))
        self.assertEqual(by_region[("euw2", 1)], (E0 + 370, E0 + 430))

    def test_client_key_falls_back_to_the_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "ase1" / "reports"
            reports.mkdir(parents=True)
            path = reports / "inference-perf.partial.stage_0.yaml"
            self.assertEqual(scale_report._client_key_for_partial(str(path)), "ase1")
            (Path(tmp) / "ase1" / "client.json").write_text('{"key": "x"}', "utf-8")
            self.assertEqual(scale_report._client_key_for_partial(str(path)), "x")

    def test_stage_without_an_end_time_is_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports = Path(tmp) / "usc1" / "reports"
            reports.mkdir(parents=True)
            (reports / "inference-perf.partial.stage_0.yaml").write_text(
                "run:\n  time:\n    start: 2026-10-30T07:00:00Z\n", "utf-8"
            )
            with self.assertRaisesRegex(ValueError, "run.time has no start or end"):
                scale_report.stage_windows_with_regions(tmp)


class ChartHelpersTest(unittest.TestCase):
    def test_region_colors_cycle_past_the_palette(self) -> None:
        keys = [f"r{i}" for i in range(len(scale_report.PALETTE) + 2)]
        colors = scale_report.region_colors(keys)
        self.assertEqual(list(colors), keys)
        self.assertEqual(colors["r0"], colors[f"r{len(scale_report.PALETTE)}"])
        self.assertEqual(len(set(colors.values())), len(scale_report.PALETTE))

    def test_slo_line_stays_inside_the_chart(self) -> None:
        self.assertAlmostEqual(scale_report.slo_ylim_top(0.6, 2.0), 2.8)
        self.assertEqual(scale_report.slo_ylim_top(40.0, 2.0), 40.0)


class RecorderTest(unittest.TestCase):
    RECORDS: list[dict[str, Any]] = [
        {
            "ts": E0,
            "hpa_desired": 2,
            "pod_list": [
                {
                    "name": "vllm-a",
                    "created": rfc3339(-600),
                    "scheduled": rfc3339(-590),
                    "ready": rfc3339(-300),
                    "node": "gpu-a",
                }
            ],
            "node_list": {"gpu-a": rfc3339(-3600)},
        },
        {
            "ts": E0 + 30,
            "hpa_desired": 3,
            "pod_list": [
                {
                    "name": "vllm-b",
                    "created": rfc3339(30),
                    "scheduled": None,
                    "ready": None,
                    "node": None,
                }
            ],
        },
        {
            "ts": E0 + 60,
            "hpa_desired": 3,
            "pod_list": [
                {
                    "name": "vllm-b",
                    "created": rfc3339(30),
                    "scheduled": rfc3339(200),
                    "ready": rfc3339(500),
                    "node": "gpu-b",
                }
            ],
            "node_list": {"gpu-a": rfc3339(-3600), "gpu-b": rfc3339(100)},
        },
    ]

    def test_pod_latencies(self) -> None:
        rows = {r["pod"]: r for r in scale_report.pod_latencies(self.RECORDS)}
        self.assertFalse(rows["vllm-a"]["new_node"])
        self.assertTrue(rows["vllm-b"]["new_node"])
        self.assertEqual(rows["vllm-b"]["wait_for_node_s"], 170.0)
        self.assertEqual(rows["vllm-b"]["start_to_ready_s"], 300.0)
        self.assertEqual(rows["vllm-b"]["created_to_ready_s"], 470.0)

    def test_scale_events_and_first_time(self) -> None:
        self.assertEqual(
            scale_report.scale_events(self.RECORDS), [(E0, None, 2), (E0 + 30, 2, 3)]
        )
        self.assertEqual(
            scale_report.first_time(self.RECORDS, lambda r: r["hpa_desired"] == 3),
            E0 + 30,
        )
        self.assertIsNone(
            scale_report.first_time(self.RECORDS, lambda r: r["hpa_desired"] == 4)
        )

    def test_gmp_helpers(self) -> None:
        gmp = {
            "pod_success_rps": {
                "mr-usc1/vllm-a": [(E0, 0.0), (E0 + 15, 0.4)],
                "mr-usc1/vllm-b": [(E0, 0.0)],
            }
        }
        self.assertEqual(scale_report.first_serving(gmp), {"vllm-a": E0 + 15})
        self.assertEqual(
            scale_report.mean_in([(1, 2.0), (2, 4.0), (9, 9.0)], 0, 5), 3.0
        )
        self.assertIsNone(scale_report.mean_in([(9, 9.0)], 0, 5))
        self.assertEqual(
            scale_report.region_of_cluster("mr-euw2", ["usc1", "euw2"]), "euw2"
        )
        self.assertEqual(scale_report.region_of_cluster("other", ["usc1"]), "other")


class MainTest(unittest.TestCase):
    def test_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runs = root / "runs" / "r1" / "llmd"
            write_client(
                runs,
                "usc1",
                [(0, 60), (70, 130)],
                [stage_report(2.0, 120, 0, 0.5), stage_report(8.0, 400, 80, 1.5)],
            )
            # euw2 started 5 minutes late and its second stage failed outright.
            write_client(
                runs,
                "euw2",
                [(300, 360), (370, 430)],
                [stage_report(2.0, 120, 0, 0.4), stage_report(8.0, 0, 480, 0.0)],
            )
            recorder = root / "recorder.jsonl"
            recorder.write_text(
                "\n".join(
                    json.dumps(dict(r, region=key))
                    for key in ("usc1", "euw2")
                    for r in RecorderTest.RECORDS
                )
                + "\n",
                "utf-8",
            )
            gmp = root / "gmp.json"
            gmp.write_text(
                json.dumps(
                    {
                        "waiting": {
                            "mr-usc1": [[E0 + 30, 1.0], [E0 + 330, 7.0]],
                            "mr-euw2": [[E0 + 30, 1.0], [E0 + 330, 9.0]],
                        }
                    }
                ),
                "utf-8",
            )
            out = root / "out"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = scale_report.main(
                    [
                        "--runs",
                        str(runs),
                        "--recorder",
                        str(recorder),
                        "--out",
                        str(out),
                        "--gmp-json",
                        str(gmp),
                    ]
                )
            report = (out / "report.md").read_text("utf-8")
            self.assertTrue((out / "stages.csv").exists())
            self.assertTrue((out / "pods.csv").exists())

        self.assertEqual(rc, 0)
        self.assertIn("wrote", stdout.getvalue())
        self.assertIn("Stages: 0: 2.0 QPS per client region, 0:00–6:00", report)
        # The second stage lost every request in euw2: no worst-region TTFT.
        self.assertIn("| 1 | 16.0 | 6.67 | 400 | 560 | 0 | 0 | - |", report)
        self.assertIn("| 0 | 4.0 | 4.00 | 240 | 0 | 0 | 0 | 500 |", report)
        self.assertIn("| usc1 | 0:30: 2→3 |", report)
        # Server-side means use each region's own stage window.
        self.assertIn("| 0 | usc1 | - | 1.0 |", report)
        self.assertIn("| 0 | euw2 | - | 9.0 |", report)
        self.assertIn(
            "cross-region Stage 0 start skew is 300.0s (usc1 vs euw2)", report
        )


if __name__ == "__main__":
    unittest.main()
