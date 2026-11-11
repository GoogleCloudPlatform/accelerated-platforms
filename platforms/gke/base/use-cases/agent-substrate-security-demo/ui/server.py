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

"""HTTP server, Host anti-rebinding, HttpOnly cookie auth, and error guards."""

import hashlib
import hmac
import ipaddress
import json
import secrets
import signal
import socket
import subprocess
import sys
import threading
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import acts
import kube
import recovery

UI_DIR = Path(__file__).resolve().parent
SESSION_COOKIE_NAME = "mc_session"
_SESSION_COOKIE_KEY = secrets.token_bytes(32)
_ACTOR_MUTATION_LOCK = threading.Lock()

STATIC_ASSETS: dict[str, tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}


def _startup_local_hostnames() -> frozenset[str]:
    names = {"127.0.0.1", "localhost", "[::1]", "::1"}
    try:
        names.add(socket.gethostname().lower())
        names.add(socket.getfqdn().lower())
    except OSError:
        pass
    return frozenset(name for name in names if name)


_LOCAL_HOSTNAMES: frozenset[str] = _startup_local_hostnames()


def _constant_time_equals(left: str, right: str) -> bool:
    """Compare UTF-8 strings in constant time without non-ASCII TypeError."""
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _normalize_host_entry(host: str) -> set[str]:
    cleaned = host.strip().lower().strip("[]")
    if not cleaned:
        return set()
    try:
        ip = ipaddress.ip_address(cleaned)
        return {str(ip), f"[{ip}]"} if ip.version == 6 else {str(ip)}
    except ValueError:
        return {cleaned}


def is_loopback_host(host: str) -> bool:
    cleaned = host.strip().lower().strip("[]")
    if cleaned == "localhost":
        return True
    try:
        return ipaddress.ip_address(cleaned).is_loopback
    except ValueError:
        return False


def is_wildcard_host(host: str) -> bool:
    cleaned = host.strip().lower().strip("[]")
    try:
        return ipaddress.ip_address(cleaned).is_unspecified
    except ValueError:
        return False


def allowed_hostnames() -> set[str]:
    names = set(_LOCAL_HOSTNAMES)
    if not is_loopback_host(kube.BIND_HOST) and not is_wildcard_host(kube.BIND_HOST):
        names.update(_normalize_host_entry(kube.BIND_HOST))
    for extra in kube.EXTRA_ALLOWED_HOSTS:
        names.update(_normalize_host_entry(extra))
    return names


def is_allowed_host_header(host_header: str) -> bool:
    """Validate the HTTP Host header against DNS-rebinding attacks."""
    raw = (host_header or "").strip().lower()
    if not raw:
        return False
    if raw.startswith("["):
        bracket_end = raw.find("]")
        if bracket_end == -1:
            return False
        hostname = raw[: bracket_end + 1]
    else:
        hostname = raw.split(":", 1)[0]
    return hostname in allowed_hostnames()


def session_cookie_value(ui_token: str) -> str:
    """Derive a per-process HMAC session token so raw secret stays off-cookie."""
    return hmac.new(
        _SESSION_COOKIE_KEY, ui_token.encode("utf-8"), hashlib.sha256
    ).hexdigest()


class MissionControlHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the 4-Act Mission Control web console."""

    MAX_REQUEST_BYTES = 65536
    timeout = 30

    def log_message(self, fmt: str, *args: Any) -> None:
        del fmt, args

    def _send_security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")

    def _send_json(self, data: dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self._send_security_headers()
        self.end_headers()
        self.wfile.write(raw)

    def _has_valid_ui_auth(self) -> bool:
        expected_token = kube.UI_AUTH_TOKEN
        if not expected_token:
            return True

        raw_cookie = self.headers.get("Cookie") or ""
        if raw_cookie:
            jar = SimpleCookie()
            try:
                jar.load(raw_cookie)
                morsel = jar.get(SESSION_COOKIE_NAME)
                if morsel and _constant_time_equals(
                    morsel.value, session_cookie_value(expected_token)
                ):
                    return True
            except CookieError:
                pass

        tok = (self.headers.get("X-UI-Token") or "").strip()
        auth = self.headers.get("Authorization") or ""
        if not tok and auth.startswith("Bearer "):
            tok = auth[len("Bearer ") :].strip()
        return bool(tok and _constant_time_equals(tok, expected_token))

    def _check_request_guards(self) -> bool:
        if not is_allowed_host_header(self.headers.get("Host", "")):
            self._send_json(
                {"error": "Forbidden: untrusted Host header"},
                status=403,
            )
            return False
        if not self._has_valid_ui_auth():
            self._send_json(
                {"error": "Unauthorized: missing or invalid UI_AUTH_TOKEN"},
                status=401,
            )
            return False
        return True

    def _try_token_cookie_exchange(self, parsed: Any) -> bool:
        """Exchange `GET /?token=<secret>` for an HttpOnly SameSite cookie."""
        expected_token = kube.UI_AUTH_TOKEN
        if not expected_token or not parsed.query:
            return False
        qs = parse_qs(parsed.query, keep_blank_values=True)
        if "token" not in qs:
            return False

        if not is_allowed_host_header(self.headers.get("Host", "")):
            self._send_json({"error": "Forbidden: untrusted Host header"}, status=403)
            return True

        candidate = (qs.pop("token")[0] or "").strip()
        if not candidate or not _constant_time_equals(candidate, expected_token):
            self._send_json(
                {"error": "Unauthorized: missing or invalid UI_AUTH_TOKEN"},
                status=401,
            )
            return True

        remaining_query = urlencode(qs, doseq=True)
        safe_path = parsed.path if parsed.path in STATIC_ASSETS else "/"
        clean_target = (
            f"{safe_path}?{remaining_query}" if remaining_query else safe_path
        )

        cookie_val = session_cookie_value(expected_token)
        self.send_response(303)
        self.send_header(
            "Set-Cookie",
            f"{SESSION_COOKIE_NAME}={cookie_val}; HttpOnly; SameSite=Strict; Path=/",
        )
        self.send_header("Location", clean_target)
        self._send_security_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def _read_body_json(self) -> dict[str, Any]:
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Transfer-Encoding is not supported")
        raw_len = self.headers.get("Content-Length", "0") or "0"
        try:
            length = int(raw_len)
        except ValueError as exc:
            raise ValueError(f"Invalid Content-Length header: {raw_len!r}") from exc
        if length < 0:
            raise ValueError(f"Negative Content-Length header: {length}")
        if length == 0:
            return {}
        if length > self.MAX_REQUEST_BYTES:
            raise ValueError(f"Request body exceeds {self.MAX_REQUEST_BYTES} bytes")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed JSON request body: {exc.msg}") from exc
        if not isinstance(parsed, dict):
            raise TypeError("JSON request body must be an object")
        return parsed

    def _dispatch_with_error_guards(
        self, fn: Any, serialize_mutation: bool = False
    ) -> None:
        try:
            if serialize_mutation:
                with _ACTOR_MUTATION_LOCK:
                    result = fn()
            else:
                result = fn()
            self._send_json(result)
        except PermissionError as exc:
            self._send_json({"error": str(exc)}, status=403)
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except subprocess.TimeoutExpired as exc:
            self._send_json(
                {"error": f"Cluster command timed out after {exc.timeout}s"},
                status=504,
            )
        except FileNotFoundError as exc:
            self._send_json(
                {"error": f"Required CLI binary or file not found: {exc}"},
                status=500,
            )
        except (kube.UpstreamCommandError, OSError) as exc:
            self._send_json({"error": str(exc)}, status=502)

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        parsed = urlparse(self.path)
        if self._try_token_cookie_exchange(parsed):
            return
        if not self._check_request_guards():
            return
        if parsed.path in STATIC_ASSETS:
            filename, content_type = STATIC_ASSETS[parsed.path]
            try:
                raw = (UI_DIR / filename).read_bytes()
            except OSError as exc:
                self._send_json({"error": f"Static asset missing: {exc}"}, status=500)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self._send_security_headers()
            self.end_headers()
            self.wfile.write(raw)
            return
        if parsed.path == "/api/status":
            self._dispatch_with_error_guards(recovery.api_status)
            return
        self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        if not self._check_request_guards():
            return
        if self.headers.get("X-Requested-With") != "MissionControl":
            self._send_json(
                {
                    "error": (
                        "Forbidden: missing X-Requested-With: MissionControl header"
                    )
                },
                status=403,
            )
            return

        parsed = urlparse(self.path)
        try:
            body = self._read_body_json()
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/prometheus":
            self._dispatch_with_error_guards(
                lambda: recovery.api_prometheus_metrics(str(body.get("query") or "")),
                serialize_mutation=False,
            )
            return

        mutating_routes: dict[str, Any] = {
            "/api/act2-snapshots": acts.api_act2_snapshots,
            "/api/act3-egress": acts.api_act3_egress_suite,
            "/api/round1-detonate": acts.api_round1_detonate,
            "/api/custom-python": lambda: acts.api_custom_python(body),
            "/api/seed-clean-buddy": recovery.api_seed_clean_buddy,
            "/api/round2-poison": recovery.api_round2_poison,
            "/api/round3-revert-and-trace": recovery.api_round3_revert_and_trace,
        }
        handler_fn = mutating_routes.get(parsed.path)
        if handler_fn is None:
            self._send_json({"error": "Not found"}, status=404)
            return
        self._dispatch_with_error_guards(handler_fn, serialize_mutation=True)


def run_server() -> None:
    """Validate bind configuration, start port-forwards, and serve HTTP."""
    if (
        not is_loopback_host(kube.BIND_HOST)
        and not kube.UI_AUTH_TOKEN
        and not kube.ALLOW_UNAUTHENTICATED_BIND
    ):
        raise SystemExit(
            f"Refusing to bind {kube.BIND_HOST}:{kube.PORT} without "
            "UI_AUTH_TOKEN (set UI_AUTH_TOKEN=<secret> or "
            "ALLOW_UNAUTHENTICATED_BIND=1 behind an authenticated proxy)."
        )
    kube.ensure_port_forwards()
    server = ThreadingHTTPServer((kube.BIND_HOST, kube.PORT), MissionControlHandler)
    signal.signal(
        signal.SIGTERM,
        lambda *_: threading.Thread(target=server.shutdown, daemon=True).start(),
    )
    print(
        "Stage Mode Mission Control listening on "
        f"http://{kube.BIND_HOST}:{kube.PORT}",
        file=sys.stderr,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        kube.stop_spawned_port_forwards()
