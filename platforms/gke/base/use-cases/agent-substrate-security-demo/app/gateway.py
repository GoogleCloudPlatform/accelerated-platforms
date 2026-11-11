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

"""Split-plane Gateway service for Google ADK actors on Agent Substrate v1.0.0.

Exposes three strictly separated HTTP listeners so untrusted sandboxes hold zero
Google Cloud credentials, cannot pivot laterally to sibling actors, and reach
actors exclusively through `atenet-router`'s authenticated mTLS listener:
- :8080 (0.0.0.0, actor-facing Service port 80, restricted via NetworkPolicy to
  `atenet-egress` only): authenticates via GKE Workload Identity Application
  Default Credentials (`google.auth.default`) and proxies Google ADK Gemini
  model calls plus GET /readyz (upstream error bodies sanitized).
- :9091 (0.0.0.0, restricted via NetworkPolicy to `gmp-system` only): serves
  Prometheus telemetry on GET /metrics and GET /readyz.
- :8081 (127.0.0.1 loopback by default, operator-facing via port-forward
  authenticated with required `X-Gateway-Admin-Token` / Bearer token):
  POST /chat/{actor}, GET /actors/{actor}/state, POST /actors/{actor}/execute,
  GET /actors/{actor}/fetch, GET /identity, GET /readyz, and GET /metrics.
"""

import asyncio
import hmac
import json
import logging
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import IO, Any

import google.auth
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from google.auth.transport.requests import Request as GoogleAuthRequest

LOGGER = logging.getLogger(__name__)

model_app = FastAPI()
metrics_app = FastAPI()
admin_app = FastAPI()

ATESPACE = os.environ.get("ATESPACE", "security-demo")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global").strip() or "global"
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash").strip()
ROUTER_HTTPS = os.environ.get(
    "ROUTER_HTTPS", "https://atenet-router.ate-system.svc:443"
).rstrip("/")
ROUTER_CLIENT_CERT = os.environ.get(
    "ROUTER_CLIENT_CERT", "/run/router-client/credential-bundle.pem"
)
ROUTER_CA_CERT = os.environ.get("ROUTER_CA_CERT", "/run/router-client/router-ca.pem")
ADMIN_BIND_HOST = os.environ.get("ADMIN_BIND_HOST", "127.0.0.1")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9091"))
GATEWAY_ADMIN_TOKEN = os.environ.get("GATEWAY_ADMIN_TOKEN", "").strip()

ACTOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
MODEL_ACTION_RE = re.compile(r"^[a-zA-Z0-9._-]+:generateContent$")
API_CLIENT_HEADER_RE = re.compile(r"^[A-Za-z0-9._/ -]{1,256}$")
BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
MAX_MODEL_BODY_BYTES = 4 * 1024 * 1024
MAX_ROUTER_RESPONSE_BYTES = 4 * 1024 * 1024

CRED_LOCK = threading.Lock()
_CREDENTIALS: Any = None

TLS_LOCK = threading.Lock()
_CACHED_SSL_CTX: tuple[tuple[int, int], tuple[int, int], ssl.SSLContext] | None = None

METRICS_LOCK = threading.Lock()
METRICS: dict[str, Any] = {
    "chat_turns_ok": 0,
    "chat_turns_error": 0,
    "model_requests": 0,
    "model_duration_sum": 0.0,
    "model_buckets": {b: 0 for b in BUCKETS},
    "tokens_input": 0,
    "tokens_output": 0,
    "actors_seen": set(),
}


