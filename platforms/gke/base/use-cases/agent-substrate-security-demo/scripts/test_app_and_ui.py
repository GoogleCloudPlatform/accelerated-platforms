#!/usr/bin/env python3
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

"""Unit tests for Gateway, Partner API, Egress Agent, and Mission Control UI."""

import json
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any
from unittest import mock

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
UI_DIR = BASE_DIR / "ui"
for p in (str(APP_DIR), str(UI_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _install_fastapi_stubs_if_missing() -> bool:
    """Provide lightweight FastAPI/uvicorn stubs when running in stdlib-only CI."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401

        return True
    except ModuleNotFoundError:
        pass

    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str = "") -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class _FakeApp:
        def get(self, *_args: Any, **_kwargs: Any) -> Any:
            return lambda fn: fn

        def post(self, *_args: Any, **_kwargs: Any) -> Any:
            return lambda fn: fn

    class _FakeResponse:
        def __init__(self, content: Any = None, status_code: int = 200) -> None:
            self.content = content
            self.status_code = status_code

    fastapi_mod = types.ModuleType("fastapi")
    fastapi_mod.FastAPI = _FakeApp  # type: ignore[attr-defined]
    fastapi_mod.HTTPException = HTTPException  # type: ignore[attr-defined]
    fastapi_mod.Depends = lambda dep=None: dep  # type: ignore[attr-defined]
    fastapi_mod.Header = lambda default=None: default  # type: ignore[attr-defined]
    fastapi_mod.Query = lambda default=None: default  # type: ignore[attr-defined]
    fastapi_mod.Request = object  # type: ignore[attr-defined]

    resp_mod = types.ModuleType("fastapi.responses")
    resp_mod.JSONResponse = _FakeResponse  # type: ignore[attr-defined]
    resp_mod.PlainTextResponse = _FakeResponse  # type: ignore[attr-defined]

    uvicorn_mod = types.ModuleType("uvicorn")
    uvicorn_mod.Config = lambda *a, **kw: None  # type: ignore[attr-defined]
    uvicorn_mod.Server = object  # type: ignore[attr-defined]
    uvicorn_mod.run = lambda *a, **kw: None  # type: ignore[attr-defined]

    sys.modules.setdefault("fastapi", fastapi_mod)
    sys.modules.setdefault("fastapi.responses", resp_mod)
    sys.modules.setdefault("uvicorn", uvicorn_mod)

    try:
        import google.auth  # noqa: F401
    except ModuleNotFoundError:
        google_mod = sys.modules.setdefault("google", types.ModuleType("google"))
        auth_mod = types.ModuleType("google.auth")
        auth_mod.default = lambda **_kw: (None, None)  # type: ignore[attr-defined]
        google_mod.auth = auth_mod  # type: ignore[attr-defined]
        req_mod = types.ModuleType("google.auth.transport.requests")
        req_mod.Request = object  # type: ignore[attr-defined]
        sys.modules["google.auth"] = auth_mod
        sys.modules["google.auth.transport"] = types.ModuleType("google.auth.transport")
        sys.modules["google.auth.transport.requests"] = req_mod
    return False


HAS_FASTAPI = _install_fastapi_stubs_if_missing()

import egress_agent  # noqa: E402
import gateway  # noqa: E402
import mission_control  # noqa: E402
import partner_api  # noqa: E402


class PartnerApiUnitTest(unittest.TestCase):
    """Verifies non-reflecting credential evaluation in partner_api."""

    def test_evaluate_authorization_never_echoes_secret(self) -> None:
        secret = "demo-partner-credential-super-secret-value"
        status_ok, body_ok = partner_api.evaluate_authorization(
            f"Bearer {secret}", secret
        )
        self.assertEqual(status_ok, 200)
        self.assertTrue(body_ok["authenticated"])
        self.assertTrue(body_ok["placeholder_replaced"])
        self.assertFalse(body_ok["raw_secret_returned"])
        self.assertTrue(str(body_ok["credential_sha256_prefix"]).startswith("sha256:"))
        self.assertNotIn(secret, json.dumps(body_ok))

        status_ph, body_ph = partner_api.evaluate_authorization(
            "Bearer placeholder", secret
        )
        self.assertEqual(status_ph, 401)
        self.assertFalse(body_ph["authenticated"])
        self.assertFalse(body_ph["placeholder_replaced"])

        status_bad, body_bad = partner_api.evaluate_authorization(
            "Bearer wrong-token", secret
        )
        self.assertEqual(status_bad, 401)
        self.assertFalse(body_bad["authenticated"])
        self.assertTrue(body_bad["placeholder_replaced"])

        status_unset, _ = partner_api.evaluate_authorization("Bearer any", "")
        self.assertEqual(status_unset, 500)


class EgressAndGatewayUnitTest(unittest.TestCase):
    """Verifies URL scheme validation, actor/action regexes, and admin token auth."""

    def test_egress_url_scheme_validation(self) -> None:
        self.assertEqual(
            egress_agent.validate_fetch_url("https://example.com/path"),
            "https://example.com/path",
        )
        self.assertEqual(
            egress_agent.validate_fetch_url(
                "http://partner-api.agent-secrets.svc.cluster.local/verify"
            ),
            "http://partner-api.agent-secrets.svc.cluster.local/verify",
        )
        for bad in (
            "file:///etc/passwd",
            "ftp://example.com/resource",
            "gopher://127.0.0.1:70",
            "http:///missing-host",
            "",
        ):
            with self.assertRaises(ValueError):
                egress_agent.validate_fetch_url(bad)

    def test_gateway_actor_and_model_action_validation(self) -> None:
        self.assertEqual(gateway.validate_actor_name("gemini-agent"), "gemini-agent")
        for invalid_actor in ("../etc", "UpperCase", "-leading", "a" * 64, "a/b"):
            with self.assertRaises(gateway.HTTPException) as ctx:
                gateway.validate_actor_name(invalid_actor)
            self.assertEqual(ctx.exception.status_code, 400)

        self.assertEqual(
            gateway.validate_model_action("gemini-3.8-flash:generateContent"),
            "gemini-3.8-flash:generateContent",
        )
        for invalid_action in (
            "gemini-3.8-flash:countTokens",
            "../other:generateContent",
            "gemini-3.8-flash",
        ):
            with self.assertRaises(gateway.HTTPException) as ctx:
                gateway.validate_model_action(invalid_action)
            self.assertEqual(ctx.exception.status_code, 400)

    def test_gateway_admin_token_and_metrics_prefix(self) -> None:
        with mock.patch.object(gateway, "GATEWAY_ADMIN_TOKEN", "top-secret-admin"):
            with self.assertRaises(gateway.HTTPException) as ctx:
                gateway.verify_admin_token(None, None)
            self.assertEqual(ctx.exception.status_code, 401)

            with self.assertRaises(gateway.HTTPException):
                gateway.verify_admin_token("wrong", None)

            gateway.verify_admin_token("top-secret-admin", None)
            gateway.verify_admin_token(None, "Bearer top-secret-admin")

        rendered = gateway.render_prometheus_metrics()
        self.assertIn("agent_gateway_chat_turns_total", rendered)
        self.assertNotIn("workshop_", rendered)


class MissionControlSecurityAndVerdictTest(unittest.TestCase):
    """Verifies Host-header anti-rebinding, CSRF/auth headers, preset guards, and verdicts."""

    def test_host_header_allowlist(self) -> None:
        self.assertTrue(mission_control.is_allowed_host_header("127.0.0.1:18090"))
        self.assertTrue(mission_control.is_allowed_host_header("localhost:18090"))
        self.assertTrue(mission_control.is_allowed_host_header("[::1]:18090"))
        self.assertFalse(mission_control.is_allowed_host_header("attacker.example"))
        self.assertFalse(
            mission_control.is_allowed_host_header("attacker.example:18090")
        )
        self.assertFalse(mission_control.is_allowed_host_header(""))

    def test_buddy_brain_verdicts_and_preset_guards(self) -> None:
        with mock.patch.object(mission_control, "_get_actors", return_value=([], "")):
            clean = mission_control._inspect_buddy_brain(
                {
                    "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
                    "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
                    "memCount": 1,
                    "diskCount": 1,
                }
            )
            self.assertEqual(clean["verdict"], "CLEAN")

            poisoned = mission_control._inspect_buddy_brain(
                {
                    "approvalPolicy": "AUTO_APPROVE_ALL",
                    "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
                }
            )
            self.assertEqual(poisoned["verdict"], "POISONED")

            errored = mission_control._inspect_buddy_brain({})
            self.assertEqual(errored["verdict"], "ERROR")

        with mock.patch.object(mission_control, "ALLOW_CUSTOM_PYTHON", False):
            with self.assertRaises(PermissionError):
                mission_control.api_custom_python(
                    {"code": "import os; os.system('id')"}
                )

        with (
            mock.patch.object(mission_control, "ALLOW_CUSTOM_PROMQL", False),
            mock.patch.object(mission_control, "ensure_port_forwards"),
            mock.patch.object(mission_control, "_detect_project_id", return_value="p1"),
        ):
            with self.assertRaises(PermissionError):
                mission_control.api_prometheus_metrics("up{job='arbitrary'}")

    def test_http_handler_blocks_forged_host_and_missing_csrf_header(self) -> None:
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), mission_control.MissionControlHandler
        )
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # 1. Forged Host header on GET must return 403 (DNS-rebinding defense)
            req_forged = urllib.request.Request(
                f"http://127.0.0.1:{port}/",
                headers={"Host": "attacker.example"},
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_host:
                urllib.request.urlopen(req_forged, timeout=5)
            self.assertEqual(ctx_host.exception.code, 403)

            # 2. POST without X-Requested-With: MissionControl must return 403
            req_no_csrf = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/round1-detonate",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx_csrf:
                urllib.request.urlopen(req_no_csrf, timeout=5)
            self.assertEqual(ctx_csrf.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
