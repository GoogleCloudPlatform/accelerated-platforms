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

"""GKE Agent Sandbox Demo (v2.0): Multi-Agent RL Rollout & gVisor Verifiable Reward Loop.

This module implements an end-to-end **Reinforcement Learning with Verifiable Rewards (RLVR)**
multi-agent pipeline on Google Kubernetes Engine (GKE) using the Google Agent Development Kit
(ADK) (`SequentialAgent` + `LlmAgent`) and GKE Agent Sandbox (`gVisor` `SandboxWarmPool`):

Multi-Agent Pipeline (`RL_Orchestrator` - `SequentialAgent`):
  1. `Policy_Rollout_Generator` (Stage 1):
     Acts as the RL policy model generating two candidate Python trajectories (`Rollout-1-Naive-Draft`
     with an edge-case defect, and `Rollout-2-Self-Corrected` with the optimal implementation)
     alongside a deterministic `assert` unit test suite (`Unit_Test_Suite`).
  2. `gVisor_Reward_Verifier` (Stage 2):
     Acts as the isolated GKE execution environment and deterministic reward function `R(s, a)`.
     For each rollout, it claims a pre-warmed `gVisor` (`runsc` Kernel `4.4.0`) pod from the
     `SandboxWarmPool` in <500ms, executes the code and unit tests in isolation, and computes
     a composite Verifiable Reward Score `R in [0.0, 1.0]`:
       - Syntax & Compilation (`+0.20`)
       - Unit Test Pass Rate (`+0.50`)
       - Sub-10ms Execution Latency (`+0.20`)
       - Verified gVisor Kernel Isolation (`+0.10`)
     Also includes `verify_zero_trust_isolation` to quarantine rogue rollouts attempting network
     exfiltration (`R = -1.00`, `TRAJECTORY_QUARANTINED`).
  3. `GRPO_Policy_Updater` (Stage 3):
     Synthesizes the sandbox telemetry across all rollouts into a comparative GRPO Advantage &
     RLVR Scoreboard table.

KV-Cache Prefix Optimization:
  All three sequential sub-agents share a byte-for-byte identical `SHARED_RLVR_SYSTEM_INSTRUCTION`
  so that LLM serving engines (Vertex AI / GKE `llm-d` vLLM) reuse 100% of the system prompt
  KV-cache prefix across sub-agent turns without context-cache misses.
"""

import json
import os
import queue
import shlex
import threading
import time
import uuid
from typing import Any, Optional

import httpx
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from kubernetes import client, config

_K8S_CUSTOM_API: Optional[client.CustomObjectsApi] = None
_HTTP_CLIENT: Optional[httpx.Client] = None
_WARM_CLAIM_QUEUE: "queue.Queue[tuple[str, Optional[str], float]]" = queue.Queue()
_POOL_INIT_LOCK = threading.Lock()
_POOL_INITIALIZED = False


def _load_k8s_custom_objects() -> client.CustomObjectsApi:
    """Initializes and caches a persistent Kubernetes CustomObjectsApi client (reusing TLS sockets)."""
    global _K8S_CUSTOM_API
    if _K8S_CUSTOM_API is None:
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()
        _K8S_CUSTOM_API = client.CustomObjectsApi()
    return _K8S_CUSTOM_API


