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

"""Unit tests for promql_scope."""

import io
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promql_scope  # noqa: E402


class PromqlScopeTest(unittest.TestCase):
    """Tests PromQL and Cloud Monitoring dashboard cluster scoping."""

    def test_bare_metric_and_vector_zero(self) -> None:
        expr = 'sum({"ate.actor.crashes"}) or vector(0)'
        self.assertEqual(
            promql_scope.scope(expr, "demo-cluster"),
            'sum({"ate.actor.crashes", cluster="demo-cluster"}) or vector(0)',
        )
        self.assertEqual(
            promql_scope.scope("max(agent_gateway_actors_tracked)", "demo-cluster"),
            'max(agent_gateway_actors_tracked{cluster="demo-cluster"})',
        )

    def test_classic_and_utf8_selectors(self) -> None:
        self.assertEqual(
            promql_scope.scope(
                'sum by (outcome) (rate(agent_gateway_chat_turns_total{outcome="ok"}[2m]))',
                "c1",
            ),
            'sum by (outcome) (rate(agent_gateway_chat_turns_total{outcome="ok", cluster="c1"}[2m]))',
        )
        utf8_q = 'max by ("ate.worker.state") ({"ate.workerpool.workers", "ate.workerpool.name"="agents"})'
        self.assertEqual(
            promql_scope.scope(utf8_q, "c1"),
            'max by ("ate.worker.state") ({"ate.workerpool.workers", "ate.workerpool.name"="agents", cluster="c1"})',
        )

    def test_existing_cluster_matcher_is_idempotent(self) -> None:
        already_scoped = 'agent_gateway_actors_tracked{cluster="other"}'
        self.assertEqual(
            promql_scope.scope(already_scoped, "c1"),
            already_scoped,
        )

    def test_escape_label_value_and_unterminated_strings(self) -> None:
        self.assertEqual(
            promql_scope.escape_label_value('a"b\\c\nd'),
            'a\\"b\\\\c\\nd',
        )
        self.assertEqual(
            promql_scope.scope("up", 'c"1'),
            'up{cluster="c\\"1"}',
        )
        with self.assertRaises(ValueError):
            promql_scope.scope('{"ate.actor.crashes"', "c1")
        with self.assertRaises(ValueError):
            promql_scope.scope('up{job="unterminated}', "c1")
        with self.assertRaises(ValueError):
            promql_scope.scope('up{job="trailing\\', "c1")

    def test_offset_and_scope_dashboard_with_atespace(self) -> None:
        self.assertEqual(
            promql_scope.scope("agent_gateway_actors_tracked offset 5m", "c1"),
            'agent_gateway_actors_tracked{cluster="c1"} offset 5m',
        )
        dash = {
            "displayName": "Agent Substrate — Security Demo",
            "tiles": [
                {
                    "timeSeriesQuery": {
                        "prometheusQuery": "max(agent_gateway_actors_tracked)"
                    }
                },
                {
                    "logsPanel": {
                        "filter": (
                            'resource.type="k8s_container"\n'
                            'jsonPayload."ate.atespace"="security-demo"'
                        )
                    }
                },
            ],
        }
        scoped = promql_scope.scope_dashboard(dash, "my-cluster", "custom-space")
        self.assertEqual(
            scoped["displayName"],
            "Agent Substrate — Security Demo (my-cluster)",
        )
        self.assertEqual(
            scoped["tiles"][0]["timeSeriesQuery"]["prometheusQuery"],
            'max(agent_gateway_actors_tracked{cluster="my-cluster"})',
        )
        log_filter = scoped["tiles"][1]["logsPanel"]["filter"]
        self.assertIn('resource.labels.cluster_name="my-cluster"', log_filter)
        self.assertIn('jsonPayload."ate.atespace"="custom-space"', log_filter)

        # Idempotent second pass on displayName and logsPanel
        rescoped = promql_scope.scope_dashboard(scoped, "my-cluster", "custom-space")
        self.assertEqual(rescoped["displayName"], scoped["displayName"])
        self.assertEqual(
            rescoped["tiles"][1]["logsPanel"]["filter"],
            log_filter,
        )

    def test_empty_selector_floats_and_cli_main(self) -> None:
        self.assertEqual(
            promql_scope.scope("{} + 1.5e-3", "c1"),
            '{cluster="c1"} + 1.5e-3',
        )
        out_q = io.StringIO()
        with mock.patch("sys.stdout", out_q):
            promql_scope.main(["promql_scope.py", "query", "c1", "up"])
        self.assertEqual(out_q.getvalue().strip(), 'up{cluster="c1"}')

        in_d = io.StringIO(json.dumps({"displayName": "Dash", "prometheusQuery": "up"}))
        out_d = io.StringIO()
        with mock.patch("sys.stdin", in_d), mock.patch("sys.stdout", out_d):
            promql_scope.main(["promql_scope.py", "dashboard", "c1", "space-a"])
        parsed = json.loads(out_d.getvalue())
        self.assertEqual(parsed["prometheusQuery"], 'up{cluster="c1"}')
        self.assertEqual(parsed["displayName"], "Dash (c1)")


if __name__ == "__main__":
    unittest.main()
