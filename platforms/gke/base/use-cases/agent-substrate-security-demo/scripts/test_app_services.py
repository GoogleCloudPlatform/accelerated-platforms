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

"""Unit tests for `gateway`, `partner_api`, `egress_agent`, and `gemini_agent`."""

import asyncio
import inspect
import io
import json
import ssl
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from unittest import mock

BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _install_app_dependency_stubs() -> None:
    """Install deterministic FastAPI / Google Auth / ADK stubs when absent."""
    try:
        import fastapi  # noqa: F401
    except ModuleNotFoundError:

        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: str = "") -> None:
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        class _DependsSpec:
            def __init__(self, dependency: Any) -> None:
                self.dependency = dependency

        class _FakeApp:
            def __init__(self, **_kwargs: Any) -> None:
                self.routes: dict[tuple[str, str], tuple[list[Any], Any]] = {}

            def _register(self, method: str, path: str, deps_raw: Any = None) -> Any:
                deps = [
                    d.dependency if isinstance(d, _DependsSpec) else d
                    for d in (deps_raw or [])
                ]

                def _decorator(fn: Any) -> Any:
                    self.routes[(method, path)] = (deps, fn)
                    return fn

                return _decorator

            def get(self, path: str, **kw: Any) -> Any:
                return self._register("GET", path, kw.get("dependencies"))

            def post(self, path: str, **kw: Any) -> Any:
                return self._register("POST", path, kw.get("dependencies"))

        class _FakeResponse:
            def __init__(
                self, content: Any = None, status_code: int = 200, **kw: Any
            ) -> None:
                self.content, self.status_code = content, status_code
                self.media_type = kw.get("media_type", "")
                self.headers = kw.get("headers") or {}
                if isinstance(content, (dict, list)):
                    self.body = json.dumps(content).encode("utf-8")
                elif isinstance(content, str):
                    self.body = content.encode("utf-8")
                else:
                    self.body = content if isinstance(content, bytes) else b""

        fastapi_mod = types.ModuleType("fastapi")
        fastapi_mod.FastAPI = _FakeApp  # type: ignore[attr-defined]
        fastapi_mod.HTTPException = HTTPException  # type: ignore[attr-defined]
        fastapi_mod.Depends = _DependsSpec  # type: ignore[attr-defined]
        fastapi_mod.Header = lambda default=None: default  # type: ignore[attr-defined]
        fastapi_mod.Query = lambda default=None: default  # type: ignore[attr-defined]
        fastapi_mod.Request = object  # type: ignore[attr-defined]
        resp_mod = types.ModuleType("fastapi.responses")
        resp_mod.JSONResponse = _FakeResponse  # type: ignore[attr-defined]
        resp_mod.PlainTextResponse = _FakeResponse  # type: ignore[attr-defined]
        sys.modules["fastapi"] = fastapi_mod
        sys.modules["fastapi.responses"] = resp_mod

    try:
        import uvicorn  # noqa: F401
    except ModuleNotFoundError:
        uvicorn_mod = types.ModuleType("uvicorn")
        uvicorn_mod.run = lambda *_a, **_kw: None  # type: ignore[attr-defined]
        uvicorn_mod.Config = lambda *_a, **_kw: object()  # type: ignore[attr-defined]
        uvicorn_mod.Server = lambda *_a, **_kw: object()  # type: ignore[attr-defined]
        sys.modules["uvicorn"] = uvicorn_mod

    try:
        import google as google_mod
    except ModuleNotFoundError:
        google_mod = types.ModuleType("google")
        google_mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules["google"] = google_mod

    try:
        import google.auth
        import google.auth.transport.requests
    except ModuleNotFoundError:
        auth_mod = types.ModuleType("google.auth")
        auth_mod.default = lambda **_kw: (None, None)  # type: ignore[attr-defined]
        google_mod.auth = auth_mod  # type: ignore[attr-defined]
        req_mod = types.ModuleType("google.auth.transport.requests")
        req_mod.Request = object  # type: ignore[attr-defined]
        sys.modules["google.auth"] = auth_mod
        sys.modules["google.auth.transport"] = types.ModuleType("google.auth.transport")
        sys.modules["google.auth.transport.requests"] = req_mod

    try:
        import google.oauth2.credentials
    except ModuleNotFoundError:
        oauth2_mod = types.ModuleType("google.oauth2")
        cred_mod = types.ModuleType("google.oauth2.credentials")

        class _Credentials:
            def __init__(self, token: str = "") -> None:
                self.token = token

        cred_mod.Credentials = _Credentials  # type: ignore[attr-defined]
        oauth2_mod.credentials = cred_mod  # type: ignore[attr-defined]
        google_mod.oauth2 = oauth2_mod  # type: ignore[attr-defined]
        sys.modules["google.oauth2"] = oauth2_mod
        sys.modules["google.oauth2.credentials"] = cred_mod

    try:
        import google.adk.agents  # noqa: F401
    except ModuleNotFoundError:
        adk_mod = types.ModuleType("google.adk")
        agents_mod = types.ModuleType("google.adk.agents")
        events_mod = types.ModuleType("google.adk.events")
        models_mod = types.ModuleType("google.adk.models")
        runners_mod = types.ModuleType("google.adk.runners")
        genai_mod = types.ModuleType("google.genai")
        genai_types_mod = types.ModuleType("google.genai.types")

        class _StubPart:
            def __init__(self, text: str = "") -> None:
                self.text = text

            @classmethod
            def from_text(cls, text: str = "") -> "_StubPart":
                return cls(text=text)

        class _StubContent:
            def __init__(
                self, role: str = "user", parts: list[Any] | None = None
            ) -> None:
                self.role = role
                self.parts = parts or []

        class _StubEvent:
            def __init__(
                self, author: str = "agent", content: Any = None, final: bool = True
            ) -> None:
                self.author = author
                self.content = content
                self._final = final

            def is_final_response(self) -> bool:
                return self._final

        class _StubSessionService:
            def __init__(self) -> None:
                self.events: list[Any] = []

            async def create_session(self, **_kwargs: Any) -> dict[str, str]:
                return {"id": "main"}

            async def append_event(self, session: Any, event: Any) -> None:
                del session
                self.events.append(event)

        class _StubRunner:
            def __init__(self, **_kwargs: Any) -> None:
                self.session_service = _StubSessionService()

            async def run_async(self, **_kwargs: Any) -> AsyncIterator[Any]:
                part = _StubPart(text="Policy verified.")
                yield _StubEvent(content=_StubContent(role="model", parts=[part]))

        agents_mod.Agent = lambda **kw: kw  # type: ignore[attr-defined]
        events_mod.Event = _StubEvent  # type: ignore[attr-defined]
        models_mod.Gemini = lambda **kw: kw  # type: ignore[attr-defined]
        runners_mod.InMemoryRunner = _StubRunner  # type: ignore[attr-defined]
        genai_types_mod.Content = _StubContent  # type: ignore[attr-defined]
        genai_types_mod.Part = _StubPart  # type: ignore[attr-defined]
        genai_mod.types = genai_types_mod  # type: ignore[attr-defined]
        google_mod.adk = adk_mod  # type: ignore[attr-defined]
        google_mod.genai = genai_mod  # type: ignore[attr-defined]
        sys.modules["google.adk"] = adk_mod
        sys.modules["google.adk.agents"] = agents_mod
        sys.modules["google.adk.events"] = events_mod
        sys.modules["google.adk.models"] = models_mod
        sys.modules["google.adk.runners"] = runners_mod
        sys.modules["google.genai"] = genai_mod
        sys.modules["google.genai.types"] = genai_types_mod


