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

"""Concurrent Cloud Storage model streamer for GKE Pod snapshot cold starts.

GKE Pod snapshots run inside gVisor (`runsc`) and do not support CSI volumes
such as `gcsfuse.csi.storage.gke.io`. On cold start, this stdlib-only helper
streams model artifacts concurrently from a regional Cloud Storage bucket into
a RAM-backed `emptyDir` (`/model-cache`) using Workload Identity credentials
from the GCE metadata server.
"""

from __future__ import annotations

import concurrent.futures
import http.client
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

_METADATA_TOKEN_URL = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/token"
)
_GCS_API_BASE_URL = "https://storage.googleapis.com/storage/v1/b"
_CHUNK_SIZE_BYTES = 64 * 1024 * 1024
_DEFAULT_DEST_ROOT = "/model-cache"
_DEFAULT_MAX_WORKERS = 16
_DEFAULT_MAX_ATTEMPTS = 4
_DEFAULT_INITIAL_BACKOFF_SECONDS = 0.5
_TOKEN_REFRESH_MARGIN_SECONDS = 60.0
_RETRYABLE_HTTP_STATUS_CODES = frozenset({401, 408, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class ModelObject:
    """Metadata for a single Cloud Storage object under the model prefix."""

    object_name: str
    relative_path: str
    size_bytes: int


class MetadataTokenProvider:
    """Thread-safe GCE Workload Identity access-token cache with refresh."""

    def __init__(
        self,
        urlopen_fn: Callable[..., http.client.HTTPResponse] = (urllib.request.urlopen),
        clock_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self._urlopen = urlopen_fn
        self._clock = clock_fn
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        """Returns a valid OAuth2 access token, refreshing before expiry."""
        with self._lock:
            now = self._clock()
            if self._token is not None and now < self._expires_at:
                return self._token

            req = urllib.request.Request(
                _METADATA_TOKEN_URL,
                headers={"Metadata-Flavor": "Google"},
            )
            with self._urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))

            token = payload.get("access_token")
            if not isinstance(token, str) or not token:
                raise RuntimeError(
                    "GCE metadata server response did not contain a non-empty "
                    "'access_token'; verify GKE Workload Identity is configured "
                    "on the Pod's Kubernetes ServiceAccount."
                )
            expires_in = float(payload.get("expires_in", 300))
            ttl = max(expires_in - _TOKEN_REFRESH_MARGIN_SECONDS, 0.0)
            self._token = token
            self._expires_at = self._clock() + ttl
            return token

    def invalidate(self) -> None:
        """Forces the next `get_token()` call to fetch a fresh token."""
        with self._lock:
            self._token = None
            self._expires_at = 0.0


def resolve_safe_destination_path(dest_root: str, relative_path: str) -> str:
    """Resolves `relative_path` inside `dest_root`, rejecting path traversal.

    Args:
        dest_root: Destination directory root (for example `/model-cache`).
        relative_path: Object key suffix relative to `MODEL_GCS_DIR/`.

    Returns:
        Canonical filesystem path strictly beneath `dest_root`.

    Raises:
        ValueError: If `relative_path` is empty, absolute, contains traversal
            segments (`..` or `.`), or resolves outside `dest_root`.
    """
    if (
        not relative_path
        or relative_path.startswith("/")
        or "\\" in relative_path
        or "\x00" in relative_path
    ):
        raise ValueError(
            f"Invalid model object relative path {relative_path!r}: "
            "must be a non-empty POSIX relative path beneath MODEL_GCS_DIR."
        )

    parts = relative_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError(
            f"Unsafe path segment in model object {relative_path!r}: "
            "empty, '.', and '..' segments are forbidden."
        )

    real_root = os.path.realpath(dest_root)
    candidate = os.path.realpath(os.path.join(real_root, *parts))
    if (
        os.path.commonpath([real_root, candidate]) != real_root
        or candidate == real_root
    ):
        raise ValueError(
            f"Refusing to write {relative_path!r} outside destination root "
            f"{real_root!r}."
        )
    return candidate


def _run_with_retries(
    operation: Callable[[], None],
    token_provider: MetadataTokenProvider,
    description: str,
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_backoff_seconds: float = _DEFAULT_INITIAL_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> None:
    """Executes `operation` with bounded exponential backoff on transient I/O."""
    assert max_attempts >= 1, "max_attempts must be >= 1"
    for attempt in range(1, max_attempts + 1):
        try:
            operation()
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                token_provider.invalidate()
            if exc.code not in _RETRYABLE_HTTP_STATUS_CODES or attempt == max_attempts:
                raise RuntimeError(
                    f"Failed {description} with HTTP {exc.code} ({exc.reason}) "
                    f"after {attempt} attempt(s); check bucket/object IAM and "
                    "MODEL_BUCKET_NAME / MODEL_GCS_DIR settings."
                ) from exc
        except (
            urllib.error.URLError,
            TimeoutError,
            http.client.HTTPException,
            OSError,
        ) as exc:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Failed {description} after {attempt} attempt(s): {exc}"
                ) from exc

        sleep_fn(initial_backoff_seconds * (2 ** (attempt - 1)))


def list_model_objects(
    bucket: str,
    prefix: str,
    token_provider: MetadataTokenProvider,
    urlopen_fn: Callable[..., http.client.HTTPResponse] = (urllib.request.urlopen),
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_backoff_seconds: float = _DEFAULT_INITIAL_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[ModelObject]:
    """Lists all non-directory objects under `gs://<bucket>/<prefix>`."""
    normalized_prefix = prefix.strip("/")
    if not normalized_prefix:
        raise ValueError(
            "MODEL_GCS_DIR must be a non-empty object prefix inside the bucket."
        )
    prefix_with_slash = f"{normalized_prefix}/"
    quoted_bucket = urllib.parse.quote(bucket, safe="")

    objects: list[ModelObject] = []
    page_token: str | None = None

    while True:
        query = {"prefix": prefix_with_slash, "maxResults": "1000"}
        if page_token:
            query["pageToken"] = page_token
        url = f"{_GCS_API_BASE_URL}/{quoted_bucket}/o?{urllib.parse.urlencode(query)}"
        page_data: dict[str, object] = {}

        def _fetch_page() -> None:
            nonlocal page_data
            token = token_provider.get_token()
            req = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {token}"}
            )
            with urlopen_fn(req, timeout=30) as resp:
                page_data = json.loads(resp.read().decode("utf-8"))

        _run_with_retries(
            _fetch_page,
            token_provider=token_provider,
            description=f"listing gs://{bucket}/{prefix_with_slash}",
            max_attempts=max_attempts,
            initial_backoff_seconds=initial_backoff_seconds,
            sleep_fn=sleep_fn,
        )

        raw_items = page_data.get("items")
        if isinstance(raw_items, list):
            for obj in raw_items:
                if not isinstance(obj, dict):
                    continue
                name = str(obj.get("name", ""))
                if not name.startswith(prefix_with_slash):
                    continue
                rel = name[len(prefix_with_slash) :]
                if not rel or rel.endswith("/"):
                    continue
                size_bytes = int(str(obj.get("size", "0")))
                if size_bytes < 0:
                    raise ValueError(
                        f"Negative size {size_bytes} reported for {name!r}."
                    )
                objects.append(
                    ModelObject(
                        object_name=name,
                        relative_path=rel,
                        size_bytes=size_bytes,
                    )
                )

        next_token = page_data.get("nextPageToken")
        if isinstance(next_token, str) and next_token:
            page_token = next_token
        else:
            break

    if not objects:
        raise RuntimeError(
            f"No model objects found at gs://{bucket}/{prefix_with_slash}; "
            "verify the model download job completed and MODEL_GCS_DIR matches."
        )
    return objects


def download_object(
    bucket: str,
    item: ModelObject,
    dest_root: str,
    token_provider: MetadataTokenProvider,
    urlopen_fn: Callable[..., http.client.HTTPResponse] = (urllib.request.urlopen),
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_backoff_seconds: float = _DEFAULT_INITIAL_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    """Downloads a single object atomically and verifies exact byte length."""
    out_path = resolve_safe_destination_path(dest_root, item.relative_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    quoted_bucket = urllib.parse.quote(bucket, safe="")
    quoted_name = urllib.parse.quote(item.object_name, safe="")
    dl_url = f"{_GCS_API_BASE_URL}/{quoted_bucket}/o/{quoted_name}?alt=media"
    tmp_path = f"{out_path}.part.{os.getpid()}.{threading.get_ident()}"

    def _download_once() -> None:
        token = token_provider.get_token()
        req = urllib.request.Request(
            dl_url, headers={"Authorization": f"Bearer {token}"}
        )
        bytes_written = 0
        try:
            with urlopen_fn(req, timeout=600) as resp, open(tmp_path, "wb") as out_file:
                while True:
                    chunk = resp.read(_CHUNK_SIZE_BYTES)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    bytes_written += len(chunk)
            if bytes_written != item.size_bytes:
                raise OSError(
                    f"Truncated download for {item.object_name!r}: expected "
                    f"{item.size_bytes} bytes, got {bytes_written} bytes."
                )
            os.replace(tmp_path, out_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
            raise

    _run_with_retries(
        _download_once,
        token_provider=token_provider,
        description=f"downloading gs://{bucket}/{item.object_name}",
        max_attempts=max_attempts,
        initial_backoff_seconds=initial_backoff_seconds,
        sleep_fn=sleep_fn,
    )
    return item.size_bytes


def stream_model_from_gcs(
    bucket: str,
    model_gcs_dir: str,
    dest_root: str = _DEFAULT_DEST_ROOT,
    max_workers: int = _DEFAULT_MAX_WORKERS,
    token_provider: MetadataTokenProvider | None = None,
    urlopen_fn: Callable[..., http.client.HTTPResponse] = (urllib.request.urlopen),
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_backoff_seconds: float = _DEFAULT_INITIAL_BACKOFF_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[int, int, float]:
    """Streams all objects under `gs://<bucket>/<model_gcs_dir>/` into RAM.

    Returns:
        Tuple of `(file_count, total_bytes, elapsed_seconds)`.
    """
    if not bucket:
        raise ValueError("MODEL_BUCKET_NAME must be non-empty.")
    if max_workers < 1:
        raise ValueError(f"max_workers must be >= 1, got {max_workers}.")

    t0 = time.monotonic()
    os.makedirs(dest_root, exist_ok=True)
    provider = token_provider or MetadataTokenProvider(urlopen_fn=urlopen_fn)
    items = list_model_objects(
        bucket=bucket,
        prefix=model_gcs_dir,
        token_provider=provider,
        urlopen_fn=urlopen_fn,
        max_attempts=max_attempts,
        initial_backoff_seconds=initial_backoff_seconds,
        sleep_fn=sleep_fn,
    )
    # Validate all destination paths up front before launching worker threads.
    for item in items:
        resolve_safe_destination_path(dest_root, item.relative_path)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [
            pool.submit(
                download_object,
                bucket=bucket,
                item=item,
                dest_root=dest_root,
                token_provider=provider,
                urlopen_fn=urlopen_fn,
                max_attempts=max_attempts,
                initial_backoff_seconds=initial_backoff_seconds,
                sleep_fn=sleep_fn,
            )
            for item in items
        ]
        total_bytes = sum(fut.result() for fut in futures)

    elapsed = time.monotonic() - t0
    return len(items), total_bytes, elapsed


def main() -> int:
    """CLI entrypoint invoked by the Pod snapshot cold-start container."""
    bucket = os.environ.get("MODEL_BUCKET_NAME", "").strip()
    model_gcs_dir = os.environ.get("MODEL_GCS_DIR", "").strip()
    dest_root = (
        os.environ.get("MODEL_CACHE_DIR", _DEFAULT_DEST_ROOT).strip()
        or _DEFAULT_DEST_ROOT
    )
    max_workers = int(
        os.environ.get("GCS_STREAMER_MAX_WORKERS", str(_DEFAULT_MAX_WORKERS))
    )
    if not bucket or not model_gcs_dir:
        print(
            "[podsnapshot] MODEL_BUCKET_NAME and MODEL_GCS_DIR must both be "
            "set when running gcs_model_streamer.py.",
            file=sys.stderr,
        )
        return 1

    file_count, total_bytes, elapsed = stream_model_from_gcs(
        bucket=bucket,
        model_gcs_dir=model_gcs_dir,
        dest_root=dest_root,
        max_workers=max_workers,
    )
    total_gib = total_bytes / (1024**3)
    rate_gib_s = total_gib / max(elapsed, 0.001)
    print(
        f"[podsnapshot] Streamed {file_count} files ({total_gib:.2f} GiB) in "
        f"{elapsed:.2f}s ({rate_gib_s:.2f} GiB/s)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
