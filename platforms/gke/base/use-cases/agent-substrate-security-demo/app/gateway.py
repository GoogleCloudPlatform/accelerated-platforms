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

"""Split-plane Gateway service for Google ADK actors on Agent Substrate.

Exposes two separate HTTP listeners so untrusted sandboxes hold zero Google
Cloud credentials and cannot pivot laterally to sibling actors:
- :8080 (Service port 80, actor-facing): authenticates via GKE Workload Identity
  Application Default Credentials (`google.auth.default`) and proxies Google ADK
  Gemini model calls to Google Cloud's Gemini platform (formerly Vertex AI),
  plus GET /readyz and GET /metrics.
- :8081 (Service port 8081, operator-facing): POST /chat/{actor},
  GET /actors/{actor}/state, GET /readyz, GET /metrics.
"""

import asyncio
import json
import os
import re
import threading
import time
import urllib.request
from typing import Any

import google.auth
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from google.auth.transport.requests import Request as GoogleAuthRequest

model_app = FastAPI()
admin_app = FastAPI()

ATESPACE = os.environ.get("ATESPACE", "security-demo")
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
ROUTER_HTTP = os.environ.get(
    "ROUTER_HTTP", "http://atenet-router.ate-system.svc.cluster.local:80"
)
SYS_PROMPT = (
    "You are a concise, friendly assistant running as an Agent Substrate actor "
    "built with Google ADK. Answer in at most three sentences."
)
ACTOR_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
MODEL_ACTION_RE = re.compile(r"^[a-zA-Z0-9._-]+:generateContent$")
BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)

CRED_LOCK = threading.Lock()
_CREDENTIALS: Any = None

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


def _validate_actor(actor: str) -> str:
    if not ACTOR_RE.fullmatch(actor):
        raise HTTPException(status_code=400, detail="Invalid actor name")
    return actor


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


def _render_metrics() -> PlainTextResponse:
    """Format metrics in Prometheus text exposition format (0.0.4) for GMP.

    `# HELP` (human-readable description) and `# TYPE` (counter/histogram/gauge)
    are required metadata headers scraped every 15s by Google Cloud Managed
    Service for Prometheus (`PodMonitoring/gateway` in `observability.yaml.tmpl`).
    """
    with METRICS_LOCK:
        tracked = len(METRICS["actors_seen"])
        bucket_lines = [
            f'workshop_model_request_duration_seconds_bucket{{backend="gemini",le="{b}"}} {METRICS["model_buckets"][b]}'
            for b in BUCKETS
        ]
        bucket_lines.append(
            f'workshop_model_request_duration_seconds_bucket{{backend="gemini",le="+Inf"}} {METRICS["model_requests"]}'
        )
        lines = [
            "# HELP workshop_chat_turns_total Total chat turns processed by the gateway.",
            "# TYPE workshop_chat_turns_total counter",
            f'workshop_chat_turns_total{{outcome="ok"}} {METRICS["chat_turns_ok"]}',
            f'workshop_chat_turns_total{{outcome="error"}} {METRICS["chat_turns_error"]}',
            "# HELP workshop_model_request_duration_seconds Gemini model request latency.",
            "# TYPE workshop_model_request_duration_seconds histogram",
            *bucket_lines,
            f'workshop_model_request_duration_seconds_sum{{backend="gemini"}} {METRICS["model_duration_sum"]:.4f}',
            f'workshop_model_request_duration_seconds_count{{backend="gemini"}} {METRICS["model_requests"]}',
            "# HELP workshop_model_tokens_total Total model tokens processed.",
            "# TYPE workshop_model_tokens_total counter",
            f'workshop_model_tokens_total{{backend="gemini",direction="input"}} {METRICS["tokens_input"]}',
            f'workshop_model_tokens_total{{backend="gemini",direction="output"}} {METRICS["tokens_output"]}',
            "# HELP workshop_actors_tracked Number of actors addressed through the gateway.",
            "# TYPE workshop_actors_tracked gauge",
            f"workshop_actors_tracked {tracked}",
        ]
    return PlainTextResponse(
        "\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


def _forward_gemini(
    payload: dict[str, Any], api_client_header: str = ""
) -> dict[str, Any]:
    """Forward a GenerateContent request to Gemini platform using Workload Identity."""
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
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
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


@model_app.get("/metrics")
@admin_app.get("/metrics")
def metrics() -> PlainTextResponse:
    return _render_metrics()


@model_app.post(
    "/v1beta1/projects/{sandbox_project}/locations/{sandbox_location}/publishers/google/models/{model_action:path}"
)
async def proxy_adk_generate_content(
    sandbox_project: str,
    sandbox_location: str,
    model_action: str,
    request: Request,
) -> JSONResponse:
    """Zero-secret proxy endpoint invoked by Google ADK (`Gemini(base_url=...)`).

    Replaces the untrusted sandbox placeholder project/token with the Gateway's
    Workload Identity token and pinned project/model, and returns `Connection: close`
    so gVisor actors never retain idle sockets across memory snapshots.
    """
    del sandbox_project, sandbox_location
    if not MODEL_ACTION_RE.fullmatch(model_action):
        raise HTTPException(status_code=400, detail="Unsupported model action")
    payload = await request.json()
    api_client = request.headers.get("x-goog-api-client", "")
    data = await asyncio.to_thread(_forward_gemini, payload, api_client)
    return JSONResponse(data, headers={"Connection": "close"})


@model_app.post("/v1/model")
async def generate(body: dict[str, Any]) -> JSONResponse:
    msgs = body.get("messages", [])
    contents = []
    for msg in msgs:
        role = "model" if msg.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
    payload = {
        "systemInstruction": {"role": "user", "parts": [{"text": SYS_PROMPT}]},
        "contents": contents,
    }
    data = await asyncio.to_thread(_forward_gemini, payload)
    reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    return JSONResponse(
        {"reply": reply, "backend": "gemini"},
        headers={"Connection": "close"},
    )


@admin_app.post("/chat/{actor}")
def chat_actor(actor: str, body: dict[str, Any]) -> JSONResponse:
    actor = _validate_actor(actor)
    with METRICS_LOCK:
        METRICS["actors_seen"].add(actor)
    raw = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{ROUTER_HTTP}/chat",
        data=raw,
        headers={
            "ate-target-actor": f"{ATESPACE}/{actor}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            with METRICS_LOCK:
                METRICS["chat_turns_ok"] += 1
            return JSONResponse(
                json.loads(resp.read().decode("utf-8")), status_code=resp.status
            )
    except Exception:
        with METRICS_LOCK:
            METRICS["chat_turns_error"] += 1
        raise


@admin_app.get("/actors/{actor}/state")
def actor_state(actor: str) -> JSONResponse:
    actor = _validate_actor(actor)
    with METRICS_LOCK:
        METRICS["actors_seen"].add(actor)
    req = urllib.request.Request(
        f"{ROUTER_HTTP}/state",
        headers={"ate-target-actor": f"{ATESPACE}/{actor}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return JSONResponse(
            json.loads(resp.read().decode("utf-8")), status_code=resp.status
        )


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
    uvicorn.run(admin_app, host="0.0.0.0", port=8081, log_level="warning")


if __name__ == "__main__":
    main()