_install_app_dependency_stubs()

import egress_agent
import gateway
import gemini_agent
import partner_api


class _StreamingRequest:
    """Test double implementing FastAPI Request.headers and Request.stream()."""

    def __init__(
        self, chunks: list[bytes], headers: dict[str, str] | None = None
    ) -> None:
        self._chunks = chunks
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}
        self.chunks_read = 0

    async def stream(self) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            self.chunks_read += 1
            yield chunk


class PartnerApiUnitTest(unittest.TestCase):
    """Tests keyed HMAC-SHA256 verification and exact `/verify` routing."""

    def test_evaluate_authorization_uses_keyed_hmac_and_handles_non_ascii(self) -> None:
        secret = "demo-partner-credential-super-secret-value"
        status_ok, body_ok = partner_api.evaluate_authorization(
            f"Bearer {secret}", secret, hmac_key=b"k" * 32
        )
        self.assertEqual(status_ok, 200)
        self.assertTrue(body_ok["authenticated"])
        self.assertTrue(body_ok["placeholder_replaced"])
        self.assertFalse(body_ok["raw_secret_returned"])
        self.assertTrue(
            str(body_ok["credential_hmac_prefix"]).startswith("hmac-sha256:")
        )
        self.assertNotIn(secret, json.dumps(body_ok))

        status_ph, body_ph = partner_api.evaluate_authorization(
            "Bearer placeholder", secret
        )
        self.assertEqual(status_ph, 401)
        self.assertFalse(body_ph["placeholder_replaced"])

        status_utf, body_utf = partner_api.evaluate_authorization(
            "Bearer \u00ff-bad", secret
        )
        self.assertEqual(status_utf, 401)
        self.assertTrue(body_utf["placeholder_replaced"])

        status_unset, _ = partner_api.evaluate_authorization("Bearer any", "")
        self.assertEqual(status_unset, 500)
        with (
            mock.patch.object(partner_api, "EXPECTED_TOKEN", ""),
            self.assertRaises(RuntimeError),
        ):
            partner_api.main()

    def test_http_handler_matches_exact_verify_path_only(self) -> None:
        with mock.patch.object(partner_api, "EXPECTED_TOKEN", "s3cr3t"):
            srv = ThreadingHTTPServer(("127.0.0.1", 0), partner_api.PartnerAPIHandler)
            port = srv.server_address[1]
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/readyz", timeout=5
                ) as r_ready:
                    self.assertEqual(r_ready.status, 200)

                req_ok = urllib.request.Request(
                    f"http://127.0.0.1:{port}/verify",
                    headers={"Authorization": "Bearer s3cr3t"},
                )
                with urllib.request.urlopen(req_ok, timeout=5) as r_ok:
                    self.assertEqual(r_ok.status, 200)
                    self.assertTrue(
                        json.loads(r_ok.read().decode("utf-8"))["authenticated"]
                    )

                with self.assertRaises(urllib.error.HTTPError) as ctx_404:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/verify-extra", timeout=5
                    )
                self.assertEqual(ctx_404.exception.code, 404)
            finally:
                srv.shutdown()
                srv.server_close()