def _constant_time_equals(left: str, right: str) -> bool:
    """Compare UTF-8 strings in constant time without non-ASCII TypeError."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never follow 30x redirects emitted by untrusted actors behind router."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, fp, code, msg, headers, newurl
        return None


def _read_bounded_stream(stream: Any, limit: int = MAX_ROUTER_RESPONSE_BYTES) -> bytes:
    """Read at most `limit` bytes from an upstream HTTP stream."""
    raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise HTTPException(
            status_code=502,
            detail=f"Upstream response exceeded {limit} bytes",
        )
    return bytes(raw)


def validate_actor_name(actor: str) -> str:
    """Validate that an actor identifier matches DNS-1123 label constraints."""
    if not ACTOR_RE.fullmatch(actor):
        raise HTTPException(status_code=400, detail="Invalid actor name")
    return actor


def validate_model_action(model_action: str) -> str:
    """Allow only `:generateContent` model actions through the sandbox proxy."""
    if not MODEL_ACTION_RE.fullmatch(model_action):
        raise HTTPException(status_code=400, detail="Unsupported model action")
    return model_action


def validate_router_url(router_url: str) -> str:
    """Reject non-HTTPS router URLs so client-cert mTLS can never downgrade."""
    parsed = urllib.parse.urlparse(router_url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(
            f"ROUTER_HTTPS must be an https:// URL for mTLS, got {router_url!r}"
        )
    return router_url.strip().rstrip("/")


def validate_startup_config() -> None:
    """Fail closed at startup if admin auth, project, or router is invalid."""
    if not GATEWAY_ADMIN_TOKEN:
        raise RuntimeError(
            "Refusing to start gateway: GATEWAY_ADMIN_TOKEN is empty "
            "(mount Secret/gateway-admin-token)."
        )
    if not PROJECT_ID:
        raise RuntimeError("Refusing to start gateway: GOOGLE_CLOUD_PROJECT is empty.")
    validate_router_url(ROUTER_HTTPS)


def verify_admin_token(
    x_gateway_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Require a non-empty operator admin token (fail closed with 503)."""
    if not GATEWAY_ADMIN_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="GATEWAY_ADMIN_TOKEN is not configured on gateway",
        )
    candidate = (x_gateway_admin_token or "").strip()
    if not candidate and authorization and authorization.startswith("Bearer "):
        candidate = authorization[len("Bearer ") :].strip()
    if not candidate or not _constant_time_equals(candidate, GATEWAY_ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized admin request")


def build_router_ssl_context(
    cert_path: str = ROUTER_CLIENT_CERT,
    ca_path: str = ROUTER_CA_CERT,
) -> ssl.SSLContext:
    """Build or reload the PodCertificate mTLS SSLContext for atenet-router.

    Presents the gateway pod's `podidentity.podcert.ate.dev/identity` SPIFFE
    client certificate and verifies `atenet-router`'s server certificate against
    `servicedns.podcert.ate.dev/identity` (`router-ca.pem`) + DNS hostname SAN.
    """
    global _CACHED_SSL_CTX
    with TLS_LOCK:
        try:
            cert_st = os.stat(cert_path)
            ca_st = os.stat(ca_path)
            cert_stamp = (cert_st.st_mtime_ns, cert_st.st_ino)
            ca_stamp = (ca_st.st_mtime_ns, ca_st.st_ino)
            if (
                _CACHED_SSL_CTX is not None
                and _CACHED_SSL_CTX[0] == cert_stamp
                and _CACHED_SSL_CTX[1] == ca_stamp
            ):
                return _CACHED_SSL_CTX[2]
            ctx = ssl.create_default_context(
                purpose=ssl.Purpose.SERVER_AUTH, cafile=ca_path
            )
            ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            ctx.check_hostname = True
            ctx.load_cert_chain(certfile=cert_path, keyfile=cert_path)
            _CACHED_SSL_CTX = (cert_stamp, ca_stamp, ctx)
            return ctx
        except (OSError, ssl.SSLError) as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Router mTLS credentials unavailable: {exc}",
            ) from exc


def _call_router(
    actor: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> tuple[int, str]:
    """Invoke an actor through `atenet-router` over mTLS without redirects."""
    actor = validate_actor_name(actor)
    try:
        router_base = validate_router_url(ROUTER_HTTPS)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    with METRICS_LOCK:
        METRICS["actors_seen"].add(actor)

    headers: dict[str, str] = {"ate-target-actor": f"{ATESPACE}/{actor}"}
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{router_base}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    ssl_ctx = build_router_ssl_context()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl_ctx),
        _NoRedirectHandler(),
    )

    try:
        with opener.open(req, timeout=timeout) as resp:
            body_bytes = _read_bounded_stream(resp)
            return resp.status, body_bytes.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body_bytes = _read_bounded_stream(exc)
        return exc.code, body_bytes.decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"atenet-router request failed: {exc}",
        ) from exc


def _wi_token() -> str:
    """Obtain a cached GKE Workload Identity OAuth token via Google Auth ADC."""
    global _CREDENTIALS
    with CRED_LOCK:
        if _CREDENTIALS is None:
            _CREDENTIALS, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        if not _CREDENTIALS.valid or _CREDENTIALS.expired:
            _CREDENTIALS.refresh(GoogleAuthRequest())
        return str(_CREDENTIALS.token)


