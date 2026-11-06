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

"""Unit tests for analyze.py."""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze  # noqa: E402


def stage_report(
    qps: float,
    ok: int,
    failed: int = 0,
    ttft_p90_s: float | None = 0.5,
    tpot_p90_s: float | None = 0.05,
    ttft_med_s: float | None = None,
    good_requests: int | None = None,
    request_goodput: float | None = None,
) -> dict[str, Any]:
    """A minimal inference-perf stage_<N>_lifecycle_metrics.json document."""
    latency: dict[str, Any] = {}
    if ttft_p90_s is not None:
        med = ttft_p90_s / 2 if ttft_med_s is None else ttft_med_s
        latency["time_to_first_token"] = {"median": med, "p90": ttft_p90_s}
    if tpot_p90_s is not None:
        latency["time_per_output_token"] = {"median": tpot_p90_s, "p90": tpot_p90_s}
    successes: dict[str, Any] = {"count": ok}
    if ok:
        successes["latency"] = latency
        successes["throughput"] = {
            "requests_per_sec": ok / 60.0,
            "output_tokens_per_sec": ok * 4.0,
        }
        if good_requests is not None or request_goodput is not None:
            successes["goodput_metrics"] = {
                "good_requests": good_requests,
                "request_goodput": request_goodput,
                "goodput_percentage": (
                    100.0 * good_requests / ok if good_requests is not None else None
                ),
            }
    return {
        "load_summary": {"requested_rate": qps, "achieved_rate": qps},
        "successes": successes,
        "failures": {"count": failed},
    }


def write_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


def build_analyze_fixture(root: Path) -> Path:
    """Writes a synthetic two-arm, two-region benchmark run directory."""
    specs = {
        ("vllm", "usc1"): [
            (1.0, 60, 0, 0.45, 0.81, 0.0434, 57, 0.82),
            (2.0, 120, 0, 0.90, 1.62, 0.0558, 114, 1.58),
            (4.0, 237, 3, 2.40, 4.32, 0.0868, 142, 1.77),
        ],
        ("vllm", "euw2"): [
            (1.0, 60, 0, 0.50, 0.90, 0.045, 57, 0.80),
            (2.0, 120, 0, 0.99, 1.78, 0.060, 114, 1.55),
            (4.0, 237, 3, 2.64, 4.752, 0.095, 142, 1.73),
        ],
        ("llmd", "usc1"): [
            (1.0, 60, 0, 0.25, 0.45, 0.041, 57, 0.83),
            (2.0, 120, 0, 0.40, 0.72, 0.050, 114, 1.61),
            (4.0, 240, 0, 0.90, 1.62, 0.068, 228, 3.04),
        ],
        ("llmd", "euw2"): [
            (1.0, 60, 0, 0.28, 0.50, 0.042, 57, 0.82),
            (2.0, 120, 0, 0.44, 0.79, 0.052, 114, 1.59),
            (4.0, 240, 0, 0.99, 1.78, 0.072, 228, 2.98),
        ],
    }
    for (arm, client), stages in specs.items():
        run_dir = root / "runs" / "fixture" / arm / "shared-prefix"
        write_json(
            run_dir / "run.json",
            {
                "schema_version": 1,
                "status": "succeeded",
                "run_id": "fixture",
                "arm": arm,
                "workload": "shared-prefix",
                "slo": {"ttft_s": 2.0, "tpot_s": 0.1},
            },
        )
        client_dir = run_dir / client
        write_json(
            client_dir / "client.json",
            {"key": client, "target_key": client, "status": "succeeded"},
        )
        for idx, (qps, ok, fail, med, p90, tpot, good, goodput) in enumerate(stages):
            write_json(
                client_dir / "reports" / f"stage_{idx}_lifecycle_metrics.json",
                stage_report(
                    qps,
                    ok,
                    fail,
                    ttft_p90_s=p90,
                    tpot_p90_s=tpot,
                    ttft_med_s=med,
                    good_requests=good,
                    request_goodput=goodput,
                ),
            )
    return root


