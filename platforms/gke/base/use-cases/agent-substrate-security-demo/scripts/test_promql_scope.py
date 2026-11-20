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
# cspell:words econnrefused ehostunreach hmac

"""Unit tests for promql_scope plus static CI checks on scripts & templates."""

import base64
import errno
import io
import json
import subprocess
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
for _p in (str(BASE_DIR / "ui"), str(BASE_DIR / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import acts
import kube
import probes
import promql_scope
import recovery
import server


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
            sh_text = sh_file.read_text(encoding="utf-8")
            self.assertNotIn(
                "network~(^|/)",
                sh_text,
                f"Unquoted gcloud --filter regex group in {sh_file}",
            )

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
            self._assert_egress_rules_are_scoped(tmpl, docs)

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

    def _assert_egress_rules_are_scoped(self, tmpl: Path, docs: list[object]) -> None:
        """No egress rule may match every destination or reach private ranges."""
        private_ranges = {
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
            "100.64.0.0/10",
            "169.254.0.0/16",
        }
        for doc in docs:
            if not isinstance(doc, dict) or doc.get("kind") != "NetworkPolicy":
                continue
            for rule in doc.get("spec", {}).get("egress") or []:
                peers = rule.get("to") or []
                self.assertTrue(
                    peers, f"{tmpl}: egress rule without `to` allows every destination"
                )
                for peer in peers:
                    block = peer.get("ipBlock") or {}
                    if block.get("cidr") == "0.0.0.0/0":
                        self.assertLessEqual(
                            private_ranges, set(block.get("except") or []), str(tmpl)
                        )
                # Option B enables GKE NodeLocal DNSCache (169.254.20.10:53) or
                # Cloud DNS for GKE (169.254.169.254:53) outside kube-system pods.
                if 53 in {port.get("port") for port in rule.get("ports") or []}:
                    cidrs = {(peer.get("ipBlock") or {}).get("cidr") for peer in peers}
                    self.assertIn("169.254.20.10/32", cidrs, str(tmpl))
                    self.assertIn("169.254.169.254/32", cidrs, str(tmpl))

    def test_act4_custom_prompt_gates_and_non_poison_session_mutation(self) -> None:
        with mock.patch.object(kube, "ALLOW_CUSTOM_PYTHON", False):
            self.assertEqual(
                probes.resolve_act4_prompt({"prompt": "  "}),
                (probes.DEFAULT_POISON_PROMPT, False),
            )
            with self.assertRaises(PermissionError):
                probes.resolve_act4_prompt({"prompt": "What is our approval policy?"})

        with mock.patch.object(kube, "ALLOW_CUSTOM_PYTHON", True):
            with self.assertRaises(ValueError):
                probes.resolve_act4_prompt({"prompt": "p" * 2001})

            actors = [{"name": "gemini-agent", "state": "RUNNING", "worker_pod": "p0"}]
            clean_pol = {
                "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
                "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
            }
            custom_states = iter(
                [
                    {**clean_pol, "memCount": 1, "diskCount": 1},
                    {"reply": "Current approval policy is REQUIRE_HUMAN_APPROVAL."},
                    {**clean_pol, "memCount": 2, "diskCount": 2},
                ]
            )
            with (
                mock.patch.object(kube, "ensure_port_forwards"),
                mock.patch.object(kube, "get_actors", return_value=(actors, "")),
                mock.patch.object(
                    kube,
                    "http_json",
                    side_effect=lambda *_a, **_kw: next(custom_states),
                ),
            ):
                res = recovery.api_round2_poison({"prompt": "What is our policy?"})
                self.assertTrue(res["is_custom_prompt"])
                self.assertTrue(res["session_mutated"])
                self.assertEqual(res["brain"]["verdict"], "CLEAN")
                self.assertIn("REQUIRE_HUMAN_APPROVAL", res["verification_reply"])

            bypass = {"approvalPolicy": "BYPASS_REVIEW", "diskPolicy": "BYPASS_REVIEW"}
            with mock.patch.object(kube, "get_actors", return_value=(actors, "")):
                self.assertEqual(
                    probes.inspect_buddy_brain(pre_state=bypass)["verdict"], "POISONED"
                )

        srv = ThreadingHTTPServer(("127.0.0.1", 0), server.MissionControlHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{srv.server_address[1]}/api/round2-poison",
                data=b'{"prompt":"custom"}',
                headers={"X-Requested-With": "MissionControl"},
                method="POST",
            )
            with (
                mock.patch.object(kube, "ALLOW_CUSTOM_PYTHON", False),
                self.assertRaises(urllib.error.HTTPError) as ctx_403,
            ):
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx_403.exception.code, 403)
        finally:
            srv.shutdown()
            srv.server_close()

    def test_e2e_verdict_signatures_secret_leak_and_exit_code_guards(self) -> None:
        def _run_act1_meta(side_eff: Exception) -> dict[str, object]:
            fake_libc = mock.MagicMock()
            fake_libc.mount.return_value = -1
            buf = io.StringIO()
            with (
                mock.patch("urllib.request.urlopen", side_effect=side_eff),
                mock.patch("ctypes.CDLL", return_value=fake_libc),
                mock.patch("ctypes.set_errno"),
                mock.patch("ctypes.get_errno", return_value=errno.EPERM),
                mock.patch("os.stat", return_value=mock.MagicMock(st_mode=0o40777)),
                mock.patch("builtins.open", side_effect=PermissionError("blocked")),
                mock.patch("sys.stdout", buf),
            ):
                exec(  # noqa: S102
                    probes.ROUND1_PYTHON_SCRIPT, {"__name__": "__probe__"}
                )
            return json.loads(buf.getvalue().strip())

        no_route = urllib.error.URLError(
            OSError(errno.EHOSTUNREACH, "No route to host")
        )
        ok_out = _run_act1_meta(no_route)
        self.assertIs(ok_out["metadata_blocked"], True)
        self.assertIn("EHOSTUNREACH", str(ok_out["gke_metadata"]))

        for err_case in (
            TimeoutError("timed out"),
            urllib.error.URLError(OSError(errno.ECONNREFUSED, "Connection refused")),
        ):
            inc_out = _run_act1_meta(err_case)
            self.assertIsNone(inc_out["metadata_blocked"])
            self.assertIn("INCONCLUSIVE", str(inc_out["gke_metadata"]))

        transient_dns = {
            "status": 502,
            "error": (
                'HTTP 502: fetch: Get "https://example.com/": '
                "<urlopen error [Errno -3] Temporary failure in name resolution>"
            ),
        }
        with self.assertRaises(kube.UpstreamCommandError):
            probes.verify_dns_block_response(transient_dns, "https://example.com/")

        b64_tok = base64.b64encode(b"live-secret-val").decode("ascii")
        with mock.patch.object(kube, "run_cmd", return_value=(b64_tok, "", 0)):
            self.assertEqual(probes.read_example_api_secret(), "live-secret-val")
        with (
            mock.patch.object(kube, "run_cmd", return_value=("!bad!", "", 0)),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            probes.read_example_api_secret()

        leak_http = [
            {
                "authenticated": True,
                "placeholder_replaced": True,
                "raw_secret_returned": False,
                "credential_hmac_prefix": "hmac-sha256:0123456789ab",
                "debug": "Bearer live-secret-val",
            }
        ]
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(
                probes, "read_example_api_secret", return_value="live-secret-val"
            ),
            mock.patch.object(kube, "http_json", side_effect=leak_http),
            mock.patch.object(probes, "suspend_actor_best_effort"),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_act3_egress_suite()

        post_b_fail = iter(
            [
                {
                    "authenticated": True,
                    "placeholder_replaced": True,
                    "credential_hmac_prefix": "hmac-sha256:0123456789ab",
                },
                {
                    "status": 502,
                    "error": (
                        'HTTP 502: fetch: Get "https://example.com/": '
                        "<urlopen error [Errno -2] Name or service not known>"
                    ),
                },
                {"error": "HTTP 502: resolver dead"},
            ]
        )
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(
                probes, "read_example_api_secret", return_value="live-secret-val"
            ),
            mock.patch.object(
                kube, "http_json", side_effect=lambda *_a, **_k: next(post_b_fail)
            ),
            mock.patch.object(probes, "suspend_actor_best_effort"),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_act3_egress_suite()

        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "http_json", return_value={"stdout": "hi"}),
            mock.patch.object(kube, "suspend_actor_checked", return_value="ok"),
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_custom_python({"probe_id": 0})

    def test_act2_poison_guard_tag_reset_and_post_no_replay(self) -> None:
        running_actors = ([{"name": "gemini-agent", "state": "RUNNING"}], "")
        poisoned_state = {
            "approvalPolicy": "AUTO_APPROVE_ALL",
            "diskPolicy": "AUTO_APPROVE_ALL",
            "bootID": "deadbeef",
        }
        clean_state = {
            "approvalPolicy": "REQUIRE_HUMAN_APPROVAL",
            "diskPolicy": "REQUIRE_HUMAN_APPROVAL",
            "memCount": 1,
            "diskCount": 1,
            "bootID": "cafebabe",
        }
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=running_actors),
            mock.patch.object(kube, "http_json", return_value=poisoned_state),
            mock.patch.object(kube, "suspend_actor_checked") as mock_suspend,
            self.assertRaises(kube.UpstreamCommandError),
        ):
            acts.api_prologue_race()
        mock_suspend.assert_not_called()

        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=running_actors),
            mock.patch.object(
                kube, "run_cmd", return_value=("Trace ID: " + "b" * 32, "", 0)
            ),
            mock.patch.object(kube, "http_json", return_value=poisoned_state),
            mock.patch.object(probes, "revert_actor_best_effort") as mock_rev,
            mock.patch.object(probes, "suspend_actor_best_effort") as mock_susp,
            self.assertRaises(kube.UpstreamCommandError),
        ):
            recovery.api_round3_revert_and_trace()
        mock_rev.assert_called_once_with("gemini-agent")
        mock_susp.assert_not_called()

        suspended_actors = ([{"name": "gemini-agent", "state": "SUSPENDED"}], "")
        states = iter([poisoned_state, clean_state])
        with (
            mock.patch.object(kube, "ensure_port_forwards"),
            mock.patch.object(kube, "get_actors", return_value=suspended_actors),
            mock.patch.object(kube, "run_cmd", return_value=("Ready", "", 0)),
            mock.patch.object(
                probes,
                "recreate_actor_from_tag",
                return_value=("create --tag clean-checkpoint-tag", "recreated"),
            ) as mock_recreate,
            mock.patch.object(
                kube, "http_json", side_effect=lambda *_a, **_k: next(states)
            ),
            mock.patch.object(kube, "suspend_actor_checked", return_value="ok"),
        ):
            healed = recovery.api_seed_clean_buddy()
        mock_recreate.assert_called_once_with("gemini-agent")
        self.assertEqual(healed["brain"]["verdict"], "CLEAN")

        # POST requests must not replay after a read TimeoutError
        gw_url = f"http://127.0.0.1:{kube.GATEWAY_PORT}/chat/gemini-agent"
        with (
            mock.patch.object(kube, "ensure_port_forwards") as mock_pf,
            mock.patch.object(kube, "_get_gateway_admin_token", return_value="tok"),
            mock.patch.object(
                kube._HTTP_OPENER, "open", side_effect=TimeoutError("read timed out")
            ) as mock_open,
        ):
            err_doc = kube.http_json(gw_url, method="POST", body={"message": "hi"})
        self.assertIn("TimeoutError", err_doc["error"])
        self.assertEqual(mock_open.call_count, 1)
        mock_pf.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