class EgressAgentUnitTest(unittest.TestCase):
    """Tests URL validation, redirect scheme validation, and fetch responses."""

    def test_url_and_redirect_validation_blocks_ftp_file_and_control_chars(
        self,
    ) -> None:
        self.assertEqual(
            egress_agent.validate_fetch_url("https://example.com/path"),
            "https://example.com/path",
        )
        bad_urls = (
            "file:///etc/passwd",
            "ftp://example.com/x",
            "http:///no-host",
            "http://:80/empty-host",
            "http://example.com/with space",
            "http://example.com/\r\ninject",
            "",
        )
        for bad in bad_urls:
            with self.assertRaises(ValueError):
                egress_agent.validate_fetch_url(bad)

        handler = egress_agent.SafeRedirectHandler()
        orig_req = urllib.request.Request("https://allowed.example/start")
        for bad_target in ("ftp://evil.example/data", "file:///etc/shadow"):
            with self.assertRaises(ValueError):
                handler.redirect_request(
                    orig_req, io.BytesIO(), 302, "Found", {}, bad_target
                )
        redirected = handler.redirect_request(
            orig_req, io.BytesIO(), 302, "Found", {}, "/next"
        )
        assert redirected is not None
        self.assertEqual(redirected.full_url, "https://allowed.example/next")

    def test_fetch_endpoint_handles_success_bad_url_and_network_errors(self) -> None:
        self.assertEqual(egress_agent.readyz().status_code, 200)
        with self.assertRaises(egress_agent.HTTPException) as ctx_400:
            egress_agent.fetch("ftp://evil.example/file")
        self.assertEqual(ctx_400.exception.status_code, 400)

        fake_resp = mock.MagicMock(status=200)
        fake_resp.read.return_value = b'{"authenticated": true}'
        fake_resp.__enter__.return_value = fake_resp
        fake_resp.__exit__.return_value = False
        mock_opener = mock.MagicMock()
        mock_opener.open.return_value = fake_resp
        with mock.patch("urllib.request.build_opener", return_value=mock_opener):
            self.assertEqual(
                egress_agent.fetch("https://example.com/").status_code, 200
            )

        mock_opener.open.side_effect = urllib.error.URLError(
            "[Errno -2] Name or service not known"
        )
        with mock.patch("urllib.request.build_opener", return_value=mock_opener):
            self.assertEqual(
                egress_agent.fetch("https://example.com/").status_code, 502
            )