def _get_http_client() -> httpx.Client:
    """Returns a persistent keep-alive HTTP client to sandbox-router-svc."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        _HTTP_CLIENT = httpx.Client(timeout=60.0)
    return _HTTP_CLIENT


def _allocate_warm_sandbox_claim() -> tuple[str, Optional[str], float]:
    """Claims a pre-warmed gVisor pod from SandboxWarmPool and verifies router endpoint readiness."""
    api_url = os.environ.get(
        "SANDBOX_API_URL",
        "http://sandbox-router-svc.agent-sandbox.svc.cluster.local:8080",
    ).rstrip("/")
    namespace = os.environ.get("SANDBOX_NAMESPACE", "agent-sandbox")
    template_name = os.environ.get("SANDBOX_TEMPLATE", "python-runtime-template")
    router_token = os.environ.get("ROUTER_AUTH_TOKEN", "")

    claim_name = f"rl-rollout-{uuid.uuid4().hex[:8]}"
    custom_api = _load_k8s_custom_objects()
    claim_body = {
        "apiVersion": "extensions.agents.x-k8s.io/v1alpha1",
        "kind": "SandboxClaim",
        "metadata": {"name": claim_name, "namespace": namespace},
        "spec": {"sandboxTemplateRef": {"name": template_name}},
    }

    t0 = time.perf_counter()
    custom_api.create_namespaced_custom_object(
        group="extensions.agents.x-k8s.io",
        version="v1alpha1",
        namespace=namespace,
        plural="sandboxclaims",
        body=claim_body,
    )

    pod_ip: Optional[str] = None
    for _ in range(400):
        try:
            sb = custom_api.get_namespaced_custom_object(
                group="agents.x-k8s.io",
                version="v1alpha1",
                namespace=namespace,
                plural="sandboxes",
                name=claim_name,
            )
            status = sb.get("status", {})
            conditions = status.get("conditions", [])
            if any(
                c.get("type") == "Ready" and c.get("status") == "True"
                for c in conditions
            ):
                pod_ips = status.get("podIPs") or []
                if pod_ips:
                    pod_ip = pod_ips[0]
                break
        except Exception:
            pass
        time.sleep(0.015)

    bind_ms = round((time.perf_counter() - t0) * 1000, 2)

    # Warm the kube-proxy Service endpoint inside sandbox-router so the first rollout call has 0ms 502 retry delay
    headers = {
        "X-Sandbox-ID": claim_name,
        "X-Sandbox-Namespace": namespace,
        "X-Sandbox-Port": "8888",
    }
    if pod_ip:
        headers["X-Sandbox-Pod-IP"] = pod_ip
    if router_token:
        headers["Authorization"] = f"Bearer {router_token}"

    with httpx.Client(timeout=10.0) as warmup_client:
        for _ in range(30):
            try:
                r = warmup_client.post(
                    f"{api_url}/execute",
                    headers=headers,
                    json={"command": "true"},
                )
                if r.status_code == 200:
                    break
            except Exception:
                pass
            time.sleep(0.1)

    return claim_name, pod_ip, bind_ms


def _replenish_claim_async() -> None:
    """Replenishes one pre-claimed gVisor SandboxClaim in the background."""

    def _worker() -> None:
        try:
            _WARM_CLAIM_QUEUE.put(_allocate_warm_sandbox_claim())
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


def _ensure_warm_claim_buffer(target_size: int = 3) -> None:
    """Pre-populates the background SandboxClaim buffer on agent startup."""
    global _POOL_INITIALIZED
    with _POOL_INIT_LOCK:
        if _POOL_INITIALIZED:
            return
        _POOL_INITIALIZED = True
        for _ in range(target_size):
            _replenish_claim_async()


# Initialize 3 pre-claimed gVisor sandboxes immediately when the module loads
_ensure_warm_claim_buffer(3)


def _execute_in_ephemeral_gvisor_sandbox(python_script: str) -> dict[str, Any]:
    """Claims a pre-warmed gVisor pod from the GKE SandboxWarmPool, executes python_script, and deletes the claim.

    Args:
        python_script: Complete Python source code string to execute inside the gVisor pod.

    Returns:
        Dictionary containing `claim_name`, `claim_latency_ms`, `stdout`, `stderr`, and `exit_code`.
    """
    api_url = os.environ.get(
        "SANDBOX_API_URL",
        "http://sandbox-router-svc.agent-sandbox.svc.cluster.local:8080",
    ).rstrip("/")
    namespace = os.environ.get("SANDBOX_NAMESPACE", "agent-sandbox")
    router_token = os.environ.get("ROUTER_AUTH_TOKEN", "")
    custom_api = _load_k8s_custom_objects()

    t_start = time.perf_counter()
    try:
        # Step 1: Pop an already-bound gVisor SandboxClaim from the warm buffer (or allocate on demand)
        try:
            claim_name, pod_ip, k8s_bind_ms = _WARM_CLAIM_QUEUE.get_nowait()
            # Immediately replenish a replacement SandboxClaim in the background
            _replenish_claim_async()
        except queue.Empty:
            claim_name, pod_ip, k8s_bind_ms = _allocate_warm_sandbox_claim()
            _replenish_claim_async()

        # Step 2: Proxy execution through sandbox-router with Bearer Token authentication
        headers = {
            "X-Sandbox-ID": claim_name,
            "X-Sandbox-Namespace": namespace,
            "X-Sandbox-Port": "8888",
        }
        if pod_ip:
            headers["X-Sandbox-Pod-IP"] = pod_ip
        if router_token:
            headers["Authorization"] = f"Bearer {router_token}"

        cmd = f"python3 -c {shlex.quote(python_script)}"
        data: dict[str, Any] = {}
        http_client = _get_http_client()
        for attempt in range(10):
            resp = http_client.post(
                f"{api_url}/execute",
                headers=headers,
                json={"command": cmd},
            )
            if resp.status_code in (502, 503, 504) and attempt < 9:
                time.sleep(0.1)
                continue
            resp.raise_for_status()
            data = resp.json()
            break

        total_roundtrip_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return {
            "claim_name": claim_name,
            "claim_latency_ms": total_roundtrip_ms,
            "k8s_warmpool_bind_ms": k8s_bind_ms,
            "stdout": (data.get("stdout") or "").strip(),
            "stderr": (data.get("stderr") or "").strip(),
            "exit_code": data.get("exit_code", 0),
        }
    except Exception as e:
        return {
            "claim_name": "error",
            "claim_latency_ms": round((time.perf_counter() - t_start) * 1000, 2),
            "stdout": "",
            "stderr": f"Sandbox Error: {str(e)}",
            "exit_code": 1,
        }
    finally:
        # Step 3: Asynchronously delete the consumed SandboxClaim so every rollout runs in a fresh single-use gVisor pod
        def _cleanup_claim() -> None:
            try:
                custom_api.delete_namespaced_custom_object(
                    group="extensions.agents.x-k8s.io",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="sandboxclaims",
                    name=claim_name,
                )
            except Exception:
                pass

        threading.Thread(target=_cleanup_claim, daemon=True).start()


def evaluate_rl_rollout_reward(
    rollout_id: str,
    candidate_code: str,
    unit_test_code: str,
) -> str:
    """Executes an RL candidate code rollout and its unit tests inside a gVisor WarmPool sandbox and computes a Verifiable Reward Score R in [0.0, 1.0].

    Reward Function Breakdown:
      - `syntax_compile` (+0.20): Code compiles and executes without SyntaxError.
      - `unit_tests_passed` (+0.50): All `assert` unit tests pass without AssertionError/Exception.
      - `latency_efficiency` (+0.20): Execution completes in <10ms (+0.10 if <50ms).
      - `gvisor_isolation_verified` (+0.10): Verified running inside gVisor kernel (`4.4.0`).

    Args:
        rollout_id: Identifier for the rollout trajectory (e.g. 'Rollout-1-Naive-Draft' or 'Rollout-2-Self-Corrected').
        candidate_code: The candidate Python implementation to evaluate.
        unit_test_code: Python assertions/tests that verify correctness and edge cases.

    Returns:
        Formatted JSON string containing sandbox metadata, reward breakdown, and GRPO policy decision.
    """
    harness = f"""
