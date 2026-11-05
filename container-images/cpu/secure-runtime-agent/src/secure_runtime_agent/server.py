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

"""Unified FastAPI server hosting Mission Control UI, /api/*, SSE, and ADK Web."""

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from .agent import (
    GEMINI_MODEL,
    GITHUB_REPO,
    audit_and_reset_actor_to_golden,
    inspect_sandbox_boundary,
    root_agent,
    run_python_in_actor,
    triage_github_issue_in_sandbox,
)
from .k8s_client import InClusterK8sClient
from .substrate_client import SubstrateClient
from .telemetry import TERMINAL_BUS

_STATIC_DIR = Path(__file__).resolve().parent / "static"
_AGENTS_DIR = str(Path(__file__).resolve().parent.parent)
_k8s = InClusterK8sClient()
_substrate = SubstrateClient()


class Part1Request(BaseModel):
    actor_name: str = Field(default="triage-actor-19", min_length=1, max_length=63)


class Part2Request(BaseModel):
    custom_note: str = Field(default="tikhonov_reg_1e-6", min_length=1, max_length=120)


class Part3Request(BaseModel):
    issue_number: int = Field(default=42, ge=1, le=999999)
    follow_instructions: bool = True
    actor_name: str = Field(default="triage-actor-42", min_length=1, max_length=63)


class Part4Request(BaseModel):
    tainted_actor: str = Field(default="triage-actor-42", min_length=1, max_length=63)


class RunCodeRequest(BaseModel):
    actor_name: str = Field(default="triage-actor-19", min_length=1, max_length=63)
    code: str = Field(..., min_length=1, max_length=32768)
    suspend_after: bool = True


class AskAgentRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8192)


api_router = APIRouter(prefix="/api")


@api_router.get("/cluster")
async def get_cluster_status() -> dict[str, Any]:
    """Queries live ate-system pods, actors, and Golden Snapshot in parallel."""
    t0 = time.monotonic()
    pods_task = asyncio.to_thread(_k8s.list_ate_system_pods)
    actors_task = asyncio.to_thread(_substrate.list_actors)
    golden_task = asyncio.to_thread(_substrate.get_golden_snapshot_tag)
    pods, actors, golden_tag = await asyncio.gather(pods_task, actors_task, golden_task)
    query_ms = round((time.monotonic() - t0) * 1000, 1)
    cluster_name = os.environ.get("GKE_CLUSTER_NAME", "gke-agent-substrate")
    substrate_ver = os.environ.get("SUBSTRATE_VERSION", "v1.0.0-rc.3")
    TERMINAL_BUS.emit(
        "k8s",
        f"Cluster refresh: {len(pods)} ate-system pods, {len(actors)} actors, "
        f"golden_tag={golden_tag or 'pending'} ({query_ms} ms)",
        duration_ms=query_ms,
    )
    return {
        "cluster": cluster_name,
        "substrate_version": substrate_ver,
        "gemini_model": GEMINI_MODEL,
        "github_repo": GITHUB_REPO,
        "atespace": _substrate.atespace,
        "golden_tag": golden_tag,
        "ate_system_pods": pods,
        "actors": actors,
        "query_ms": query_ms,
    }


