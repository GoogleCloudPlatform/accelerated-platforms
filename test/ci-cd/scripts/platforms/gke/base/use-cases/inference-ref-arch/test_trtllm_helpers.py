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

"""Unit tests for TensorRT-LLM runtime metrics patch and GCS model streamer."""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
import urllib.error
import urllib.request
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, MutableMapping
from pathlib import Path
from typing import Any
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[8]
_ONLINE_GPU_DIR = (
    _REPO_ROOT
    / "platforms/gke/base/use-cases/inference-ref-arch"
    / "kubernetes-manifests/online-inference-gpu"
)
_SITECUSTOMIZE_PATH = _ONLINE_GPU_DIR / "trtllm-runtime/sitecustomize.py"
_GCS_STREAMER_PATH = (
    _ONLINE_GPU_DIR / "components/gke-pod-snapshot/gcs_model_streamer.py"
)


def _load_module(module_name: str, file_path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


class _FakeHTTPResponse(io.BytesIO):
    """Minimal context-manager HTTP response stub for urllib tests."""

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class GcsModelStreamerTest(unittest.TestCase):
    """Tests security, pagination, 0-byte files, and retries in streamer."""

    @classmethod
    def setUpClass(cls) -> None:
        with mock.patch.dict(os.environ, {"TRTLLM_DISABLE_METRICS_PATCH": "1"}):
            cls.streamer = _load_module(
                "test_loaded_gcs_model_streamer", _GCS_STREAMER_PATH
            )

    def test_rejects_path_traversal_and_invalid_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_paths = [
                "",
                "/etc/passwd",
                "../etc/passwd",
                "weights/../../etc/shadow",
                "./config.json",
                "weights//model.safetensors",
                "weights\\model.safetensors",
                "weights/bad\x00name",
            ]
            for bad_path in bad_paths:
                with self.subTest(bad_path=bad_path):
                    with self.assertRaises(ValueError):
                        self.streamer.resolve_safe_destination_path(tmp_dir, bad_path)

    def test_rejects_symlink_escape_outside_dest_root(self) -> None:
        with (
            tempfile.TemporaryDirectory() as dest_root,
            tempfile.TemporaryDirectory() as outside_dir,
        ):
            os.symlink(outside_dir, os.path.join(dest_root, "escape_link"))
            with self.assertRaises(ValueError):
                self.streamer.resolve_safe_destination_path(
                    dest_root, "escape_link/authorized_keys"
                )

    def test_streams_paginated_and_zero_byte_files_with_401_refresh(
        self,
    ) -> None:
        token_calls = 0

        def fake_urlopen(
            req: urllib.request.Request, timeout: float = 30
        ) -> _FakeHTTPResponse:
            del timeout
            nonlocal token_calls
            url = req.full_url
            if "metadata.google.internal" in url:
                token_calls += 1
                return _FakeHTTPResponse(
                    json.dumps(
                        {
                            "access_token": f"tok-{token_calls}",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8")
                )

            auth = req.get_header("Authorization")
            if "alt=media" not in url:
                if "pageToken=p2" not in url:
                    return _FakeHTTPResponse(
                        json.dumps(
                            {
                                "items": [
                                    {
                                        "name": "nvidia/model/",
                                        "size": "0",
                                    },
                                    {
                                        "name": "nvidia/model/__init__.py",
                                        "size": "0",
                                    },
                                ],
                                "nextPageToken": "p2",
                            }
                        ).encode("utf-8")
                    )
                return _FakeHTTPResponse(
                    json.dumps(
                        {
                            "items": [
                                {
                                    "name": "nvidia/model/sub/weights.bin",
                                    "size": "11",
                                }
                            ]
                        }
                    ).encode("utf-8")
                )

            if "__init__.py" in url:
                return _FakeHTTPResponse(b"")

            # Force a single 401 on the first token to verify token invalidation.
            if auth == "Bearer tok-1":
                raise urllib.error.HTTPError(
                    url=url,
                    code=401,
                    msg="Unauthorized",
                    hdrs=None,  # type: ignore[arg-type]
                    fp=None,
                )
            return _FakeHTTPResponse(b"hello-world")

        with tempfile.TemporaryDirectory() as dest_root:
            provider = self.streamer.MetadataTokenProvider(urlopen_fn=fake_urlopen)
            count, total_bytes, _ = self.streamer.stream_model_from_gcs(
                bucket="test-bucket",
                model_gcs_dir="nvidia/model",
                dest_root=dest_root,
                max_workers=2,
                token_provider=provider,
                urlopen_fn=fake_urlopen,
                sleep_fn=lambda _: None,
            )
            self.assertEqual(count, 2)
            self.assertEqual(total_bytes, 11)
            self.assertGreaterEqual(token_calls, 2)

            init_path = Path(dest_root) / "__init__.py"
            weights_path = Path(dest_root) / "sub/weights.bin"
            self.assertTrue(init_path.is_file())
            self.assertEqual(init_path.read_bytes(), b"")
            self.assertEqual(weights_path.read_bytes(), b"hello-world")

    def test_retries_truncated_download_and_fails_fast_on_403(self) -> None:
        attempts = 0

        def truncated_then_ok(
            req: urllib.request.Request, timeout: float = 30
        ) -> _FakeHTTPResponse:
            del req, timeout
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return _FakeHTTPResponse(b"short")
            return _FakeHTTPResponse(b"0123456789")

        provider = mock.MagicMock()
        provider.get_token.return_value = "tok"
        item = self.streamer.ModelObject(
            object_name="m/shard.safetensors",
            relative_path="shard.safetensors",
            size_bytes=10,
        )
        with tempfile.TemporaryDirectory() as dest_root:
            written = self.streamer.download_object(
                bucket="b",
                item=item,
                dest_root=dest_root,
                token_provider=provider,
                urlopen_fn=truncated_then_ok,
                sleep_fn=lambda _: None,
            )
            self.assertEqual(written, 10)
            self.assertEqual(attempts, 2)
            # Ensure temporary .part files were cleaned up.
            self.assertEqual(os.listdir(dest_root), ["shard.safetensors"])

            forbidden_calls = 0

            def always_403(
                req: urllib.request.Request, timeout: float = 30
            ) -> _FakeHTTPResponse:
                del timeout
                nonlocal forbidden_calls
                forbidden_calls += 1
                raise urllib.error.HTTPError(
                    url=req.full_url,
                    code=403,
                    msg="Forbidden",
                    hdrs=None,  # type: ignore[arg-type]
                    fp=None,
                )

            with self.assertRaises(RuntimeError):
                self.streamer.download_object(
                    bucket="b",
                    item=item,
                    dest_root=dest_root,
                    token_provider=provider,
                    urlopen_fn=always_403,
                    sleep_fn=lambda _: None,
                )
            self.assertEqual(forbidden_calls, 1)


class _FakeApp:
    """Minimal ASGI app recording registered middleware classes."""

    def __init__(
        self,
        handler: Callable[
            [
                MutableMapping[str, Any],
                Callable[[], Awaitable[MutableMapping[str, Any]]],
                Callable[[MutableMapping[str, Any]], Awaitable[None]],
            ],
            Awaitable[None],
        ],
    ) -> None:
        self._handler = handler

    def add_middleware(self, middleware_cls: Any, **kwargs: Any) -> None:
        self._handler = middleware_cls(self._handler, **kwargs)

    async def send_http(self, method: str, path: str) -> None:
        async def _recv() -> MutableMapping[str, Any]:
            return {"type": "http.request", "body": b""}

        async def _send(msg: MutableMapping[str, Any]) -> None:
            del msg

        await self._handler(
            {"type": "http", "method": method, "path": path}, _recv, _send
        )


class _FakeMetricsCollector:
    """Records gauge updates matching TensorRT-LLM MetricsCollector API."""

    def __init__(self) -> None:
        self.num_requests_running = "running"
        self.num_requests_waiting = "waiting"
        self.gauges: dict[str, float] = {}

    def _log_gauge(self, gauge: str, value: float) -> None:
        self.gauges[gauge] = value

    def log_iteration_stats(self, stats: dict[str, Any]) -> None:
        if "numActiveRequests" in stats:
            self._log_gauge(self.num_requests_running, stats["numActiveRequests"])
        if "numQueuedRequests" in stats:
            self._log_gauge(self.num_requests_waiting, stats["numQueuedRequests"])


class _FakeGenerator:
    """Stubs TensorRT-LLM AsyncLLM.get_stats_async queue behavior."""

    def __init__(self) -> None:
        self.stats_queue: deque[dict[str, Any]] = deque()

    async def get_stats_async(
        self, timeout: float = 0.5
    ) -> AsyncIterator[dict[str, Any]]:
        del timeout
        while self.stats_queue:
            yield self.stats_queue.popleft()


class SitecustomizeMetricsPatchTest(unittest.IsolatedAsyncioTestCase):
    """Tests startup zero-init, active polling, and idle reset on OpenAIServer."""

    def setUp(self) -> None:
        super().setUp()
        with mock.patch.dict(
            os.environ,
            {
                "TRTLLM_DISABLE_METRICS_PATCH": "1",
                "TRTLLM_METRICS_POLL_INTERVAL_SECONDS": "0.03",
            },
        ):
            self.patch_mod = _load_module(
                "test_loaded_trtllm_sitecustomize", _SITECUSTOMIZE_PATH
            )

    async def test_initializes_polls_during_long_think_and_resets_on_idle(
        self,
    ) -> None:
        request_entered = asyncio.Event()
        release_request = asyncio.Event()

        async def slow_inference_handler(
            scope: MutableMapping[str, Any],
            receive: Callable[[], Awaitable[MutableMapping[str, Any]]],
            send: Callable[[MutableMapping[str, Any]], Awaitable[None]],
        ) -> None:
            del receive, send
            if scope.get("path") == "/v1/chat/completions":
                request_entered.set()
                await release_request.wait()

        class FakeOpenAIServer:
            def __init__(self) -> None:
                self._iteration_stats_wakeup_event = asyncio.Event()
                self._iteration_stats_buffer: deque[dict[str, Any]] = deque(maxlen=100)
                self.metrics_collector = _FakeMetricsCollector()
                self.generator = _FakeGenerator()
                self.app = _FakeApp(slow_inference_handler)

            async def _iteration_stats_collector_loop(self) -> None:
                raise AssertionError("Original loop should have been replaced")

        fake_mod = types.ModuleType("tensorrt_llm.serve.openai_server")
        fake_mod.OpenAIServer = FakeOpenAIServer  # type: ignore[attr-defined]

        with mock.patch.dict(
            os.environ, {"TRTLLM_METRICS_POLL_INTERVAL_SECONDS": "0.03"}
        ):
            applied = self.patch_mod.apply_openai_server_metrics_patch(fake_mod)
        self.assertTrue(applied)

        server = FakeOpenAIServer()
        # 1. Startup must initialize both gauges to 0 before any request runs.
        self.assertEqual(server.metrics_collector.gauges, {"running": 0, "waiting": 0})

        loop_task = asyncio.create_task(server._iteration_stats_collector_loop())
        try:
            # 2. Non-inference endpoints must not increment in_flight.
            await server.app.send_http("GET", "/health")
            await server.app.send_http("POST", "/v1/messages/count_tokens")
            self.assertEqual(server._acp_inflight_state.in_flight, 0)  # type: ignore[attr-defined]

            # 3. Start a long-running chat completion that has NOT finished yet.
            req_task = asyncio.create_task(
                server.app.send_http("POST", "/v1/chat/completions")
            )
            await request_entered.wait()

            # Simulate PyExecutor emitting mid-generation stats while request is
            # still decoding (<think> trace) without setting wakeup_event.
            server.generator.stats_queue.append(
                {"numActiveRequests": 5, "numQueuedRequests": 2}
            )
            await asyncio.sleep(0.08)
            self.assertEqual(
                server.metrics_collector.gauges, {"running": 5, "waiting": 2}
            )

            # 4. Simulate PyExecutor's final iteration stat (which upstream
            # records BEFORE retiring the last request, leaving active=1) and
            # complete the HTTP request.
            server.generator.stats_queue.append(
                {"numActiveRequests": 1, "numQueuedRequests": 0}
            )
            release_request.set()
            await req_task
            await asyncio.sleep(0.05)

            # Gauges must reset to 0 once in-flight requests drain to idle.
            self.assertEqual(
                server.metrics_collector.gauges, {"running": 0, "waiting": 0}
            )
            self.assertEqual(len(server._iteration_stats_buffer), 2)
        finally:
            loop_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await loop_task

    def test_skips_cleanly_if_upstream_signature_changes(self) -> None:
        fake_mod = types.ModuleType("tensorrt_llm.serve.openai_server")
        stderr_buf = io.StringIO()
        with mock.patch.object(sys, "stderr", stderr_buf):
            applied = self.patch_mod.apply_openai_server_metrics_patch(fake_mod)
        self.assertFalse(applied)
        self.assertIn("Skipping patch", stderr_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
