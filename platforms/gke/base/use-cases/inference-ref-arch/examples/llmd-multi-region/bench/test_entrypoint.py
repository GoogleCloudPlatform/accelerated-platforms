#!/usr/bin/env python3
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for entrypoint.py."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import threading
import unittest
from collections.abc import Iterable
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrypoint  # noqa: E402

PREFIX = "qwen/qwen3-32b/"
CONFIG = """\
server:
  base_url: http://10.10.0.50:80
tokenizer:
  pretrained_model_name_or_path: Qwen/Qwen3-32B
"""


class FakeBlob:
    def __init__(self, name: str, size: int | None, content: str = "{}") -> None:
        self.name = name
        self.size = size
        self.content = content

    def download_to_filename(self, filename: str) -> None:
        Path(filename).write_text(self.content, encoding="utf-8")


class FakeStorageClient:
    def __init__(self, blobs: list[FakeBlob]) -> None:
        self.blobs = blobs
        self.calls: list[tuple[str, str]] = []

    def list_blobs(self, bucket_or_name: str, prefix: str) -> Iterable[FakeBlob]:
        self.calls.append((bucket_or_name, prefix))
        return [b for b in self.blobs if b.name.startswith(prefix)]


MODEL_BLOBS = [
    FakeBlob(PREFIX + "tokenizer.json", 11_000_000, '{"model": {}}'),
    FakeBlob(PREFIX + "tokenizer_config.json", 9_000),
    FakeBlob(PREFIX + "config.json", 700),
    FakeBlob(PREFIX + "model-00001-of-00017.safetensors", 4_000_000_000),
    FakeBlob(PREFIX + "huge.json", entrypoint.MAX_TOKENIZER_FILE_BYTES + 1),
    FakeBlob(PREFIX + "subdir/vocab.txt", 100),
    FakeBlob(PREFIX + "/escape.json", 10),
    FakeBlob(PREFIX + "../escape.json", 10),
    FakeBlob("other-model/tokenizer.json", 100),
]


class ShouldDownloadBlobTest(unittest.TestCase):
    def test_selection(self) -> None:
        self.assertTrue(entrypoint.should_download_blob("tokenizer.json", 1024))
        self.assertTrue(entrypoint.should_download_blob("chat_template.jinja", None))
        self.assertFalse(entrypoint.should_download_blob("model.SAFETENSORS", 1))
        self.assertFalse(entrypoint.should_download_blob("pytorch_model.bin", 1))
        self.assertFalse(entrypoint.should_download_blob("subdir/", 0))
        self.assertFalse(entrypoint.should_download_blob("", 0))
        self.assertTrue(
            entrypoint.should_download_blob(
                "big.json", entrypoint.MAX_TOKENIZER_FILE_BYTES
            )
        )
        self.assertFalse(
            entrypoint.should_download_blob(
                "big.json", entrypoint.MAX_TOKENIZER_FILE_BYTES + 1
            )
        )


class StageTokenizerTest(unittest.TestCase):
    def test_copies_tokenizer_files_only(self) -> None:
        client = FakeStorageClient(MODEL_BLOBS)
        with (
            tempfile.TemporaryDirectory() as tmp,
            contextlib.redirect_stderr(io.StringIO()) as err,
        ):
            dest = Path(tmp) / "tok"
            copied = entrypoint.stage_tokenizer_from_gcs(
                "models-usc1", "/qwen/qwen3-32b/", dest, client
            )
            files = sorted(str(p.relative_to(dest)) for p in dest.rglob("*.*"))
            self.assertFalse((Path(tmp) / "escape.json").exists())
        self.assertEqual(client.calls, [("models-usc1", PREFIX)])
        self.assertEqual(
            sorted(copied),
            [
                "config.json",
                "subdir/vocab.txt",
                "tokenizer.json",
                "tokenizer_config.json",
            ],
        )
        self.assertEqual(files, sorted(copied))
        self.assertEqual(err.getvalue().count("unsafe path"), 2)

    def test_fails_without_tokenizer_files(self) -> None:
        client = FakeStorageClient(
            [
                FakeBlob(PREFIX + "config.json", 700),
                FakeBlob(PREFIX + "model.safetensors", 10),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                RuntimeError,
                "no tokenizer files .* under gs://models-usc1/qwen/qwen3-32b/; "
                "stage the model with scripts/deploy-all.sh",
            ):
                entrypoint.stage_tokenizer_from_gcs(
                    "models-usc1", "qwen/qwen3-32b", Path(tmp), client
                )

    def test_storage_errors_propagate(self) -> None:
        class DeniedClient:
            def list_blobs(self, bucket_or_name: str, prefix: str) -> list[FakeBlob]:
                raise PermissionError("403 storage.objects.list denied")

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PermissionError, "403"):
                entrypoint.stage_tokenizer_from_gcs(
                    "models-usc1", "qwen/qwen3-32b", Path(tmp), DeniedClient()
                )


class PrepareConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.src = self.tmp / "config.yaml"
        self.src.write_text(CONFIG, encoding="utf-8")
        self.dst = self.tmp / "runtime.yaml"
        self.tok = self.tmp / "tokenizer"

    def test_points_inference_perf_at_the_staged_tokenizer(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()) as err:
            entrypoint.prepare_config(
                self.src,
                self.dst,
                self.tok,
                "models-usc1",
                "qwen/qwen3-32b",
                FakeStorageClient(MODEL_BLOBS),
            )
        cfg = yaml.safe_load(self.dst.read_text(encoding="utf-8"))
        self.assertEqual(
            cfg["tokenizer"]["pretrained_model_name_or_path"], str(self.tok)
        )
        self.assertEqual(cfg["server"]["base_url"], "http://10.10.0.50:80")
        self.assertTrue((self.tok / "tokenizer.json").exists())
        self.assertIn("Copied 4 tokenizer files from gs://models-usc1/", err.getvalue())

    def test_other_tokenizers_come_from_hugging_face(self) -> None:
        client = FakeStorageClient(MODEL_BLOBS)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            entrypoint.prepare_config(
                self.src, self.dst, self.tok, "models-usc1", "", client
            )
        self.assertEqual(self.dst.read_text(encoding="utf-8"), CONFIG)
        self.assertEqual(client.calls, [])
        self.assertIn("downloads the tokenizer from Hugging Face", err.getvalue())

    def test_staging_failure_is_fatal(self) -> None:
        with self.assertRaises(RuntimeError):
            entrypoint.prepare_config(
                self.src,
                self.dst,
                self.tok,
                "models-usc1",
                "qwen/qwen3-32b",
                FakeStorageClient([]),
            )


class StartBarrierTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.ready = Path(tmp.name) / "bench-ready"
        self.go = Path(tmp.name) / "bench-go"
        self.enterContext(contextlib.redirect_stderr(io.StringIO()))

    def test_without_sync_start(self) -> None:
        self.assertTrue(
            entrypoint.wait_for_start_barrier(self.ready, self.go, False, 0.0)
        )
        self.assertTrue(self.ready.exists())

    def test_released_by_the_go_file(self) -> None:
        timer = threading.Timer(0.3, self.go.write_text, args=("go\n",))
        timer.start()
        self.addCleanup(timer.cancel)
        self.assertTrue(
            entrypoint.wait_for_start_barrier(
                self.ready, self.go, True, 10.0, poll_interval_s=0.05
            )
        )
        self.assertTrue(self.ready.exists())

    def test_times_out(self) -> None:
        self.assertFalse(
            entrypoint.wait_for_start_barrier(
                self.ready, self.go, True, 0.2, poll_interval_s=0.05
            )
        )


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "config.yaml").write_text(CONFIG, encoding="utf-8")
        for name, path in {
            "CONFIG_SRC": root / "config.yaml",
            "CONFIG_DST": root / "runtime.yaml",
            "TOKENIZER_DIR": root / "tokenizer",
            "READY_FILE": root / "bench-ready",
            "GO_FILE": root / "bench-go",
        }.items():
            patcher = mock.patch.object(entrypoint, name, path)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.root = root
        self.env = {
            "BENCH_SYNC_START": "false",
            "BENCH_SYNC_TIMEOUT_S": "0.2",
            "BENCH_MODELS_BUCKET": "models-usc1",
            "BENCH_MODEL_PATH": "",
        }

    def run_main(self, env: dict[str, str]) -> tuple[int | None, mock.MagicMock]:
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(entrypoint.os, "execvp") as execvp,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            rc = entrypoint.main()
        return rc, execvp

    def test_execs_inference_perf(self) -> None:
        _rc, execvp = self.run_main(self.env)
        execvp.assert_called_once_with(
            "python",
            [
                "python",
                "inference_perf/main.py",
                "--config_file",
                str(self.root / "runtime.yaml"),
                "--log-level",
                "INFO",
            ],
        )
        self.assertTrue((self.root / "bench-ready").exists())

    def test_barrier_timeout_fails_the_pod(self) -> None:
        rc, execvp = self.run_main(dict(self.env, BENCH_SYNC_START="true"))
        self.assertEqual(rc, 1)
        execvp.assert_not_called()

    def test_requires_the_job_environment(self) -> None:
        env = dict(self.env)
        del env["BENCH_SYNC_TIMEOUT_S"]
        with self.assertRaisesRegex(SystemExit, "BENCH_SYNC_TIMEOUT_S is not set"):
            self.run_main(env)


if __name__ == "__main__":
    unittest.main()