import json, platform, time

uname = platform.uname()
r_syntax = 0.20
r_tests = 0.0
r_latency = 0.0
r_safety = 0.10 if uname.release.startswith("4.4") else 0.0
error_msg = None

ns = {{}}
t0 = time.perf_counter()
try:
    exec({candidate_code!r}, ns)
    exec({unit_test_code!r}, ns)
    exec_ms = (time.perf_counter() - t0) * 1000.0
    r_tests = 0.50
    if exec_ms < 10.0:
        r_latency = 0.20
    elif exec_ms < 50.0:
        r_latency = 0.10
except SyntaxError as e:
    r_syntax = 0.0
    exec_ms = (time.perf_counter() - t0) * 1000.0
    error_msg = f"SyntaxError: {{e}}"
except Exception as e:
    exec_ms = (time.perf_counter() - t0) * 1000.0
    error_msg = f"{{type(e).__name__}}: {{e}}"

total_reward = round(r_syntax + r_tests + r_latency + r_safety, 2)
print(json.dumps({{
    "rollout_id": {rollout_id!r},
    "warmpool_pod": uname.node,
    "kernel_release": uname.release,
    "exec_time_ms": round(exec_ms, 3),
    "reward_breakdown": {{
        "syntax_compile": r_syntax,
        "unit_tests_passed": r_tests,
        "latency_efficiency": r_latency,
        "gvisor_isolation_verified": r_safety,
    }},
    "total_verifiable_reward": total_reward,
    "policy_decision": "ACCEPTED_FOR_GRPO_UPDATE" if total_reward >= 0.95 else "REJECTED_NEEDS_REFINEMENT",
    "environment_feedback": error_msg or "All unit test assertions passed within latency budget."
}}, indent=2))
"""
    res = _execute_in_ephemeral_gvisor_sandbox(harness)
    if res["exit_code"] != 0 and not res["stdout"]:
        return json.dumps(
            {
                "rollout_id": rollout_id,
                "sandbox_claim": res["claim_name"],
                "total_verifiable_reward": 0.0,
                "policy_decision": "REJECTED_SANDBOX_ERROR",
                "stderr": res["stderr"],
            },
            indent=2,
        )
    return (
        f"SandboxClaim `{res['claim_name']}` (Claim Latency: {res['claim_latency_ms']} ms):\n"
        f"{res['stdout']}"
    )


def verify_zero_trust_isolation(target_url: str = "http://93.184.215.14") -> str:
    """Simulates a rogue or hallucinated RL rollout attempting network exfiltration inside the gVisor sandbox and computes the security penalty.

    Args:
        target_url: The external URL or metadata IP (`http://169.254.169.254` or `http://93.184.215.14`) to probe.

    Returns:
        Formatted JSON string proving `restrict-sandbox-egress` NetworkPolicy / Workload Identity blocked egress (`R = -1.0`).
    """
    # If probing GCP Metadata Server, target the actual IAM token endpoint with Metadata-Flavor header
    effective_url = target_url
    if "169.254.169.254" in target_url and "service-accounts" not in target_url:
        effective_url = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"

    probe_script = f"""
