# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Scoped in-cluster Kubernetes REST client for pod telemetry and cold-pod race."""

import http.client
import json
import os
import secrets
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from .telemetry import TERMINAL_BUS

_SA_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
_SA_CA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
_ALLOWED_LOG_DEPLOYMENTS = {
    "intent-extproc": ("app=intent-extproc", "intent-extproc"),
    "atenet-egress": ("app=atenet-egress", "envoy"),
    "atenet-router": ("app=atenet-router", "atenet-router"),
    "ate-api-server": ("app=ate-api-server", "ate-api-server"),
}


class InClusterK8sClient:
    """Minimal Kubernetes API client scoped to ate-system reads and demo-bench pods."""

    def __init__(self) -> None:
        self.bench_namespace = os.environ.get("DEMO_BENCH_NAMESPACE", "demo-bench")
        self.ate_namespace = os.environ.get("ATE_SYSTEM_NAMESPACE", "ate-system")

    def _connect(self) -> tuple[http.client.HTTPSConnection, dict[str, str]]:
        host = os.environ.get("KUBERNETES_SERVICE_HOST", "")
        port = int(os.environ.get("KUBERNETES_SERVICE_PORT", "443"))
        if not host or not _SA_TOKEN_PATH.is_file() or not _SA_CA_PATH.is_file():
            raise RuntimeError(
                "Kubernetes in-cluster ServiceAccount credentials not found; "
                "this endpoint must run inside deploy/triage-agent."
            )
        token = _SA_TOKEN_PATH.read_text(encoding="utf-8").strip()
        ssl_ctx = ssl.create_default_context(cafile=str(_SA_CA_PATH))
        conn = http.client.HTTPSConnection(host, port, context=ssl_ctx, timeout=20.0)
        return conn, {"Authorization": f"Bearer {token}"}

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[int, str]:
        conn, headers = self._connect()
        body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
            return resp.status, raw
        finally:
            conn.close()

    def list_ate_system_pods(self) -> list[dict[str, str]]:
        """Lists control-plane and gateway pods in ate-system."""
        status, raw = self._request(
            "GET", f"/api/v1/namespaces/{self.ate_namespace}/pods"
        )
        if status >= 400:
            raise RuntimeError(f"K8s GET pods in {self.ate_namespace} failed: {status}")
        data = json.loads(raw)
        pods: list[dict[str, str]] = []
        for item in data.get("items", []):
            name = item.get("metadata", {}).get("name", "")
            statuses = item.get("status", {}).get("containerStatuses") or []
            ready = sum(1 for cs in statuses if cs.get("ready"))
            total = len(item.get("spec", {}).get("containers") or [])
            pods.append(
                {
                    "name": name,
                    "ready": f"{ready}/{total}",
                    "phase": item.get("status", {}).get("phase", "Unknown"),
                }
            )
        return pods

    def tail_ate_system_logs(self, source: str, tail_lines: int = 80) -> dict[str, Any]:
        """Fetches real container logs from an allowlisted ate-system component."""
        if source not in _ALLOWED_LOG_DEPLOYMENTS:
            allowed = ", ".join(sorted(_ALLOWED_LOG_DEPLOYMENTS))
            raise ValueError(f"Unsupported log source {source!r}; choose: {allowed}")
        selector, preferred_container = _ALLOWED_LOG_DEPLOYMENTS[source]
        qs = urlencode({"labelSelector": selector})
        status, raw = self._request(
            "GET", f"/api/v1/namespaces/{self.ate_namespace}/pods?{qs}"
        )
        if status >= 400:
            raise RuntimeError(f"K8s pod lookup for {source} failed: HTTP {status}")
        items = json.loads(raw).get("items") or []
        if not items:
            return {"source": source, "pod": "", "container": "", "lines": []}
        pod = items[0]
        pod_name = pod["metadata"]["name"]
        containers = [c["name"] for c in pod.get("spec", {}).get("containers") or []]
        container = (
            preferred_container
            if preferred_container in containers
            else (containers[0] if containers else "")
        )
        bounded_lines = max(10, min(int(tail_lines), 250))
        log_qs_dict: dict[str, Any] = {"tailLines": bounded_lines, "timestamps": "true"}
        if container:
            log_qs_dict["container"] = container
        log_path = (
            f"/api/v1/namespaces/{self.ate_namespace}/pods/{pod_name}/log?"
            f"{urlencode(log_qs_dict)}"
        )
        l_status, l_raw = self._request("GET", log_path)
        if l_status >= 400:
            raise RuntimeError(
                f"K8s pod log read for {pod_name} failed: HTTP {l_status}: {l_raw[:200]}"
            )
        return {
            "source": source,
            "pod": pod_name,
            "container": container,
            "lines": [ln for ln in l_raw.splitlines() if ln.strip()],
        }

    def measure_cold_gvisor_pod_ms(self, runner_image: str) -> dict[str, Any]:
        """Spawns an isolated cold gVisor Pod in demo-bench and times until Ready."""
        if not runner_image:
            raise ValueError(
                "RUNNER_IMAGE environment variable is required for cold-pod race"
            )
        suffix = secrets.token_hex(3)
        pod_name = f"cold-gvisor-baseline-{suffix}"
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": pod_name,
                "namespace": self.bench_namespace,
                "labels": {"app": "cold-gvisor-baseline"},
            },
            "spec": {
                "runtimeClassName": "gvisor",
                "nodeSelector": {"sandbox-runtime": "gvisor"},
                "restartPolicy": "Never",
                "automountServiceAccountToken": False,
                "containers": [
                    {
                        "name": "runner",
                        "image": runner_image,
                        "imagePullPolicy": "Always",
                        "readinessProbe": {
                            "httpGet": {"path": "/readyz", "port": 80},
                            "initialDelaySeconds": 1,
                            "periodSeconds": 1,
                        },
                        "resources": {
                            "requests": {"cpu": "500m", "memory": "2Gi"},
                            "limits": {"cpu": "1", "memory": "2Gi"},
                        },
                    }
                ],
            },
        }
        create_path = f"/api/v1/namespaces/{self.bench_namespace}/pods"
        pod_path = f"{create_path}/{pod_name}"
        t0 = time.monotonic()
        TERMINAL_BUS.emit(
            "k8s",
            f"K8s POST {create_path} -> spawning cold gVisor Pod {pod_name}",
            step="2",
        )
        try:
            c_status, c_raw = self._request("POST", create_path, json_body=pod_manifest)
            if c_status >= 400:
                raise RuntimeError(
                    f"Failed creating {pod_name} in {self.bench_namespace}: "
                    f"HTTP {c_status} {c_raw[:240]}"
                )
            last_phase = ""
            deadline = t0 + 180.0
            while time.monotonic() < deadline:
                g_status, g_raw = self._request("GET", pod_path)
                if g_status == 200:
                    pdata = json.loads(g_raw)
                    phase = pdata.get("status", {}).get("phase", "Pending")
                    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
                    if phase != last_phase:
                        last_phase = phase
                        TERMINAL_BUS.emit(
                            "k8s",
                            f"K8s Pod {self.bench_namespace}/{pod_name} phase={phase} (+{elapsed_ms} ms)",
                            step="2",
                            duration_ms=elapsed_ms,
                        )
                    conditions = pdata.get("status", {}).get("conditions") or []
                    if any(
                        c.get("type") == "Ready" and c.get("status") == "True"
                        for c in conditions
                    ):
                        TERMINAL_BUS.emit(
                            "verdict",
                            f"Cold gVisor Pod {self.bench_namespace}/{pod_name} Ready in {elapsed_ms} ms",
                            step="2",
                            duration_ms=elapsed_ms,
                        )
                        return {
                            "pod_ref": f"{self.bench_namespace}/{pod_name}",
                            "cold_ms": elapsed_ms,
                        }
                time.sleep(0.4)
            raise TimeoutError(
                f"Timed out waiting 180s for {self.bench_namespace}/{pod_name} Ready"
            )
        finally:
            self._request("DELETE", f"{pod_path}?gracePeriodSeconds=0")
            TERMINAL_BUS.emit(
                "k8s",
                f"K8s DELETE {pod_path} (ephemeral benchmark pod cleaned up)",
                step="2",
            )
