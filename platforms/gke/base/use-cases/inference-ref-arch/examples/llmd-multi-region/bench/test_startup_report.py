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

"""Unit tests for startup_report.py."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import startup_report  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "testdata" / "startup"


def run_main(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = startup_report.main(argv)
    return rc, out.getvalue(), err.getvalue()


def read_pods(out_dir: Path) -> dict[str, dict[str, str]]:
    with open(out_dir / "startup.csv", newline="", encoding="utf-8") as f:
        return {r["pod"]: r for r in csv.DictReader(f)}


def pulled_event(ts: float, message: str) -> dict[str, Any]:
    return {
        "kind": "Pod",
        "name": "vllm-0",
        "field_path": "spec.containers{modelserver}",
        "reason": "Pulled",
        "message": message,
        "ts": ts,
    }


class FixtureEndToEndTest(unittest.TestCase):
    """Runs startup_report.py on the two-Pod fixture in testdata/startup."""

    EXPECTED: dict[str, dict[str, Any]] = {
        "vllm-0": {
            "source": "startup",
            "arm": "llmd",
            "node_provisioned": "True",
            "restarts": 0,
            "apply_to_scheduled_s": 135.0,
            "apply_to_node_created_s": 40.0,
            "node_created_to_ready_s": 90.0,
            "node_ready_to_scheduled_s": 5.0,
            "scheduled_to_initialized_s": 65.0,
            "image_pull_s": 103.0,
            "image_pull_incl_wait_s": 104.5,
            "images_cached": "False",
            "container_start_to_ready_s": 267.0,
            "container_start_to_app_startup_s": 257.0,
            "weights_load_s": 35.42,
            "model_load_s": 36.871,
            "dynamo_transform_s": 13.91,
            "torch_compile_s": 68.25,
            "cuda_graph_s": 29.0,
            "engine_init_s": 109.73,
            "kv_cache_tokens": 81088,
            "apply_to_ready_s": 560.0,
        },
        "vllm-1": {
            "node_provisioned": "False",
            "restarts": 1,
            "apply_to_scheduled_s": 6.0,
            "apply_to_node_created_s": "",
            "image_pull_s": 0.0,
            "images_cached": "True",
            # Its log has no timestamps (kubectl logs without --timestamps).
            "container_start_to_app_startup_s": "",
            "weights_load_s": "",
            "model_load_s": 40.1,
            "torch_compile_s": 31.5,
            "cuda_graph_s": 22.0,
            "engine_init_s": 95.2,
            "kv_cache_tokens": 79872,
            "apply_to_ready_s": 330.0,
        },
    }

    def test_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            rc, stdout, stderr = run_main([str(FIXTURE), "--out", str(out)])
            self.assertEqual(rc, 0, stderr)
            self.assertIn("(2 Pods)", stdout)
            pods = read_pods(out)
            with open(out / "startup_summary.json", encoding="utf-8") as f:
                summaries = json.load(f)
            md = (out / "startup.md").read_text(encoding="utf-8")

        self.assertEqual(set(pods), {"vllm-0", "vllm-1"})
        for pod, fields in self.EXPECTED.items():
            for key, want in fields.items():
                with self.subTest(pod=pod, key=key):
                    got = pods[pod][key]
                    if isinstance(want, str):
                        self.assertEqual(got, want)
                    else:
                        self.assertAlmostEqual(float(got), want, places=6)

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["arm"], "llmd")
        self.assertEqual(summaries[0]["pods"], 2)
        self.assertEqual(summaries[0]["pods_ready"], 2)
        self.assertEqual(summaries[0]["apply_to_all_pods_ready_s"], 560.0)
        self.assertEqual(summaries[0]["apply_to_first_ok_via_gateway_s"], 575.0)
        self.assertIn("## Phase medians (seconds)", md)
        self.assertIn("| apply -> Ready | startup | llmd | 2 | 445.0 | 560.0 |", md)

    def test_pod_regex_filters_pods(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, _out, stderr = run_main(
                [str(FIXTURE), "--out", tmp, "--pod-regex", "vllm-1$"]
            )
            self.assertEqual(rc, 0, stderr)
            self.assertEqual(set(read_pods(Path(tmp))), {"vllm-1"})

    def test_fails_without_pods_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rc, _out, stderr = run_main([tmp, "--out", os.path.join(tmp, "out")])
        self.assertEqual(rc, 1)
        self.assertIn("pods.json not found", stderr)


class ArmComparisonTest(unittest.TestCase):
    """Directories of two arms in the same region must not be pooled."""

    def test_same_region_of_two_arms_is_reported_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "startup" / "run1"
            baseline, llmd = root / "baseline" / "usc1", root / "llmd" / "usc1"
            shutil.copytree(FIXTURE, baseline)
            shutil.copytree(FIXTURE, llmd)
            markers = json.loads((baseline / "markers.json").read_text("utf-8"))
            markers["arm"] = "baseline"
            (baseline / "markers.json").write_text(json.dumps(markers), "utf-8")
            pods = json.loads((baseline / "pods.json").read_text("utf-8"))
            pods["items"] = [
                p for p in pods["items"] if p["metadata"]["name"] == "vllm-1"
            ]
            (baseline / "pods.json").write_text(json.dumps(pods), "utf-8")

            out = Path(tmp) / "out"
            rc, _stdout, stderr = run_main(
                [str(baseline), str(llmd), "--out", str(out)]
            )
            self.assertEqual(rc, 0, stderr)
            with open(out / "startup_summary.json", encoding="utf-8") as f:
                summaries = json.load(f)
            md = (out / "startup.md").read_text(encoding="utf-8")

        self.assertEqual(
            [(s["source"], s["arm"], s["pods"]) for s in summaries],
            [("baseline/usc1", "baseline", 1), ("llmd/usc1", "llmd", 2)],
        )
        self.assertIn(
            "| apply -> Ready | baseline/usc1 | baseline | 1 | 330.0 | 330.0 |", md
        )
        self.assertIn("| apply -> Ready | llmd/usc1 | llmd | 2 | 445.0 | 560.0 |", md)

    def test_resolve_source_labels(self) -> None:
        self.assertEqual(
            startup_report.resolve_source_labels(["/r/baseline/usc1", "/r/llmd/usc1"]),
            ["baseline/usc1", "llmd/usc1"],
        )
        self.assertEqual(
            startup_report.resolve_source_labels(["/r/usc1/", "/r/euw2"]),
            ["usc1", "euw2"],
        )


class ImagePullTest(unittest.TestCase):
    def test_cold_pull_is_kept_after_a_cached_restart(self) -> None:
        pulls = startup_report.image_pulls(
            "vllm-0",
            [
                pulled_event(
                    100.0,
                    'Successfully pulled image "vllm:1" in 1m30s (1m32s including waiting)',
                ),
                pulled_event(
                    250.0, 'Container image "vllm:1" already present on machine'
                ),
            ],
        )
        self.assertEqual(pulls["modelserver"]["pull_s"], 90.0)
        self.assertEqual(pulls["modelserver"]["wait_s"], 92.0)
        self.assertFalse(pulls["modelserver"]["cached"])

    def test_cached_image(self) -> None:
        pulls = startup_report.image_pulls(
            "vllm-0",
            [pulled_event(5.0, 'Container image "vllm:1" already present on machine')],
        )
        self.assertEqual(pulls["modelserver"]["pull_s"], 0.0)
        self.assertTrue(pulls["modelserver"]["cached"])

    def test_falls_back_to_event_times_and_ignores_other_pods(self) -> None:
        events = [
            dict(pulled_event(10.0, ""), reason="Pulling"),
            pulled_event(42.5, "Pulled without a duration"),
            dict(pulled_event(1.0, ""), name="vllm-9", reason="Pulling"),
        ]
        pulls = startup_report.image_pulls("vllm-0", events)
        self.assertEqual(set(pulls), {"modelserver"})
        self.assertEqual(pulls["modelserver"]["pull_s"], 32.5)
        self.assertEqual(pulls["modelserver"]["wait_s"], 32.5)


class ParsingTest(unittest.TestCase):
    def test_parse_ts(self) -> None:
        self.assertEqual(
            startup_report.parse_ts("2026-10-30T02:00:00Z"),
            startup_report.parse_ts("2026-10-29T21:00:00-05:00"),
        )
        self.assertAlmostEqual(
            startup_report.parse_ts("2026-10-30T02:00:00.000000123Z") or 0.0,
            (startup_report.parse_ts("2026-10-30T02:00:00Z") or 0.0) + 123e-9,
            places=6,
        )
        self.assertEqual(startup_report.parse_ts(1793325600), 1793325600.0)
        self.assertIsNone(startup_report.parse_ts("30 Oct 2026"))
        self.assertIsNone(startup_report.parse_ts(None))

    def test_go_duration(self) -> None:
        self.assertEqual(startup_report.go_duration("1m30.5s"), 90.5)
        self.assertEqual(startup_report.go_duration("1h2m"), 3720.0)
        self.assertAlmostEqual(startup_report.go_duration("250ms") or 0.0, 0.25)
        self.assertIsNone(startup_report.go_duration("soon"))
        self.assertIsNone(startup_report.go_duration(None))

    def test_parse_log_last_match_wins_and_needs_timestamps_for_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "vllm.log"
            path.write_text(
                "2026-10-30T02:05:30Z INFO Loading weights took 35.42 seconds\n"
                "2026-10-30T02:09:10.5Z INFO:     Application startup complete.\n"
                "2026-10-30T02:15:00+00:00 INFO Loading weights took 12.00 seconds\n"
                "INFO:     Application startup complete.\n",
                encoding="utf-8",
            )
            log = startup_report.parse_log(str(path))
        self.assertEqual(log["weights_load_s"], 12.0)
        self.assertEqual(
            log["app_startup_complete"],
            startup_report.parse_ts("2026-10-30T02:09:10.5Z"),
        )
        self.assertIsNone(log["engine_init_s"])

    def test_parse_log_without_a_file(self) -> None:
        log = startup_report.parse_log("/nonexistent/vllm.log")
        self.assertTrue(all(v is None for v in log.values()))


if __name__ == "__main__":
    unittest.main()
