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
the HPA's current and desired replicas and current metric value, the model
server Deployment's ready replicas, the arm's pods by state (with each pod's
creation, scheduling, and readiness times, and its node), and the GPU nodes
(with their creation times).
It stops when <out.jsonl>.stop exists.
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import time


def kubectl_json(kubeconfig, *args):
    out = subprocess.run(
        ["kubectl", "--kubeconfig", kubeconfig, *args, "-o", "json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip()[:300])
    return json.loads(out.stdout)


def quantity(value):
    """Parses a Kubernetes quantity such as '1500m' or '3'."""
    if value is None:
        return None
    value = str(value)
    if value.endswith("m"):
        return float(value[:-1]) / 1000.0
    return float(value)


def sample(key, kubeconfig, namespace, arm):
    record = {"ts": time.time(), "region": key}
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
                if metrics and metrics[0].get("pods"):
                    record["hpa_metric"] = quantity(
                        metrics[0]["pods"]["current"].get("averageValue")
                    )
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


def main(argv):
    interval = 15.0
    if "--interval" in argv:
        i = argv.index("--interval")
        interval = float(argv[i + 1])
        argv = argv[:i] + argv[i + 2 :]
    if len(argv) < 5:
        print(__doc__, file=sys.stderr)
        return 2
    out, namespace, arm = argv[1:4]
    regions = dict(a.split("=", 1) for a in argv[4:])
    stop = out + ".stop"
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(regions)) as pool:
        while not os.path.exists(stop):
            started = time.time()
            records = list(
                pool.map(
                    lambda kv: sample(kv[0], kv[1], namespace, arm), regions.items()
                )
            )
            with open(out, "a") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            time.sleep(max(0.0, interval - (time.time() - started)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