import json, platform, urllib.request
uname = platform.uname()
req = urllib.request.Request({effective_url!r}, headers={{"Metadata-Flavor": "Google"}})
try:
    with urllib.request.urlopen(req, timeout=3) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
        if "access_token" in body:
            status = "EXFILTRATION_SUCCEEDED_BREACH"
            reward = -10.0
            detail = "WARNING: IAM access_token was exposed!"
        else:
            status = "BLOCKED_BY_ZERO_TRUST_SANDBOX"
            reward = -1.0
            detail = "No IAM credentials exposed in sandbox."
except Exception as e:
    status = "BLOCKED_BY_ZERO_TRUST_SANDBOX"
    reward = -1.0
    detail = f"{{type(e).__name__}}: {{e}}"

print(json.dumps({{
    "probe_target": {effective_url!r},
    "warmpool_pod": uname.node,
    "kernel_release": uname.release,
    "sandbox_enforcement": status,
    "rl_security_reward_penalty": reward,
    "policy_decision": "TRAJECTORY_QUARANTINED",
    "network_policy_detail": detail
}}, indent=2))
"""
    res = _execute_in_ephemeral_gvisor_sandbox(probe_script)
    return (
        f"SandboxClaim `{res['claim_name']}` (Claim Latency: {res['claim_latency_ms']} ms):\n"
        f"{res['stdout']}"
    )


api_base = os.environ.get("OPENAI_API_BASE")
if api_base:
    model_id = os.environ.get("OPENAI_MODEL_NAME", "openai/google/gemma-3-27b-it")
    agent_model = LiteLlm(
        model=model_id,
        api_base=api_base,
        api_key=os.environ.get("OPENAI_API_KEY", "none"),
    )
else:
    agent_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# Shared system prompt across all 3 sequential sub-agents to preserve 100% KV-cache prefix reuse
SHARED_RLVR_SYSTEM_INSTRUCTION = (
    "You are part of the GKE Reinforcement Learning with Verifiable Rewards (RLVR) pipeline (`RL_Orchestrator`), "
    "consisting of three sequential stages that share a unified system prompt for KV-cache prefix reuse:\n"
    "- Stage 1 (`Policy_Rollout_Generator`): Output two concise candidate Python functions (`Rollout-1-Naive-Draft` with a deliberate edge-case bug, and `Rollout-2-Self-Corrected` with the optimal fix) plus a short `assert` test suite (`Unit_Test_Suite`) that exposes the bug in Rollout 1 and passes on Rollout 2. Do NOT call tools in Stage 1.\n"
    "- Stage 2 (`gVisor_Reward_Verifier`): Call `evaluate_rl_rollout_reward` twice (first for `Rollout-1-Naive-Draft` so it scores R = 0.30, second for `Rollout-2-Self-Corrected` so it scores R = 1.00 on gVisor Kernel 4.4.0). If the user also asked to test network security or rogue exfiltration, call `verify_zero_trust_isolation`. Output the raw JSON telemetry from each tool.\n"
    "- Stage 3 (`GRPO_Policy_Updater`): Present the final Markdown RLVR Scoreboard table comparing `Rollout ID | Claimed GKE WarmPool Pod | gVisor Kernel | Exec Time (ms) | Syntax | Unit Tests | Latency | Safety | Total Reward (R) | GRPO Policy Decision` and explain how the deterministic gVisor sandbox rewards drove policy refinement."
)


def _enforce_shared_kv_cache_prefix(callback_context: Any, llm_request: Any) -> None:
    """Overwrites the per-agent identity suffix appended by ADK's _IdentityLlmRequestProcessor.

    By normalizing `llm_request.config.system_instruction` right before the model call,
    all three sub-agents send the exact same byte-for-byte `system_instruction` to Vertex AI,
    ensuring 100% KV-cache prefix reuse and zero ADK Dev UI 'System instructions modified' warnings.
    """
    stage_name = getattr(callback_context, "agent_name", "RL_Orchestrator")
    if getattr(llm_request, "config", None) is not None:
        llm_request.config.system_instruction = SHARED_RLVR_SYSTEM_INSTRUCTION
    # Inject the active stage name as user-turn context rather than mutating system_instruction
    if getattr(llm_request, "contents", None):
        llm_request.contents.append(
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"[Active Pipeline Stage: {stage_name}]")
                ],
            )
        )
    return None


# Sub-Agent 1: Policy Rollout Generator
policy_rollout_agent = LlmAgent(
    name="Policy_Rollout_Generator",
    model=agent_model,
    description="Stage 1: Generates two candidate Python code trajectories (Rollout-1-Naive-Draft and Rollout-2-Self-Corrected) plus unit test assertions.",
    instruction=SHARED_RLVR_SYSTEM_INSTRUCTION,
    before_model_callback=_enforce_shared_kv_cache_prefix,
    output_key="candidate_rollouts",
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)

# Sub-Agent 2: gVisor Sandbox Reward Verifier
gvisor_reward_verifier_agent = LlmAgent(
    name="gVisor_Reward_Verifier",
    model=agent_model,
    description="Stage 2: Claims ephemeral gVisor pods from the GKE SandboxWarmPool to execute candidate rollouts, enforce Zero-Trust NetworkPolicy, and compute Verifiable Rewards R.",
    instruction=SHARED_RLVR_SYSTEM_INSTRUCTION,
    before_model_callback=_enforce_shared_kv_cache_prefix,
    tools=[evaluate_rl_rollout_reward, verify_zero_trust_isolation],
    output_key="verifier_telemetry",
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)

# Sub-Agent 3: GRPO Policy Updater & Reward Judge
grpo_policy_updater_agent = LlmAgent(
    name="GRPO_Policy_Updater",
    model=agent_model,
    description="Stage 3: Computes relative GRPO group advantage across rollouts and presents the RLVR Sandbox Telemetry & Reward Scoreboard.",
    instruction=SHARED_RLVR_SYSTEM_INSTRUCTION,
    before_model_callback=_enforce_shared_kv_cache_prefix,
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)

# Root Sequential Workflow Agent so all 3 sub-agents execute in order and render in the ADK Graph
root_agent = SequentialAgent(
    name="RL_Orchestrator",
    description="End-to-end Reinforcement Learning with Verifiable Rewards (RLVR) pipeline on GKE: Policy_Rollout_Generator -> gVisor_Reward_Verifier -> GRPO_Policy_Updater.",
    sub_agents=[
        policy_rollout_agent,
        gvisor_reward_verifier_agent,
        grpo_policy_updater_agent,
    ],
)
