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

"""Stateful Gemini chat actor (gemini-agent-v1) running inside gVisor.

Demonstrates Act 2 (instant memory snapshot restore and forensic cloning via
BOOT_ID frozen in the Golden Tag / clean-checkpoint-tag) and Act 4 (dual-layer
in-memory HISTORY + /data disk persistence rewound via `kubectl ate revert`).
"""

import datetime
import json
import os
import socket
import sys
import tempfile
import threading
import urllib.request
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse

app = FastAPI()
BOOT_ID = os.urandom(4).hex()
STARTED_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()
MODEL_URL = os.environ.get(
    "MODEL_URL", "http://gateway.workshop.svc.cluster.local/v1/model"
)
DATA_DIR = "/data"
HIST_FILE = os.path.join(DATA_DIR, "history.json")
COUNT_FILE = os.path.join(DATA_DIR, "count")

STATE_LOCK = threading.Lock()
MEM_COUNT = 0
HISTORY: list[dict[str, str]] = []


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


def _load() -> None:
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
        print(f"warning: failed to persist state in {DATA_DIR}: {exc}", file=sys.stderr)


_load()


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
            "bootID": BOOT_ID,
            "startedAt": STARTED_AT,
            "memCount": mem_count,
            "diskCount": disk_count,
            "turns": turns,
            "hostname": socket.gethostname(),
        }
    )


@app.post("/chat")
def chat(body: dict[str, Any]) -> JSONResponse:
    global MEM_COUNT
    msg = str(body.get("message", ""))
    with STATE_LOCK:
        HISTORY.append({"role": "user", "content": msg})
        recent = list(HISTORY[-20:])
    req = urllib.request.Request(
        MODEL_URL,
        data=json.dumps({"messages": recent}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    reply = str(res.get("reply", ""))
    with STATE_LOCK:
        HISTORY.append({"role": "assistant", "content": reply})
        MEM_COUNT += 1
        _save(MEM_COUNT)
        turns = sum(1 for item in HISTORY if item.get("role") == "user")
    return JSONResponse(
        {
            "reply": reply,
            "turn": turns,
            "backend": res.get("backend", "gemini"),
            "bootID": BOOT_ID,
        }
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
