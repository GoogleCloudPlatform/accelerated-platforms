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

"""Startup patch for TensorRT-LLM v1.4.0rc2 Prometheus queue/load gauges.

Why this override exists (ACP R-3.4):
In NVIDIA/TensorRT-LLM v1.4.0rc2 (`tensorrt_llm/serve/openai_server.py` lines
999-1024, 1924-1949, 1998-2014 and `tensorrt_llm/_torch/pyexecutor/py_executor.py`
lines 2352, 2539-2560):
1. `trtllm_num_requests_running` and `trtllm_num_requests_waiting` are not
   initialized to `0` at server startup, causing Google Cloud Managed Service
   for Prometheus / Custom Metrics Adapter queries to fail before the first
   completed request.
2. `OpenAIServer._extract_metrics` only sets `_iteration_stats_wakeup_event`
   once `res.finished` is True, leaving Prometheus gauges stale throughout
   long reasoning/decode generations.
3. `PyExecutor` records `numActiveRequests` prior to retiring the last finished
   request and then blocks idle without emitting a `0` stat, leaving
   `trtllm_num_requests_running >= 1` indefinitely while idle and causing
   runaway HPA scale-out.

When to remove:
Delete this file (and remove `PYTHONPATH=/etc/trtllm` from the TensorRT-LLM
Deployment manifests) once upstream `NVIDIA/TensorRT-LLM` initializes both
gauges on startup, drains iteration stats periodically while requests are in
flight, and resets `trtllm_num_requests_running` to `0` when the batch goes
idle.
"""

from __future__ import annotations

import asyncio
import functools
import importlib.abc
import importlib.machinery
import os
import sys
import types
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

_TARGET_MODULE = "tensorrt_llm.serve.openai_server"
_DISABLE_ENV_VAR = "TRTLLM_DISABLE_METRICS_PATCH"
_POLL_INTERVAL_ENV_VAR = "TRTLLM_METRICS_POLL_INTERVAL_SECONDS"
_DEFAULT_POLL_INTERVAL_SECONDS = 1.0
_INFERENCE_POST_PATHS = frozenset(
    {
        "/v1/chat/completions",
        "/v1/completions",
        "/v1/responses",
        "/v1/messages",
        "/generate",
    }
)


@dataclass
class _InFlightState:
    """Tracks active HTTP inference requests on an OpenAIServer instance."""

    in_flight: int = 0
    arrival_seq: int = 0


