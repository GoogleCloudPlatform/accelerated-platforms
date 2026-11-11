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

"""Unit tests for kube, probes, acts, server, and gateway proxy helpers."""

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest import mock

BASE_DIR = Path(__file__).resolve().parent.parent
for p in (str(BASE_DIR / "ui"), str(BASE_DIR / "app"), str(BASE_DIR / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import test_app_services

test_app_services._install_app_dependency_stubs()

import acts
import gateway
import kube
import probes
import server


class _JsonEchoHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        del fmt, args

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        if self.path == "/auth-check":
            tok = self.headers.get("X-Gateway-Admin-Token", "")
            status = 200 if tok == "refreshed-tok" else 401
            raw = json.dumps({"ok": status == 200, "tok": tok}).encode("utf-8")
        elif self.path == "/plain":
            status = 200
            raw = b"plain-text-metrics"
        else:
            status = 200
            raw = b'{"service": "agent-substrate-gateway"}'
        self.send_response(status)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class KubeAndProbesCoverageTest(unittest.TestCase):
    """Covers kube.py subprocess/HTTP/metadata helpers, probes.py, and proxy."""

    def setUp(self) -> None:
        kube.reset_caches()

    def test_kube_cluster_project_meta_actors_and_suspend(self) -> None:
        out, err, rc = kube.run_cmd([sys.executable, "-c", "print('hello-kube')"])
        self.assertEqual(rc, 0)
        self.assertEqual(out, "hello-kube")
        self.assertEqual(err, "")

        def _fake_kubectl(args: list[str], **_kw: Any) -> tuple[str, str, int]:
            if args[:3] == ["kubectl", "config", "current-context"]:
                return ("gke_my-proj_us-central1-b_my-cluster", "", 0)
            if args[:3] == ["kubectl", "get", "nodes"]:
                return ("v1.37.2-gke.100|6.6.72+", "", 0)
            if "ate-api-server" in args:
                return (
                    "ghcr.io/agent-substrate/substrate/ate-apiserver:v1.0.0@sha256:aa",
                    "",
                    0,
                )
            if args[:4] == ["kubectl", "ate", "get", "actors"] and "-o" in args:
                doc = {
                    "actors": [
                        {
                            "metadata": {
                                "atespace": "security-demo",
                                "name": "gemini-agent",
                                "version": "2",
                            },
                            "actorTemplate": {
                                "atespace": "security-demo",
                                "name": "gemini-agent-v1",
                            },
                            "status": {
                                "state": "ACTOR_STATE_SUSPENDED",
                                "workerAssignment": {
                                    "workerNamespace": "agent-sandbox",
                                    "workerPod": "agents-0",
                                },
                            },
                        }
                    ]
                }
                return ("Warning: shared client\n" + json.dumps(doc), "", 0)
            if args[:4] == ["kubectl", "ate", "get", "actors"]:
                return ("Warning: shared client\nNAME STATE", "", 0)
            if args[:4] == ["kubectl", "ate", "suspend", "actor"]:
                return ("Suspended", "", 0)
            if "gateway-admin-token" in args:
                return (base64.b64encode(b"secret-123").decode("ascii"), "", 0)
            return ("", "", 0)

        with (
            mock.patch.dict(
                os.environ,
                {"CLUSTER_NAME": "", "PROJECT_ID": "", "GATEWAY_ADMIN_TOKEN": ""},
                clear=False,
            ),
            mock.patch.object(kube, "run_cmd", side_effect=_fake_kubectl),
        ):
            self.assertEqual(kube.get_cluster_name(), "my-cluster")
            self.assertEqual(kube.detect_project_id(), "my-proj")
            meta = kube.detect_cluster_meta()
            self.assertEqual(meta["gke_version"], "1.37.2-gke.100")
            self.assertEqual(meta["substrate_version"], "v1.0.0")
            actors_list, tbl = kube.get_actors(include_table=True)
            self.assertEqual(len(actors_list), 1)
            self.assertEqual(actors_list[0]["state"], "SUSPENDED")
            self.assertEqual(tbl, "NAME STATE")
            self.assertEqual(kube._get_gateway_admin_token(), "secret-123")
            self.assertEqual(kube.suspend_actor_checked("gemini-agent"), "Suspended")

    def test_kube_http_json_token_refresh_and_isolated_port_forward_lifecycle(
        self,
    ) -> None:
        srv = ThreadingHTTPServer(("127.0.0.1", 0), _JsonEchoHandler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as tmp_state:
                tokens = iter(["stale-tok", "refreshed-tok", "refreshed-tok"])
                gw_url = f"http://127.0.0.1:{port}"
                with (
                    mock.patch.object(kube, "STATE_DIR", Path(tmp_state)),
                    mock.patch.object(kube, "GATEWAY_URL", gw_url),
                    mock.patch.object(kube, "PROMETHEUS_URL", gw_url),
                    mock.patch.object(kube, "GATEWAY_PORT", port),
                    mock.patch.object(kube, "PROM_PORT", port),
                    mock.patch.object(
                        kube,
                        "_get_gateway_admin_token",
                        side_effect=lambda **_kw: next(tokens),
                    ),
                ):
                    kube.ensure_port_forwards()
                    res = kube.http_json(f"{gw_url}/auth-check")
                    self.assertTrue(res["ok"])
                    plain = kube.http_json(f"{gw_url}/plain")
                    self.assertEqual(plain["raw"], "plain-text-metrics")

                fake_proc = mock.MagicMock(spec=subprocess.Popen)
                fake_proc.poll.return_value = None
                fake_proc.wait.return_value = 0
                with mock.patch.object(kube, "STATE_DIR", Path(tmp_state)):
                    kube._PF_PROCESSES[port] = fake_proc
                    kube.stop_spawned_port_forwards()
                fake_proc.terminate.assert_called_once()

                spawned = mock.MagicMock(spec=subprocess.Popen)
                spawned.pid = 999999
                spawned.poll.return_value = None
                spawned.wait.return_value = 0
                with (
                    mock.patch.object(kube, "STATE_DIR", Path(tmp_state)),
                    mock.patch.object(kube, "GATEWAY_PORT", 19991),
                    mock.patch.object(kube, "_port_open", return_value=False),
                    mock.patch.object(kube, "_probe_http", side_effect=[False, True]),
                    mock.patch("subprocess.Popen", return_value=spawned),
                ):
                    kube._start_single_pf(19991)
                    kube.stop_spawned_port_forwards()

                with (
                    mock.patch.object(kube, "STATE_DIR", Path(tmp_state)),
                    mock.patch.object(kube, "GATEWAY_PORT", 19992),
                    mock.patch.object(kube, "_port_open", return_value=True),
                    mock.patch.object(kube, "_probe_http", return_value=False),
                    self.assertRaises(kube.UpstreamCommandError),
                ):
                    kube._start_single_pf(19992)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_snapshot_cpu_features_act2_ipv6_hosts_and_gateway_proxy(self) -> None:
        snap_doc = {
            "status": {
                "snapshots": [
                    {
                        "sandboxRuntime": {
                            "version": {
                                "attributes": [{"key": "cpu_features", "value": "avx2"}]
                            }
                        }
                    },
                    {
                        "sandboxRuntime": {
                            "version": {
                                "attributes": [
                                    {"key": "cpu_features", "value": "avx512"}
                                ]
                            }
                        }
                    },
                ]
            }
        }
        tag_doc = {
            "status": {
                "snapshot": {
                    "sandboxRuntime": {
                        "version": {
                            "attributes": [{"key": "cpu_features", "value": "avx2"}]
                        }
                    }
                }
            }
        }
        with mock.patch.object(
            kube, "run_cmd", return_value=(json.dumps(snap_doc), "", 0)
        ):
            self.assertEqual(
                probes.snapshot_cpu_features("gemini-agent-forensic"),
                ["avx2", "avx512"],
            )
        with mock.patch.object(
            kube, "run_cmd", return_value=(json.dumps(tag_doc), "", 0)
        ):
            self.assertEqual(probes.tag_cpu_features("clean-checkpoint-tag"), "avx2")
        with (
            mock.patch.object(kube, "run_cmd", return_value=("", "boom", 1)),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            probes.snapshot_cpu_features("gemini-agent-forensic")

        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "run_cmd", return_value=("TAG_TABLE", "", 0)),
            mock.patch.object(
                acts,
                "api_prologue_race",
                return_value={
                    "local_restore_avg_ms": 180.0,
                    "gcs_restore_avg_ms": 420.0,
                    "cli_roundtrip_resume_ms": 600.0,
                    "trace_id": "b" * 32,
                    "buddy_state": {"bootID": "11223344"},
                    "under_the_hood": [],
                },
            ),
            mock.patch.object(
                acts,
                "api_round3_forensic_clone",
                return_value={
                    "buddy_boot_id": "11223344",
                    "forensic_boot_id": "11223344",
                    "boot_ids_match": True,
                    "memory_checkpoint_restored": True,
                    "cross_cpu_durable_fallback": False,
                    "checkpoint_restored": True,
                    "under_the_hood": [],
                },
            ),
        ):
            act2 = acts.api_act2_snapshots()
            self.assertTrue(act2["boot_ids_match"])

        # Host allowlist IPv6 + non-loopback bind guard (`0.0.0.0` and `::`)
        self.assertTrue(server.is_loopback_host("[::1]"))
        self.assertTrue(server.is_allowed_host_header("[::1]:18090"))
        self.assertFalse(server.is_allowed_host_header("[::1"))
        with mock.patch.object(kube, "BIND_HOST", "fd00::1"):
            self.assertTrue(server.is_allowed_host_header("[fd00::1]:18090"))

        for wildcard_bind in ("0.0.0.0", "::"):
            with (
                mock.patch.object(kube, "BIND_HOST", wildcard_bind),
                mock.patch.object(kube, "UI_AUTH_TOKEN", ""),
                mock.patch.object(kube, "ALLOW_UNAUTHENTICATED_BIND", False),
                self.assertRaises(SystemExit),
            ):
                server.run_server()

        # Gateway proxy_adk_generate_content + _wi_token
        fake_creds = mock.MagicMock()
        fake_creds.valid = False
        fake_creds.expired = True
        fake_creds.token = "mock-refreshed-token"
        with (
            mock.patch.object(gateway, "_CREDENTIALS", None),
            mock.patch("google.auth.default", return_value=(fake_creds, "p1")),
        ):
            self.assertEqual(gateway._wi_token(), "mock-refreshed-token")
            fake_creds.refresh.assert_called_once()

        req = test_app_services._StreamingRequest([b'{"contents": []}'])
        with mock.patch.object(
            gateway, "_forward_gemini", return_value={"candidates": []}
        ):
            resp = asyncio.run(
                gateway.proxy_adk_generate_content(
                    "sandbox",
                    "global",
                    "gemini-3.8-flash:generateContent",
                    req,  # type: ignore[arg-type]
                )
            )
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
