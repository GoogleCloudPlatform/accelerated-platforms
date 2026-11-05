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

"""Unit tests for podsnapshot_patch.py."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import podsnapshot_patch  # noqa: E402

WRAPPER = 'vllm serve "$@" &\nwait\n'
RENDERED = """\
apiVersion: v1
kind: Service
metadata:
  name: vllm-llmd
spec:
  ports:
  - port: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llmd-epp
spec:
  template:
    spec:
      containers:
      - name: epp
        command: ["/epp"]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-llmd
spec:
  replicas: 2
  template:
    metadata:
      labels:
        acp-mr/arm: llmd
    spec:
      containers:
      - name: routing-sidecar
        image: sidecar:1
      - name: modelserver
        image: vllm:1
        command: ["vllm", "serve"]
        args:
        - Qwen/Qwen3-32B
        - --port=8000
        - --kv-events-config
        - '{"endpoint":"tcp://$(POD_IP):5557"}'
        - --kv-events-config={"topic":"kv@$(POD_IP)"}
        - --enable-prefix-caching
        env:
        - name: POD_IP
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: POD_PORT
          value: "8000"
        - name: KV_EVENTS_ENDPOINT
          value: tcp://$(POD_IP):5557
        - name: HF_HOME
          value: /cache
        livenessProbe:
          httpGet:
            port: 8000
        readinessProbe:
          httpGet:
            port: 8000
        resources:
          requests:
            memory: 80Gi
          limits:
            memory: 80Gi
            nvidia.com/gpu: "1"
