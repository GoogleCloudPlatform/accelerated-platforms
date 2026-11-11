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

"""Regression unit tests for Mission Control UI (`E1`–`E6`, `S1`, `R-5.4`)."""

import errno
import io
import json
import os
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from unittest import mock

BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "ui"
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

import acts
import kube
import mission_control
import probes
import recovery
import server


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Capture 303 redirect responses without following automatically."""

    def http_error_303(  # pylint: disable=unused-argument
        self, req: Any, fp: Any, code: int, msg: str, headers: Any
    ) -> Any:
        del req, code, msg, headers
        return fp


class MissionControlRegressionTest(unittest.TestCase):
    """Regression coverage for E1–E6, S1, open-redirect, and R-5.4 error paths."""

    def setUp(self) -> None:
        kube.reset_caches()

    def test_e1_dns_and_direct_ip_blocks_require_exact_signatures(self) -> None:
        target = "https://example.com/"
        valid = {
            "status": 502,
            "error": (
                f'HTTP 502: fetch: Get "{target}": '
                "<urlopen error [Errno -2] Name or service not known>"
            ),
        }
        self.assertIn(
            "BLOCKED by Local DNS Relay",
            probes.verify_dns_block_response(valid, target),
        )

        false_positives: list[dict[str, Any]] = [
            {"status": 200, "raw": "<html>ok</html>"},
            {"status": 401, "error": "HTTP 401: Unauthorized"},
            {"error": "URLError: <urlopen error [Errno 111] Connection refused>"},
            {"status": 502, "error": "HTTP 502: upstream connect error from router"},
            {
                "status": 502,
                "error": (
                    f'HTTP 502: fetch: Get "{target}": '
                    "<urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF>"
                ),
            },
        ]
        for bad_resp in false_positives:
            with self.assertRaises(kube.UpstreamCommandError):
                probes.verify_dns_block_response(bad_resp, target)

        ip_ok = {"status": 403, "error": "HTTP 403: egress denied"}
        self.assertIn(
            "HTTP 403", probes.verify_direct_ip_block_response(ip_ok, "http://1.1.1.1/")
        )
        with self.assertRaises(kube.UpstreamCommandError):
            probes.verify_direct_ip_block_response(
                {"status": 502, "error": "HTTP 502: timeout"}, "http://1.1.1.1/"
            )

    def test_e3_seed_clean_buddy_raises_unless_verdict_is_clean(self) -> None:
        poisoned = {
            "approvalPolicy": "AUTO_APPROVE_ALL",
            "diskPolicy": "AUTO_APPROVE_ALL",
            "bootID": "deadbeef",
        }
        actors = ([{"name": "gemini-agent", "state": "SUSPENDED"}], "")
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=actors),
            mock.patch.object(kube, "http_json", return_value=poisoned),
            mock.patch.object(kube, "suspend_actor_checked") as mock_suspend,
        ):
            with self.assertRaises(kube.UpstreamCommandError):
                recovery.api_seed_clean_buddy()
            mock_suspend.assert_not_called()

        clean = {
            "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
            "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
            "memCount": 1,
            "diskCount": 1,
            "turns": 1,
            "bootID": "cafebabe",
        }
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=actors),
            mock.patch.object(kube, "http_json", return_value=clean),
            mock.patch.object(kube, "suspend_actor_checked", return_value="suspended"),
        ):
            self.assertEqual(
                recovery.api_seed_clean_buddy()["brain"]["verdict"], "CLEAN"
            )

    def test_e4_forensic_clone_checks_exit_codes_and_tag_cpu_features(self) -> None:
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=([], "")),
            mock.patch.object(kube, "run_cmd", return_value=("", "denied", 1)),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_round3_forensic_clone()

        def _fake_cmd(args: list[str], **_kw: Any) -> tuple[str, str, int]:
            if args[:4] == ["kubectl", "ate", "get", "actor"] and "-o" not in args:
                return ("", "actor not found", 1)
            return ("ok", "", 0)

        forensic_doc = {
            "bootID": "2222bbbb",
            "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
            "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
            "diskCount": 1,
        }
        buddy_doc = {
            "bootID": "1111aaaa",
            "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
            "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
            "memCount": 1,
        }
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=([], "")),
            mock.patch.object(kube, "run_cmd", side_effect=_fake_cmd),
            mock.patch.object(kube, "http_json", return_value=forensic_doc),
            mock.patch.object(
                probes, "snapshot_cpu_features", return_value=["amd_zen"]
            ),
            mock.patch.object(probes, "tag_cpu_features", return_value="intel_avx"),
        ):
            clone_res = acts.api_round3_forensic_clone(pre_buddy_state=buddy_doc)
            self.assertFalse(clone_res["boot_ids_match"])
            self.assertFalse(clone_res["memory_checkpoint_restored"])
            self.assertTrue(clone_res["cross_cpu_durable_fallback"])
            self.assertTrue(clone_res["checkpoint_restored"])

        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=([], "")),
            mock.patch.object(kube, "run_cmd", side_effect=_fake_cmd),
            mock.patch.object(kube, "http_json", return_value=forensic_doc),
            mock.patch.object(
                probes, "snapshot_cpu_features", return_value=["intel_avx"]
            ),
            mock.patch.object(probes, "tag_cpu_features", return_value="intel_avx"),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_round3_forensic_clone(pre_buddy_state=buddy_doc)

        def _fail_policy_cmd(args: list[str], **_kw: Any) -> tuple[str, str, int]:
            if args[:4] == ["kubectl", "ate", "create", "egress-policy"]:
                return ("", "webhook denied", 1)
            return _fake_cmd(args)

        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=([], "")),
            mock.patch.object(kube, "run_cmd", side_effect=_fail_policy_cmd),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_round3_forensic_clone(pre_buddy_state=buddy_doc)

    def test_e5_act1_probe_checks_metadata_enoent_and_write_mode_sysrq(self) -> None:
        http_403 = urllib.error.HTTPError(
            url="http://169.254.169.254/",
            code=403,
            msg="Forbidden",
            hdrs=cast(Any, None),
            fp=io.BytesIO(b"forbidden"),
        )
        fake_libc = mock.MagicMock()
        fake_libc.mount.return_value = -1
        captured = io.StringIO()
        open_modes: dict[str, str] = {}

        def _fake_open(path: str, mode: str = "r", **_kw: Any) -> Any:
            open_modes[path] = mode
            raise PermissionError("blocked")

        with (
            mock.patch("urllib.request.urlopen", side_effect=http_403),
            mock.patch("ctypes.CDLL", return_value=fake_libc),
            mock.patch("ctypes.set_errno"),
            mock.patch("ctypes.get_errno", return_value=errno.ENOENT),
            mock.patch("os.stat", return_value=mock.MagicMock(st_mode=0o40777)),
            mock.patch("builtins.open", side_effect=_fake_open),
            mock.patch("sys.stdout", captured),
        ):
            exec(probes.ROUND1_PYTHON_SCRIPT, {"__name__": "__probe__"})  # noqa: S102
        out = json.loads(captured.getvalue().strip())
        self.assertFalse(out["metadata_blocked"])
        self.assertIn("HTTP 403", out["gke_metadata"])
        self.assertFalse(out["mount_blocked"])
        self.assertIn("ENOENT", out["mount_syscall"])
        self.assertEqual(open_modes.get("/proc/sysrq-trigger"), "wb")

    def test_e6_cluster_name_promql_errors_and_slow_restores_not_fabricated(
        self,
    ) -> None:
        with (
            mock.patch.dict(os.environ, {"CLUSTER_NAME": ""}, clear=False),
            mock.patch.object(kube, "_load_staged_defaults", return_value={}),
            mock.patch.object(kube, "run_cmd", return_value=("minikube", "", 0)),
        ):
            kube.reset_caches()
            with self.assertRaises(kube.UpstreamCommandError):
                kube.get_cluster_name()

        with (
            mock.patch.dict(os.environ, {"CLUSTER_NAME": "c1"}, clear=False),
            mock.patch.object(
                kube, "http_json", return_value={"error": "HTTP 503: unavailable"}
            ),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            kube.promql_query("up")

        slow_prom = {
            "status": "success",
            "data": {"result": [{"value": [1700000000, "75.25"]}]},
        }
        with (
            mock.patch.dict(os.environ, {"CLUSTER_NAME": "c1"}, clear=False),
            mock.patch.object(kube, "http_json", return_value=slow_prom),
        ):
            self.assertEqual(kube.query_restore_ms("latest"), 75250.0)

        bad_test_a = {
            "authenticated": True,
            "placeholder_replaced": True,
            "raw_secret_returned": False,
        }
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "http_json", return_value=bad_test_a),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_act3_egress_suite()

    def test_s1_cookie_exchange_open_redirect_defense_and_non_ascii_auth(self) -> None:
        with mock.patch.object(kube, "UI_AUTH_TOKEN", "ui-top-secret"):
            srv = ThreadingHTTPServer(("127.0.0.1", 0), server.MissionControlHandler)
            port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                with self.assertRaises(urllib.error.HTTPError) as ctx_unauth:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5)
                self.assertEqual(ctx_unauth.exception.code, 401)

                req_utf = urllib.request.Request(
                    f"http://127.0.0.1:{port}/", headers={"X-UI-Token": "\u00ff-bad"}
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx_utf:
                    urllib.request.urlopen(req_utf, timeout=5)
                self.assertEqual(ctx_utf.exception.code, 401)

                no_redirect = urllib.request.build_opener(_NoRedirect())
                resp_open_redirect = no_redirect.open(
                    f"http://127.0.0.1:{port}////evil.example/?token=ui-top-secret",
                    timeout=5,
                )
                self.assertEqual(resp_open_redirect.status, 303)
                self.assertEqual(resp_open_redirect.headers.get("Location"), "/")
                self.assertEqual(
                    resp_open_redirect.headers.get("X-Frame-Options"), "DENY"
                )
                set_cookie = resp_open_redirect.headers.get("Set-Cookie") or ""
                self.assertIn("HttpOnly", set_cookie)
                self.assertIn("SameSite=Strict", set_cookie)
                self.assertNotIn("ui-top-secret", set_cookie)
                cookie_kv = set_cookie.split(";", 1)[0]

                for asset_path in ("/", "/styles.css", "/app.js"):
                    req_asset = urllib.request.Request(
                        f"http://127.0.0.1:{port}{asset_path}",
                        headers={"Cookie": cookie_kv},
                    )
                    with urllib.request.urlopen(req_asset, timeout=5) as r_ok:
                        self.assertEqual(r_ok.status, 200)
                        self.assertEqual(
                            r_ok.headers.get("X-Content-Type-Options"), "nosniff"
                        )

                hdrs = {
                    "Authorization": "Bearer ui-top-secret",
                    "Content-Type": "application/json",
                    "X-Requested-With": "MissionControl",
                }
                req_bad = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/prometheus",
                    data=b"{bad",
                    headers=hdrs,
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx_400:
                    urllib.request.urlopen(req_bad, timeout=5)
                self.assertEqual(ctx_400.exception.code, 400)

                req_404 = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/unknown",
                    data=b"{}",
                    headers=hdrs,
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx_404:
                    urllib.request.urlopen(req_404, timeout=5)
                self.assertEqual(ctx_404.exception.code, 404)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_r54_handler_catches_timeout_missing_binary_and_forged_host(self) -> None:
        srv = ThreadingHTTPServer(
            ("127.0.0.1", 0), mission_control.MissionControlHandler
        )
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req_host = urllib.request.Request(
                f"http://127.0.0.1:{port}/", headers={"Host": "evil.example"}
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_403:
                urllib.request.urlopen(req_host, timeout=5)
            self.assertEqual(ctx_403.exception.code, 403)

            req_csrf = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/round1-detonate",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_csrf:
                urllib.request.urlopen(req_csrf, timeout=5)
            self.assertEqual(ctx_csrf.exception.code, 403)

            with mock.patch.object(
                acts,
                "api_round1_detonate",
                side_effect=subprocess.TimeoutExpired(cmd=["kubectl"], timeout=5),
            ):
                req_to = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/round1-detonate",
                    data=b"{}",
                    headers={
                        "Content-Type": "application/json",
                        "X-Requested-With": "MissionControl",
                    },
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx_504:
                    urllib.request.urlopen(req_to, timeout=5)
                self.assertEqual(ctx_504.exception.code, 504)

            with (
                mock.patch.object(
                    recovery,
                    "api_status",
                    side_effect=FileNotFoundError("kubectl not found"),
                ),
                self.assertRaises(urllib.error.HTTPError) as ctx_500,
            ):
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=5)
            self.assertEqual(ctx_500.exception.code, 500)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_status_act1_act2_act3_act4_and_prometheus_happy_paths(self) -> None:
        sample_actors = [
            {
                "atespace": "security-demo",
                "name": "gemini-agent",
                "template": "security-demo/gemini-agent-v1",
                "state": "SUSPENDED",
                "worker_pod": "agent-sandbox/agents-0",
                "version": "1",
            }
        ]
        meta = {
            "gke_version": "1.37.2-gke.100",
            "host_kernel": "6.6.72+",
            "substrate_version": "v1.0.0",
        }
        with (
            mock.patch.dict(os.environ, {"CLUSTER_NAME": "c1", "PROJECT_ID": "p1"}),
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=(sample_actors, "NAME")),
            mock.patch.object(kube, "detect_cluster_meta", return_value=meta),
            mock.patch.object(
                kube, "run_cmd", return_value=("agents-0\nagents-1", "", 0)
            ),
        ):
            st = recovery.api_status()
            self.assertEqual(st["cluster"], "c1")
            self.assertEqual(len(st["preset_probes"]), 3)

        probe_json = json.dumps({"kernel": "Linux 4.19.0", "mount_blocked": True})
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "detect_cluster_meta", return_value=meta),
            mock.patch.object(kube, "http_json", return_value={"stdout": probe_json}),
            mock.patch.object(kube, "suspend_actor_checked", return_value="ok"),
        ):
            r1 = acts.api_round1_detonate()
            self.assertEqual(r1["probes"]["kernel"], "Linux 4.19.0")
            self.assertIn("platform", acts.api_custom_python({"probe_id": 0})["code"])

        def _act3_http(url: str, **_kw: Any) -> dict[str, Any]:
            if "partner-api" in url:
                return {
                    "authenticated": True,
                    "placeholder_replaced": True,
                    "raw_secret_returned": False,
                    "credential_hmac_prefix": "hmac-sha256:0123456789ab",
                }
            if "1.1.1.1" in url:
                return {"status": 403, "error": "HTTP 403: egress denied"}
            return {
                "status": 502,
                "error": (
                    'HTTP 502: fetch: Get "https://example.com/": '
                    "<urlopen error [Errno -2] Name or service not known>"
                ),
            }

        valid_pol = (
            'credentialUri: "ate-secret://k8s.io/default/'
            'agent-secrets/example-api/token"'
        )
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "http_json", side_effect=_act3_http),
            mock.patch.object(kube, "run_cmd", return_value=(valid_pol, "", 0)),
            mock.patch.object(kube, "suspend_actor_checked", return_value="ok"),
        ):
            r3 = acts.api_act3_egress_suite()
            self.assertIn("hmac-sha256:0123456789ab", r3["verification_badge"])
            self.assertIn("HTTP 403", r3["direct_ip_block_summary"])

        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "http_json", side_effect=_act3_http),
            mock.patch.object(kube, "run_cmd", return_value=("rules: []", "", 0)),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_act3_egress_suite()

        states = iter(
            [
                {
                    "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
                    "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
                    "memCount": 1,
                    "diskCount": 1,
                },
                {"reply": "Updated to AUTO_APPROVE_ALL"},
                {
                    "approvalPolicy": "AUTO_APPROVE_ALL",
                    "diskPolicy": "AUTO_APPROVE_ALL",
                    "memCount": 2,
                    "diskCount": 2,
                },
            ]
        )
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=(sample_actors, "")),
            mock.patch.object(
                kube, "http_json", side_effect=lambda *_a, **_kw: next(states)
            ),
        ):
            self.assertEqual(
                recovery.api_round2_poison()["brain"]["verdict"], "POISONED"
            )

        clean_boot = {
            "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
            "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
            "bootID": "abcd1234",
        }
        with (
            mock.patch.dict(os.environ, {"CLUSTER_NAME": "c1"}),
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=(sample_actors, "")),
            mock.patch.object(
                kube, "run_cmd", return_value=("Trace ID: " + "a" * 32, "", 0)
            ),
            mock.patch.object(kube, "http_json", return_value=clean_boot),
            mock.patch.object(kube, "query_restore_ms", return_value=210.5),
        ):
            self.assertEqual(
                recovery.api_round3_revert_and_trace()["brain"]["verdict"], "CLEAN"
            )
            self.assertEqual(acts.api_prologue_race()["buddy_boot_id"], "abcd1234")

        def _prom_http(url: str, **_kw: Any) -> dict[str, Any]:
            if url.endswith("/metrics"):
                return {
                    "raw": (
                        'agent_gateway_chat_turns_total{outcome="ok"} 4\n'
                        "agent_gateway_actors_tracked 3\n"
                    ),
                    "status": 200,
                }
            return {
                "status": "success",
                "data": {
                    "result": [
                        {"metric": {"ate.worker.state": "idle"}, "value": [1, "2"]}
                    ]
                },
            }

        with (
            mock.patch.dict(os.environ, {"CLUSTER_NAME": "c1", "PROJECT_ID": "p1"}),
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "http_json", side_effect=_prom_http),
        ):
            pm = recovery.api_prometheus_metrics("workers")
            self.assertEqual(pm["gateway_chat_turns_ok"], "4")
            self.assertEqual(pm["worker_states"]["idle"], 2)


if __name__ == "__main__":
    unittest.main()