class GatewaySecurityUnitTest(unittest.TestCase):
    """Tests Gateway auth, redirect-SSRF defense, streaming caps, and sanitization."""

    def test_admin_auth_fails_closed_and_enforces_route_dependencies(self) -> None:
        with mock.patch.object(gateway, "GATEWAY_ADMIN_TOKEN", ""):
            with self.assertRaises(gateway.HTTPException) as ctx_503:
                gateway.verify_admin_token("anything", None)
            self.assertEqual(ctx_503.exception.status_code, 503)
            with self.assertRaises(RuntimeError):
                gateway.validate_startup_config()

        with (
            mock.patch.object(gateway, "GATEWAY_ADMIN_TOKEN", "secret-tok"),
            mock.patch.object(gateway, "PROJECT_ID", ""),
            self.assertRaises(RuntimeError),
        ):
            gateway.validate_startup_config()

        with (
            mock.patch.object(gateway, "GATEWAY_ADMIN_TOKEN", "secret-tok"),
            mock.patch.object(gateway, "PROJECT_ID", "demo-proj"),
        ):
            for bad_tok in ("wrong", "\u00ff-non-ascii"):
                with self.assertRaises(gateway.HTTPException) as ctx_401:
                    gateway.verify_admin_token(bad_tok, None)
                self.assertEqual(ctx_401.exception.status_code, 401)
            gateway.verify_admin_token("secret-tok", None)
            gateway.verify_admin_token(None, "Bearer secret-tok")
            gateway.validate_startup_config()

        if hasattr(gateway.admin_app, "routes") and isinstance(
            gateway.admin_app.routes, dict
        ):
            for route_key in (
                ("GET", "/metrics"),
                ("POST", "/chat/{actor}"),
                ("GET", "/actors/{actor}/state"),
                ("POST", "/actors/{actor}/execute"),
                ("GET", "/actors/{actor}/fetch"),
            ):
                self.assertIn(route_key, gateway.admin_app.routes)
                deps, _ = gateway.admin_app.routes[route_key]
                self.assertIn(gateway.verify_admin_token, deps)

    def test_router_https_no_redirect_and_bounded_response(self) -> None:
        for bad_router in ("http://atenet-router.ate-system.svc:80", "ftp://r", ""):
            with self.assertRaises(ValueError):
                gateway.validate_router_url(bad_router)
            with (
                mock.patch.object(gateway, "GATEWAY_ADMIN_TOKEN", "tok"),
                mock.patch.object(gateway, "PROJECT_ID", "demo-proj"),
                mock.patch.object(gateway, "ROUTER_HTTPS", bad_router),
            ):
                with self.assertRaises(ValueError):
                    gateway.validate_startup_config()
                with self.assertRaises(gateway.HTTPException) as ctx_500:
                    gateway._call_router("gemini-agent", "/state")
                self.assertEqual(ctx_500.exception.status_code, 500)

        no_redirect = gateway._NoRedirectHandler()
        self.assertIsNone(
            no_redirect.redirect_request(
                urllib.request.Request("https://router/state"),
                io.BytesIO(),
                302,
                "Found",
                {},
                "http://169.254.169.254/computeMetadata/v1/",
            )
        )
        with self.assertRaises(gateway.HTTPException) as ctx_big:
            gateway._read_bounded_stream(io.BytesIO(b"x" * 32), limit=16)
        self.assertEqual(ctx_big.exception.status_code, 502)

    def test_streaming_body_checks_content_length_first_and_caps_stream(self) -> None:
        req_cl_big = _StreamingRequest(
            [b'{"x": 1}'],
            headers={"Content-Length": str(gateway.MAX_MODEL_BODY_BYTES + 10)},
        )
        with self.assertRaises(gateway.HTTPException) as ctx_cl:
            asyncio.run(gateway.read_bounded_model_body(cast(Any, req_cl_big)))
        self.assertEqual(ctx_cl.exception.status_code, 413)
        self.assertEqual(req_cl_big.chunks_read, 0)

        chunk = b"x" * (gateway.MAX_MODEL_BODY_BYTES // 2 + 10)
        req_stream_big = _StreamingRequest([chunk, chunk, chunk])
        with self.assertRaises(gateway.HTTPException) as ctx_st:
            asyncio.run(gateway.read_bounded_model_body(cast(Any, req_stream_big)))
        self.assertEqual(ctx_st.exception.status_code, 413)
        self.assertEqual(req_stream_big.chunks_read, 2)

        req_ok = _StreamingRequest([b'{"contents": ', b"[]}"])
        parsed = asyncio.run(gateway.read_bounded_model_body(cast(Any, req_ok)))
        self.assertEqual(parsed, {"contents": []})

    def test_forward_gemini_sanitizes_upstream_errors_and_records_metrics(self) -> None:
        secret_err = b'{"error": {"message": "internal project 123456 quota details"}}'
        http_err = urllib.error.HTTPError(
            url="https://aiplatform.googleapis.com",
            code=403,
            msg="Forbidden",
            hdrs=cast(Any, None),
            fp=io.BytesIO(secret_err),
        )
        with (
            mock.patch.object(gateway, "PROJECT_ID", "demo-proj"),
            mock.patch.object(gateway, "_wi_token", return_value="mock-wi-token"),
            mock.patch("urllib.request.urlopen", side_effect=http_err),
            self.assertRaises(gateway.HTTPException) as ctx,
        ):
            gateway._forward_gemini({"contents": []})
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertNotIn("123456", str(ctx.exception.detail))

        ok_payload = json.dumps(
            {
                "candidates": [],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 7},
            }
        ).encode("utf-8")
        fake_resp = mock.MagicMock(status=200)
        fake_resp.read.return_value = ok_payload
        fake_resp.__enter__.return_value = fake_resp
        fake_resp.__exit__.return_value = False
        with (
            mock.patch.object(gateway, "PROJECT_ID", "demo-proj"),
            mock.patch.object(gateway, "_wi_token", return_value="mock-wi-token"),
            mock.patch("urllib.request.urlopen", return_value=fake_resp),
        ):
            out = gateway._forward_gemini({"contents": []}, "google-genai-sdk/1.0")
            self.assertIn("usageMetadata", out)

    def test_admin_endpoints_and_ssl_context_reload(self) -> None:
        fake_opener = mock.MagicMock()
        fake_resp = mock.MagicMock(status=200)
        fake_resp.read.return_value = b'{"bootID": "abc12345"}'
        fake_resp.__enter__.return_value = fake_resp
        fake_resp.__exit__.return_value = False
        fake_opener.open.return_value = fake_resp
        with (
            mock.patch.object(
                gateway,
                "build_router_ssl_context",
                return_value=mock.MagicMock(spec=ssl.SSLContext),
            ),
            mock.patch("urllib.request.build_opener", return_value=fake_opener),
        ):
            self.assertEqual(gateway.actor_state("gemini-agent").status_code, 200)
            chat_req = cast(Any, _StreamingRequest([b'{"message": "hi"}']))
            chat_res = gateway.chat_actor("gemini-agent", chat_req)
            if inspect.iscoroutine(chat_res):
                chat_res = asyncio.run(chat_res)
            self.assertEqual(chat_res.status_code, 200)

            exec_req = cast(Any, _StreamingRequest([b'{"command": "id"}']))
            exec_res = gateway.actor_execute("py-detonation-agent", exec_req)
            if inspect.iscoroutine(exec_res):
                exec_res = asyncio.run(exec_res)
            self.assertEqual(exec_res.status_code, 200)

            self.assertEqual(
                gateway.actor_fetch("egress-agent", "https://example.com/").status_code,
                200,
            )
        self.assertEqual(gateway.readyz().status_code, 200)
        ident_doc = json.loads(gateway.identity().body.decode("utf-8"))
        self.assertEqual(ident_doc, {"service": "agent-substrate-gateway"})
        self.assertEqual(gateway.scrape_metrics().status_code, 200)
        self.assertEqual(gateway.admin_metrics().status_code, 200)

        with self.assertRaises(gateway.HTTPException) as ctx_503:
            gateway.build_router_ssl_context("/nonexistent/cert", "/nonexistent/ca")
        self.assertEqual(ctx_503.exception.status_code, 503)