"""


def load_docs() -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(RENDERED) if d]


def model_server_deployment(docs: list[dict[str, Any]]) -> dict[str, Any]:
    return next(
        d
        for d in docs
        if d["kind"] == "Deployment" and d["metadata"]["name"] == "vllm-llmd"
    )


def model_server(docs: list[dict[str, Any]]) -> dict[str, Any]:
    return next(
        c
        for c in model_server_deployment(docs)["spec"]["template"]["spec"]["containers"]
        if c["name"] == "modelserver"
    )


def template_sha(docs: list[dict[str, Any]]) -> str:
    template = model_server_deployment(docs)["spec"]["template"]
    return hashlib.sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()


class PatchDeploymentDocsTest(unittest.TestCase):
    def test_makes_the_pod_template_snapshot_ready(self) -> None:
        docs = load_docs()
        podsnapshot_patch.patch_deployment_docs(docs, "vllm-llmd", WRAPPER, "140Gi")
        pod = docs[2]["spec"]["template"]["spec"]
        container = model_server(docs)

        self.assertEqual(pod["runtimeClassName"], "gvisor")
        self.assertIs(pod["enableServiceLinks"], False)
        self.assertEqual(
            container["command"], ["/bin/sh", "-c", WRAPPER, "vllm-podsnapshot"]
        )
        self.assertEqual(
            container["args"],
            ["Qwen/Qwen3-32B", "--port=8000", "--enable-prefix-caching"],
        )
        self.assertNotIn("livenessProbe", container)
        self.assertIn("readinessProbe", container)
        self.assertEqual(
            container["env"],
            [
                {"name": "HF_HOME", "value": "/cache"},
                {"name": "VLLM_HOST_IP", "value": "127.0.0.1"},
            ],
        )
        self.assertEqual(
            container["resources"],
            {
                "requests": {"memory": "80Gi"},
                "limits": {"memory": "140Gi", "nvidia.com/gpu": "1"},
            },
        )
        # The replica count stays with the caller (deploy-arm.sh and the HPA).
        self.assertEqual(docs[2]["spec"]["replicas"], 2)
        sidecar = docs[2]["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual(sidecar, {"name": "routing-sidecar", "image": "sidecar:1"})

    def test_leaves_other_documents_unchanged(self) -> None:
        docs = load_docs()
        before = copy.deepcopy(docs[:2])
        podsnapshot_patch.patch_deployment_docs(docs, "vllm-llmd", WRAPPER, "140Gi")
        self.assertEqual(docs[:2], before)

    def test_replaces_a_pod_ip_vllm_host_ip(self) -> None:
        docs = load_docs()
        model_server(docs)["env"].append(
            {
                "name": "VLLM_HOST_IP",
                "valueFrom": {"fieldRef": {"fieldPath": "status.podIP"}},
            }
        )
        podsnapshot_patch.patch_deployment_docs(docs, "vllm-llmd", WRAPPER, "140Gi")
        host_ip = [e for e in model_server(docs)["env"] if e["name"] == "VLLM_HOST_IP"]
        self.assertEqual(host_ip, [{"name": "VLLM_HOST_IP", "value": "127.0.0.1"}])

    def test_keeps_an_explicit_vllm_host_ip(self) -> None:
        docs = load_docs()
        model_server(docs)["env"].append({"name": "VLLM_HOST_IP", "value": "0.0.0.0"})
        podsnapshot_patch.patch_deployment_docs(docs, "vllm-llmd", WRAPPER, "140Gi")
        host_ip = [e for e in model_server(docs)["env"] if e["name"] == "VLLM_HOST_IP"]
        self.assertEqual(host_ip, [{"name": "VLLM_HOST_IP", "value": "0.0.0.0"}])

    def test_hash_is_of_the_final_pod_template(self) -> None:
        docs = load_docs()
        sha = podsnapshot_patch.patch_deployment_docs(
            docs, "vllm-llmd", WRAPPER, "140Gi"
        )
        self.assertEqual(sha, template_sha(docs))

    def test_hash_changes_with_the_memory_limit_and_the_wrapper(self) -> None:
        def sha(wrapper: str, memory_limit: str) -> str:
            return podsnapshot_patch.patch_deployment_docs(
                load_docs(), "vllm-llmd", wrapper, memory_limit
            )

        self.assertEqual(sha(WRAPPER, "140Gi"), sha(WRAPPER, "140Gi"))
        self.assertNotEqual(sha(WRAPPER, "140Gi"), sha(WRAPPER, "160Gi"))
        self.assertNotEqual(sha(WRAPPER, "140Gi"), sha(WRAPPER + "\n", "140Gi"))

    def test_errors(self) -> None:
        cases = [
            ("missing", "140Gi", None, "Deployment missing not found"),
            ("vllm-llmd", "140GB", None, "not a Kubernetes quantity"),
            ("vllm-llmd", "", None, "check MR_POD_SNAPSHOT_MEMORY_LIMIT"),
            (
                "vllm-llmd",
                "140Gi",
                lambda c: c.update(name="vllm"),
                "container 'modelserver' not found in Deployment vllm-llmd",
            ),
            (
                "vllm-llmd",
                "140Gi",
                lambda c: c.update(command=["/bin/sh", "-c", WRAPPER]),
                r"expected the modelserver command \['vllm', 'serve'\], "
                r"got \['/bin/sh', '-c', '...'\] \(already patched\?\)",
            ),
            (
                "vllm-llmd",
                "140Gi",
                lambda c: c["args"].append("--host=$(POD_IP)"),
                r"arguments \['--host=\$\(POD_IP\)'\] reference pod-specific "
                r"variables \(POD_IP, POD_NAME, POD_PORT, KV_EVENTS_ENDPOINT\)",
            ),
        ]
        for name, memory_limit, mutate, message in cases:
            with self.subTest(message=message):
                docs = load_docs()
                if mutate is not None:
                    mutate(model_server(docs))
                with self.assertRaisesRegex(ValueError, message):
                    podsnapshot_patch.patch_deployment_docs(
                        docs, name, WRAPPER, memory_limit
                    )


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.rendered = Path(tmp.name) / "llmd.rendered.yaml"
        self.rendered.write_text(RENDERED, encoding="utf-8")
        self.wrapper = Path(tmp.name) / "checkpoint-wrapper.sh"
        self.wrapper.write_text(WRAPPER, encoding="utf-8")

    def run_main(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = podsnapshot_patch.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_rewrites_the_manifests_and_prints_the_template_hash(self) -> None:
        rc, out, err = self.run_main(
            str(self.rendered), "vllm-llmd", str(self.wrapper), "140Gi"
        )
        self.assertEqual(rc, 0, err)
        docs = [d for d in yaml.safe_load_all(self.rendered.read_text("utf-8")) if d]
        self.assertEqual(len(docs), 3)
        self.assertEqual(model_server(docs)["command"][3], "vllm-podsnapshot")
        self.assertEqual(out, template_sha(docs) + "\n")

    def test_reports_errors_without_touching_the_manifests(self) -> None:
        rc, out, err = self.run_main(
            str(self.rendered), "missing", str(self.wrapper), "140Gi"
        )
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")
        self.assertEqual(err, f"{self.rendered}: Deployment missing not found\n")
        self.assertEqual(self.rendered.read_text("utf-8"), RENDERED)

    def test_command_line(self) -> None:
        script = str(SCRIPTS_DIR / "podsnapshot_patch.py")
        proc = subprocess.run(
            [
                sys.executable,
                script,
                str(self.rendered),
                "vllm-llmd",
                str(self.wrapper),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("the following arguments are required: memory_limit", proc.stderr)
        proc = subprocess.run(
            [
                sys.executable,
                script,
                str(self.rendered),
                "vllm-llmd",
                str(self.wrapper),
                "140Gi",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout, r"^[0-9a-f]{64}\n$")


if __name__ == "__main__":
    unittest.main()
