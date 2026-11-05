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

"""Records the autoscaling state of one experiment arm in every region.

Usage: record_scaling.py <out.jsonl> <namespace> <arm> <key>=<kubeconfig>...
                         [--interval 15]

Every interval, for each region (in parallel), it appends one JSON line with:
the HPA's current and desired replicas and all current metric values, the model
server Deployment's ready replicas, the arm's pods by state (with each pod's
creation, scheduling, and readiness times, and its node), and the GPU nodes
(with their creation times).
It stops when <out.jsonl>.stop exists.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import subprocess
import sys
import time
from typing import Any

QUANTITY_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(Ki|Mi|Gi|Ti|Pi|Ei|n|u|µ|m|k|M|G|T|P|E)?$"
)
QUANTITY_MULTIPLIERS: dict[str, float] = {
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "M": 1e6,
    "G": 1e9,
    "T": 1e12,
    "P": 1e15,
    "E": 1e18,
    "Ki": float(2**10),
    "Mi": float(2**20),
    "Gi": float(2**30),
    "Ti": float(2**40),
    "Pi": float(2**50),
    "Ei": float(2**60),
}


def kubectl_json(kubeconfig: str, *args: str) -> Any:
    out = subprocess.run(
        ["kubectl", "--kubeconfig", kubeconfig, *args, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300])
    return json.loads(out.stdout)


def quantity(value: str | int | float | None) -> float | None:
    """Parses a Kubernetes resource.Quantity string (SI or binary suffix) to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip()
    if not raw:
        return None
    m = QUANTITY_RE.match(raw)
    if not m:
        raise ValueError(f"Unsupported Kubernetes quantity: {value!r}")
    num_str, suffix = m.groups()
    base = float(num_str)
    return base * QUANTITY_MULTIPLIERS[suffix] if suffix else base


def extract_hpa_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """Extracts the Pods metrics reported in an HPA's status.currentMetrics.

    The list order isn't significant, so the queue (num_requests_waiting) and
    running (num_requests_running) metrics are found by name. hpa_metric is the
    queue metric, which scale_report.py plots as the waiting line.
    """
    out: dict[str, Any] = {}
    parsed: dict[str, float | None] = {}
    for idx, m_entry in enumerate(metrics):
        pods_m = m_entry.get("pods")
        if not isinstance(pods_m, dict):
            continue
        m_name = (pods_m.get("metric") or {}).get("name") or f"metric_{idx}"
        avg_raw = (pods_m.get("current") or {}).get("averageValue")
        parsed[m_name] = quantity(avg_raw)
    if not parsed:
        return out
    out["hpa_metrics"] = parsed
    waiting = next(
        (v for k, v in parsed.items() if "num_requests_waiting" in k and v is not None),
        None,
    )
    running = next(
        (v for k, v in parsed.items() if "num_requests_running" in k and v is not None),
        None,
    )
    if waiting is not None:
        out["hpa_waiting_average"] = waiting
        out["hpa_metric"] = waiting
    if running is not None:
        out["hpa_running_average"] = running
    return out


def sample(key: str, kubeconfig: str, namespace: str, arm: str) -> dict[str, Any]:
    record: dict[str, Any] = {"ts": time.time(), "region": key}
    try:
        items = kubectl_json(
            kubeconfig,
            "get",
            "hpa,deployment,pod",
            "-n",
            namespace,
            "-l",
            f"acp-mr/arm={arm}",
        )["items"]
        pods = {"total": 0, "pending": 0, "running": 0, "ready": 0, "terminating": 0}
        pod_list = []
        for item in items:
            kind = item["kind"]
            if kind == "HorizontalPodAutoscaler":
                status = item.get("status", {})
                record["hpa_current"] = status.get("currentReplicas")
                record["hpa_desired"] = status.get("desiredReplicas")
                metrics = status.get("currentMetrics") or []
                record.update(extract_hpa_metrics(metrics))
            elif kind == "Deployment":
                record["deploy_replicas"] = item["spec"].get("replicas")
                record["deploy_ready"] = item.get("status", {}).get("readyReplicas", 0)
            elif kind == "Pod":
                pods["total"] += 1
                conds = item.get("status", {}).get("conditions", [])
                times = {
                    c["type"]: c.get("lastTransitionTime")
                    for c in conds
                    if c.get("status") == "True"
                }
                pod_list.append(
                    {
                        "name": item["metadata"]["name"],
                        "created": item["metadata"].get("creationTimestamp"),
                        "deleted": item["metadata"].get("deletionTimestamp"),
                        "node": item.get("spec", {}).get("nodeName"),
                        "scheduled": times.get("PodScheduled"),
                        "ready": times.get("Ready"),
                    }
                )
                if item["metadata"].get("deletionTimestamp"):
                    pods["terminating"] += 1
                    continue
                phase = item.get("status", {}).get("phase")
                if phase == "Pending":
                    pods["pending"] += 1
                elif phase == "Running":
                    pods["running"] += 1
                conditions = {
                    c["type"]: c["status"]
                    for c in item.get("status", {}).get("conditions", [])
                }
                if conditions.get("Ready") == "True":
                    pods["ready"] += 1
        record["pods"] = pods
        record["pod_list"] = pod_list
        nodes = kubectl_json(
            kubeconfig, "get", "nodes", "-l", "cloud.google.com/gke-accelerator"
        )["items"]
        record["node_list"] = {
            n["metadata"]["name"]: n["metadata"].get("creationTimestamp") for n in nodes
        }
        record["gpu_nodes"] = len(nodes)
        record["gpu_nodes_ready"] = sum(
            1
            for n in nodes
            if any(
                c["type"] == "Ready" and c["status"] == "True"
                for c in n.get("status", {}).get("conditions", [])
            )
        )
    except Exception as e:  # keep recording through transient API errors
        record["error"] = str(e)
    return record


def main(argv: list[str]) -> int:
    interval = 15.0
    args = list(argv)
    if "--interval" in args:
        i = args.index("--interval")
        interval = float(args[i + 1])
        args = args[:i] + args[i + 2 :]
    if len(args) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    out, namespace, arm = args[1:4]
    regions = dict(a.split("=", 1) for a in args[4:])
    stop = out + ".stop"
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(regions)) as pool:
        while not os.path.exists(stop):
            started = time.time()
            records = list(
                pool.map(
                    lambda kv: sample(kv[0], kv[1], namespace, arm), regions.items()
                )
            )
            with open(out, "a", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            time.sleep(max(0.0, interval - (time.time() - started)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
