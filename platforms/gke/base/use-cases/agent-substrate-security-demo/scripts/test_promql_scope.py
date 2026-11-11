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

"""Unit tests for promql_scope plus static CI checks on scripts & templates."""

import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promql_scope


class PromqlScopeTest(unittest.TestCase):
    """Tests PromQL/dashboard scoping and validates shipped `.sh`/`.yaml.tmpl`."""

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

    def test_classic_utf8_uppercase_trailing_comma_and_comments(self) -> None:
        self.assertEqual(
            promql_scope.scope(
                "sum by (outcome) "
                '(rate(agent_gateway_chat_turns_total{outcome="ok"}[2m]))',
                "c1",
            ),
            (
                "sum by (outcome) (rate(agent_gateway_chat_turns_total"
                '{outcome="ok", cluster="c1"}[2m]))'
            ),
        )
        utf8_q = (
            'max by ("ate.worker.state") '
            '({"ate.workerpool.workers", "ate.workerpool.name"="agents"})'
        )
        self.assertEqual(
            promql_scope.scope(utf8_q, "c1"),
            (
                'max by ("ate.worker.state") ({"ate.workerpool.workers", '
                '"ate.workerpool.name"="agents", cluster="c1"})'
            ),
        )
        # Uppercase SUM BY, trailing selector comma, quoted cluster=, and # comment
        self.assertEqual(
            promql_scope.scope("SUM BY (job) (up{job='a',})", "c1"),
            "SUM BY (job) (up{job='a', cluster=\"c1\"})",
        )
        self.assertEqual(
            promql_scope.scope('err_total{msg="bad cluster=x"}', "c1"),
            'err_total{msg="bad cluster=x", cluster="c1"}',
        )
        commented = "# actor's latency\nup OFFSET 5m"
        self.assertEqual(
            promql_scope.scope(commented, "c1"),
            '# actor\'s latency\nup{cluster="c1"} OFFSET 5m',
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

    def test_offset_time_series_filter_and_scope_dashboard(self) -> None:
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
                    "timeSeriesQuery": {
                        "timeSeriesFilter": {
                            "filter": 'resource.type="prometheus_target"'
                        }
                    }
                },
                {
                    "title": "Actor state changes (logs, security-demo atespace)",
                    "logsPanel": {
                        "filter": (
                            'resource.type="k8s_container"\n'
                            'jsonPayload."ate.atespace"="security-demo"'
                        )
                    },
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
        self.assertIn(
            'resource.labels.cluster="my-cluster"',
            scoped["tiles"][1]["timeSeriesQuery"]["timeSeriesFilter"]["filter"],
        )
        self.assertIn("custom-space atespace", scoped["tiles"][2]["title"])
        log_filter = scoped["tiles"][2]["logsPanel"]["filter"]
        self.assertIn('resource.labels.cluster_name="my-cluster"', log_filter)
        self.assertIn('jsonPayload."ate.atespace"="custom-space"', log_filter)

        rescoped = promql_scope.scope_dashboard(scoped, "my-cluster", "custom-space")
        self.assertEqual(rescoped["displayName"], scoped["displayName"])

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

    def test_shipped_dashboards_manifests_and_shell_scripts_parse_cleanly(
        self,
    ) -> None:
        use_case_dir = Path(__file__).resolve().parent.parent
        for sh_file in sorted(use_case_dir.rglob("*.sh")):
            if ".state" in sh_file.parts:
                continue
            res = subprocess.run(
                ["bash", "-n", str(sh_file)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"{sh_file}: {res.stderr}")

        substitutions = {
            "${NAMESPACE}": "agent-sandbox",
            "${SECRETS_NAMESPACE}": "agent-secrets",
            "${ATESPACE}": "security-demo",
            "${WORKER_IMAGE}": (
                "ghcr.io/agent-substrate/substrate/ateworker-gvisor:v1.0.0"
                "@sha256:" + "a" * 64
            ),
            "${GATEWAY_IMAGE}": (
                "us-east4-docker.pkg.dev/proj/repo/app:v1@sha256:" + "b" * 64
            ),
            "${AGENT_IMAGE}": (
                "us-east4-docker.pkg.dev/proj/repo/app:v1@sha256:" + "b" * 64
            ),
            "${GATEWAY_CODE_SHA}": "c" * 64,
            "${GEMINI_MODEL}": "gemini-3.8-flash",
            "${PROJECT_ID}": "demo-project",
        }
        for tmpl in sorted((use_case_dir / "manifests").glob("*.yaml.tmpl")):
            rendered = tmpl.read_text(encoding="utf-8")
            for placeholder, value in substitutions.items():
                rendered = rendered.replace(placeholder, value)
            self.assertNotIn("${", rendered, f"Unexpanded placeholder in {tmpl}")
            docs = [doc for doc in yaml.safe_load_all(rendered) if doc is not None]
            self.assertGreater(len(docs), 0, f"Empty YAML in {tmpl}")

        for dash_path in sorted((use_case_dir / "observability").rglob("*.json")):
            raw_dash = json.loads(dash_path.read_text(encoding="utf-8"))
            scoped = promql_scope.scope_dashboard(raw_dash, "ci-cluster", "ci-space")
            for tile in scoped.get("mosaicLayout", {}).get("tiles", []):
                widget = tile.get("widget", {})
                for ds in widget.get("xyChart", {}).get("dataSets", []):
                    tsq = ds.get("timeSeriesQuery", {})
                    if "prometheusQuery" in tsq:
                        self.assertIn(
                            'cluster="ci-cluster"',
                            tsq["prometheusQuery"],
                            str(dash_path),
                        )
                    if "timeSeriesFilter" in tsq:
                        self.assertIn(
                            'resource.labels.cluster="ci-cluster"',
                            tsq["timeSeriesFilter"]["filter"],
                            str(dash_path),
                        )


if __name__ == "__main__":
    unittest.main()
