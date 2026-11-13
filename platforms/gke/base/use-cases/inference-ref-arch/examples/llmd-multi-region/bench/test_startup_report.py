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
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import startup_report  # noqa: E402


def write_startup_fixture(dst: Path, arm: str = "llmd") -> Path:
    """Writes a synthetic two-Pod startup snapshot directory."""
    (dst / "logs").mkdir(parents=True, exist_ok=True)
    (dst / "markers.json").write_text(
        json.dumps(
            {
                "apply_epoch_s": 1793325600.0,
                "first_ok_via_gateway_epoch_s": 1793326175.0,
                "arm": arm,
            }
        ),
        encoding="utf-8",
    )
    (dst / "nodes.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "gke-inf-mrusc1-gpu-a",
                            "creationTimestamp": "2026-10-30T02:00:40Z",
                        },
                        "status": {
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:02:10Z",
                                }
                            ]
                        },
                    },
                    {
                        "metadata": {
                            "name": "gke-inf-mrusc1-gpu-b",
                            "creationTimestamp": "2026-10-30T01:00:00Z",
                        },
                        "status": {
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T01:01:40Z",
                                }
                            ]
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (dst / "pods.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "metadata": {
                            "name": "vllm-0",
                            "creationTimestamp": "2026-10-30T02:00:05Z",
                        },
                        "spec": {"nodeName": "gke-inf-mrusc1-gpu-a"},
                        "status": {
                            "conditions": [
                                {
                                    "type": "PodScheduled",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:02:15Z",
                                },
                                {
                                    "type": "Initialized",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:03:20Z",
                                },
                                {
                                    "type": "Ready",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:09:20Z",
                                },
                            ],
                            "containerStatuses": [
                                {
                                    "name": "vllm",
                                    "restartCount": 0,
                                    "state": {
                                        "running": {"startedAt": "2026-10-30T02:04:53Z"}
                                    },
                                }
                            ],
                        },
                    },
                    {
                        "metadata": {
                            "name": "vllm-1",
                            "creationTimestamp": "2026-10-30T02:00:05Z",
                        },
                        "spec": {"nodeName": "gke-inf-mrusc1-gpu-b"},
                        "status": {
                            "conditions": [
                                {
                                    "type": "PodScheduled",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:00:06Z",
                                },
                                {
                                    "type": "Initialized",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:01:00Z",
                                },
                                {
                                    "type": "Ready",
                                    "status": "True",
                                    "lastTransitionTime": "2026-10-30T02:05:30Z",
                                },
                            ],
                            "containerStatuses": [
                                {
                                    "name": "vllm",
                                    "restartCount": 1,
                                    "state": {
                                        "running": {"startedAt": "2026-10-30T02:01:02Z"}
                                    },
                                }
                            ],
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (dst / "events.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "involvedObject": {
                            "kind": "Pod",
                            "name": "vllm-0",
                            "fieldPath": "spec.initContainers{model-sync}",
                        },
                        "reason": "Pulled",
                        "message": 'Successfully pulled image "slim" in 12.5s (12.5s including waiting).',
                        "firstTimestamp": "2026-10-30T02:02:29Z",
                    },
                    {
                        "involvedObject": {
                            "kind": "Pod",
                            "name": "vllm-0",
                            "fieldPath": "spec.containers{vllm}",
                        },
                        "reason": "Pulled",
                        "message": 'Successfully pulled image "vllm:0.31.0" in 1m30.5s (1m32s including waiting).',
                        "firstTimestamp": "2026-10-30T02:04:52Z",
                    },
                    {
                        "involvedObject": {
                            "kind": "Pod",
                            "name": "vllm-1",
                            "fieldPath": "spec.containers{vllm}",
                        },
                        "reason": "Pulled",
                        "message": 'Container image "vllm:0.31.0" already present on machine',
                        "firstTimestamp": "2026-10-30T02:01:01Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (dst / "logs" / "vllm-0.log").write_text(
        "2026-10-30T02:05:30.000000123Z \x1b[1;36m(EngineCore_DP0)\x1b[0;0m INFO Loading weights took 35.42 seconds\n"
        "2026-10-30T02:05:31.000000123Z INFO Model loading took 61.0349 GiB and 36.871 seconds\n"
        "2026-10-30T02:05:45.000000123Z INFO Dynamo bytecode transform time: 13.91 s\n"
        "2026-10-30T02:06:40.000000123Z INFO torch.compile takes 68.25 s in total\n"
        "2026-10-30T02:06:50.000000123Z INFO GPU KV cache size: 81,088 tokens\n"
        "2026-10-30T02:07:20.000000123Z INFO Graph capturing finished in 29 secs\n"
        "2026-10-30T02:07:21.000000123Z INFO init engine (profile, create kv cache, warmup model) took 109.73 seconds\n"
        "2026-10-30T02:09:10.000000123Z INFO:     Application startup complete.\n",
        encoding="utf-8",
    )
    (dst / "logs" / "vllm-1.log").write_text(
        "INFO Loading model weights took 61.0349 GB and 40.10 seconds\n"
        "INFO Compiling a graph for dynamic shape takes 31.5 s\n"
        "INFO GPU KV cache size: 79,872 tokens\n"
        "INFO Graph capturing finished in 22 secs\n"
        "INFO init engine (profile, create kv cache, warmup model) took 95.20 seconds\n"
        "INFO:     Application startup complete.\n",
        encoding="utf-8",
    )
    return dst


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
    """Runs startup_report.py on a synthetic two-Pod fixture."""

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
            fixture = write_startup_fixture(Path(tmp) / "startup")
            out = Path(tmp) / "out"
            rc, stdout, stderr = run_main([str(fixture), "--out", str(out)])
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
            fixture = write_startup_fixture(Path(tmp) / "startup")
            out = Path(tmp) / "out"
            rc, _out, stderr = run_main(
                [str(fixture), "--out", str(out), "--pod-regex", "vllm-1$"]
            )
            self.assertEqual(rc, 0, stderr)
            self.assertEqual(set(read_pods(out)), {"vllm-1"})

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
            baseline = write_startup_fixture(root / "baseline" / "usc1", arm="baseline")
            llmd = write_startup_fixture(root / "llmd" / "usc1", arm="llmd")
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