def render_prometheus_metrics() -> str:
    """Format gateway telemetry in Prometheus text exposition format (0.0.4)."""
    with METRICS_LOCK:
        tracked = len(METRICS["actors_seen"])
        bucket_lines = [
            (
                "agent_gateway_model_request_duration_seconds_bucket"
                f'{{backend="gemini",le="{b}"}} {METRICS["model_buckets"][b]}'
            )
            for b in BUCKETS
        ]
        bucket_lines.append(
            "agent_gateway_model_request_duration_seconds_bucket"
            f'{{backend="gemini",le="+Inf"}} {METRICS["model_requests"]}'
        )
        lines = [
            "# HELP agent_gateway_chat_turns_total Total actor chat turns.",
            "# TYPE agent_gateway_chat_turns_total counter",
            (
                'agent_gateway_chat_turns_total{outcome="ok"} '
                f'{METRICS["chat_turns_ok"]}'
            ),
            (
                'agent_gateway_chat_turns_total{outcome="error"} '
                f'{METRICS["chat_turns_error"]}'
            ),
            "# HELP agent_gateway_model_request_duration_seconds Gemini latency.",
            "# TYPE agent_gateway_model_request_duration_seconds histogram",
            *bucket_lines,
            (
                "agent_gateway_model_request_duration_seconds_sum"
                f'{{backend="gemini"}} {METRICS["model_duration_sum"]:.4f}'
            ),
            (
                "agent_gateway_model_request_duration_seconds_count"
                f'{{backend="gemini"}} {METRICS["model_requests"]}'
            ),
            "# HELP agent_gateway_model_tokens_total Total model tokens processed.",
            "# TYPE agent_gateway_model_tokens_total counter",
            (
                'agent_gateway_model_tokens_total{backend="gemini",direction="input"} '
                f'{METRICS["tokens_input"]}'
            ),
            (
                'agent_gateway_model_tokens_total{backend="gemini",direction="output"} '
                f'{METRICS["tokens_output"]}'
            ),
            "# HELP agent_gateway_actors_tracked Number of actors addressed.",
            "# TYPE agent_gateway_actors_tracked gauge",
            f"agent_gateway_actors_tracked {tracked}",
        ]
    return "\n".join(lines) + "\n"


def _forward_gemini(
    payload: dict[str, Any], api_client_header: str = ""
) -> dict[str, Any]:
    """Forward a GenerateContent request using Workload Identity credentials."""
    if not PROJECT_ID:
        raise HTTPException(
            status_code=500,
            detail="Gateway model proxy is not configured",
        )
    t0 = time.monotonic()
    token = _wi_token()
    url = (
        f"https://aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}"
        f"/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "x-goog-user-project": PROJECT_ID,
    }
    clean_client = api_client_header.strip()
    if clean_client and API_CLIENT_HEADER_RE.fullmatch(clean_client):
        headers["x-goog-api-client"] = clean_client
    data: dict[str, Any] = {}
    for attempt in range(2):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=55) as resp:
                raw_bytes = _read_bounded_stream(resp)
                data = json.loads(raw_bytes.decode("utf-8"))
                break
        except urllib.error.HTTPError as exc:
            _ = exc.read(4096)
            if exc.code in (429, 502, 503, 504) and attempt == 0:
                time.sleep(1.5)
                continue
            LOGGER.warning("Upstream Vertex AI returned HTTP %s", exc.code)
            status = exc.code if 400 <= exc.code < 600 else 502
            raise HTTPException(
                status_code=status,
                detail=f"Upstream model request failed (HTTP {exc.code})",
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 0:
                time.sleep(1.0)
                continue
            LOGGER.warning("Upstream Vertex AI transport failure: %s", exc)
            raise HTTPException(
                status_code=502,
                detail="Upstream model endpoint unreachable",
            ) from exc

    dur = time.monotonic() - t0
    usage = data.get("usageMetadata") or {}
    with METRICS_LOCK:
        METRICS["model_requests"] += 1
        METRICS["model_duration_sum"] += dur
        for bucket in BUCKETS:
            if dur <= bucket:
                METRICS["model_buckets"][bucket] += 1
        METRICS["tokens_input"] += int(usage.get("promptTokenCount") or 0)
        METRICS["tokens_output"] += int(usage.get("candidatesTokenCount") or 0)
    return data


@model_app.get("/readyz")
@metrics_app.get("/readyz")
@admin_app.get("/readyz")
def readyz() -> PlainTextResponse:
    return PlainTextResponse("ok\n")


@admin_app.get("/identity")
def identity() -> JSONResponse:
    """Service identity endpoint verified by local port-forward helpers."""
    return JSONResponse({"service": "agent-substrate-gateway"})


@metrics_app.get("/metrics")
def scrape_metrics() -> PlainTextResponse:
    return PlainTextResponse(
        render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@admin_app.get("/metrics", dependencies=[Depends(verify_admin_token)])
def admin_metrics() -> PlainTextResponse:
    return PlainTextResponse(
        render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def parse_model_request_body(raw_body: bytes) -> dict[str, Any]:
    """Validate and parse an inbound JSON object body for gateway POST calls."""
    if len(raw_body) > MAX_MODEL_BODY_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Request payload exceeds {MAX_MODEL_BODY_BYTES} bytes",
        )
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON payload: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Request payload must be a JSON object"
        )
    return payload


async def read_bounded_model_body(request: Request) -> dict[str, Any]:
    """Enforce Content-Length and streaming byte cap before buffering body."""
    raw_cl = request.headers.get("content-length")
    if raw_cl is not None:
        try:
            declared = int(raw_cl)
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail="Invalid Content-Length header"
            ) from exc
        if declared < 0:
            raise HTTPException(
                status_code=400, detail="Negative Content-Length header"
            )
        if declared > MAX_MODEL_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Request payload exceeds {MAX_MODEL_BODY_BYTES} bytes",
            )

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_MODEL_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Request payload exceeds {MAX_MODEL_BODY_BYTES} bytes",
            )
        chunks.append(chunk)
    return parse_model_request_body(b"".join(chunks))