ASGIApp = Callable[
    [
        MutableMapping[str, Any],
        Callable[[], Awaitable[MutableMapping[str, Any]]],
        Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]


class _InFlightMetricsMiddleware:
    """Pure ASGI middleware that wakes the stats collector on load changes."""

    def __init__(
        self,
        app: ASGIApp,
        state: _InFlightState,
        wakeup_event: asyncio.Event,
    ) -> None:
        self.app = app
        self._state = state
        self._wakeup_event = wakeup_event

    async def __call__(
        self,
        scope: MutableMapping[str, Any],
        receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
    ) -> None:
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return

        raw_path = str(scope.get("path", ""))
        normalized_path = raw_path.rstrip("/") or "/"
        if normalized_path not in _INFERENCE_POST_PATHS:
            await self.app(scope, receive, send)
            return

        self._state.in_flight += 1
        self._state.arrival_seq += 1
        self._wakeup_event.set()
        try:
            await self.app(scope, receive, send)
        finally:
            self._state.in_flight = max(0, self._state.in_flight - 1)
            self._wakeup_event.set()


def _zero_load_gauges(metrics_collector: Any) -> None:
    """Sets running and waiting request gauges to 0 using MetricsCollector."""
    log_gauge = getattr(metrics_collector, "_log_gauge", None)
    running_gauge = getattr(metrics_collector, "num_requests_running", None)
    waiting_gauge = getattr(metrics_collector, "num_requests_waiting", None)
    if callable(log_gauge) and running_gauge is not None and waiting_gauge is not None:
        log_gauge(running_gauge, 0)
        log_gauge(waiting_gauge, 0)


def _get_poll_interval_seconds() -> float:
    """Returns the active-request iteration stats poll interval in seconds."""
    raw_value = os.environ.get(_POLL_INTERVAL_ENV_VAR)
    if not raw_value:
        return _DEFAULT_POLL_INTERVAL_SECONDS
    try:
        parsed = float(raw_value)
    except ValueError:
        return _DEFAULT_POLL_INTERVAL_SECONDS
    return parsed if parsed > 0 else _DEFAULT_POLL_INTERVAL_SECONDS


def apply_openai_server_metrics_patch(module: types.ModuleType) -> bool:
    """Patches `OpenAIServer` in-place to keep queue/running gauges accurate.

    Args:
        module: The imported `tensorrt_llm.serve.openai_server` module.

    Returns:
        True if the patch was applied (or already present), False if skipped
        because the upstream class attributes no longer match expectations.
    """
    server_cls = getattr(module, "OpenAIServer", None)
    if server_cls is None:
        print(
            "[trtllm-metrics-patch] Skipping patch: OpenAIServer not found.",
            file=sys.stderr,
        )
        return False

    if getattr(server_cls, "_acp_metrics_patch_applied", False):
        return True

    orig_init = getattr(server_cls, "__init__", None)
    orig_loop = getattr(server_cls, "_iteration_stats_collector_loop", None)
    if not callable(orig_init) or not callable(orig_loop):
        print(
            "[trtllm-metrics-patch] Skipping patch: expected OpenAIServer "
            "methods (__init__, _iteration_stats_collector_loop) are missing.",
            file=sys.stderr,
        )
        return False

    poll_interval_seconds = _get_poll_interval_seconds()

    @functools.wraps(orig_init)
    def _patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        orig_init(self, *args, **kwargs)
        wakeup_event = getattr(self, "_iteration_stats_wakeup_event", None)
        app = getattr(self, "app", None)
        if not isinstance(wakeup_event, asyncio.Event) or app is None:
            print(
                "[trtllm-metrics-patch] Skipping instance wiring: missing "
                "_iteration_stats_wakeup_event or FastAPI app.",
                file=sys.stderr,
            )
            return

        state = _InFlightState()
        self._acp_inflight_state = state
        if getattr(self, "metrics_collector", None) is not None:
            _zero_load_gauges(self.metrics_collector)
        app.add_middleware(
            _InFlightMetricsMiddleware,
            state=state,
            wakeup_event=wakeup_event,
        )

    @functools.wraps(orig_loop)
    async def _patched_collector_loop(self: Any) -> None:
        state: _InFlightState | None = getattr(self, "_acp_inflight_state", None)
        metrics_collector = getattr(self, "metrics_collector", None)
        if state is None or metrics_collector is None:
            await orig_loop(self)
            return

        pending_idle_recheck = True
        while True:
            if state.in_flight > 0 or pending_idle_recheck:
                try:
                    await asyncio.wait_for(
                        self._iteration_stats_wakeup_event.wait(),
                        timeout=poll_interval_seconds,
                    )
                except TimeoutError:
                    pass
            else:
                await self._iteration_stats_wakeup_event.wait()

            self._iteration_stats_wakeup_event.clear()
            in_flight_before = state.in_flight
            seq_before = state.arrival_seq
            saw_nonzero_load = False

            try:
                async for llm_stat in self.generator.get_stats_async(timeout=0.5):
                    metrics_collector.log_iteration_stats(llm_stat)
                    if isinstance(llm_stat, dict) and (
                        llm_stat.get("numActiveRequests", 0) > 0
                        or llm_stat.get("numQueuedRequests", 0) > 0
                    ):
                        saw_nonzero_load = True
                    stats_buf = getattr(self, "_iteration_stats_buffer", None)
                    if stats_buf is not None:
                        stats_buf.append(llm_stat)

                if (
                    in_flight_before == 0
                    and state.in_flight == 0
                    and state.arrival_seq == seq_before
                ):
                    _zero_load_gauges(metrics_collector)
                    pending_idle_recheck = saw_nonzero_load
                else:
                    pending_idle_recheck = True
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger = getattr(module, "logger", None)
                if logger is not None:
                    logger.error(
                        f"Error collecting iteration stats: {exc}",
                        exc_info=True,
                    )
                await asyncio.sleep(0.1)

    server_cls.__init__ = _patched_init
    server_cls._iteration_stats_collector_loop = _patched_collector_loop
    server_cls._acp_metrics_patch_applied = True
    return True


class _OpenAIServerImportFinder(importlib.abc.MetaPathFinder):
    """Post-import hook that patches `tensorrt_llm.serve.openai_server`."""

    def find_spec(
        self,
        fullname: str,
        path: Any,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del target
        if fullname != _TARGET_MODULE:
            return None

        if self in sys.meta_path:
            sys.meta_path.remove(self)

        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None or spec.loader is None:
            return spec

        orig_exec_module = spec.loader.exec_module

        def _exec_and_patch(mod: types.ModuleType) -> None:
            orig_exec_module(mod)
            apply_openai_server_metrics_patch(mod)

        spec.loader.exec_module = _exec_and_patch  # type: ignore[method-assign]
        return spec


def install_import_hook() -> bool:
    """Installs the lazy import hook unless explicitly disabled via env var."""
    if os.environ.get(_DISABLE_ENV_VAR) == "1":
        return False

    existing_module = sys.modules.get(_TARGET_MODULE)
    if existing_module is not None:
        return apply_openai_server_metrics_patch(existing_module)

    for finder in sys.meta_path:
        if isinstance(finder, _OpenAIServerImportFinder):
            return True

    sys.meta_path.insert(0, _OpenAIServerImportFinder())
    return True


install_import_hook()
