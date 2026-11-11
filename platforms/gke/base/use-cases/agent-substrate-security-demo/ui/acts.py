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

"""Acts 1–3 sandbox detonation, snapshot cloning, and egress suite APIs."""

import base64
import json
import re
import tempfile
import time
from typing import Any
from urllib.parse import urlencode

import kube
import probes


def api_prologue_race() -> dict[str, Any]:
    """Run a live suspend -> resume cycle on gemini-agent and report timings."""
    t0 = time.monotonic()
    kube.ensure_port_forwards()
    clean_s_out = kube.suspend_actor_checked("gemini-agent", timeout=20)

    t_resume0 = time.monotonic()
    resume_args = [
        "kubectl",
        "ate",
        "--trace",
        "resume",
        "actor",
        "gemini-agent",
        "-a",
        kube.ATESPACE,
    ]
    out, err, rc = kube.run_cmd(resume_args, timeout=25)
    cli_resume_ms = round((time.monotonic() - t_resume0) * 1000, 1)
    combined = kube.strip_ate_warnings(f"{out}\n{err}")
    if rc != 0:
        raise kube.UpstreamCommandError(f"Failed to resume gemini-agent: {combined}")

    m = re.search(r"Trace ID:\s*([0-9a-f]{32})", combined)
    trace_id = m.group(1) if m else ""

    state_resp = kube.http_json(
        f"{kube.GATEWAY_URL}/actors/gemini-agent/state", timeout=10.0
    )
    if state_resp.get("error"):
        raise kube.UpstreamCommandError(
            f"Failed to read gemini-agent state: {state_resp['error']}"
        )

    kube.suspend_actor_checked("gemini-agent", timeout=20)
    susp_cmd = f"kubectl ate suspend actor gemini-agent -a {kube.ATESPACE}"
    res_cmd = f"kubectl ate --trace resume actor gemini-agent -a {kube.ATESPACE}"

    return {
        "local_restore_avg_ms": kube.query_restore_ms(kind="local", phase="total"),
        "gcs_restore_avg_ms": kube.query_restore_ms(kind="latest", phase="total"),
        "cli_roundtrip_resume_ms": cli_resume_ms,
        "trace_id": trace_id,
        "buddy_boot_id": state_resp.get("bootID") or "n/a",
        "buddy_state": state_resp,
        "summary_cmd": f"{susp_cmd} && {res_cmd}",
        "under_the_hood": [
            {
                "step": (
                    "2. Suspend Actor 'gemini-agent' "
                    "(checkpoints gVisor RAM + /data to GCS zstd snapshot)"
                ),
                "cmd": susp_cmd,
                "output": clean_s_out,
            },
            {
                "step": (
                    "3. Resume Actor 'gemini-agent' with OpenTelemetry "
                    "distributed tracing (--trace)"
                ),
                "cmd": res_cmd,
                "output": combined,
            },
        ],
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def api_round1_detonate() -> dict[str, Any]:
    """Execute the 6-point gVisor boundary probe inside py-detonation-agent."""
    t0 = time.monotonic()
    kube.ensure_port_forwards()
    meta = kube.detect_cluster_meta()
    b64 = base64.b64encode(probes.ROUND1_PYTHON_SCRIPT.encode("utf-8")).decode("ascii")
    cmd_str = f"python3 -c \"import base64; exec(base64.b64decode('{b64}'))\""
    resp = kube.http_json(
        f"{kube.GATEWAY_URL}/actors/py-detonation-agent/execute",
        method="POST",
        body={"command": cmd_str},
        timeout=25.0,
    )
    if resp.get("error"):
        raise kube.UpstreamCommandError(
            f"Act 1 detonation probe failed: {resp['error']}"
        )
    suspend_msg = kube.suspend_actor_checked("py-detonation-agent", timeout=20)

    stdout = (resp.get("stdout") or "").strip()
    parsed: dict[str, Any] = {}
    for line in reversed(stdout.splitlines()):
        if line.strip().startswith("{"):
            try:
                parsed = json.loads(line.strip())
                break
            except json.JSONDecodeError:
                continue
    if not parsed:
        raise kube.UpstreamCommandError(
            f"Act 1 probe did not return structured JSON output: {stdout or resp}"
        )

    readable_cmd = (
        f"curl -fsS -X POST {kube.GATEWAY_URL}/actors/py-detonation-agent/execute "
        '-H @admin-hdr.txt -d \'{"command": "python3 -c <6-vector-probe>"}\''
    )
    return {
        "actor": f"{kube.ATESPACE}/py-detonation-agent",
        "host_kernel": meta["host_kernel"],
        "probes": parsed,
        "summary_cmd": readable_cmd,
        "under_the_hood": [
            {
                "step": (
                    "1. Wake Actor 'py-detonation-agent' via mTLS router "
                    "& run 6-point Python probe"
                ),
                "cmd": readable_cmd,
                "output": json.dumps(parsed, indent=2),
            },
            {
                "step": "2. Suspend 'py-detonation-agent' back to Cloud Storage",
                "cmd": (
                    f"kubectl ate suspend actor py-detonation-agent -a {kube.ATESPACE}"
                ),
                "output": suspend_msg,
            },
        ],
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def api_custom_python(body: dict[str, Any]) -> dict[str, Any]:
    """Execute a preset verification probe (or custom code when opted in)."""
    probe_id = body.get("probe_id")
    if isinstance(probe_id, int) and 0 <= probe_id < len(probes.PRESET_PROBES):
        code = probes.PRESET_PROBES[probe_id]
    else:
        raw_code = str(body.get("code") or "").strip()
        if raw_code in probes.PRESET_PROBES or (kube.ALLOW_CUSTOM_PYTHON and raw_code):
            code = raw_code
        else:
            raise PermissionError(
                "Arbitrary Python execution is disabled by default; select a "
                "preset probe_id (0-2) or start mission_control.py with "
                "ALLOW_CUSTOM_PYTHON=1."
            )

    t0 = time.monotonic()
    kube.ensure_port_forwards()
    b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    cmd_str = f"python3 -c \"import base64; exec(base64.b64decode('{b64}'))\""
    resp = kube.http_json(
        f"{kube.GATEWAY_URL}/actors/py-detonation-agent/execute",
        method="POST",
        body={"command": cmd_str},
        timeout=25.0,
    )
    if resp.get("error"):
        raise kube.UpstreamCommandError(f"Live probe failed: {resp['error']}")
    kube.suspend_actor_checked("py-detonation-agent", timeout=20)
    exit_code = int(resp.get("exit_code") or 0)
    stdout = str(resp.get("stdout") or "")
    stderr = str(resp.get("stderr") or "")
    combined_out = "\n".join(part for part in (stdout.strip(), stderr.strip()) if part)
    if exit_code != 0:
        raise kube.UpstreamCommandError(
            f"Sandbox probe exited with code {exit_code}: {combined_out}"
        )
    cmd_display = (
        f"curl -fsS -X POST {kube.GATEWAY_URL}/actors/py-detonation-agent/execute "
        f"-H @admin-hdr.txt -d {json.dumps({'command': f'python3 -c {code!r}'})}"
    )
    return {
        "actor": f"{kube.ATESPACE}/py-detonation-agent",
        "code": code,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary_cmd": cmd_display,
        "under_the_hood": [
            {
                "step": (
                    "1. Execute live verification snippet inside gVisor "
                    "sandbox 'py-detonation-agent'"
                ),
                "cmd": cmd_display,
                "output": combined_out,
            }
        ],
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def _apply_forensic_egress_policy() -> None:
    """Attach egress-gateway policy to gemini-agent-forensic and fail fast."""
    egress_gw = kube.STATE_DIR / "egress-gateway.yaml"
    args = [
        "kubectl",
        "ate",
        "create",
        "egress-policy",
        "gemini-agent-forensic",
        "-a",
        kube.ATESPACE,
        "-f",
    ]
    if egress_gw.exists():
        p_out, p_err, p_rc = kube.run_cmd([*args, str(egress_gw)], timeout=15)
    else:
        tmpl = kube.MANIFESTS_DIR / "egress-gateway.yaml.tmpl"
        raw_tmpl = tmpl.read_text(encoding="utf-8")
        if "${NAMESPACE}" not in raw_tmpl:
            raise kube.UpstreamCommandError(
                f"Expected ${{NAMESPACE}} placeholder in {tmpl}"
            )
        rendered = raw_tmpl.replace("${NAMESPACE}", kube.NAMESPACE)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", encoding="utf-8", delete=True
        ) as tmp:
            tmp.write(rendered)
            tmp.flush()
            p_out, p_err, p_rc = kube.run_cmd([*args, tmp.name], timeout=15)
    if p_rc != 0:
        detail = kube.strip_ate_warnings(f"{p_out}\n{p_err}")
        raise kube.UpstreamCommandError(
            "Failed to create egress-policy on gemini-agent-forensic "
            f"(exit {p_rc}): {detail}"
        )


def _is_cross_cpu_clone() -> bool:
    """Compare `clean-checkpoint-tag` cpu_features vs forensic actor snapshot."""
    forensic_snaps = probes.snapshot_cpu_features("gemini-agent-forensic")
    if not forensic_snaps:
        return False
    tag_cpu = probes.tag_cpu_features("clean-checkpoint-tag")
    if tag_cpu:
        return tag_cpu != forensic_snaps[-1]
    return len(forensic_snaps) >= 2 and forensic_snaps[-1] != forensic_snaps[-2]


def api_round3_forensic_clone(
    pre_buddy_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Clone gemini-agent-forensic from clean-checkpoint-tag and verify mode."""
    t0 = time.monotonic()
    kube.ensure_port_forwards()
    actors_before, _ = kube.get_actors()
    buddy_was_running = any(
        a["name"] == "gemini-agent" and a["state"] == "RUNNING" for a in actors_before
    )

    del_cmd = ["kubectl", "ate", "delete", "actor", "gemini-agent-forensic"]
    d_out, d_err, d_rc = kube.run_cmd([*del_cmd, "-a", kube.ATESPACE], timeout=15)
    d_combined = kube.strip_ate_warnings(f"{d_out}\n{d_err}")
    if d_rc != 0 and not kube.is_not_found_error(d_combined):
        raise kube.UpstreamCommandError(
            f"Failed to delete gemini-agent-forensic (exit {d_rc}): {d_combined}"
        )

    deleted = False
    get_cmd = ["kubectl", "ate", "get", "actor", "gemini-agent-forensic"]
    for _ in range(15):
        g_out, g_err, check_rc = kube.run_cmd(
            [*get_cmd, "-a", kube.ATESPACE], timeout=5
        )
        if check_rc != 0 and kube.is_not_found_error(f"{g_out}\n{g_err}"):
            deleted = True
            break
        time.sleep(0.5)
    if not deleted:
        raise kube.UpstreamCommandError(
            "Timed out waiting for gemini-agent-forensic deletion to finalize."
        )

    create_args = [
        "kubectl",
        "ate",
        "create",
        "actor",
        "gemini-agent-forensic",
        "--template=gemini-agent-v1",
        "--tag",
        "clean-checkpoint-tag",
        "-a",
        kube.ATESPACE,
    ]
    c_out, c_err, c_rc = kube.run_cmd(create_args, timeout=15)
    clone_cmd = " ".join(create_args)
    clone_out = kube.strip_ate_warnings(f"{c_out}\n{c_err}")
    if c_rc != 0:
        raise kube.UpstreamCommandError(
            f"Failed to create gemini-agent-forensic: {clone_out}"
        )

    _apply_forensic_egress_policy()

    forensic_state: dict[str, Any] = {}
    for attempt in range(2):
        forensic_state = kube.http_json(
            f"{kube.GATEWAY_URL}/actors/gemini-agent-forensic/state", timeout=35.0
        )
        if not forensic_state.get("error"):
            break
        if attempt == 0:
            time.sleep(1.5)
    if forensic_state.get("error"):
        raise kube.UpstreamCommandError(
            f"Failed to read gemini-agent-forensic state: {forensic_state['error']}"
        )
    kube.suspend_actor_checked("gemini-agent-forensic", timeout=20)

    if pre_buddy_state is not None:
        buddy_state = pre_buddy_state
    else:
        buddy_state = kube.http_json(
            f"{kube.GATEWAY_URL}/actors/gemini-agent/state", timeout=25.0
        )
        if buddy_state.get("error"):
            raise kube.UpstreamCommandError(
                f"Failed to read gemini-agent state: {buddy_state['error']}"
            )
        if not buddy_was_running:
            kube.suspend_actor_checked("gemini-agent", timeout=20)

    buddy_boot = str(buddy_state.get("bootID") or "")
    forensic_boot = str(forensic_state.get("bootID") or "")
    boot_match = bool(buddy_boot and buddy_boot == forensic_boot)
    cross_cpu_fallback = False if boot_match else _is_cross_cpu_clone()
    durable_fallback_verified = bool(
        not boot_match
        and cross_cpu_fallback
        and forensic_state.get("approvalPolicy") == "REQUIRE_HUMAN_APPROVAL"
        and forensic_state.get("diskPolicy") == "REQUIRE_HUMAN_APPROVAL"
        and int(forensic_state.get("diskCount") or 0) >= 1
    )
    if not boot_match and not durable_fallback_verified:
        raise kube.UpstreamCommandError(
            f"Forensic clone bootID mismatch: gemini-agent={buddy_boot!r} vs "
            f"gemini-agent-forensic={forensic_boot!r}"
        )

    f_url = f"{kube.GATEWAY_URL}/actors/gemini-agent-forensic/state"
    b_url = f"{kube.GATEWAY_URL}/actors/gemini-agent/state"
    return {
        "forensic_actor": f"{kube.ATESPACE}/gemini-agent-forensic",
        "buddy_boot_id": buddy_boot,
        "forensic_boot_id": forensic_boot,
        "boot_ids_match": boot_match,
        "memory_checkpoint_restored": boot_match,
        "cross_cpu_durable_fallback": durable_fallback_verified,
        "checkpoint_restored": boot_match or durable_fallback_verified,
        "summary_cmd": f"{clone_cmd} && curl -fsS {f_url} -H @admin-hdr.txt",
        "under_the_hood": [
            {
                "step": (
                    "4. Clone fresh forensic Actor 'gemini-agent-forensic' "
                    "live from Conversation Tag 'clean-checkpoint-tag'"
                ),
                "cmd": clone_cmd,
                "output": clone_out,
            },
            {
                "step": (
                    "5. Compare post-Golden-Snapshot state of 'gemini-agent' "
                    "& 'gemini-agent-forensic'"
                ),
                "cmd": (
                    f"curl -fsS {b_url} -H @admin-hdr.txt && "
                    f"curl -fsS {f_url} -H @admin-hdr.txt"
                ),
                "output": (
                    f"gemini-agent.bootID          = {buddy_boot} "
                    f"(memCount={buddy_state.get('memCount')}, "
                    f"turns={buddy_state.get('turns')}, "
                    f"framework={buddy_state.get('framework')})\n"
                    f"gemini-agent-forensic.bootID = {forensic_boot} "
                    f"(boot_ids_match={boot_match}, "
                    f"cross_cpu_durable_fallback={durable_fallback_verified}, "
                    f"diskPolicy={forensic_state.get('diskPolicy')}, "
                    f"diskCount={forensic_state.get('diskCount')})"
                ),
            },
        ],
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def api_act2_snapshots() -> dict[str, Any]:
    """Run Act 2: Snapshot Restore + Golden vs Conversation Tags + Cloning."""
    t0 = time.monotonic()
    kube.ensure_port_forwards()
    tags_out, tags_err, tags_rc = kube.run_cmd(
        ["kubectl", "ate", "get", "tags", "-a", kube.ATESPACE], timeout=15
    )
    clean_tags = kube.strip_ate_warnings(f"{tags_out}\n{tags_err}")
    if tags_rc != 0:
        raise kube.UpstreamCommandError(
            f"Failed to list tags in {kube.ATESPACE}: {clean_tags}"
        )
    race = api_prologue_race()
    clone_data = api_round3_forensic_clone(pre_buddy_state=race.get("buddy_state"))
    return {
        "local_restore_avg_ms": race["local_restore_avg_ms"],
        "gcs_restore_avg_ms": race["gcs_restore_avg_ms"],
        "cli_roundtrip_resume_ms": race["cli_roundtrip_resume_ms"],
        "trace_id": race["trace_id"],
        "buddy_boot_id": clone_data["buddy_boot_id"],
        "forensic_boot_id": clone_data["forensic_boot_id"],
        "boot_ids_match": clone_data["boot_ids_match"],
        "memory_checkpoint_restored": clone_data["memory_checkpoint_restored"],
        "cross_cpu_durable_fallback": clone_data["cross_cpu_durable_fallback"],
        "checkpoint_restored": clone_data["checkpoint_restored"],
        "tags_table": clean_tags,
        "summary_cmd": (
            f"kubectl ate get tags -a {kube.ATESPACE} && "
            f"kubectl ate --trace resume actor gemini-agent -a {kube.ATESPACE} && "
            f"curl -fsS {kube.GATEWAY_URL}/actors/gemini-agent-forensic/state "
            "-H @admin-hdr.txt"
        ),
        "under_the_hood": [
            {
                "step": (
                    "1. Inspect Golden Template Tag (TAG_SCOPE_PUBLISHED) vs. "
                    "Conversation Tag (clean-checkpoint-tag) in GCS"
                ),
                "cmd": f"kubectl ate get tags -a {kube.ATESPACE}",
                "output": clean_tags,
            },
            *race["under_the_hood"],
            *clone_data["under_the_hood"],
        ],
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def api_act3_egress_suite() -> dict[str, Any]:
    """Run Act 3 on egress-agent: wire swap, DNS block, IP block, and audit."""
    t0 = time.monotonic()
    kube.ensure_port_forwards()

    partner_url = (
        f"http://partner-api.{kube.SECRETS_NAMESPACE}.svc.cluster.local/verify"
    )
    fetch_base = f"{kube.GATEWAY_URL}/actors/egress-agent/fetch"
    test_a = kube.http_json(
        f"{fetch_base}?" + urlencode({"url": partner_url}), method="GET", timeout=20.0
    )
    if test_a.get("error"):
        raise kube.UpstreamCommandError(
            f"Act 3 Test A ({partner_url}) failed: {test_a['error']}"
        )
    hmac_prefix = str(test_a.get("credential_hmac_prefix") or "").strip()
    if not (
        test_a.get("authenticated") is True
        and test_a.get("placeholder_replaced") is True
        and test_a.get("raw_secret_returned") is False
        and hmac_prefix.startswith("hmac-sha256:")
    ):
        raise kube.UpstreamCommandError(
            f"Act 3 Test A credential verification failed: {test_a}"
        )

    target_b = "https://example.com/"
    test_b = kube.http_json(
        f"{fetch_base}?" + urlencode({"url": target_b}), method="GET", timeout=15.0
    )
    dns_block_summary = probes.verify_dns_block_response(test_b, target_b)
    dns_block_msg = str(test_b.get("error") or "").strip()

    target_c = "http://1.1.1.1/"
    test_c = kube.http_json(
        f"{fetch_base}?" + urlencode({"url": target_c}), method="GET", timeout=15.0
    )
    direct_ip_summary = probes.verify_direct_ip_block_response(test_c, target_c)
    direct_ip_msg = str(test_c.get("error") or "").strip()

    pol_cmd = ["kubectl", "ate", "get", "egress-policy", "egress-agent"]
    pol_out, pol_err, pol_rc = kube.run_cmd(
        [*pol_cmd, "-a", kube.ATESPACE, "-o", "yaml"], timeout=15
    )
    clean_pol = kube.strip_ate_warnings(f"{pol_out}\n{pol_err}")
    if pol_rc != 0:
        raise kube.UpstreamCommandError(f"Failed to read egress-policy: {clean_pol}")

    expected_uri = (
        f"ate-secret://k8s.io/default/{kube.SECRETS_NAMESPACE}/example-api/token"
    )
    uri_matches = re.findall(r"ate-secret://[^\s\"']+", clean_pol)
    if expected_uri not in uri_matches:
        raise kube.UpstreamCommandError(
            f"EgressPolicy audit failed: expected {expected_uri!r} in policy "
            f"YAML, observed: {clean_pol}"
        )

    kube.suspend_actor_checked("egress-agent", timeout=20)
    pol_cli = f"kubectl ate get egress-policy egress-agent -a {kube.ATESPACE} -o yaml"

    return {
        "actor": f"{kube.ATESPACE}/egress-agent",
        "partner_url": partner_url,
        "verification_badge": (
            f"Authenticated (wire swap {hmac_prefix}, 0 secret bytes echoed)"
        ),
        "credential_hmac_prefix": hmac_prefix,
        "dns_block_msg": dns_block_msg,
        "dns_block_summary": dns_block_summary,
        "direct_ip_block_msg": direct_ip_msg,
        "direct_ip_block_summary": direct_ip_summary,
        "credential_uri": expected_uri,
        "policy_yaml": clean_pol,
        "summary_cmd": (
            f'curl -fsSG "{fetch_base}" -H @admin-hdr.txt '
            f'--data-urlencode "url={partner_url}" && {pol_cli}'
        ),
        "under_the_hood": [
            {
                "step": (
                    f"1. Test A ({partner_url}): egress-agent sends 'Bearer "
                    "placeholder' -> partner-api verifies wire swap"
                ),
                "cmd": (
                    f'curl -fsSG "{fetch_base}" -H @admin-hdr.txt '
                    f'--data-urlencode "url={partner_url}"'
                ),
                "output": json.dumps(test_a, indent=2),
            },
            {
                "step": (
                    "2. Test B (Unauthorized FQDN https://example.com/): "
                    "Blocked before TCP connect by Local DNS Relay"
                ),
                "cmd": (
                    f'curl -sG "{fetch_base}" -H @admin-hdr.txt '
                    '--data-urlencode "url=https://example.com/"'
                ),
                "output": dns_block_msg,
            },
            {
                "step": (
                    "3. Test C (Direct-IP Bypass http://1.1.1.1/): "
                    "Blocked at atenet-egress (HTTP 403 egress denied)"
                ),
                "cmd": (
                    f'curl -sG "{fetch_base}" -H @admin-hdr.txt '
                    '--data-urlencode "url=http://1.1.1.1/"'
                ),
                "output": direct_ip_msg,
            },
            {
                "step": (
                    "4. Audit EgressPolicy on 'egress-agent' "
                    "(proving only the opaque ate-secret:// URI is referenced)"
                ),
                "cmd": pol_cli,
                "output": clean_pol,
            },
        ],
        "_exec_ms": round((time.monotonic() - t0) * 1000, 1),
    }
