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

"""The Secure Runtime: Autonomous GitHub Triage Agent on GKE Agent Substrate."""

import json
import os
from typing import Any

from .substrate_client import SubstrateClient, classify_tool_intent
from .telemetry import TERMINAL_BUS

try:
    from google.adk.agents import LlmAgent
    from google.adk.tools.base_tool import BaseTool
    from google.adk.tools.tool_context import ToolContext
except ImportError:  # pragma: no cover - bare CI unittest environment fallback
    BaseTool = Any  # type: ignore[assignment,misc]
    ToolContext = Any  # type: ignore[assignment,misc]
    LlmAgent = None  # type: ignore[assignment,misc]

_substrate = SubstrateClient()

DEFAULT_ACTOR_NAME = os.environ.get("SUBSTRATE_DEFAULT_ACTOR", "triage-actor-1")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "GoogleCloudPlatform/accelerated-platforms")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")

SYSTEM_INSTRUCTION = (
    "You are **The Secure Runtime Triage Agent** running on GKE with "
    "**Gemini on Vertex AI** and **Agent Substrate** (`ateworker-gvisor` + "
    "Golden Snapshots + `atenet-egress` + `k8s-credential-provider` + "
    "`intent-extproc`).\n\n"
    "Available tools (#1 through #4):\n"
    "1. `inspect_sandbox_boundary(actor_name)` — #1 gVisor user-space kernel "
    "& syscall boundary.\n"
    "2. `run_python_in_actor(code, declared_purpose, actor_name, "
    "suspend_after)` — #2 Golden Snapshot execution & stateful GCS suspend.\n"
    "3. `triage_github_issue_in_sandbox(issue_number, "
    f"follow_issue_instructions, actor_name)` — #3 Out-of-sandbox token "
    f"injection on `{GITHUB_REPO}` & L7 `intent-extproc` method/path filter.\n"
    "4. `audit_and_reset_actor_to_golden(actor_name, new_actor_name)` — #4 "
    "SPIFFE-attributed audit trail, policy revocation, and clean Golden reset."
)


def _sync_intent_policy(
    tool_name: str, actor_name: str, declared_purpose: str = ""
) -> dict[str, Any]:
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
        "intent_extproc": _substrate.apply_intent_extproc(actor_ref, classification),
    }