@model_app.post(
    "/v1beta1/projects/{sandbox_project}/locations/{sandbox_location}"
    "/publishers/google/models/{model_action:path}"
)
async def proxy_adk_generate_content(
    sandbox_project: str,
    sandbox_location: str,
    model_action: str,
    request: Request,
) -> JSONResponse:
    """Zero-secret proxy endpoint invoked by Google ADK (`Gemini(base_url=...)`)."""
    del sandbox_project, sandbox_location
    validate_model_action(model_action)
    payload = await read_bounded_model_body(request)
    api_client = request.headers.get("x-goog-api-client", "")
    data = await asyncio.to_thread(_forward_gemini, payload, api_client)
    return JSONResponse(data, headers={"Connection": "close"})


def _json_or_text_response(status_code: int, raw_text: str) -> Any:
    try:
        return JSONResponse(json.loads(raw_text), status_code=status_code)
    except json.JSONDecodeError:
        return PlainTextResponse(raw_text, status_code=status_code)


@admin_app.post("/chat/{actor}", dependencies=[Depends(verify_admin_token)])
async def chat_actor(actor: str, request: Request) -> Any:
    body = await read_bounded_model_body(request)
    status_code, raw_text = await asyncio.to_thread(
        _call_router,
        actor,
        "/chat",
        "POST",
        body,
        60.0,
    )
    with METRICS_LOCK:
        if 200 <= status_code < 300:
            METRICS["chat_turns_ok"] += 1
        else:
            METRICS["chat_turns_error"] += 1
    return _json_or_text_response(status_code, raw_text)


@admin_app.get("/actors/{actor}/state", dependencies=[Depends(verify_admin_token)])
def actor_state(actor: str) -> Any:
    status_code, raw_text = _call_router(
        actor=actor, path="/state", method="GET", timeout=45.0
    )
    return _json_or_text_response(status_code, raw_text)


@admin_app.post("/actors/{actor}/execute", dependencies=[Depends(verify_admin_token)])
async def actor_execute(actor: str, request: Request) -> Any:
    body = await read_bounded_model_body(request)
    status_code, raw_text = await asyncio.to_thread(
        _call_router,
        actor,
        "/execute",
        "POST",
        body,
        30.0,
    )
    return _json_or_text_response(status_code, raw_text)


@admin_app.get("/actors/{actor}/fetch", dependencies=[Depends(verify_admin_token)])
def actor_fetch(actor: str, url: str = Query(...)) -> Any:
    encoded = urllib.parse.urlencode({"url": url})
    status_code, raw_text = _call_router(
        actor=actor, path=f"/fetch?{encoded}", method="GET", timeout=20.0
    )
    return _json_or_text_response(status_code, raw_text)


async def _serve_all() -> None:
    """Run model, metrics, and admin listeners concurrently and fail fast."""
    configs = (
        uvicorn.Config(model_app, host="0.0.0.0", port=8080, log_level="warning"),
        uvicorn.Config(
            metrics_app, host="0.0.0.0", port=METRICS_PORT, log_level="warning"
        ),
        uvicorn.Config(admin_app, host=ADMIN_BIND_HOST, port=8081, log_level="warning"),
    )
    servers = [uvicorn.Server(cfg) for cfg in configs]
    tasks = [asyncio.create_task(srv.serve()) for srv in servers]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for srv in servers:
        srv.should_exit = True
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for finished in done:
        exc = finished.exception()
        if exc is not None:
            raise exc


def main() -> None:
    validate_startup_config()
    asyncio.run(_serve_all())


if __name__ == "__main__":
    main()
