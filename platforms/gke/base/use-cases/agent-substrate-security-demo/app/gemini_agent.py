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

"""Stateful Google ADK Gemini actor (gemini-agent-v1) running inside gVisor.

Built with Google Agent Development Kit (`google-adk`) and Gemini models
(`gemini-3.8-flash`) with zero Google Cloud credentials inside the sandbox:
- Outbound ADK model calls target the cluster-local split-plane Gateway
  (`GATEWAY_URL`) using a placeholder token (`sandbox-zero-secret`).
- Demonstrates Act 2 (instant memory snapshot restore and forensic cloning via
  BOOT_ID + pre-warmed Google ADK `InMemoryRunner` frozen in the Golden Tag /
  `clean-checkpoint-tag`) and Act 4 (dual-layer ADK session memory + `/data`
  disk persistence rewound in milliseconds via `kubectl ate revert`).
"""

import asyncio
import datetime
import json
import os
import socket
import sys
import tempfile
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import google.oauth2.credentials
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from google.adk.agents import Agent
from google.adk.events import Event
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

APP_NAME = "security-demo"
USER_ID = "operator"
SESSION_ID = "main"
AGENT_NAME = "security_demo_agent"

BOOT_ID = os.urandom(4).hex()
STARTED_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://gateway.workshop.svc.cluster.local")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
DATA_DIR = "/data"
HIST_FILE = os.path.join(DATA_DIR, "history.json")
COUNT_FILE = os.path.join(DATA_DIR, "count")

STATE_LOCK = threading.Lock()
CHAT_LOCK = asyncio.Lock()
MEM_COUNT = 0
HISTORY: list[dict[str, str]] = []
_SESSION_READY = False

AGENT = Agent(
    name=AGENT_NAME,
    model=Gemini(
        model=GEMINI_MODEL,
        base_url=GATEWAY_URL,
        api_version="v1beta1",
        client_kwargs={
            "vertexai": True,
            "project": "sandbox-zero-secret",
            "location": "global",
            "credentials": google.oauth2.credentials.Credentials(
                token="sandbox-zero-secret"
            ),
            "http_options": {
                "headers": {"Connection": "close"},
                "timeout": 45000,
            },
        },
    ),
    instruction=(
        "You are a concise, friendly assistant running as an Agent Substrate "
        "actor built with Google ADK. Answer in at most three sentences."
    ),
)
RUNNER = InMemoryRunner(agent=AGENT, app_name=APP_NAME)


def _atomic_write(path: str, content: str) -> None:
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except OSError:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def _load_disk_history() -> None:
    global HISTORY
    try:
        if os.path.exists(HIST_FILE):
            with open(HIST_FILE, "r", encoding="utf-8") as handle:
                HISTORY = json.load(handle)
    except (OSError, ValueError) as exc:
        print(f"warning: failed to load {HIST_FILE}: {exc}", file=sys.stderr)


def _save(disk_count: int) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        _atomic_write(HIST_FILE, json.dumps(HISTORY))
        _atomic_write(COUNT_FILE, str(disk_count))
    except OSError as exc:
        print(
            f"warning: failed to persist state in {DATA_DIR}: {exc}",
            file=sys.stderr,
        )


async def _ensure_session() -> None:
    """Create the Google ADK in-memory session and hydrate any `/data` turns."""
    global _SESSION_READY
    if _SESSION_READY:
        return
    _load_disk_history()
    session = await RUNNER.session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )
    for item in HISTORY:
        is_assistant = item.get("role") == "assistant"
        author = AGENT_NAME if is_assistant else "user"
        adk_role = "model" if is_assistant else "user"
        await RUNNER.session_service.append_event(
            session=session,
            event=Event(
                author=author,
                content=types.Content(
                    role=adk_role,
                    parts=[types.Part.from_text(text=str(item.get("content", "")))],
                ),
            ),
        )
    _SESSION_READY = True


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    await _ensure_session()
    yield


app = FastAPI(lifespan=_lifespan)


@app.get("/readyz")
def readyz() -> PlainTextResponse:
    return PlainTextResponse("ok\n")


@app.get("/state")
def state() -> JSONResponse:
    disk_count = 0
    with STATE_LOCK:
        try:
            if os.path.exists(COUNT_FILE):
                with open(COUNT_FILE, "r", encoding="utf-8") as handle:
                    disk_count = int(handle.read().strip() or "0")
        except (OSError, ValueError) as exc:
            print(f"warning: failed to read {COUNT_FILE}: {exc}", file=sys.stderr)
        turns = sum(1 for msg in HISTORY if msg.get("role") == "user")
        mem_count = MEM_COUNT
    return JSONResponse(
        {
            "greeting": "hello from gemini-agent-v1",
            "framework": "google-adk",
            "model": GEMINI_MODEL,
            "bootID": BOOT_ID,
            "startedAt": STARTED_AT,
            "memCount": mem_count,
            "diskCount": disk_count,
            "turns": turns,
            "hostname": socket.gethostname(),
        }
    )


@app.post("/chat")
async def chat(body: dict[str, Any]) -> JSONResponse:
    global MEM_COUNT
    msg = str(body.get("message", ""))
    async with CHAT_LOCK:
        await _ensure_session()
        reply_parts: list[str] = []
        async for event in RUNNER.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=msg)],
            ),
        ):
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        reply_parts.append(part.text)
        reply = "".join(reply_parts).strip()
        with STATE_LOCK:
            HISTORY.append({"role": "user", "content": msg})
            HISTORY.append({"role": "assistant", "content": reply})
            MEM_COUNT += 1
            _save(MEM_COUNT)
            turns = sum(1 for item in HISTORY if item.get("role") == "user")
    return JSONResponse(
        {
            "reply": reply,
            "turn": turns,
            "backend": "google-adk",
            "model": GEMINI_MODEL,
            "bootID": BOOT_ID,
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