def _before_tool_intent_gate(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """Enforces least-privilege egress policy before tool execution (fail-closed)."""
    tool_name = getattr(tool, "name", "")
    if tool_name in (
        "inspect_sandbox_boundary",
        "audit_and_reset_actor_to_golden",
    ):
        return None
    actor_name = args.get("actor_name") or DEFAULT_ACTOR_NAME
    try:
        synced = _sync_intent_policy(
            tool_name, actor_name, args.get("declared_purpose", "")
        )
        tool_context.state["last_intent_classification"] = synced
        return None
    except Exception as exc:  # noqa: BLE001
        blocked = {
            "status": "blocked",
            "error": (
                f"Blocked tool {tool_name!r} (fail-closed): "
                f"control-plane intent policy sync failed: {exc}"
            ),
        }
        tool_context.state["last_intent_classification"] = blocked
        TERMINAL_BUS.emit("error", blocked["error"])
        return blocked


def inspect_sandbox_boundary(actor_name: str = DEFAULT_ACTOR_NAME) -> str:
    """#1: Inspects the gVisor security boundary, UID, and syscall filtering."""
    TERMINAL_BUS.emit(
        "verdict",
        f"[#1] Probing gVisor user-space kernel boundary on actor {actor_name}",
        step="1",
    )
    ensure_info = _substrate.ensure_actor(actor_name)
    sandbox_info = _substrate.call_actor(actor_name, "GET", "/info")
    probe_res = _substrate.call_actor(actor_name, "POST", "/probe-boundary", {})
    verdicts = probe_res.get("verdicts") or {}
    TERMINAL_BUS.emit(
        "verdict",
        f"[#1] {len(verdicts)}/{len(verdicts)} escape vectors blocked by gVisor "
        f"({sandbox_info.get('kernel_version', 'runsc')})",
        step="1",
    )
    return json.dumps(
        {
            "section": "#1 — Sandbox Boundary (gVisor User-Space Kernel Isolation)",
            "actor": ensure_info,
            "sandbox_identity": sandbox_info,
            "user_space_syscall_verdicts": verdicts,
        },
        indent=2,
    )


def run_python_in_actor(
    code: str,
    declared_purpose: str = "offline_scientific_reproducer",
    actor_name: str = DEFAULT_ACTOR_NAME,
    suspend_after: bool = True,
) -> str:
    """#2: Executes Python inside a Golden-Snapshot Actor and optionally suspends."""
    policy_sync = _sync_intent_policy(
        "run_python_in_actor", actor_name, declared_purpose
    )
    exec_result = _substrate.call_actor(actor_name, "POST", "/run", {"code": code})
    suspend_info = _substrate.suspend_actor(actor_name) if suspend_after else None
    return json.dumps(
        {
            "section": "#2 — Golden Snapshot Restore & Zero-Import-Tax Execution",
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
    """#3: Fetches a GitHub issue with egress token injection & L7 intent filter."""
    actor_ref = f"{_substrate.atespace}/{actor_name}"
    TERMINAL_BUS.emit(
        "verdict",
        f"[#3] Syncing read-only GitHub EgressPolicy + intent-extproc rules for "
        f"{actor_ref} (issue #{issue_number})",
        step="3",
    )
    policy_sync = _sync_intent_policy(
        "triage_github_issue_in_sandbox",
        actor_name,
        f"triage issue #{issue_number}",
    )
    triage_report = _substrate.call_actor(
        actor_name,
        "POST",
        "/triage-github-issue",
        {
            "repo": GITHUB_REPO,
            "issue_number": int(issue_number),
            "follow_untrusted": bool(follow_issue_instructions),
        },
    )
    s1 = (triage_report.get("steps") or {}).get("1_fetch_issue_get", {})
    s2 = (triage_report.get("steps") or {}).get("2_attempt_post_comment", {})
    TERMINAL_BUS.emit(
        "verdict",
        f"[#3] Sandbox verdicts: GET={s1.get('status_code')} "
        f"({s1.get('verdict')}), POST={s2.get('status_code', 'skipped')} "
        f"({s2.get('verdict', 'not attempted')})",
        step="3",
    )
    return json.dumps(
        {
            "section": (
                "#3 — Dynamic Intent Filtering & Out-of-Sandbox Credential Injection"
            ),
            "actor_ref": actor_ref,
            "policy_sync": policy_sync,
            "triage_execution": triage_report,
            "intent_extproc_audit_trail": _substrate.list_audit_events(actor_ref)[-6:],
        },
        indent=2,
    )


def audit_and_reset_actor_to_golden(
    actor_name: str = DEFAULT_ACTOR_NAME,
    new_actor_name: str = "triage-actor-clean",
) -> str:
    """#4: Queries SPIFFE audit trail, quarantines tainted actor, and resets clean."""
    actor_ref = f"{_substrate.atespace}/{actor_name}"
    TERMINAL_BUS.emit(
        "verdict",
        f"[#4] Quarantining {actor_ref} and restoring clean actor {new_actor_name} "
        "from Golden Snapshot",
        step="4",
    )
    audit_events = _substrate.list_audit_events(actor_ref)
    revoke_extproc = _substrate.revoke_intent_extproc(actor_ref)
    revoke_egress = _substrate.apply_egress_policy(
        actor_name, classify_tool_intent("offline")
    )
    delete_info = _substrate.delete_actor(actor_name)
    clean_actor_info = _substrate.ensure_actor(new_actor_name)
    clean_sandbox_check = _substrate.call_actor(new_actor_name, "GET", "/info")
    TERMINAL_BUS.emit(
        "verdict",
        f"[#4] Clean actor {clean_actor_info['actor_ref']} ready in "
        f"{clean_actor_info['ensure_ms']} ms",
        step="4",
    )
    return json.dumps(
        {
            "section": (
                "#4 — SPIFFE-Attributed Audit Trail & Clean Reset from Golden Snapshot"
            ),
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


root_agent = (
    LlmAgent(
        name="Secure_Runtime_Triage_Agent",
        model=GEMINI_MODEL,
        description=(
            "Autonomous GitHub issue triage and scientific reproducer agent "
            "on GKE Agent Substrate."
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
    if LlmAgent is not None
    else None
)
