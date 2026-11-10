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

Exposes two strictly separated HTTP listeners so untrusted sandboxes hold zero
Google Cloud credentials, cannot pivot laterally to sibling actors, and reach
actors exclusively through `atenet-router`'s authenticated SPIFFE mTLS listener:
- :8080 (0.0.0.0, actor-facing Service port 80, restricted via NetworkPolicy to
  `atenet-egress` and Managed Prometheus): authenticates via GKE Workload Identity
  Application Default Credentials (`google.auth.default`) and proxies Google ADK
  Gemini model calls, plus GET /readyz and GET /metrics.
- :8081 (127.0.0.1 loopback by default, operator-facing via `kubectl port-forward`
  authenticated with `X-Gateway-Admin-Token` / Bearer token): POST /chat/{actor},
  GET /actors/{actor}/state, POST /actors/{actor}/execute,
  GET /actors/{actor}/fetch, GET /identity, GET /readyz, and GET /metrics.
"""

import asyncio
import hmac
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import google.auth
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from google.auth.transport.requests import Request as GoogleAuthRequest

model_app = FastAPI()
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
GATEWAY_ADMIN_TOKEN = os.environ.get("GATEWAY_ADMIN_TOKEN", "").strip()

ACTOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
MODEL_ACTION_RE = re.compile(r"^[a-zA-Z0-9._-]+:generateContent$")
BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)

CRED_LOCK = threading.Lock()
_CREDENTIALS: Any = None

TLS_LOCK = threading.Lock()
_CACHED_SSL_CTX: tuple[float, float, ssl.SSLContext] | None = None

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


def verify_admin_token(
    x_gateway_admin_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """Require the operator admin token when configured on the deployment."""
    if not GATEWAY_ADMIN_TOKEN:
        return
    candidate = (x_gateway_admin_token or "").strip()
    if not candidate and authorization and authorization.startswith("Bearer "):
        candidate = authorization[len("Bearer ") :].strip()
    if not candidate or not hmac.compare_digest(candidate, GATEWAY_ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Unauthorized admin request")


def build_router_ssl_context(
    cert_path: str = ROUTER_CLIENT_CERT,
    ca_path: str = ROUTER_CA_CERT,
) -> ssl.SSLContext:
    """Build or reload the PodCertificate SPIFFE mTLS SSLContext for atenet-router."""
    global _CACHED_SSL_CTX
    try:
        cert_mtime = os.path.getmtime(cert_path)
        ca_mtime = os.path.getmtime(ca_path)
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Router mTLS credentials unavailable: {exc}",
        ) from exc

    with TLS_LOCK:
        if (
            _CACHED_SSL_CTX is not None
            and _CACHED_SSL_CTX[0] == cert_mtime
            and _CACHED_SSL_CTX[1] == ca_mtime
        ):
            return _CACHED_SSL_CTX[2]
        ctx = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH, cafile=ca_path
        )
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.check_hostname = True
        ctx.load_cert_chain(certfile=cert_path, keyfile=cert_path)
        _CACHED_SSL_CTX = (cert_mtime, ca_mtime, ctx)
        return ctx


def _call_router(
    actor: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 60.0,
) -> tuple[int, str]:
    """Invoke an actor through `atenet-router` over PodCertificate SPIFFE mTLS."""
    actor = validate_actor_name(actor)
    with METRICS_LOCK:
        METRICS["actors_seen"].add(actor)

    headers: dict[str, str] = {"ate-target-actor": f"{ATESPACE}/{actor}"}
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        f"{ROUTER_HTTPS}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    opener: urllib.request.OpenerDirector
    if ROUTER_HTTPS.startswith("https://"):
        ssl_ctx = build_router_ssl_context()
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl_ctx)
        )
    else:
        opener = urllib.request.build_opener()

    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return exc.code, body_text
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
            f'agent_gateway_model_request_duration_seconds_bucket{{backend="gemini",le="{b}"}} {METRICS["model_buckets"][b]}'
            for b in BUCKETS
        ]
        bucket_lines.append(
            f'agent_gateway_model_request_duration_seconds_bucket{{backend="gemini",le="+Inf"}} {METRICS["model_requests"]}'
        )
        lines = [
            "# HELP agent_gateway_chat_turns_total Total chat turns processed by the gateway.",
            "# TYPE agent_gateway_chat_turns_total counter",
            f'agent_gateway_chat_turns_total{{outcome="ok"}} {METRICS["chat_turns_ok"]}',
            f'agent_gateway_chat_turns_total{{outcome="error"}} {METRICS["chat_turns_error"]}',
            "# HELP agent_gateway_model_request_duration_seconds Gemini model request latency.",
            "# TYPE agent_gateway_model_request_duration_seconds histogram",
            *bucket_lines,
            f'agent_gateway_model_request_duration_seconds_sum{{backend="gemini"}} {METRICS["model_duration_sum"]:.4f}',
            f'agent_gateway_model_request_duration_seconds_count{{backend="gemini"}} {METRICS["model_requests"]}',
            "# HELP agent_gateway_model_tokens_total Total model tokens processed.",
            "# TYPE agent_gateway_model_tokens_total counter",
            f'agent_gateway_model_tokens_total{{backend="gemini",direction="input"}} {METRICS["tokens_input"]}',
            f'agent_gateway_model_tokens_total{{backend="gemini",direction="output"}} {METRICS["tokens_output"]}',
            "# HELP agent_gateway_actors_tracked Number of actors addressed through the gateway.",
            "# TYPE agent_gateway_actors_tracked gauge",
            f"agent_gateway_actors_tracked {tracked}",
        ]
    return "\n".join(lines) + "\n"


def _forward_gemini(
    payload: dict[str, Any], api_client_header: str = ""
) -> dict[str, Any]:
    """Forward a GenerateContent request using GKE Workload Identity credentials."""
    if not PROJECT_ID:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLOUD_PROJECT is not configured on gateway",
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
    if api_client_header:
        headers["x-goog-api-client"] = api_client_header
    data: dict[str, Any] = {}
    for attempt in range(2):
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=55) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                break
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 502, 503, 504) and attempt == 0:
                time.sleep(1.5)
                continue
            raise HTTPException(status_code=exc.code, detail=err_body) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == 0:
                time.sleep(1.0)
                continue
            raise HTTPException(
                status_code=502, detail=f"Upstream Gemini request failed: {exc}"
            ) from exc

    dur = time.monotonic() - t0
    usage = data.get("usageMetadata", {})
    with METRICS_LOCK:
        METRICS["model_requests"] += 1
        METRICS["model_duration_sum"] += dur
        for bucket in BUCKETS:
            if dur <= bucket:
                METRICS["model_buckets"][bucket] += 1
        METRICS["tokens_input"] += int(usage.get("promptTokenCount", 0))
        METRICS["tokens_output"] += int(usage.get("candidatesTokenCount", 0))
    return data


@model_app.get("/readyz")
@admin_app.get("/readyz")
def readyz() -> PlainTextResponse:
    return PlainTextResponse("ok\n")


@admin_app.get("/identity")
def identity() -> JSONResponse:
    """Service identity endpoint verified by local port-forward helpers."""
    return JSONResponse(
        {
            "service": "agent-substrate-gateway",
            "atespace": ATESPACE,
            "router": ROUTER_HTTPS,
        }
    )


@model_app.get("/metrics")
@admin_app.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(
        render_prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


MAX_MODEL_BODY_BYTES = 4 * 1024 * 1024


def parse_model_request_body(raw_body: bytes) -> dict[str, Any]:
    """Validate and parse an inbound JSON object body for model proxy calls."""
    if len(raw_body) > MAX_MODEL_BODY_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Model request payload exceeds {MAX_MODEL_BODY_BYTES} bytes",
        )
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Invalid JSON payload: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=400, detail="Model request payload must be a JSON object"
        )
    return payload


@model_app.post(
    "/v1beta1/projects/{sandbox_project}/locations/{sandbox_location}/publishers/google/models/{model_action:path}"
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
    payload = parse_model_request_body(await request.body())
    api_client = request.headers.get("x-goog-api-client", "")
    data = await asyncio.to_thread(_forward_gemini, payload, api_client)
    return JSONResponse(data, headers={"Connection": "close"})


def _json_or_text_response(status_code: int, raw_text: str) -> Any:
    try:
        return JSONResponse(json.loads(raw_text), status_code=status_code)
    except json.JSONDecodeError:
        return PlainTextResponse(raw_text, status_code=status_code)


@admin_app.post("/chat/{actor}", dependencies=[Depends(verify_admin_token)])
def chat_actor(actor: str, body: dict[str, Any]) -> Any:
    status_code, raw_text = _call_router(
        actor=actor, path="/chat", method="POST", payload=body, timeout=60.0
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
def actor_execute(actor: str, body: dict[str, Any]) -> Any:
    status_code, raw_text = _call_router(
        actor=actor, path="/execute", method="POST", payload=body, timeout=30.0
    )
    return _json_or_text_response(status_code, raw_text)


@admin_app.get("/actors/{actor}/fetch", dependencies=[Depends(verify_admin_token)])
def actor_fetch(actor: str, url: str = Query(...)) -> Any:
    encoded = urllib.parse.urlencode({"url": url})
    status_code, raw_text = _call_router(
        actor=actor, path=f"/fetch?{encoded}", method="GET", timeout=20.0
    )
    return _json_or_text_response(status_code, raw_text)


def main() -> None:
    threading.Thread(
        target=uvicorn.run,
        kwargs={
            "app": model_app,
            "host": "0.0.0.0",
            "port": 8080,
            "log_level": "warning",
        },
        daemon=True,
    ).start()
    uvicorn.run(admin_app, host=ADMIN_BIND_HOST, port=8081, log_level="warning")


if __name__ == "__main__":
    main()
