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

"""Unit tests for the gVisor Actor runner HTTP endpoints and execution bounds."""

import http.client
import json
import os
import threading
import unittest
from http.server import HTTPServer

os.environ.setdefault("RUNNER_ALLOW_MINIMAL_IMPORTS", "1")

import runner  # noqa: E402


class TestRunner(unittest.TestCase):
    server: HTTPServer
    thread: threading.Thread
    port: int

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), runner.RunnerHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def _req(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        headers: dict | None = None,
    ) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            resp = conn.getresponse()
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
        finally:
            conn.close()

    def test_readyz_and_info(self) -> None:
        code, ready = self._req("GET", "/readyz")
        self.assertEqual(code, 200)
        self.assertEqual(ready["status"], "ready")

        code, info = self._req("GET", "/info")
        self.assertEqual(code, 200)
        self.assertIn("kernel_version", info)
        self.assertIn("credential_env_vars_present", info)

    def test_probe_boundary_returns_six_vectors(self) -> None:
        code, data = self._req("POST", "/probe-boundary", b"{}")
        self.assertEqual(code, 200)
        verdicts = data["verdicts"]
        self.assertEqual(len(verdicts), 6)
        self.assertIn("af_packet_raw_socket", verdicts)
        self.assertIn("/proc/kcore", verdicts)

    def test_run_stateful_snippet_and_error_capture(self) -> None:
        code1, res1 = self._req(
            "POST",
            "/run",
            json.dumps({"code": "TEST_STATE = 42; print(TEST_STATE)"}).encode(),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(code1, 200)
        self.assertEqual(res1["exit_code"], 0)
        self.assertEqual(res1["stdout"].strip(), "42")

        code2, res2 = self._req(
            "POST",
            "/run",
            json.dumps({"code": "print(TEST_STATE + 8)"}).encode(),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(code2, 200)
        self.assertEqual(res2["stdout"].strip(), "50")

        code3, res3 = self._req(
            "POST",
            "/run",
            json.dumps({"code": "raise ValueError('boom')"}).encode(),
            {"Content-Type": "application/json"},
        )
        self.assertEqual(code3, 200)
        self.assertEqual(res3["exit_code"], 1)
        self.assertIn("ValueError: boom", res3["stderr"])

    def test_rejects_oversized_payload(self) -> None:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest("POST", "/run")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(runner.MAX_BODY_BYTES + 1024))
            conn.endheaders()
            resp = conn.getresponse()
            self.assertEqual(resp.status, 413)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
