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

"""Actor runner workload for 'The Secure Runtime' on Agent Substrate.

Pre-imports heavy scientific libraries (numpy, pandas, scipy, matplotlib, httpx)
before answering /readyz so that Agent Substrate's Golden Snapshot captures the
warm Python interpreter memory image. Restored actors wake with all libraries
already resident in RAM and zero credentials in the environment.
"""

import contextlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
import os
import platform
import time
import traceback

_BOOT_START = time.monotonic()

import httpx  # noqa: E402
import matplotlib  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import scipy  # noqa: E402
import scipy.stats  # noqa: E402

matplotlib.use("Agg")
_WARM_IMPORT_MS = round((time.monotonic() - _BOOT_START) * 1000, 2)

# Persistent execution namespace across requests to the same actor instance.
_EXEC_GLOBALS = {
    "__builtins__": __builtins__,
    "np": np,
    "pd": pd,
    "scipy": scipy,
    "matplotlib": matplotlib,
    "httpx": httpx,
}


def _read_proc_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError as exc:
        return f"<unavailable: {exc}>"


def _collect_sandbox_info() -> dict:
    status_text = _read_proc_file("/proc/self/status")
    cap_eff = ""
    for line in status_text.splitlines():
        if line.startswith("CapEff:"):
            cap_eff = line.split(":", 1)[1].strip()
            break

    secret_env_keys = [
        k
        for k in os.environ
        if any(
            token in k.upper()
            for token in ("TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL")
        )
    ]

    return {
        "kernel_version": _read_proc_file("/proc/version"),
        "uname": platform.uname()._asdict(),
        "uid": os.getuid(),
        "gid": os.getgid(),
        "cap_eff": cap_eff,
        "warm_import_ms_at_boot": _WARM_IMPORT_MS,
        "preloaded_modules": {
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
            "httpx": httpx.__version__,
        },
        "credential_env_vars_present": secret_env_keys,
        "ssl_cert_dir": os.environ.get("SSL_CERT_DIR", ""),
    }


class RunnerHandler(BaseHTTPRequestHandler):
    """HTTP handler for wakeupProbe (/readyz), boundary inspection (/info), and execution (/run)."""

    def _send_json(self, status_code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/readyz", "/healthz"):
            self._send_json(
                200,
                {
                    "status": "ready",
                    "warm_import_ms": _WARM_IMPORT_MS,
                },
            )
            return

        if self.path in ("/info", "/boundary"):
            self._send_json(200, _collect_sandbox_info())
            return

        if self.path == "/fs-state":
            state_file = "/tmp/triage-state.json"
            if os.path.exists(state_file):
                with open(state_file, "r", encoding="utf-8") as fh:
                    self._send_json(200, json.load(fh))
            else:
                self._send_json(200, {"exists": False})
            return

        self._send_json(404, {"error": f"unknown path: {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        content_len = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            request_data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"invalid JSON: {exc}"})
            return

        if self.path == "/fs-state":
            state_file = "/tmp/triage-state.json"
            with open(state_file, "w", encoding="utf-8") as fh:
                json.dump(request_data, fh)
            self._send_json(200, {"saved": True, "path": state_file, "state": request_data})
            return

        if self.path == "/egress-test":
            method = str(request_data.get("method", "GET")).upper()
            url = str(request_data.get("url", ""))
            headers = request_data.get("headers") or {}
            req_body = request_data.get("body")
            t0 = time.monotonic()
            try:
                with httpx.Client(timeout=10.0) as client:
                    resp = client.request(method, url, headers=headers, content=req_body)
                self._send_json(
                    200,
                    {
                        "method": method,
                        "url": url,
                        "status_code": resp.status_code,
                        "duration_ms": round((time.monotonic() - t0) * 1000, 2),
                        "response_preview": resp.text[:400],
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_json(
                    200,
                    {
                        "method": method,
                        "url": url,
                        "blocked_or_failed": True,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "duration_ms": round((time.monotonic() - t0) * 1000, 2),
                    },
                )
            return

        if self.path not in ("/run", "/exec"):
            self._send_json(404, {"error": f"unknown path: {self.path}"})
            return

        code = request_data.get("code", "")
        if not isinstance(code, str) or not code.strip():
            self._send_json(400, {"error": "field 'code' is required"})
            return

        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        exec_start = time.monotonic()
        exit_code = 0

        try:
            with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(
                stderr_buf
            ):
                exec(compile(code, "<actor-sandbox>", "exec"), _EXEC_GLOBALS)
        except SystemExit as exc:
            exit_code = int(exc.code) if isinstance(exc.code, int) else 1
        except Exception:  # noqa: BLE001
            exit_code = 1
            traceback.print_exc(file=stderr_buf)

        duration_ms = round((time.monotonic() - exec_start) * 1000, 2)
        self._send_json(
            200,
            {
                "exit_code": exit_code,
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
                "duration_ms": duration_ms,
                "warm_import_ms_saved": _WARM_IMPORT_MS,
            },
        )

    def log_message(self, fmt: str, *args) -> None:
        return


def main() -> None:
    port = int(os.environ.get("PORT", "80"))
    # Configure default CA bundle if Substrate's egress MITM trust bundle is mounted.
    trust_bundle = "/run/ate/egress-trust-bundle/trust-bundle.pem"
    if os.path.exists(trust_bundle):
        os.environ.setdefault("SSL_CERT_FILE", trust_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", trust_bundle)

    server = HTTPServer(("0.0.0.0", port), RunnerHandler)
    print(
        f"[secure-runtime-runner] Listening on :{port} "
        f"(preloaded scientific stack in {_WARM_IMPORT_MS} ms)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