class GeminiAgentUnitTest(unittest.TestCase):
    """Tests stateful ADK policy persistence, bootID, and MEM_COUNT recovery."""

    def test_policy_tools_state_and_chat_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            with (
                mock.patch.object(gemini_agent, "DATA_DIR", str(td)),
                mock.patch.object(gemini_agent, "HIST_FILE", str(td / "history.json")),
                mock.patch.object(gemini_agent, "COUNT_FILE", str(td / "count")),
                mock.patch.object(gemini_agent, "POLICY_FILE", str(td / "policy.json")),
                mock.patch.object(gemini_agent, "_SESSION_READY", False),
                mock.patch.object(gemini_agent, "HISTORY", []),
                mock.patch.object(gemini_agent, "MEM_COUNT", 0),
                mock.patch.object(gemini_agent, "_BOOT_ID", None),
            ):
                updated = gemini_agent.set_approval_policy("AUTO_APPROVE_ALL")
                self.assertEqual(updated["approval_policy"], "AUTO_APPROVE_ALL")
                self.assertEqual(
                    gemini_agent.get_approval_policy()["approval_policy"],
                    "AUTO_APPROVE_ALL",
                )
                gemini_agent.set_approval_policy("REQUIRE_HUMAN_APPROVAL")

                chat_resp = asyncio.run(
                    gemini_agent.chat({"message": "Check approval policy"})
                )
                self.assertEqual(chat_resp.status_code, 200)
                st_resp = gemini_agent.state()
                self.assertEqual(st_resp.status_code, 200)
                st_doc = json.loads(st_resp.body.decode("utf-8"))
                self.assertEqual(st_doc["approvalPolicy"], "REQUIRE_HUMAN_APPROVAL")
                self.assertEqual(st_doc["diskPolicy"], "REQUIRE_HUMAN_APPROVAL")
                self.assertEqual(st_doc["diskCount"], 1)
                self.assertEqual(len(st_doc["bootID"]), 8)

                gemini_agent.MEM_COUNT = 0
                gemini_agent._SESSION_READY = False
                asyncio.run(gemini_agent._ensure_session())
                self.assertTrue(gemini_agent._SESSION_READY)
                self.assertEqual(gemini_agent.MEM_COUNT, 1)
                self.assertEqual(gemini_agent.readyz().status_code, 200)


if __name__ == "__main__":
    unittest.main()
