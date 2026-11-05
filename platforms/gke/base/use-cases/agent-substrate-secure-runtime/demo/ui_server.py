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

"""Stateless zero-IAM HTTP & SSE reverse proxy to in-cluster triage-agent-svc.

Used by the optional IAP-protected Cloud Run frontend (Direct VPC Egress) or
local development so zero GCP/GKE IAM roles, kubeconfigs, or CLI binaries are
needed outside the cluster.
"""

import http.client
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

MAX_BODY_BYTES = 1024 * 1024
HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


def resolve_upstream() -> tuple[str, str, int]:
    raw = os.environ.get("UPSTREAM_URL", "http://127.0.0.1:18080").strip()
    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if scheme == "https" else 80)
    return scheme, host, port


class StatelessProxyHandler(BaseHTTPRequestHandler):
    """Forwards HTTP and Server-Sent Events to the in-cluster FastAPI server."""

    protocol_version = "HTTP/1.1"

    def _send_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method: str) -> None:
        if self.path == "/_proxy/healthz":
            self._send_json(200, b'{"status":"ok"}')
            return

        content_len = int(self.headers.get("Content-Length", "0"))
        if content_len > MAX_BODY_BYTES:
            self._send_json(413, b'{"error":"request body exceeds 1 MiB limit"}')
            return
        body = self.rfile.read(content_len) if content_len > 0 else None

        scheme, host, port = resolve_upstream()
        conn_cls = (
            http.client.HTTPSConnection
            if scheme == "https"
            else http.client.HTTPConnection
        )
        conn = conn_cls(host, port, timeout=240)
        fwd_headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower() not in HOP_BY_HOP_HEADERS
            and k.lower() not in ("host", "accept-encoding")
        }
        fwd_headers["Host"] = f"{host}:{port}"
        try:
            conn.request(method, self.path, body=body, headers=fwd_headers)
            resp = conn.getresponse()
            ctype = resp.getheader("Content-Type", "application/octet-stream")
            is_sse = "text/event-stream" in ctype

            self.send_response(resp.status)
            for hk, hv in resp.getheaders():
                if hk.lower() in HOP_BY_HOP_HEADERS or hk.lower() == "content-length":
                    continue
                self.send_header(hk, hv)

            if is_sse:
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                while True:
                    chunk = resp.read(1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                resp_body = resp.read()
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except OSError as exc:
            err = f'{{"error":"upstream unavailable: {exc}"}}'.encode("utf-8")
            self._send_json(502, err)
        finally:
            conn.close()

    def do_GET(self) -> None:  # noqa: N802
        self._proxy("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._proxy("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._proxy("PUT")

    def do_PATCH(self) -> None:  # noqa: N802
        self._proxy("PATCH")

    def do_DELETE(self) -> None:  # noqa: N802
        self._proxy("DELETE")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._proxy("OPTIONS")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> None:
    cloud_port = os.environ.get("PORT")
    host = "0.0.0.0" if cloud_port else os.environ.get("UI_HOST", "127.0.0.1")
    port = int(cloud_port or os.environ.get("UI_PORT", "18090"))
    ThreadingHTTPServer((host, port), StatelessProxyHandler).serve_forever()


if __name__ == "__main__":
    main()
