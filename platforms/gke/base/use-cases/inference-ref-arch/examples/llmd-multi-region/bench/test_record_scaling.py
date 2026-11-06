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

"""Unit tests for record_scaling.py."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import record_scaling  # noqa: E402

WAITING = "prometheus.googleapis.com|vllm:num_requests_waiting|gauge"
RUNNING = "prometheus.googleapis.com|vllm:num_requests_running|gauge"


def pods_metric(name: str | None, average: str) -> dict[str, Any]:
    metric = {"name": name} if name else {}
    return {
        "type": "Pods",
        "pods": {"metric": metric, "current": {"averageValue": average}},
    }


def pod(
    name: str,
    phase: str,
    ready: bool,
    deleting: bool = False,
    node: str | None = "gpu-a",
) -> dict[str, Any]:
    conditions = [
        {
            "type": "PodScheduled",
            "status": "True",
            "lastTransitionTime": "2026-10-30T02:00:10Z",
        },
        {
            "type": "Ready",
            "status": "True" if ready else "False",
            "lastTransitionTime": "2026-10-30T02:05:00Z",
        },
    ]
    metadata = {"name": name, "creationTimestamp": "2026-10-30T02:00:00Z"}
    if deleting:
        metadata["deletionTimestamp"] = "2026-10-30T02:10:00Z"
    return {
        "kind": "Pod",
        "metadata": metadata,
        "spec": {"nodeName": node} if node else {},
        "status": {"phase": phase, "conditions": conditions},
    }


class QuantityTest(unittest.TestCase):
    def test_suffixes(self) -> None:
        cases = {
            "1500m": 1.5,
            "500u": 0.0005,
            "250n": 2.5e-7,
            "2k": 2000.0,
            "2Ki": 2048.0,
            "1.5Mi": 1.5 * 2**20,
            "3": 3.0,
            "1.2e2": 120.0,
            "-2": -2.0,
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertAlmostEqual(record_scaling.quantity(raw) or 0.0, want)

    def test_numbers_and_missing_values(self) -> None:
        self.assertEqual(record_scaling.quantity(7), 7.0)
        self.assertIsNone(record_scaling.quantity(None))
        self.assertIsNone(record_scaling.quantity(" "))

    def test_rejects_unknown_suffixes(self) -> None:
        for raw in ("5x", "1.5GB", "Mi"):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(
                    ValueError, "Unsupported Kubernetes quantity"
                ):
                    record_scaling.quantity(raw)


class ExtractHpaMetricsTest(unittest.TestCase):
    def test_reads_metrics_by_name_in_any_order(self) -> None:
        parsed = record_scaling.extract_hpa_metrics(
            [pods_metric(RUNNING, "18"), pods_metric(WAITING, "2500m")]
        )
        self.assertEqual(parsed["hpa_metrics"], {RUNNING: 18.0, WAITING: 2.5})
        self.assertEqual(parsed["hpa_waiting_average"], 2.5)
        self.assertEqual(parsed["hpa_running_average"], 18.0)
        # The primary HPA metric is the queue (waiting) metric.
        self.assertEqual(parsed["hpa_metric"], 2.5)

    def test_running_metric_is_never_recorded_as_the_queue(self) -> None:
        parsed = record_scaling.extract_hpa_metrics(
            [
                {"type": "Resource", "resource": {"name": "cpu"}},
                pods_metric(None, "4"),
                pods_metric(RUNNING, "6"),
            ]
        )
        self.assertEqual(parsed["hpa_metrics"], {"metric_1": 4.0, RUNNING: 6.0})
        self.assertEqual(parsed["hpa_running_average"], 6.0)
        self.assertNotIn("hpa_waiting_average", parsed)
        self.assertNotIn("hpa_metric", parsed)

    def test_no_pod_metrics(self) -> None:
        self.assertEqual(record_scaling.extract_hpa_metrics([]), {})


class SampleTest(unittest.TestCase):
    def fake_kubectl(self, kubeconfig: str, *args: str) -> dict[str, Any]:
        self.assertEqual(kubeconfig, "/kube/usc1")
        if args[1] == "nodes":
            self.assertEqual(
                args, ("get", "nodes", "-l", "cloud.google.com/gke-accelerator")
            )
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "gpu-a",
                            "creationTimestamp": "2026-10-30T01:59:00Z",
                        },
                        "status": {"conditions": [{"type": "Ready", "status": "True"}]},
                    },
                    {
                        "metadata": {
                            "name": "gpu-b",
                            "creationTimestamp": "2026-10-30T02:01:00Z",
                        },
                        "status": {
                            "conditions": [{"type": "Ready", "status": "False"}]
                        },
                    },
                ]
            }
        self.assertEqual(
            args,
            ("get", "hpa,deployment,pod", "-n", "llm-mr", "-l", "acp-mr/arm=llmd"),
        )
        return {
            "items": [
                {
                    "kind": "HorizontalPodAutoscaler",
                    "status": {
                        "currentReplicas": 2,
                        "desiredReplicas": 3,
                        "currentMetrics": [
                            pods_metric(RUNNING, "21"),
                            pods_metric(WAITING, "6"),
                        ],
                    },
                },
                {
                    "kind": "Deployment",
                    "spec": {"replicas": 3},
                    "status": {"readyReplicas": 2},
                },
                pod("vllm-a", "Running", ready=True),
                pod("vllm-b", "Running", ready=False),
                pod("vllm-c", "Pending", ready=False, node=None),
                pod("vllm-d", "Running", ready=True, deleting=True),
            ]
        }

    def test_records_hpa_deployment_pods_and_gpu_nodes(self) -> None:
        with mock.patch.object(
            record_scaling, "kubectl_json", side_effect=self.fake_kubectl
        ):
            record = record_scaling.sample("usc1", "/kube/usc1", "llm-mr", "llmd")
        self.assertNotIn("error", record)
        self.assertEqual(record["region"], "usc1")
        self.assertEqual((record["hpa_current"], record["hpa_desired"]), (2, 3))
        self.assertEqual(record["hpa_metric"], 6.0)
        self.assertEqual(record["hpa_running_average"], 21.0)
        self.assertEqual((record["deploy_replicas"], record["deploy_ready"]), (3, 2))
        self.assertEqual(
            record["pods"],
            {"total": 4, "pending": 1, "running": 2, "ready": 1, "terminating": 1},
        )
        self.assertEqual(
            record["pod_list"][0],
            {
                "name": "vllm-a",
                "created": "2026-10-30T02:00:00Z",
                "deleted": None,
                "node": "gpu-a",
                "scheduled": "2026-10-30T02:00:10Z",
                "ready": "2026-10-30T02:05:00Z",
            },
        )
        self.assertIsNone(record["pod_list"][1]["ready"])
        self.assertEqual(
            record["node_list"],
            {"gpu-a": "2026-10-30T01:59:00Z", "gpu-b": "2026-10-30T02:01:00Z"},
        )
        self.assertEqual((record["gpu_nodes"], record["gpu_nodes_ready"]), (2, 1))

    def test_records_kubectl_errors_and_keeps_going(self) -> None:
        with mock.patch.object(
            record_scaling,
            "kubectl_json",
            side_effect=RuntimeError("Unable to connect to the server"),
        ):
            record = record_scaling.sample("euw2", "/kube/euw2", "llm-mr", "llmd")
        self.assertEqual(record["region"], "euw2")
        self.assertEqual(record["error"], "Unable to connect to the server")


class MainTest(unittest.TestCase):
    def test_usage(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = record_scaling.main(
                ["record_scaling.py", "out.jsonl", "llm-mr", "llmd"]
            )
        self.assertEqual(rc, 2)
        self.assertIn("Usage: record_scaling.py", err.getvalue())


if __name__ == "__main__":
    unittest.main()