def read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = analyze.main(argv)
    return rc, out.getvalue(), err.getvalue()


class FixtureEndToEndTest(unittest.TestCase):
    """Runs analyze.py on a synthetic two-arm, two-region fixture."""

    out: Path
    stdout: str
    stderr: str

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        base = Path(cls._tmp.name)
        fixture = build_analyze_fixture(base / "in")
        cls.out = base / "out"
        rc, cls.stdout, cls.stderr = run_main([str(fixture), "--out", str(cls.out)])
        if rc != 0:
            raise AssertionError(f"analyze.main returned {rc}: {cls.stderr}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_writes_every_report(self) -> None:
        for name in (
            "report.md",
            "stages.csv",
            "summary.csv",
            "aggregate.csv",
            "relative.csv",
        ):
            self.assertGreater((self.out / name).stat().st_size, 0, name)
        self.assertIn("wrote", self.stdout)
        self.assertEqual(self.stderr, "")

    def test_stage_rows(self) -> None:
        stages = read_csv(self.out / "stages.csv")
        self.assertEqual(len(stages), 12)
        row = next(
            r
            for r in stages
            if r["arm"] == "vllm"
            and r["client"] == "usc1"
            and float(r["requested_qps"]) == 4.0
        )
        self.assertEqual(row["failures"], "3")
        self.assertAlmostEqual(float(row["ttft_p50_ms"]), 2400.0)
        self.assertAlmostEqual(float(row["ttft_p90_ms"]), 4320.0)
        self.assertAlmostEqual(float(row["error_rate"]), 3 / 240)
        # goodput_metrics.good_requests / (successes + failures).
        self.assertAlmostEqual(float(row["slo_attainment_pct"]), 100.0 * 142 / 240)

    def test_capacity_within_slo(self) -> None:
        summary = {
            (r["arm"], r["client"]): r for r in read_csv(self.out / "summary.csv")
        }
        self.assertEqual(summary[("vllm", "usc1")]["max_qps_p90_ttft_slo"], "2.0")
        self.assertEqual(summary[("llmd", "usc1")]["max_qps_p90_ttft_slo"], "4.0")

    def test_aggregate_sums_client_regions(self) -> None:
        agg = [
            r
            for r in read_csv(self.out / "aggregate.csv")
            if r["arm"] == "vllm" and float(r["requested_qps"]) == 4.0
        ]
        self.assertEqual(len(agg), 1)
        self.assertEqual(agg[0]["failures"], "6")
        self.assertEqual(agg[0]["clients"], "euw2 usc1")

    def test_relative_change_vs_baseline(self) -> None:
        rel = read_csv(self.out / "relative.csv")
        stage = [
            r
            for r in rel
            if r["arm"] == "llmd"
            and r["client"] == "usc1"
            and r["requested_qps"] == "4.0"
        ]
        self.assertEqual(len(stage), 1)
        self.assertAlmostEqual(float(stage[0]["ttft_p90_ms_change_pct"]), -62.5)
        cap = [
            r
            for r in rel
            if r["requested_qps"] == "max-within-slo" and r["client"] == "usc1"
        ]
        self.assertEqual(len(cap), 1)
        self.assertAlmostEqual(float(cap[0]["max_qps_p90_ttft_slo_change_pct"]), 100.0)

    def test_markdown_report(self) -> None:
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertIn("SLO: p90 TTFT <= 2000 ms, p90 TPOT <= 100 ms", md)
        self.assertIn("error rate <= 5.0%", md)
        self.assertIn("## All client regions combined", md)
        self.assertIn("## Relative change vs `vllm`", md)
        self.assertNotIn("[!WARNING]", md)


class ParseStageTest(unittest.TestCase):
    def test_converts_seconds_to_ms_and_reads_goodput(self) -> None:
        report = stage_report(4.0, ok=230, failed=10, ttft_p90_s=0.8, tpot_p90_s=0.04)
        report["successes"]["goodput_metrics"] = {
            "request_goodput": 3.5,
            "goodput_percentage": 90.0,
            "good_requests": 216,
        }
        row = analyze.parse_stage(report)
        self.assertEqual(row["requested_qps"], 4.0)
        self.assertAlmostEqual(row["ttft_p90_ms"], 800.0)
        self.assertAlmostEqual(row["ttft_p50_ms"], 400.0)
        self.assertAlmostEqual(row["tpot_p90_ms"], 40.0)
        self.assertIsNone(row["itl_p90_ms"])
        self.assertAlmostEqual(row["error_rate"], 10 / 240)
        self.assertEqual(row["goodput_rps"], 3.5)
        self.assertAlmostEqual(row["slo_attainment_pct"], 90.0)

    def test_all_failed_stage_reports_zero_throughput_not_none(self) -> None:
        row = analyze.parse_stage(stage_report(6.0, ok=0, failed=120))
        self.assertEqual(row["successes"], 0)
        self.assertEqual(row["failures"], 120)
        self.assertEqual(row["error_rate"], 1.0)
        self.assertEqual(row["completed_rps"], 0.0)
        self.assertEqual(row["output_tokens_per_s"], 0.0)
        self.assertEqual(row["input_tokens_per_s"], 0.0)
        self.assertEqual(row["goodput_rps"], 0.0)
        self.assertEqual(row["slo_attainment_pct"], 0.0)
        self.assertIsNone(row["ttft_p90_ms"])

    def test_stage_without_requests_has_no_rates(self) -> None:
        row = analyze.parse_stage({"load_summary": {"requested_rate": 1.0}})
        self.assertIsNone(row["error_rate"])
        self.assertIsNone(row["completed_rps"])
        self.assertIsNone(row["goodput_rps"])
        self.assertIsNone(row["slo_attainment_pct"])


class SloTest(unittest.TestCase):
    def row(self, qps: float, **kwargs: Any) -> dict[str, Any]:
        defaults: dict[str, Any] = {
            "requested_qps": qps,
            "successes": 100,
            "failures": 0,
            "error_rate": 0.0,
            "ttft_p90_ms": 500.0,
            "tpot_p90_ms": 50.0,
        }
        defaults.update(kwargs)
        return defaults

    def test_meets_rejects_stage_with_high_error_rate(self) -> None:
        # 99% of the requests failed fast; the survivors were quick.
        lucky = self.row(8.0, successes=1, failures=99, error_rate=0.99)
        self.assertFalse(analyze.meets(lucky, 2000.0, 100.0, False, 0.05))
        self.assertFalse(analyze.meets(lucky, 2000.0, 100.0, True, 0.05))

    def test_meets_accepts_error_rate_at_the_limit(self) -> None:
        self.assertTrue(
            analyze.meets(self.row(2.0, error_rate=0.05), 2000.0, 100.0, True, 0.05)
        )

    def test_meets_rejects_stage_without_successes(self) -> None:
        dead = self.row(2.0, successes=0, failures=0, error_rate=None)
        self.assertFalse(analyze.meets(dead, 2000.0, 100.0, False))

    def test_meets_checks_tpot_only_when_asked(self) -> None:
        slow_tokens = self.row(2.0, tpot_p90_ms=150.0)
        self.assertTrue(analyze.meets(slow_tokens, 2000.0, 100.0, False))
        self.assertFalse(analyze.meets(slow_tokens, 2000.0, 100.0, True))

    def test_max_qps_stops_at_the_first_stage_outside_the_slo(self) -> None:
        rows = [
            self.row(6.0),
            self.row(2.0),
            self.row(4.0, error_rate=0.2),
            self.row(1.0),
        ]
        self.assertEqual(analyze.max_qps_within_slo(rows, 2000.0, 100.0, False), 2.0)

    def test_summarize_uses_max_error_rate(self) -> None:
        stages = [
            dict(
                self.row(q, error_rate=e),
                run_id="r",
                arm="llmd",
                workload="chat",
                client="usc1",
                target="usc1",
                goodput_rps=q,
                output_tokens_per_s=10.0 * q,
            )
            for q, e in ((2.0, 0.0), (4.0, 0.03))
        ]
        strict = analyze.summarize(stages, 2000.0, 100.0, max_error_rate=0.01)
        lenient = analyze.summarize(stages, 2000.0, 100.0, max_error_rate=0.05)
        self.assertEqual(strict[0]["max_qps_p90_ttft_slo"], 2.0)
        self.assertEqual(lenient[0]["max_qps_p90_ttft_slo"], 4.0)
        self.assertEqual(lenient[0]["max_goodput_rps"], 4.0)


class AggregateTest(unittest.TestCase):
    def stage(self, stage: int, client: str, **kwargs: Any) -> dict[str, Any]:
        row: dict[str, Any] = {
            "run_id": "r1",
            "arm": "llmd",
            "workload": "shared-prefix",
            "stage": stage,
            "requested_qps": 8.0,
            "client": client,
            "completed_rps": 7.5,
            "successes": 450,
            "failures": 0,
            "output_tokens_per_s": 1900.0,
            "goodput_rps": 7.2,
            "ttft_p90_ms": 500.0,
            "tpot_p90_ms": 70.0,
        }
        row.update(kwargs)
        return row

    def test_repeated_qps_stages_stay_separate(self) -> None:
        agg = analyze.aggregate(
            [
                self.stage(1, "usc1"),
                self.stage(1, "euw2", goodput_rps=6.8),
                self.stage(2, "usc1", goodput_rps=7.4),
                self.stage(2, "euw2", goodput_rps=7.0),
            ]
        )
        self.assertEqual([a["stage"] for a in agg], [1, 2])
        self.assertAlmostEqual(agg[0]["goodput_rps"], 14.0)
        self.assertAlmostEqual(agg[1]["goodput_rps"], 14.4)
        self.assertEqual(agg[0]["clients"], "euw2 usc1")
        self.assertAlmostEqual(agg[0]["completed_rps"], 15.0)

    def test_region_with_only_failures_is_not_masked(self) -> None:
        agg = analyze.aggregate(
            [
                self.stage(2, "usc1", ttft_p90_ms=350.0),
                self.stage(
                    2,
                    "euw2",
                    completed_rps=0.0,
                    successes=0,
                    failures=480,
                    output_tokens_per_s=0.0,
                    goodput_rps=0.0,
                    ttft_p90_ms=None,
                    tpot_p90_ms=None,
                ),
            ]
        )
        self.assertEqual(len(agg), 1)
        self.assertIsNone(agg[0]["worst_ttft_p90_ms"])
        self.assertIsNone(agg[0]["worst_tpot_p90_ms"])
        self.assertEqual(agg[0]["failures"], 480)
        self.assertAlmostEqual(agg[0]["goodput_rps"], 7.2)

    def test_worst_latency_is_the_maximum_over_regions(self) -> None:
        agg = analyze.aggregate(
            [self.stage(0, "usc1", ttft_p90_ms=350.0), self.stage(0, "euw2")]
        )
        self.assertEqual(agg[0]["worst_ttft_p90_ms"], 500.0)


class CollectTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.run_dir = self.root / "runs" / "r1" / "llmd" / "shared-prefix"

    def add_client(
        self, client: str, partial_stage_0: str | None, status: str = "succeeded"
    ) -> None:
        reports = self.run_dir / client / "reports"
        write_json(reports / "stage_0_lifecycle_metrics.json", stage_report(2.0, 60))
        write_json(reports / "stage_1_lifecycle_metrics.json", stage_report(4.0, 120))
        write_json(
            self.run_dir / client / "client.json", {"key": client, "status": status}
        )
        if partial_stage_0 is not None:
            (reports / "inference-perf.partial.stage_0.yaml").write_text(
                partial_stage_0, encoding="utf-8"
            )

    def test_reads_identity_from_the_directory_layout(self) -> None:
        self.add_client("usc1", None)
        stages, notes = analyze.collect([str(self.root)])
        self.assertEqual(notes, [])
        self.assertEqual([s["stage"] for s in stages], [0, 1])
        self.assertEqual(
            {(s["run_id"], s["arm"], s["workload"], s["client"]) for s in stages},
            {("r1", "llmd", "shared-prefix", "usc1")},
        )

    def test_notes_failed_clients(self) -> None:
        self.add_client("usc1", None, status="failed")
        _stages, notes = analyze.collect([str(self.root)])
        self.assertEqual(len(notes), 1)
        self.assertIn("client status is 'failed'", notes[0])

    def test_warns_on_cross_region_stage_0_start_skew(self) -> None:
        # inference-perf writes the partial stage reports as YAML; PyYAML parses
        # an unquoted timestamp into a datetime.
        self.add_client(
            "euw2", "run:\n  time:\n    start: 2026-10-30T05:48:00.000000Z\n"
        )
        self.add_client(
            "usc1",
            json.dumps({"run": {"time": {"start": "2026-10-30T05:49:35.5Z"}}}),
        )
        stages, notes = analyze.collect([str(self.root)])
        self.assertEqual(len(stages), 4)
        self.assertEqual(
            notes,
            [
                "r1/llmd/shared-prefix: cross-region Stage 0 start skew is 95.5s "
                "(euw2 vs usc1)"
            ],
        )

    def test_no_skew_warning_within_tolerance(self) -> None:
        for client, start in (("euw2", "05:48:00Z"), ("usc1", "07:48:03+02:00")):
            self.add_client(
                client,
                json.dumps({"run": {"time": {"start": f"2026-10-30T{start}"}}}),
            )
        _stages, notes = analyze.collect([str(self.root)])
        self.assertEqual(notes, [])

    def test_rejects_a_partial_report_that_is_not_a_mapping(self) -> None:
        self.add_client("usc1", "- not\n- a mapping\n")
        with self.assertRaisesRegex(ValueError, "expected a mapping, got list"):
            analyze.collect([str(self.root)])


class MarkdownTest(unittest.TestCase):
    def test_single_client_region_report_names_the_region(self) -> None:
        stages = [
            {
                "run_id": "r1",
                "arm": "llmd",
                "workload": "chat",
                "client": "usc1",
                "target": "usc1",
                "stage": 0,
                **analyze.parse_stage(stage_report(2.0, 120)),
            }
        ]
        args = argparse.Namespace(
            slo_ttft=2.0, slo_tpot=0.1, max_error_rate=0.05, baseline_arm="vllm"
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            analyze.write_markdown(
                str(path), stages, [], analyze.aggregate(stages), [], args, []
            )
            md = path.read_text(encoding="utf-8")
        self.assertIn("## Client region `usc1`", md)
        self.assertIn("usc1 TTFT p90", md)
        self.assertNotIn("## All client regions combined", md)
        self.assertNotIn("worst TTFT p90", md)


class MainTest(unittest.TestCase):
    def test_fails_when_there_are_no_stage_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, _out, err = run_main([tmp, "--out", os.path.join(tmp, "out")])
        self.assertEqual(rc, 1)
        self.assertIn("no inference-perf stage reports found under", err)

    def test_warns_when_run_slo_differs_from_the_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = build_analyze_fixture(Path(tmp) / "in")
            out = os.path.join(tmp, "out")
            rc, _stdout, err = run_main(
                [str(fixture), "--out", out, "--slo-ttft", "1.0"]
            )
            md = Path(out, "report.md").read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn(
            "WARNING: goodput columns use the SLO configured at run time", err
        )
        self.assertIn("> [!WARNING]", md)

    def test_notes_missing_baseline_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = build_analyze_fixture(Path(tmp) / "in")
            out = os.path.join(tmp, "out")
            rc, _stdout, err = run_main(
                [str(fixture), "--out", out, "--baseline-arm", "none"]
            )
            rel = Path(out, "relative.csv").read_text(encoding="utf-8")
        self.assertEqual(rc, 0)
        self.assertIn("baseline arm 'none' not found (arms: llmd, vllm)", err)
        self.assertEqual(rel.strip(), "")


if __name__ == "__main__":
    unittest.main()
