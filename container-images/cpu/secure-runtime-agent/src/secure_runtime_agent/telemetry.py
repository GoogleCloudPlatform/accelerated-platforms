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

"""Thread-safe live terminal telemetry bus for real-time SSE streaming."""

import asyncio
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any


class TerminalBus:
    """Publishes real-time control-plane, mTLS, and K8s events to SSE clients."""

    def __init__(self, max_events: int = 300) -> None:
        self._lock = threading.Lock()
        self._seq = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=max(max_events, 50))
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = []

    def emit(
        self,
        kind: str,
        text: str,
        *,
        step: str = "",
        duration_ms: float | None = None,
        detail: str = "",
    ) -> dict[str, Any]:
        """Records an execution line and fans out to active SSE streams."""
        now_iso = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + "Z"
        with self._lock:
            self._seq += 1
            event: dict[str, Any] = {
                "seq": self._seq,
                "ts": now_iso,
                "kind": kind,
                "step": step,
                "text": text,
            }
            if duration_ms is not None:
                event["duration_ms"] = round(duration_ms, 2)
            if detail:
                event["detail"] = detail[:2000]
            self._events.append(event)
            subs = list(self._subscribers)

        for loop, queue in subs:
            try:
                loop.call_soon_threadsafe(self._push_nonblocking, queue, event)
            except RuntimeError:
                pass
        return event

    @staticmethod
    def _push_nonblocking(queue: asyncio.Queue, event: dict[str, Any]) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(event)

    def recent(self, limit: int = 60) -> list[dict[str, Any]]:
        """Returns up to `limit` most recent terminal events."""
        with self._lock:
            items = list(self._events)
        return items[-max(limit, 1) :]

    def subscribe(self) -> tuple[list[dict[str, Any]], asyncio.Queue]:
        """Subscribes the caller's asyncio loop to live terminal events."""
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=150)
        with self._lock:
            backlog = list(self._events)[-40:]
            self._subscribers.append((loop, queue))
        return backlog, queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Removes a disconnected SSE subscriber queue."""
        with self._lock:
            self._subscribers = [
                (lp, q) for lp, q in self._subscribers if q is not queue
            ]


TERMINAL_BUS = TerminalBus()
