#!/usr/bin/env python3
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

"""Container entrypoint of the inference-perf benchmark client Jobs.

bench/manifests/job.yaml.tmpl runs it from the Job's ConfigMap. It:
  1. copies the inference-perf configuration to a writable path,
  2. when BENCH_MODEL_PATH is set (the tokenizer is the served model's), copies
     the tokenizer from the regional Cloud Storage model bucket with the Pod's
     Workload Identity and points the configuration at the copy, so that no
     client downloads from Hugging Face (gated models need no token there); it
     fails if the bucket has no tokenizer files,
  3. writes /tmp/bench-ready and, with BENCH_SYNC_START=true, waits until
     scripts/run-benchmark.sh creates /tmp/bench-go in every client Pod (the
     cross-region start barrier),
  4. replaces itself with inference-perf.
"""

from __future__ import annotations

import os
import shutil
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

import yaml

CONFIG_SRC = Path("/config/config.yaml")
CONFIG_DST = Path("/tmp/config.yaml")
TOKENIZER_DIR = Path("/cache/tokenizer")
READY_FILE = Path("/tmp/bench-ready")
GO_FILE = Path("/tmp/bench-go")

# Model weights are not needed to load a tokenizer.
WEIGHT_SUFFIXES = (
    ".safetensors",
    ".bin",
    ".pt",
    ".pth",
    ".gguf",
    ".h5",
    ".ot",
    ".msgpack",
)
# A usable tokenizer has at least one of these files.
TOKENIZER_MARKERS = frozenset(
    {
        "tokenizer.json",
        "tokenizer_config.json",
        "tokenizer.model",
        "vocab.json",
        "tiktoken.model",
    }
)
MAX_TOKENIZER_FILE_BYTES = 64 * 1024 * 1024


class Blob(Protocol):
    """The part of google.cloud.storage.Blob that is used here."""

    name: str
    size: int | None

    def download_to_filename(self, filename: str) -> None: ...


class StorageClient(Protocol):
    """The part of google.cloud.storage.Client that is used here."""

    def list_blobs(self, bucket_or_name: str, prefix: str) -> Iterable[Blob]: ...


def _log(msg: str) -> None:
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[{timestamp}] [bench-entrypoint] {msg}", file=sys.stderr, flush=True)


def should_download_blob(rel_path: str, size_bytes: int | None) -> bool:
    """Whether a model bucket object can be needed to load the tokenizer.

    Everything except weights qualifies (tokenizer, vocabulary, chat template,
    and model configuration files), up to MAX_TOKENIZER_FILE_BYTES.
    """
    if not rel_path or rel_path.endswith("/"):
        return False
    if rel_path.lower().endswith(WEIGHT_SUFFIXES):
        return False
    return size_bytes is None or size_bytes <= MAX_TOKENIZER_FILE_BYTES


def stage_tokenizer_from_gcs(
    bucket_name: str,
    model_path: str,
    dest_dir: Path,
    storage_client: StorageClient | None = None,
) -> list[str]:
    """Copies the tokenizer files under gs://<bucket_name>/<model_path>/ to dest_dir.

    Args:
        bucket_name: Regional Cloud Storage bucket with the staged model.
        model_path: Object prefix of the model in the bucket.
        dest_dir: Local directory to copy the files to.
        storage_client: Cloud Storage client; a new one by default.

    Returns:
        The copied object paths, relative to the model prefix.

    Raises:
        RuntimeError: If no tokenizer file (TOKENIZER_MARKERS) was copied.
    """
    prefix = f"{model_path.strip('/')}/"
    if storage_client is None:
        # Installed in the inference-perf container image.
        from google.cloud import storage  # type: ignore[import-not-found]

        storage_client = storage.Client()
    copied = []
    for blob in storage_client.list_blobs(bucket_name, prefix=prefix):
        rel = blob.name[len(prefix) :]
        # Never write outside dest_dir.
        if rel.startswith("/") or ".." in Path(rel).parts:
            _log(f"Skipping gs://{bucket_name}/{blob.name}: unsafe path")
            continue
        if not should_download_blob(rel, blob.size):
            continue
        target = dest_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target))
        copied.append(rel)
    if not {Path(rel).name for rel in copied} & TOKENIZER_MARKERS:
        raise RuntimeError(
            f"no tokenizer files ({', '.join(sorted(TOKENIZER_MARKERS))}) under "
            f"gs://{bucket_name}/{prefix}; stage the model with "
            "scripts/stage-model.sh <region key>"
        )
    return copied


def prepare_config(
    src_config: Path,
    dst_config: Path,
    tokenizer_dir: Path,
    bucket_name: str,
    model_path: str,
    storage_client: StorageClient | None = None,
) -> None:
    """Writes the inference-perf configuration to dst_config.

    With a model path, the tokenizer is copied from the model bucket (see
    stage_tokenizer_from_gcs) and the configuration points at the copy.
    Without one, inference-perf downloads the configured tokenizer from Hugging
    Face.
    """
    shutil.copyfile(src_config, dst_config)
    if not model_path:
        _log(
            "BENCH_MODEL_PATH is empty: inference-perf downloads the tokenizer "
            "from Hugging Face, after the start barrier"
        )
        return
    copied = stage_tokenizer_from_gcs(
        bucket_name, model_path, tokenizer_dir, storage_client
    )
    cfg = yaml.safe_load(dst_config.read_text(encoding="utf-8"))
    cfg["tokenizer"]["pretrained_model_name_or_path"] = str(tokenizer_dir)
    dst_config.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    _log(
        f"Copied {len(copied)} tokenizer files from gs://{bucket_name}/"
        f"{model_path.strip('/')}/ to {tokenizer_dir}"
    )


def wait_for_start_barrier(
    ready_file: Path,
    go_file: Path,
    sync_start: bool,
    timeout_s: float,
    poll_interval_s: float = 0.2,
) -> bool:
    """Marks this client Pod ready and waits for the harness to release it.

    Returns:
        False if go_file didn't appear within timeout_s.
    """
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    ready_file.write_text("ready\n", encoding="utf-8")
    if not sync_start:
        return True
    _log(f"Waiting up to {timeout_s:.0f}s for the start barrier ({go_file})")
    deadline = time.monotonic() + timeout_s
    while not go_file.exists():
        if time.monotonic() >= deadline:
            _log(f"ERROR: timed out after {timeout_s:.0f}s waiting for {go_file}")
            return False
        time.sleep(poll_interval_s)
    _log("Start barrier released")
    return True


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise SystemExit(
            f"{name} is not set; render the Job with scripts/run-benchmark.sh"
        )
    return value


def main() -> int:
    sync_start = required_env("BENCH_SYNC_START") == "true"
    sync_timeout_s = float(required_env("BENCH_SYNC_TIMEOUT_S"))
    prepare_config(
        CONFIG_SRC,
        CONFIG_DST,
        TOKENIZER_DIR,
        required_env("BENCH_MODELS_BUCKET"),
        required_env("BENCH_MODEL_PATH"),
    )
    if not wait_for_start_barrier(READY_FILE, GO_FILE, sync_start, sync_timeout_s):
        return 1
    # The Job's working directory (/workspace) is the inference-perf checkout
    # of the image.
    os.execvp(
        "python",
        [
            "python",
            "inference_perf/main.py",
            "--config_file",
            str(CONFIG_DST),
            "--log-level",
            "INFO",
        ],
    )


if __name__ == "__main__":
    sys.exit(main())
