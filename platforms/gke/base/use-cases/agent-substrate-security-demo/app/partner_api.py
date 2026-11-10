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

"""Cluster-local non-reflecting credential verification service for Act 3.

Runs inside the isolated secrets namespace (`SECRETS_NAMESPACE`) with NetworkPolicy
allowing ingress solely from `atenet-egress` (`ns/ate-system`). Verifies that
`atenet-egress` replaced the sandbox's `Authorization: Bearer placeholder` header
with the real `Secret/example-api` credential, and returns ONLY a boolean status
plus a truncated SHA-256 fingerprint — never echoing the raw secret back to the
sandbox or transmitting it to any external third party.
"""

import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

EXPECTED_TOKEN = os.environ.get("EXPECTED_API_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", "8080"))


def evaluate_authorization(
    auth_header: str, expected_token: str
) -> tuple[int, dict[str, Any]]:
    """Verify the inbound Authorization header without reflecting the secret."""
    if not expected_token:
        return 500, {
            "authenticated": False,
            "error": "EXPECTED_API_TOKEN is not configured",
            "raw_secret_returned": False,
        }
    expected_header = f"Bearer {expected_token}"
    placeholder_replaced = auth_header.strip() != "Bearer placeholder" and bool(
        auth_header.strip()
    )
    matched = hmac.compare_digest(auth_header.strip(), expected_header)
    digest_prefix = hashlib.sha256(expected_token.encode("utf-8")).hexdigest()[:12]
    if not matched:
        return 401, {
            "authenticated": False,
            "placeholder_replaced": placeholder_replaced,
            "raw_secret_returned": False,
        }
    return 200, {
        "authenticated": True,
        "placeholder_replaced": True,
        "credential_sha256_prefix": f"sha256:{digest_prefix}",
        "raw_secret_returned": False,
    }


class PartnerAPIHandler(BaseHTTPRequestHandler):
    """Minimal non-reflecting HTTP handler for credential-injection verification."""

    def log_message(self, fmt: str, *args: Any) -> None:
        pass

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        if self.path == "/readyz":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/verify"):
            auth = self.headers.get("Authorization", "")
            status, payload = evaluate_authorization(auth, EXPECTED_TOKEN)
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_response(404)
        self.end_headers()


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), PartnerAPIHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