@api_router.get("/logs")
async def get_pod_logs(
    source: str = Query(default="intent-extproc"),
    lines: int = Query(default=80, ge=10, le=250),
) -> dict[str, Any]:
    """Fetches real Kubernetes container logs from ate-system pods."""
    try:
        return await asyncio.to_thread(_k8s.tail_ate_system_logs, source, lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api_router.get("/events")
async def stream_terminal_events() -> StreamingResponse:
    """Streams real-time control-plane, mTLS, and K8s execution events via SSE."""

    async def event_generator() -> AsyncIterator[str]:
        backlog, queue = TERMINAL_BUS.subscribe()
        try:
            for item in backlog:
                yield f"data: {json.dumps(item)}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(ev)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            TERMINAL_BUS.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.post("/part1")
async def run_part1(req: Part1Request) -> dict[str, Any]:
    t0 = time.monotonic()
    raw = await asyncio.to_thread(inspect_sandbox_boundary, req.actor_name)
    out = json.loads(raw)
    out["_exec_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return out


def _run_golden_actor_race_leg(custom_note: str) -> dict[str, Any]:
    actor_name = f"race-actor-{int(time.time() * 1000) % 1000000}"
    ensure_res = _substrate.ensure_actor(actor_name)
    ready = _substrate.call_actor(actor_name, "GET", "/readyz")
    warm_ms = float(ready["router_roundtrip_ms"])
    TERMINAL_BUS.emit(
        "verdict",
        f"[#2] Golden Snapshot Actor {actor_name} Ready in {warm_ms} ms "
        f"(saved {ready.get('warm_import_ms')} ms scientific import)",
        step="2",
        duration_ms=warm_ms,
    )

    state_obj = {
        "issue": 19,
        "solver": custom_note,
        "status": "verified",
        "saved_at": round(time.time(), 2),
    }
    run_python_in_actor(
        code=f"STATE = {json.dumps(state_obj)}",
        actor_name=actor_name,
        suspend_after=True,
    )
    resumed = json.loads(
        run_python_in_actor(
            code="import json; print(json.dumps(STATE))",
            actor_name=actor_name,
            suspend_after=True,
        )
    )["execution"]
    resume_ms = float(resumed["router_roundtrip_ms"])
    TERMINAL_BUS.emit(
        "verdict",
        f"[#2] Stateful Pause -> Resume restored STATE in {resume_ms} ms",
        step="2",
        duration_ms=resume_ms,
    )
    return {
        "actor_name": actor_name,
        "ensure_ms": ensure_res["ensure_ms"],
        "golden_snapshot_wake_ms": warm_ms,
        "stateful_pause_resume_ms": resume_ms,
        "warm_import_ms_saved": ready.get("warm_import_ms"),
        "restored_state": json.loads(resumed["stdout"].strip()),
    }


@api_router.post("/part2")
async def run_part2(req: Part2Request) -> dict[str, Any]:
    """Races a cold gVisor Pod in demo-bench concurrently against Golden Snapshot."""
    runner_image = os.environ.get("RUNNER_IMAGE", "")
    t0 = time.monotonic()
    TERMINAL_BUS.emit(
        "verdict",
        "[#2] Starting parallel race: Cold K8s gVisor Pod vs Golden Snapshot Actor",
        step="2",
    )
    cold_res, actor_res = await asyncio.gather(
        asyncio.to_thread(_k8s.measure_cold_gvisor_pod_ms, runner_image),
        asyncio.to_thread(_run_golden_actor_race_leg, req.custom_note),
    )
    cold_ms = float(cold_res["cold_ms"])
    wake_ms = float(actor_res["golden_snapshot_wake_ms"])
    resume_ms = float(actor_res["stateful_pause_resume_ms"])
    return {
        **actor_res,
        "cold_gvisor_pod": f"{cold_res['pod_ref']} (runtimeClassName: gvisor)",
        "cold_gvisor_pod_ms": cold_ms,
        "speedup_wake": round(cold_ms / max(wake_ms, 0.1), 1),
        "speedup_resume": round(cold_ms / max(resume_ms, 0.1), 1),
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }


@api_router.post("/part3")
async def run_part3(req: Part3Request) -> dict[str, Any]:
    t0 = time.monotonic()
    raw = await asyncio.to_thread(
        triage_github_issue_in_sandbox,
        req.issue_number,
        req.follow_instructions,
        req.actor_name,
    )
    out = json.loads(raw)
    out["_exec_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return out


@api_router.post("/part4")
async def run_part4(req: Part4Request) -> dict[str, Any]:
    t0 = time.monotonic()
    clean_name = f"triage-actor-clean-{int(time.time())}"

    def _exec() -> dict[str, Any]:
        res = json.loads(audit_and_reset_actor_to_golden(req.tainted_actor, clean_name))
        _substrate.suspend_actor(clean_name)
        return res

    out = await asyncio.to_thread(_exec)
    out["_exec_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return out


@api_router.post("/run_code")
async def run_custom_code(req: RunCodeRequest) -> dict[str, Any]:
    t0 = time.monotonic()
    TERMINAL_BUS.emit(
        "cmd",
        f"[#1] Dispatching custom Python snippet ({len(req.code)} chars) to "
        f"{req.actor_name}",
        step="1",
    )
    raw = await asyncio.to_thread(
        run_python_in_actor,
        req.code,
        "interactive_scientific_snippet",
        req.actor_name,
        req.suspend_after,
    )
    out = json.loads(raw)
    out["_exec_ms"] = round((time.monotonic() - t0) * 1000, 1)
    return out


@api_router.post("/ask_agent")
async def ask_agent(req: AskAgentRequest) -> dict[str, Any]:
    if root_agent is None:
        raise HTTPException(status_code=503, detail="ADK root_agent unavailable")
    t0 = time.monotonic()
    TERMINAL_BUS.emit(
        "cmd", f"[ADK {GEMINI_MODEL}] Prompt: {req.prompt[:140]}", step="agent"
    )
    runner = InMemoryRunner(agent=root_agent, app_name="mission_control")
    session = await runner.session_service.create_session(
        app_name="mission_control", user_id="demo_user"
    )
    msg = types.Content(role="user", parts=[types.Part.from_text(text=req.prompt)])
    tool_calls: list[dict[str, Any]] = []
    texts: list[str] = []
    async for ev in runner.run_async(
        user_id="demo_user", session_id=session.id, new_message=msg
    ):
        if ev.content and ev.content.parts:
            for part in ev.content.parts:
                if part.function_call:
                    tc = {
                        "name": part.function_call.name,
                        "args": dict(part.function_call.args or {}),
                    }
                    tool_calls.append(tc)
                    TERMINAL_BUS.emit(
                        "cmd",
                        f"[ADK Tool Call] {tc['name']}({json.dumps(tc['args'])})",
                        step="agent",
                    )
                if part.text:
                    texts.append(part.text.strip())
    final_session = await runner.session_service.get_session(
        app_name="mission_control", user_id="demo_user", session_id=session.id
    )
    total_ms = round((time.monotonic() - t0) * 1000, 1)
    TERMINAL_BUS.emit(
        "verdict",
        f"[ADK {GEMINI_MODEL}] Turn completed in {total_ms} ms "
        f"({len(tool_calls)} tool call(s))",
        step="agent",
        duration_ms=total_ms,
    )
    return {
        "model": root_agent.model,
        "prompt": req.prompt,
        "tool_calls": tool_calls,
        "response": "\n\n".join(t for t in texts if t),
        "last_intent_classification": (final_session.state or {}).get(
            "last_intent_classification"
        ),
        "total_ms": total_ms,
    }


def create_app() -> FastAPI:
    raw_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").strip()
    allow_origins = (
        [o.strip() for o in raw_origins.split(",") if o.strip()]
        if raw_origins
        else None
    )
    otel_enabled = os.environ.get("OTEL_TO_CLOUD", "1") == "1"
    app = get_fast_api_app(
        agents_dir=_AGENTS_DIR,
        web=True,
        otel_to_cloud=otel_enabled,
        allow_origins=allow_origins,
    )
    app.router.routes = [
        r for r in app.router.routes if getattr(r, "path", None) != "/"
    ]

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def mission_control_index() -> FileResponse:
        return FileResponse(
            _STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-store"},
        )

    app.include_router(api_router)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    return app


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
