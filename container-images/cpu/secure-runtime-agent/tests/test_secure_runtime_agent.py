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

"""Unit tests for secure_runtime_agent policy gate, mTLS, K8s, and telemetry."""

import asyncio
import unittest
from unittest.mock import MagicMock, patch

from secure_runtime_agent import agent
from secure_runtime_agent.k8s_client import InClusterK8sClient
from secure_runtime_agent.substrate_client import (
    SubstrateClient,
    classify_tool_intent,
)
from secure_runtime_agent.telemetry import TerminalBus


class TestSecureRuntimeAgent(unittest.TestCase):
    def test_classify_tool_intent_github_vs_offline(self) -> None:
        gh = classify_tool_intent(
            "triage_github_issue_in_sandbox",
            declared_purpose="triage issue #42",
            github_repo="/GoogleCloudPlatform/accelerated-platforms/",
        )
        self.assertEqual(gh.intent_name, "github_issue_read_only")
        self.assertTrue(gh.requires_network)
        self.assertEqual(gh.allowed_hosts, ["api.github.com"])
        self.assertEqual(gh.allowed_methods, ["GET", "HEAD"])
        self.assertEqual(
            gh.allowed_path_prefixes,
            ["/repos/GoogleCloudPlatform/accelerated-platforms/"],
        )
        self.assertTrue(gh.secret_uri.startswith("ate-secret://"))

        offline = classify_tool_intent(
            "run_python_in_actor", declared_purpose="compute eigenvalues"
        )
        self.assertEqual(offline.intent_name, "offline_compute_only")
        self.assertFalse(offline.requires_network)
        self.assertEqual(offline.allowed_hosts, [])

    def test_mtls_context_fails_closed_when_bundles_missing(self) -> None:
        client = SubstrateClient()
        client.podidentity_cert = "/nonexistent/podidentity.pem"
        client.servicedns_ca = "/nonexistent/servicedns-ca.pem"
        with self.assertRaises(FileNotFoundError):
            client._build_mtls_context()

    def test_before_tool_intent_gate_fails_closed_on_error(self) -> None:
        fake_tool = MagicMock()
        fake_tool.name = "run_python_in_actor"
        fake_ctx = MagicMock()
        fake_ctx.state = {}

        with patch.object(
            agent,
            "_sync_intent_policy",
            side_effect=RuntimeError("extproc connection refused"),
        ):
            res = agent._before_tool_intent_gate(
                fake_tool, {"actor_name": "triage-actor-1"}, fake_ctx
            )

        self.assertIsInstance(res, dict)
        assert res is not None
        self.assertEqual(res["status"], "blocked")
        self.assertIn("fail-closed", res["error"])
        self.assertEqual(fake_ctx.state["last_intent_classification"], res)

    def test_before_tool_intent_gate_allows_when_policy_synced(self) -> None:
        fake_tool = MagicMock()
        fake_tool.name = "triage_github_issue_in_sandbox"
        fake_ctx = MagicMock()
        fake_ctx.state = {}
        synced_payload = {"intent_name": "github_issue_read_only"}

        with patch.object(agent, "_sync_intent_policy", return_value=synced_payload):
            res = agent._before_tool_intent_gate(
                fake_tool, {"actor_name": "triage-actor-42"}, fake_ctx
            )

        self.assertIsNone(res)
        self.assertEqual(fake_ctx.state["last_intent_classification"], synced_payload)

    def test_k8s_tail_rejects_unallowlisted_source(self) -> None:
        k8s = InClusterK8sClient()
        with self.assertRaises(ValueError):
            k8s.tail_ate_system_logs("kube-apiserver")

    def test_terminal_bus_ring_buffer_and_async_subscriber(self) -> None:
        bus = TerminalBus(max_events=50)
        bus.emit("cmd", "$ kubectl-ate get actors", step="0", duration_ms=12.3)
        self.assertEqual(len(bus.recent()), 1)

        async def _check_sub() -> dict:
            backlog, queue = bus.subscribe()
            try:
                self.assertEqual(len(backlog), 1)
                bus.emit("verdict", "[#1] 6/6 blocked", step="1")
                return await asyncio.wait_for(queue.get(), timeout=2.0)
            finally:
                bus.unsubscribe(queue)

        ev = asyncio.run(_check_sub())
        self.assertEqual(ev["kind"], "verdict")
        self.assertIn("6/6 blocked", ev["text"])


if __name__ == "__main__":
    unittest.main()
