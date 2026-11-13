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
import shutil
import subprocess
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


class MultiRegionHelpersShellTest(unittest.TestCase):
    """Tests multi-region preflight, checkout hygiene, and model-staging helpers."""

    def test_stage_hf_model_leaves_repo_clean_and_polls_job(self) -> None:
        helpers_sh = (
            _REPO_ROOT
            / "platforms/gke/base/use-cases/inference-ref-arch"
            / "terraform/multi-region/helpers.sh"
        )
        hf_manifest_dir = (
            _REPO_ROOT
            / "platforms/gke/base/use-cases/inference-ref-arch"
            / "kubernetes-manifests/model-download/huggingface"
        )
        before_kustomization = (hf_manifest_dir / "kustomization.yaml").read_text(
            encoding="utf-8"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = Path(tmp_dir) / "bin"
            bin_dir.mkdir()
            log_file = Path(tmp_dir) / "calls.log"
            (bin_dir / "gcloud").write_text(
                "#!/usr/bin/env bash\n"
                f'echo "gcloud $*" >> "{log_file}"\n'
                'if [[ "$1 $2 $3" == "secrets versions list" ]]; then exit 0; fi\n'
                'if [[ "$1 $2 $3" == "secrets versions add" ]]; then cat >/dev/null; exit 0; fi\n'
                'if [[ "$1 $2" == "storage du" ]]; then echo "10 GiB gs://b/m"; exit 0; fi\n'
                'if [[ "$1 $2" == "storage cat" ]]; then echo \'{"resources":[{}]}\'; exit 0; fi\n'
                "exit 1\n",
                encoding="utf-8",
            )
            (bin_dir / "kubectl").write_text(
                "#!/usr/bin/env bash\n"
                f'echo "kubectl $*" >> "{log_file}"\n'
                'if [[ "$1 $2" == "get job" ]]; then echo \'{"status":{"succeeded":1}}\'; fi\n'
                "exit 0\n",
                encoding="utf-8",
            )
            os.chmod(bin_dir / "gcloud", 0o755)
            os.chmod(bin_dir / "kubectl", 0o755)
            if shutil.which("kustomize") is None:
                (bin_dir / "kustomize").write_text(
                    "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
                )
                os.chmod(bin_dir / "kustomize", 0o755)
            if shutil.which("terraform") is None:
                (bin_dir / "terraform").write_text(
                    "#!/usr/bin/env bash\n"
                    'if [[ "$*" == *"output -json"* ]]; then\n'
                    '  jq -n --arg b "${TF_VAR_huggingface_hub_models_bucket_name:-test-proj-inf-usc1-hf-hub-models}" \'{\n'
                    "    huggingface_hub_models_bucket_name: {value: $b},\n"
                    '    huggingface_hub_downloader_kubernetes_namespace_name: {value: "inf-usc1-hf-hub-downloader"},\n'
                    '    huggingface_hub_downloader_kubernetes_service_account_name: {value: "inf-usc1-hf-hub-downloader"},\n'
                    '    huggingface_secret_manager_project_id: {value: "test-proj"},\n'
                    '    huggingface_hub_access_token_read_secret_manager_secret_name: {value: "inf-usc1-huggingface-hub-access-token-read"},\n'
                    '    huggingface_hub_access_token_write_secret_manager_secret_name: {value: "inf-usc1-huggingface-hub-access-token-write"}\n'
                    "  }'\n"
                    "fi\n"
                    "exit 0\n",
                    encoding="utf-8",
                )
                os.chmod(bin_dir / "terraform", 0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            env["PROJECT_ID"] = "test-proj"
            env["HF_TOKEN"] = "hf_test_token"
            env["TF_VAR_huggingface_hub_models_bucket_name"] = "custom-hf-models-bkt"
            proc = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{helpers_sh}" && '
                    "use_region usc1 us-central1 && "
                    "stage_hf_model --skip-existing Qwen/Qwen3-32B && "
                    "mr_tf_state_has_resources bench terraform/llmd-multi-region/bench",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            calls = log_file.read_text(encoding="utf-8")
            self.assertIn("gs://custom-hf-models-bkt/qwen/qwen3-32b", calls)
            self.assertIn(
                "secrets versions add inf-usc1-huggingface-hub-access-token-read",
                calls,
            )
            self.assertIn("kubectl apply --kustomize", calls)
            self.assertIn("kubectl get job", calls)
            self.assertIn("kubectl delete --ignore-not-found --kustomize", calls)
            self.assertIn(
                "gs://test-proj-inf-mr-terraform/terraform/llmd-multi-region/bench/default.tfstate",
                calls,
            )

        after_kustomization = (hf_manifest_dir / "kustomization.yaml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(before_kustomization, after_kustomization)

    def test_provision_pod_snapshots_fails_fast_without_gcloud_beta(self) -> None:
        provision_sh = (
            _REPO_ROOT
            / "platforms/gke/base/use-cases/inference-ref-arch"
            / "terraform/multi-region/provision.sh"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            bin_dir = Path(tmp_dir) / "bin"
            bin_dir.mkdir()
            log_file = Path(tmp_dir) / "gcloud.log"
            (bin_dir / "gcloud").write_text(
                "#!/usr/bin/env bash\n"
                f'echo "gcloud $*" >> "{log_file}"\n'
                'if [[ " $* " == *" beta "* ]]; then exit 1; fi\n'
                "exit 0\n",
                encoding="utf-8",
            )
            for stub in ("kubectl", "terraform"):
                if shutil.which(stub) is None:
                    (bin_dir / stub).write_text("#!/usr/bin/env bash\nexit 0\n")
                    os.chmod(bin_dir / stub, 0o755)
            os.chmod(bin_dir / "gcloud", 0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            env["PROJECT_ID"] = "test-proj"
            env["ENABLE_POD_SNAPSHOTS"] = "true"
            proc = subprocess.run(
                ["bash", str(provision_sh), "americas:us-central1:0"],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("gcloud beta", proc.stderr)
            self.assertNotIn("projects describe", log_file.read_text(encoding="utf-8"))

    def test_mr_clean_checkout_restores_tracked_and_cleans_worktree(self) -> None:
        helpers_sh = (
            _REPO_ROOT
            / "platforms/gke/base/use-cases/inference-ref-arch"
            / "terraform/multi-region/helpers.sh"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir) / "repo"
            (repo / "platforms/gke/base/core/initialize").mkdir(parents=True)
            (repo / "platforms/gke/base/core/container_node_pool").mkdir(parents=True)
            (repo / "platforms/gke/base/core/workloads/lws/manifests").mkdir(
                parents=True
            )
            (repo / "platforms/gke/base/kubernetes/manifests").mkdir(parents=True)
            (repo / "platforms/gke/base/kubernetes/kubeconfig").mkdir(parents=True)

            backend_tpl = repo / "platforms/gke/base/core/initialize/backend.tf.bucket"
            lockfile = repo / "platforms/gke/base/core/initialize/.terraform.lock.hcl"
            backend_tpl.write_text('bucket = "TEMPLATE"\n', encoding="utf-8")
            lockfile.write_text("provider {}\n", encoding="utf-8")
            (repo / "platforms/gke/base/kubernetes/manifests/.gitkeep").write_text("")
            (repo / "platforms/gke/base/kubernetes/kubeconfig/.gitkeep").write_text("")
            (repo / ".gitignore").write_text(
                "platforms/gke/base/kubernetes/kubeconfig/*\n"
                "!platforms/gke/base/kubernetes/kubeconfig/.gitkeep\n"
                "**/*/backend.tf\n",
                encoding="utf-8",
            )

            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.email", "t@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo), "config", "user.name", "Test"], check=True
            )
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True
            )

            # Dirty tracked files and write generated untracked artifacts.
            backend_tpl.write_text('bucket = "DIRTIED"\n', encoding="utf-8")
            lockfile.write_text("provider { dirty = true }\n", encoding="utf-8")
            (repo / "platforms/gke/base/core/initialize/backend.tf").write_text("ok")
            (
                repo
                / "platforms/gke/base/core/container_node_pool/container_node_pool_a.tf"
            ).write_text("gen")
            (
                repo / "platforms/gke/base/core/workloads/lws/manifests/lws.yaml"
            ).write_text("gen")
            (repo / "platforms/gke/base/kubernetes/manifests/m.yaml").write_text("gen")
            (
                repo / "platforms/gke/base/kubernetes/kubeconfig/test-proj-inf-usc1"
            ).write_text("kc")

            proc = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{helpers_sh}" && mr_clean_checkout "{repo}" true true',
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            status = subprocess.check_output(
                ["git", "-C", str(repo), "status", "--porcelain"], text=True
            )
            self.assertEqual(status, "")
            self.assertEqual(
                backend_tpl.read_text(encoding="utf-8"), 'bucket = "TEMPLATE"\n'
            )
            self.assertTrue(
                (repo / "platforms/gke/base/core/initialize/backend.tf").exists()
            )
            self.assertFalse(
                (
                    repo / "platforms/gke/base/kubernetes/kubeconfig/test-proj-inf-usc1"
                ).exists()
            )
            self.assertTrue(
                (repo / "platforms/gke/base/kubernetes/kubeconfig/.gitkeep").exists()
            )

    def test_download_wait_fails_without_pkill_on_failed_job(self) -> None:
        download_wait_sh = (
            _REPO_ROOT
            / "test/scripts/platforms/gke/base/use-cases/inference-ref-arch"
            / "model-download/huggingface/download_wait.sh"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_repo = Path(tmp_dir) / "repo"
            script_dir = (
                fake_repo
                / "test/scripts/platforms/gke/base/use-cases/inference-ref-arch"
                / "model-download/huggingface"
            )
            cfg_dir = (
                fake_repo
                / "platforms/gke/base/use-cases/inference-ref-arch"
                / "terraform/_shared_config/scripts"
            )
            script_dir.mkdir(parents=True)
            cfg_dir.mkdir(parents=True)
            shutil.copy2(download_wait_sh, script_dir / "download_wait.sh")
            (script_dir.parents[1] / "config").mkdir(parents=True)
            (script_dir.parents[1] / "config/huggingface.sh").write_text(
                'hf_models=("qwen/qwen3-32b")\n', encoding="utf-8"
            )
            (cfg_dir / "set_environment_variables.sh").write_text(
                'huggingface_hub_downloader_kubernetes_namespace_name="ns"\n'
                'huggingface_hub_models_bucket_name="bkt"\n'
                'HF_MODEL_ID_HASH="12345678"\n',
                encoding="utf-8",
            )
            bin_dir = Path(tmp_dir) / "bin"
            bin_dir.mkdir()
            (bin_dir / "kubectl").write_text(
                '#!/usr/bin/env bash\necho ":True"\n', encoding="utf-8"
            )
            (bin_dir / "gcloud").write_text(
                '#!/usr/bin/env bash\necho "1 GiB"\n', encoding="utf-8"
            )
            os.chmod(bin_dir / "kubectl", 0o755)
            os.chmod(bin_dir / "gcloud", 0o755)

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            env["HF_MODEL_ID"] = "Qwen/Qwen3-32B"
            proc = subprocess.run(
                ["bash", str(script_dir / "download_wait.sh")],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("failed", proc.stderr)


if __name__ == "__main__":
    unittest.main()
