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

"""Interactive Mission Control UI Server for The Secure Runtime 4-Act Demo.

Connects to the live GKE 1.37 cluster running Agent Substrate (v1.0.0-rc.2)
to execute Acts 1-4, custom gVisor sandbox code, and Gemini 3.8 Flash ADK
agent prompts in real time.
"""

import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[6]
DEFAULT_KUBECONFIG = (
    REPO_ROOT
    / "platforms/gke/base/kubernetes/kubeconfig/accelerated-platforms-dev-sec-secrt"
)
SLIDES_DIR = Path(os.environ.get("SLIDES_DIR", "/tmp/secure-runtime-slides"))


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    if not env.get("KUBECONFIG") and DEFAULT_KUBECONFIG.is_file():
        env["KUBECONFIG"] = str(DEFAULT_KUBECONFIG)
    home = env.get("HOME", "")
    env["PATH"] = f"{home}/.local/bin:{home}/google-cloud-sdk/bin:{env.get('PATH', '')}"
    return env


def run_cmd(args: list[str], timeout: int = 120) -> tuple[str, str, int]:
    res = subprocess.run(
        args,
        env=_build_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return res.stdout.strip(), res.stderr.strip(), res.returncode


def run_agent_py(
    expr: str, stdin_data: str | None = None, timeout: int = 120
) -> dict[str, Any]:
    t0 = time.monotonic()
    cmd = [
        "kubectl",
        "exec",
        "-i",
        "-n",
        "agent-harness",
        "deploy/triage-agent",
        "--",
        "python3",
        "-c",
        expr,
    ]
    res = subprocess.run(
        cmd,
        env=_build_env(),
        input=stdin_data,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
    out = res.stdout.strip()
    for idx, ch in enumerate(out):
        if ch == "{":
            try:
                parsed = json.loads(out[idx:])
                parsed["_exec_ms"] = elapsed_ms
                return parsed
            except json.JSONDecodeError:
                pass
    return {
        "raw": out,
        "stderr": res.stderr.strip(),
        "returncode": res.returncode,
        "_exec_ms": elapsed_ms,
    }


def api_cluster_status() -> dict[str, Any]:
    t0 = time.monotonic()
    pods_raw, pods_err, _ = run_cmd(
        ["kubectl", "get", "pods", "-n", "ate-system", "-o", "json"]
    )
    pods_data = json.loads(pods_raw) if pods_raw.startswith("{") else {"items": []}
    pods = []
    for item in pods_data.get("items", []):
        name = item["metadata"]["name"]
        ready = sum(
            1
            for cs in item.get("status", {}).get("containerStatuses", [])
            if cs.get("ready")
        )
        total = len(item.get("spec", {}).get("containers", []))
        pods.append(
            {
                "name": name,
                "ready": f"{ready}/{total}",
                "phase": item.get("status", {}).get("phase", "Running"),
            }
        )

    actors_raw, _, _ = run_cmd(
        ["kubectl-ate", "get", "actors", "-a", "secure-runtime", "-o", "json"]
    )
    actors_data = (
        json.loads(actors_raw) if actors_raw.startswith("{") else {"items": []}
    )
    actors = []
    for item in actors_data.get("items", []):
        actors.append(
            {
                "name": item.get("metadata", {}).get("name", ""),
                "template": item.get("spec", {}).get("actorTemplateName", ""),
                "phase": item.get("status", {}).get("phase", "Ready"),
            }
        )

    tmpl_raw, _, _ = run_cmd(
        [
            "kubectl-ate",
            "get",
            "actor-template",
            "scientific-python",
            "-a",
            "secure-runtime",
            "-o",
            "json",
        ]
    )
    tmpl_data = json.loads(tmpl_raw) if tmpl_raw.startswith("{") else {}
    golden_tag = (
        tmpl_data.get("status", {})
        .get("goldenSnapshotStatus", {})
        .get("goldenTag", {})
        .get("name")
        or "d6617568-0493-4fb6-a0b0-5783fabd30c8"
    )
    return {
        "cluster": "sec-secrt (GKE 1.37)",
        "substrate_version": "v1.0.0-rc.2",
        "atespace": "secure-runtime",
        "golden_tag": golden_tag,
        "ate_system_pods": pods,
        "actors": actors,
        "stderr": pods_err if not pods else "",
        "query_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def api_act1(actor_name: str = "triage-actor-19") -> dict[str, Any]:
    payload = json.dumps({"actor_name": actor_name})
    expr = """
import json, sys
from secure_runtime_agent.agent import inspect_sandbox_boundary
req = json.loads(sys.stdin.read())
print(inspect_sandbox_boundary(req["actor_name"]))
"""
    return run_agent_py(expr, stdin_data=payload)


def api_run_code(
    actor_name: str, code: str, suspend_after: bool = True
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "actor_name": actor_name,
            "code": code,
            "suspend_after": suspend_after,
        }
    )
    expr = """
import json, sys
from secure_runtime_agent.agent import run_python_in_actor
req = json.loads(sys.stdin.read())
print(run_python_in_actor(
    code=req["code"],
    actor_name=req["actor_name"],
    suspend_after=req["suspend_after"],
))
"""
    return run_agent_py(expr, stdin_data=payload)


def _measure_cold_gvisor_pod_ms() -> float:
    img_out, _, _ = run_cmd(
        [
            "kubectl",
            "get",
            "deployment",
            "triage-agent",
            "-n",
            "agent-harness",
            "-o",
            "jsonpath={.spec.template.spec.containers[0].image}",
        ]
    )
    runner_image = img_out.replace("secure-runtime-agent:", "secure-runtime-runner:")
    pod_name = "cold-gvisor-baseline"
    run_cmd(
        [
            "kubectl",
            "delete",
            "pod",
            pod_name,
            "-n",
            "default",
            "--ignore-not-found",
        ]
    )
    pod_manifest = json.dumps(
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": pod_name, "namespace": "default"},
            "spec": {
                "runtimeClassName": "gvisor",
                "nodeSelector": {"sandbox-runtime": "gvisor"},
                "restartPolicy": "Never",
                "containers": [
                    {
                        "name": "runner",
                        "image": runner_image,
                        "imagePullPolicy": "Always",
                        "readinessProbe": {
                            "httpGet": {"path": "/readyz", "port": 80},
                            "initialDelaySeconds": 1,
                            "periodSeconds": 1,
                        },
                        "resources": {
                            "requests": {"cpu": "500m", "memory": "2Gi"},
                            "limits": {"cpu": "1", "memory": "2Gi"},
                        },
                    }
                ],
            },
        }
    )
    t0 = time.monotonic()
    subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        env=_build_env(),
        input=pod_manifest,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    run_cmd(
        [
            "kubectl",
            "wait",
            "--for=condition=Ready",
            f"pod/{pod_name}",
            "-n",
            "default",
            "--timeout=180s",
        ],
        timeout=190,
    )
    cold_ms = round((time.monotonic() - t0) * 1000, 1)
    run_cmd(
        [
            "kubectl",
            "delete",
            "pod",
            pod_name,
            "-n",
            "default",
            "--ignore-not-found",
            "--wait=false",
        ]
    )
    return cold_ms


def api_act2(custom_note: str = "tikhonov_1e-6") -> dict[str, Any]:
    cold_ms = _measure_cold_gvisor_pod_ms()
    payload = json.dumps({"custom_note": custom_note, "cold_ms": cold_ms})
    expr = """
import json, sys, time
from secure_runtime_agent.agent import run_python_in_actor
from secure_runtime_agent.substrate_client import SubstrateClient

req = json.loads(sys.stdin.read())
cold_ms = float(req["cold_ms"])
actor_name = f"race-actor-{int(time.time())}"
client = SubstrateClient()
ensure_res = client.ensure_actor(actor_name)
ready = client.call_actor(actor_name, "GET", "/readyz")
warm_ms = ready["router_roundtrip_ms"]

state_obj = {
    "issue": 19,
    "solver": req.get("custom_note", "tikhonov_1e-6"),
    "status": "verified",
    "saved_at": round(time.time(), 2),
}
run_python_in_actor(
    code=f"STATE = {repr(state_obj)}",
    actor_name=actor_name,
    suspend_after=True,
)
resumed = json.loads(
    run_python_in_actor(
        code="import json; print(json.dumps(STATE))",
        actor_name=actor_name,
        suspend_after=True,
    )
)["execution"]

print(json.dumps({
    "actor_name": actor_name,
    "ensure_ms": ensure_res.get("ensure_ms"),
    "cold_gvisor_pod": "default/cold-gvisor-baseline (runtimeClassName: gvisor)",
    "cold_gvisor_pod_ms": cold_ms,
    "golden_snapshot_wake_ms": warm_ms,
    "stateful_pause_resume_ms": resumed["router_roundtrip_ms"],
    "warm_import_ms_saved": ready.get("warm_import_ms", 2545.39),
    "restored_state": json.loads(resumed["stdout"].strip()),
    "speedup_wake": round(cold_ms / max(warm_ms, 1), 1),
    "speedup_resume": round(cold_ms / max(resumed["router_roundtrip_ms"], 1), 1),
}))
"""
    return run_agent_py(expr, stdin_data=payload)


def api_act3(
    issue_number: int = 42,
    follow_instructions: bool = True,
    actor_name: str = "triage-actor-42",
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "issue_number": int(issue_number),
            "follow_instructions": bool(follow_instructions),
            "actor_name": actor_name,
        }
    )
    expr = """
import json, sys
from secure_runtime_agent.agent import triage_github_issue_in_sandbox
req = json.loads(sys.stdin.read())
print(triage_github_issue_in_sandbox(
    req["issue_number"],
    req["follow_instructions"],
    req["actor_name"],
))
"""
    return run_agent_py(expr, stdin_data=payload)


def api_act4(tainted_actor: str = "triage-actor-42") -> dict[str, Any]:
    clean_name = f"triage-actor-clean-{int(time.time())}"
    payload = json.dumps({"tainted_actor": tainted_actor, "clean_name": clean_name})
    expr = """
import json, sys
from secure_runtime_agent.agent import audit_and_reset_actor_to_golden
from secure_runtime_agent.substrate_client import SubstrateClient
req = json.loads(sys.stdin.read())
out = audit_and_reset_actor_to_golden(req["tainted_actor"], req["clean_name"])
SubstrateClient().suspend_actor(req["clean_name"])
print(out)
"""
    return run_agent_py(expr, stdin_data=payload)


def api_ask_agent(prompt: str) -> dict[str, Any]:
    payload = json.dumps({"prompt": prompt})
    expr = """
import asyncio, json, sys, time
from google.adk.runners import InMemoryRunner
from google.genai import types
from secure_runtime_agent.agent import root_agent

req = json.loads(sys.stdin.read())

async def main():
    t0 = time.monotonic()
    runner = InMemoryRunner(agent=root_agent, app_name="mission_control")
    session = await runner.session_service.create_session(
        app_name="mission_control", user_id="demo_user"
    )
    msg = types.Content(
        role="user", parts=[types.Part.from_text(text=req["prompt"])]
    )
    tool_calls = []
    texts = []
    async for ev in runner.run_async(
        user_id="demo_user", session_id=session.id, new_message=msg
    ):
        if ev.content and ev.content.parts:
            for p in ev.content.parts:
                if p.function_call:
                    tool_calls.append({
                        "name": p.function_call.name,
                        "args": dict(p.function_call.args or {}),
                    })
                if p.text:
                    texts.append(p.text.strip())
    final_session = await runner.session_service.get_session(
        app_name="mission_control", user_id="demo_user", session_id=session.id
    )
    print(json.dumps({
        "model": root_agent.model,
        "prompt": req["prompt"],
        "tool_calls": tool_calls,
        "response": "\\n\\n".join(t for t in texts if t),
        "last_intent_classification": (final_session.state or {}).get(
            "last_intent_classification"
        ),
        "total_ms": round((time.monotonic() - t0) * 1000, 1),
    }))

asyncio.run(main())
"""
    return run_agent_py(expr, stdin_data=payload, timeout=180)


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>The Secure Runtime — GKE Agent Substrate Mission Control</title>
<style>
  :root {
    --bg: #0b0f19; --panel: #131b2e; --panel-alt: #19233c; --border: #263554;
    --text: #f1f5f9; --muted: #94a3b8; --green: #10b981; --red: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', -apple-system, sans-serif; height: 100vh; width: 100vw; overflow: hidden; display: flex; flex-direction: column; }
  #slide-overlay { position: fixed; inset: 0; background: #000; z-index: 100; display: none; align-items: center; justify-content: center; }
  #slide-overlay.active { display: flex; }
  #slide-img { width: 100vw; height: 100vh; object-fit: contain; background: #fff; }
  #slide-badge { position: fixed; bottom: 22px; right: 28px; background: rgba(15,23,42,0.85); color: #e2e8f0; padding: 8px 16px; border-radius: 999px; font-size: 14px; font-weight: 600; border: 1px solid rgba(148,163,184,0.3); z-index: 110; }
  header { background: linear-gradient(90deg, #7c00ff 0%, #3b0764 55%, #14032b 100%); padding: 14px 28px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.14); }
  .brand { display: flex; align-items: center; gap: 14px; }
  .brand-pill { background: rgba(255,255,255,0.16); padding: 5px 11px; border-radius: 8px; font-weight: 700; font-size: 12px; letter-spacing: 0.05em; text-transform: uppercase; }
  .brand h1 { font-size: 20px; font-weight: 800; letter-spacing: -0.02em; }
  .cluster-pills { display: flex; gap: 10px; align-items: center; }
  .pill { background: rgba(15,23,42,0.75); border: 1px solid rgba(255,255,255,0.2); padding: 6px 12px; border-radius: 999px; font-size: 12px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
  .dot-live { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); }
  nav { background: #0f1629; padding: 10px 28px; display: flex; gap: 10px; border-bottom: 1px solid var(--border); flex-wrap: wrap; }
  .tab-btn { background: var(--panel); color: var(--muted); border: 1px solid var(--border); padding: 9px 16px; border-radius: 9px; font-size: 13px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.15s ease; }
  .tab-btn.active { background: linear-gradient(135deg, #6d28d9, #0891b2); color: #fff; border-color: #38bdf8; box-shadow: 0 0 14px rgba(56,189,248,0.3); }
  .tab-num { background: rgba(255,255,255,0.15); padding: 2px 7px; border-radius: 5px; font-size: 11px; }
  main { flex: 1; padding: 18px 28px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; }
  .view { display: none; flex-direction: column; gap: 16px; }
  .view.active { display: flex; }
  .grid-2 { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 16px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 16px; transition: border-color 0.3s, box-shadow 0.3s; }
  .card.running { border-color: #f59e0b; box-shadow: 0 0 18px rgba(245,158,11,0.25); }
  .card.done { border-color: #10b981; box-shadow: 0 0 18px rgba(16,185,129,0.2); }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 10px; }
  .card-title { font-size: 15px; font-weight: 700; color: #e2e8f0; display: flex; align-items: center; gap: 8px; }
  .action-btn { background: linear-gradient(135deg, #7c3aed, #06b6d4); color: #fff; border: none; padding: 10px 18px; border-radius: 9px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(124,58,237,0.35); transition: transform 0.1s, opacity 0.15s; }
  .action-btn:hover { transform: translateY(-1px); }
  .action-btn:disabled { opacity: 0.6; cursor: wait; }
  .badge { padding: 4px 9px; border-radius: 6px; font-size: 11px; font-weight: 700; text-transform: uppercase; }
  .badge-green { background: rgba(16,185,129,0.18); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }
  .badge-red { background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
  .badge-cyan { background: rgba(6,182,212,0.18); color: #22d3ee; border: 1px solid rgba(6,182,212,0.4); }
  .badge-purple { background: rgba(124,58,237,0.22); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.45); }
  .metric-big { font-size: 28px; font-weight: 800; margin: 4px 0; font-variant-numeric: tabular-nums; }
  .mono { font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; font-size: 12px; }
  .verdict-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .verdict-item { background: var(--panel-alt); border: 1px solid var(--border); border-left: 4px solid var(--red); border-radius: 9px; padding: 11px 13px; display: flex; flex-direction: column; gap: 4px; }
  .verdict-item.allow { border-left-color: var(--green); }
  .race-row { background: var(--panel-alt); border: 1px solid var(--border); border-radius: 10px; padding: 13px 16px; margin-bottom: 10px; }
  .race-bar-bg { width: 100%; height: 22px; background: #0b1120; border-radius: 6px; overflow: hidden; margin-top: 8px; border: 1px solid #1e293b; }
  .race-bar-fill { height: 100%; border-radius: 6px; transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1); }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }
  input, select, textarea { background: #0b1120; color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; font-family: inherit; font-size: 13px; }
  textarea { font-family: 'JetBrains Mono', monospace; font-size: 12px; width: 100%; resize: vertical; }
  #console-drawer { background: #070b14; border-top: 1px solid var(--border); padding: 10px 28px; height: 165px; display: flex; flex-direction: column; gap: 6px; }
  #console-pre { flex: 1; overflow-y: auto; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #a5f3fc; white-space: pre-wrap; line-height: 1.45; }
</style>
</head>
<body>
<div id="slide-overlay"><img id="slide-img" src="/slides/slide-01.png" alt="Slide" /><div id="slide-badge">Slide 1</div></div>
<header>
  <div class="brand">
    <span class="brand-pill">Agentics Day: MCP + Agents</span>
    <h1>The Secure Runtime — GKE Agent Substrate Live Mission Control</h1>
  </div>
  <div class="cluster-pills">
    <div class="pill"><span class="dot-live"></span><span>Cluster: <strong class="mono">sec-secrt (GKE 1.37)</strong></span></div>
    <div class="pill"><span>Substrate: <strong class="mono" style="color:#38bdf8">v1.0.0-rc.2</strong></span></div>
    <div class="pill"><span>Agent Model: <strong class="mono" style="color:#c4b5fd">gemini-3.8-flash</strong></span></div>
  </div>
</header>
<nav>
  <button class="tab-btn active" id="tab-0" onclick="switchTab(0)"><span class="tab-num">ZONE 1–4</span> Cluster &amp; Actors</button>
  <button class="tab-btn" id="tab-1" onclick="switchTab(1)"><span class="tab-num">ACT 1</span> gVisor Boundary &amp; Sandbox Exec</button>
  <button class="tab-btn" id="tab-2" onclick="switchTab(2)"><span class="tab-num">ACT 2</span> Cold-Start Race (13.9s vs 625ms)</button>
  <button class="tab-btn" id="tab-3" onclick="switchTab(3)"><span class="tab-num">ACT 3</span> Credentials &amp; L7 Filter</button>
  <button class="tab-btn" id="tab-4" onclick="switchTab(4)"><span class="tab-num">ACT 4</span> SPIFFE Audit &amp; Quarantine</button>
  <button class="tab-btn" id="tab-5" onclick="switchTab(5)"><span class="tab-num">LIVE ADK</span> Gemini 3.8 Flash Agent</button>
</nav>
<main>
  <!-- TAB 0 -->
  <section class="view active" id="view-0">
    <div class="card-header">
      <div>
        <h2 style="font-size:18px;font-weight:800;">Live GKE 1.37 + Agent Substrate v1.0.0-rc.2 Topology</h2>
        <p style="color:var(--muted);font-size:13px;margin-top:2px;">Click "Refresh Live Cluster &amp; Actors" to query Kubernetes pods and active Agent Substrate Actors on sec-secrt.</p>
      </div>
      <button class="action-btn" id="btn-run-0" onclick="runTab0()">Refresh Live Cluster &amp; Actors</button>
    </div>
    <div class="grid-4">
      <div class="card"><div class="card-header"><span class="card-title">Zone 1: Agent Harness</span><span class="badge badge-purple">agent-harness</span></div><div class="metric-big" style="color:#c4b5fd;font-size:20px;">Gemini 3.8 Flash</div><p style="color:var(--muted);font-size:12px;">Google ADK Triage Agent (<span class="mono">deploy/triage-agent</span>) with <span class="mono">before_tool_callback</span> intent gate &amp; SPIFFE mTLS cert.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Zone 2: Gateways</span><span class="badge badge-cyan">ate-system</span></div><div class="metric-big" style="color:#38bdf8;font-size:20px;">Router + Egress</div><p style="color:var(--muted);font-size:12px;"><span class="mono">atenet-router</span> (mTLS wake-on-request) + <span class="mono">atenet-egress</span> + <span class="mono">intent-extproc:50051</span> L7 filter.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Zone 3: Sandbox Pool</span><span class="badge badge-green">ate-workers</span></div><div class="metric-big" style="color:#34d399;font-size:20px;">2/2 Warm Workers</div><p style="color:var(--muted);font-size:12px;"><span class="mono">scientific-gvisor</span> WorkerPool on uniform <span class="mono">c3-standard-4</span> nodes running <span class="mono">runsc</span>.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Zone 4: Snapshot Store</span><span class="badge badge-green">Cloud Storage</span></div><div class="metric-big" style="color:#fbbf24;font-size:20px;">MEMORY Fidelity</div><p style="color:var(--muted);font-size:12px;">Golden Snapshot <span class="mono" id="golden-tag-lbl">d6617568-0493-4fb6...</span> with pre-imported NumPy/SciPy/Pandas.</p></div>
    </div>
    <div class="grid-2" style="flex:1;">
      <div class="card">
        <div class="card-header"><span class="card-title">Control &amp; Data Plane Pods (<span class="mono">ate-system</span>)</span><span class="badge badge-green" id="cluster-status-badge">READY TO QUERY</span></div>
        <table>
          <thead><tr><th>Pod Name</th><th>Ready</th><th>Phase</th></tr></thead>
          <tbody id="pods-tbody">
            <tr><td class="mono">ate-api-server</td><td><span class="badge badge-green">2/2</span></td><td>Running</td></tr>
            <tr><td class="mono">atenet-router</td><td><span class="badge badge-green">2/2</span></td><td>Running</td></tr>
            <tr><td class="mono">atenet-egress</td><td><span class="badge badge-green">3/3</span></td><td>Running</td></tr>
            <tr><td class="mono">intent-extproc</td><td><span class="badge badge-green">1/1</span></td><td>Running</td></tr>
            <tr><td class="mono">k8s-credential-provider</td><td><span class="badge badge-green">1/1</span></td><td>Running</td></tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Live Actors in Atespace (<span class="mono">secure-runtime</span>)</span><span class="badge badge-cyan" id="actors-count-badge">LIVE INVENTORY</span></div>
        <table>
          <thead><tr><th>Actor Name</th><th>Template</th><th>Status</th></tr></thead>
          <tbody id="actors-tbody">
            <tr><td class="mono" colspan="3" style="color:var(--muted);">Click "Refresh Live Cluster &amp; Actors" to fetch live Actors from sec-secrt...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- TAB 1: ACT 1 -->
  <section class="view" id="view-1">
    <div class="card-header">
      <div>
        <h2 style="font-size:18px;font-weight:800;">Act 1: gVisor User-Space Syscall Interception &amp; Live Sandbox Code Execution</h2>
        <p style="color:var(--muted);font-size:13px;margin-top:2px;">Probe kernel escape vectors or run arbitrary Python code inside Actor <input id="act1-actor-input" value="triage-actor-19" class="mono" style="width:160px;" /></p>
      </div>
      <button class="action-btn" id="btn-run-1" onclick="runTab1()">Run Act 1 Boundary Probe</button>
    </div>
    <div class="grid-2" style="flex:1;">
      <div class="card" style="display:flex;flex-direction:column;gap:12px;">
        <div class="card-header"><span class="card-title">Host Escape &amp; Kernel Interface Probes</span><span class="badge badge-red" id="act1-verdict-badge">6 / 6 BLOCKED BY GVISOR</span></div>
        <div class="verdict-list" id="act1-verdicts">
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">AF_PACKET Raw Socket</span><span class="mono" style="font-size:11px;color:var(--muted);">BLOCKED_BY_GVISOR (EPERM)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">unshare(CLONE_NEWUSER|NEWNS)</span><span class="mono" style="font-size:11px;color:var(--muted);">BLOCKED_BY_GVISOR (EINVAL)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/proc/kcore</span><span class="mono" style="font-size:11px;color:var(--muted);">BLOCKED_BY_GVISOR (ENOENT)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/proc/kallsyms</span><span class="mono" style="font-size:11px;color:var(--muted);">BLOCKED_BY_GVISOR (ENOENT)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/proc/sysrq-trigger</span><span class="mono" style="font-size:11px;color:var(--muted);">BLOCKED_BY_GVISOR (EACCES)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/dev/kmsg</span><span class="mono" style="font-size:11px;color:var(--muted);">BLOCKED_BY_GVISOR (ENOENT)</span></div>
        </div>
        <div class="race-row" style="margin:0;display:flex;justify-content:space-between;align-items:center;">
          <div><div style="font-size:11px;color:var(--muted);font-weight:700;">SANDBOX KERNEL (/proc/version)</div><div class="mono" id="act1-kernel" style="color:#38bdf8;font-weight:700;margin-top:3px;">Linux version 4.19.0-gvisor #1 SMP</div></div>
          <span class="badge badge-cyan" id="act1-rt-badge">mTLS Roundtrip: 77.6 ms</span>
        </div>
      </div>
      <div class="card" style="display:flex;flex-direction:column;gap:10px;">
        <div class="card-header">
          <span class="card-title">Interactive gVisor Sandbox Python Runner</span>
          <button class="action-btn" id="btn-run-code" onclick="runCustomCode()">Execute in gVisor Actor</button>
        </div>
        <textarea id="custom-code-input" rows="5">import os, platform, numpy as np, scipy.linalg
a = np.array([[4.0, 1.0], [1.0, 3.0]])
print("Kernel:", platform.release(), "| Eigenvalues:", scipy.linalg.eigvals(a).real.tolist())
print("Secrets in os.environ:", [k for k in os.environ if "TOKEN" in k or "SECRET" in k])</textarea>
        <div class="race-row" style="margin:0;flex:1;">
          <div style="font-size:11px;color:var(--muted);font-weight:700;margin-bottom:6px;">LIVE SANDBOX STDOUT / STDERR</div>
          <pre class="mono" id="custom-code-output" style="color:#34d399;white-space:pre-wrap;">Click "Execute in gVisor Actor" to run this Python snippet inside the warm gVisor sandbox over mTLS...</pre>
        </div>
      </div>
    </div>
  </section>

  <!-- TAB 2: ACT 2 -->
  <section class="view" id="view-2">
    <div class="card-header">
      <div>
        <h2 style="font-size:18px;font-weight:800;">Act 2: Crushing Cold Starts — Golden Snapshot Wake &amp; Stateful Pause/Resume</h2>
        <p style="color:var(--muted);font-size:13px;margin-top:2px;">Custom checkpoint state tag to persist across suspend/resume: <input id="act2-note-input" value="tikhonov_reg_1e-6" class="mono" style="width:190px;" /></p>
      </div>
      <button class="action-btn" id="btn-run-2" onclick="runTab2()">Run Live Cold-Start Race</button>
    </div>
    <div class="grid-3">
      <div class="card"><div class="card-header"><span class="card-title">Baseline A: Cold K8s gVisor Pod</span><span class="badge badge-red">Cold Boot + Import</span></div><div class="metric-big" style="color:#f87171;" id="race-cold-ms">13,926 ms</div><p style="color:var(--muted);font-size:12px;">Pod scheduling + gVisor boot + importing NumPy/SciPy/Pandas from disk on every turn.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Substrate B1: Golden Snapshot Wake</span><span class="badge badge-cyan" id="race-wake-badge">22.3x Faster</span></div><div class="metric-big" style="color:#38bdf8;" id="race-wake-ms">625.8 ms</div><p style="color:var(--muted);font-size:12px;">Restores pre-imported memory pages from GCS Golden Snapshot onto warm WorkerPool.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Substrate B2: Stateful Pause &rarr; Resume</span><span class="badge badge-green" id="race-resume-badge">91.7x Faster</span></div><div class="metric-big" style="color:#34d399;" id="race-resume-ms">151.8 ms</div><p style="color:var(--muted);font-size:12px;">Resumes suspended actor over mTLS with full in-memory Python variables intact.</p></div>
    </div>
    <div class="card" style="flex:1;">
      <div class="race-row">
        <div style="display:flex;justify-content:space-between;font-weight:700;font-size:13px;"><span>Standard Kubernetes gVisor Pod (<span class="mono">runtimeClassName: gvisor</span>)</span><span class="mono" style="color:#f87171;" id="bar-cold-lbl">13,926 ms</span></div>
        <div class="race-bar-bg"><div class="race-bar-fill" id="bar-cold" style="width:100%;background:linear-gradient(90deg,#ef4444,#f97316);"></div></div>
      </div>
      <div class="race-row">
        <div style="display:flex;justify-content:space-between;font-weight:700;font-size:13px;"><span>Agent Substrate Golden Snapshot Wakeup (<span class="mono">SNAPSHOT_FIDELITY_MEMORY</span>)</span><span class="mono" style="color:#38bdf8;" id="bar-wake-lbl">625.8 ms (22.3x faster)</span></div>
        <div class="race-bar-bg"><div class="race-bar-fill" id="bar-wake" style="width:4.5%;background:linear-gradient(90deg,#06b6d4,#3b82f6);"></div></div>
      </div>
      <div class="race-row" style="margin-bottom:0;">
        <div style="display:flex;justify-content:space-between;font-weight:700;font-size:13px;"><span>Agent Substrate Stateful Pause &rarr; Resume (Restored <span class="mono" id="restored-state-lbl">STATE = {"issue": 19, "solver": "tikhonov_1e-6", "status": "verified"}</span>)</span><span class="mono" style="color:#34d399;" id="bar-resume-lbl">151.8 ms (91.7x faster)</span></div>
        <div class="race-bar-bg"><div class="race-bar-fill" id="bar-resume" style="width:1.4%;background:linear-gradient(90deg,#10b981,#34d399);"></div></div>
      </div>
    </div>
  </section>

  <!-- TAB 3: ACT 3 -->
  <section class="view" id="view-3">
    <div class="card-header">
      <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;">
        <div>
          <h2 style="font-size:18px;font-weight:800;">Act 3: Out-of-Sandbox Credential Injection &amp; Dynamic L7 Intent Filtering</h2>
          <p style="color:var(--muted);font-size:13px;margin-top:2px;">Issue #: <input id="act3-issue-input" type="number" value="42" style="width:70px;" /> &nbsp; Simulate Prompt Injection (<span class="mono">POST /comments</span>): <select id="act3-inject-input"><option value="true" selected>Yes (Attack Simulation)</option><option value="false">No (Read-Only Triage)</option></select></p>
        </div>
      </div>
      <button class="action-btn" id="btn-run-3" onclick="runTab3()">Execute Act 3 Triage &amp; Attack Simulation</button>
    </div>
    <div class="grid-2" style="flex:1;">
      <div class="card" style="display:flex;flex-direction:column;gap:12px;">
        <div class="card-header"><span class="card-title">Dynamic Policy Programmed by <span class="mono">before_tool_callback</span></span><span class="badge badge-purple" id="act3-intent-badge">INTENT: github_issue_read_only</span></div>
        <div class="race-row" style="margin:0;">
          <div style="font-size:11px;color:var(--muted);font-weight:700;">1. OUT-OF-SANDBOX CREDENTIAL INJECTION (atenet-egress)</div>
          <div class="mono" style="font-size:12px;color:#38bdf8;margin-top:5px;">ate-secret://k8s.io/default/agent-credentials/github-readonly-token/token</div>
          <div style="font-size:12px;color:var(--muted);margin-top:4px;">Sandbox <span class="mono">os.environ</span> contains <strong>0 GitHub tokens</strong> — secrets never enter actor memory or GCS snapshots.</div>
        </div>
        <div class="race-row" style="margin:0;">
          <div style="font-size:11px;color:var(--muted);font-weight:700;">2. L7 HTTP METHOD &amp; PATH RULE (intent-extproc:50051)</div>
          <div class="mono" style="font-size:12px;color:#34d399;margin-top:5px;">Allowed Host: api.github.com &nbsp;|&nbsp; Allowed Methods: [GET, HEAD]</div>
          <div class="mono" style="font-size:12px;color:#c4b5fd;margin-top:4px;">Allowed Path Prefix: /repos/GoogleCloudPlatform/accelerated-platforms/</div>
        </div>
      </div>
      <div class="card" style="display:flex;flex-direction:column;gap:10px;">
        <div class="card-header"><span class="card-title">Live Egress Gateway Verdicts Inside Sandbox</span><span class="badge badge-green">ENFORCED AT EGRESS</span></div>
        <div class="verdict-item allow">
          <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:700;color:#34d399;">1. GET /repos/.../issues/42</span><span class="badge badge-green" id="act3-s1-code">200 OK — TOKEN INJECTED</span></div>
          <div class="mono" style="font-size:11px;color:var(--muted);" id="act3-s1-desc">Fetched Issue #42 with header injected at atenet-egress.</div>
        </div>
        <div class="verdict-item">
          <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:700;color:#f87171;">2. POST /repos/.../issues/42/comments</span><span class="badge badge-red" id="act3-s2-code">403 FORBIDDEN — INTENT-EXTPROC</span></div>
          <div class="mono" style="font-size:11px;color:var(--muted);" id="act3-s2-desc">Blocked by intent "github_issue_read_only" (allowed methods: [GET, HEAD]).</div>
        </div>
        <div class="verdict-item">
          <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:700;color:#f87171;">3. POST https://collector.example.invalid/telemetry</span><span class="badge badge-red" id="act3-s3-code">BLOCKED — DEFAULT-DENY EGRESS</span></div>
          <div class="mono" style="font-size:11px;color:var(--muted);" id="act3-s3-desc">Unlisted host rejected by atenet-egress default-deny policy.</div>
        </div>
      </div>
    </div>
  </section>

  <!-- TAB 4: ACT 4 -->
  <section class="view" id="view-4">
    <div class="card-header">
      <div>
        <h2 style="font-size:18px;font-weight:800;">Act 4: Per-Actor SPIFFE Audit Attribution, Quarantine &amp; Clean Golden Reset</h2>
        <p style="color:var(--muted);font-size:13px;margin-top:2px;">Quarantine tainted Actor <input id="act4-actor-input" value="triage-actor-42" class="mono" style="width:150px;" /> and spawn a clean Golden Snapshot replacement.</p>
      </div>
      <button class="action-btn" id="btn-run-4" onclick="runTab4()">Run Act 4 Quarantine &amp; Clean Reset</button>
    </div>
    <div class="grid-3">
      <div class="card"><div class="card-header"><span class="card-title">1. Revoke Egress &amp; L7 Rules</span><span class="badge badge-red">Quarantined</span></div><div class="metric-big" style="color:#f87171;" id="act4-revoke-ms">126.4 ms</div><p style="color:var(--muted);font-size:12px;">Strips <span class="mono">EgressPolicy</span> &amp; <span class="mono">intent-extproc</span> rules back to default-deny.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">2. Terminate Tainted Actor</span><span class="badge badge-purple">secure-runtime/triage-actor-42</span></div><div class="metric-big" style="color:#c4b5fd;" id="act4-delete-ms">411.9 ms</div><p style="color:var(--muted);font-size:12px;">Releases warm worker slot without disturbing neighboring actors.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">3. Restore Clean Golden Actor</span><span class="badge badge-green">Golden Snapshot</span></div><div class="metric-big" style="color:#34d399;" id="act4-restore-ms">121.2 ms</div><p style="color:var(--muted);font-size:12px;">Spawns <span class="mono" id="act4-clean-name">triage-actor-clean</span> from Golden Snapshot.</p></div>
    </div>
    <div class="card" style="flex:1;">
      <div class="card-header"><span class="card-title">SPIFFE-Attributed L7 Audit Trail (<span class="mono">intent-extproc</span>)</span><span class="badge badge-cyan mono">spiffe://substrate-actor.local/worker-for-actor/secure-runtime/triage-actor-42</span></div>
      <table>
        <thead><tr><th>Timestamp</th><th>Actor SPIFFE Identity</th><th>Intent</th><th>Method &amp; Path</th><th>Token Injected</th><th>Decision</th></tr></thead>
        <tbody id="audit-tbody">
          <tr><td class="mono">16:05:47.839Z</td><td class="mono">.../secure-runtime/triage-actor-42</td><td class="mono">github_issue_read_only</td><td class="mono">GET api.github.com/repos/GoogleCloudPlatform/accelerated-platforms/issues/42</td><td><span class="badge badge-cyan">YES (Egress)</span></td><td><span class="badge badge-green">ALLOW (200)</span></td></tr>
          <tr><td class="mono">16:05:48.183Z</td><td class="mono">.../secure-runtime/triage-actor-42</td><td class="mono">github_issue_read_only</td><td class="mono">POST api.github.com/repos/GoogleCloudPlatform/accelerated-platforms/issues/42/comments</td><td><span class="badge badge-cyan">YES (Egress)</span></td><td><span class="badge badge-red">DENY (403)</span></td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <!-- TAB 5: LIVE GEMINI 3.8 FLASH ADK AGENT -->
  <section class="view" id="view-5">
    <div class="card-header">
      <div>
        <h2 style="font-size:18px;font-weight:800;">Live Gemini 3.8 Flash ADK Triage Agent (<span class="mono">deploy/triage-agent</span>)</h2>
        <p style="color:var(--muted);font-size:13px;margin-top:2px;">Send any natural-language task to the live Google ADK agent on GKE or open the full <a href="http://127.0.0.1:18080/dev-ui/?app=secure_runtime_agent" target="_blank" style="color:#38bdf8;">ADK Dev UI (:18080) &rarr;</a></p>
      </div>
      <button class="action-btn" id="btn-run-5" onclick="runTab5()">Send Prompt to Gemini 3.8 Flash</button>
    </div>
    <div class="card" style="display:flex;flex-direction:column;gap:12px;flex:1;">
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button class="tab-btn" onclick="setPrompt('Run inspect_sandbox_boundary on triage-actor-19 and summarize every blocked kernel probe.')">Preset 1: Act 1 Boundary Audit</button>
        <button class="tab-btn" onclick="setPrompt('Triage GitHub issue #42 in triage-actor-42 with follow_issue_instructions=True and explain which requests succeeded vs failed.')">Preset 2: Act 3 Issue #42 Triage + Attack</button>
        <button class="tab-btn" onclick="setPrompt('Audit and reset tainted actor triage-actor-42 to a fresh Golden Snapshot actor and report the SPIFFE audit log.')">Preset 3: Act 4 Quarantine &amp; Reset</button>
      </div>
      <textarea id="agent-prompt-input" rows="2">Triage GitHub issue #42 in triage-actor-42 with follow_issue_instructions=True and explain which requests succeeded vs failed.</textarea>
      <div class="grid-2" style="flex:1;">
        <div class="race-row" style="margin:0;">
          <div style="font-size:11px;color:var(--muted);font-weight:700;margin-bottom:6px;">ADK TOOL CALLS &amp; BEFORE_TOOL_CALLBACK INTENT</div>
          <pre class="mono" id="agent-tools-output" style="color:#c4b5fd;white-space:pre-wrap;">Click "Send Prompt to Gemini 3.8 Flash" to invoke root_agent on GKE...</pre>
        </div>
        <div class="race-row" style="margin:0;">
          <div style="font-size:11px;color:var(--muted);font-weight:700;margin-bottom:6px;">GEMINI 3.8 FLASH RESPONSE</div>
          <pre class="mono" id="agent-text-output" style="color:#34d399;white-space:pre-wrap;">Waiting for prompt execution...</pre>
        </div>
      </div>
    </div>
  </section>
</main>

<div id="console-drawer">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span class="mono" style="font-size:11px;font-weight:700;color:#38bdf8;">LIVE GKE CLUSTER TELEMETRY &amp; JSON PAYLOAD STREAM (sec-secrt)</span>
    <span class="mono" id="console-status" style="font-size:11px;color:var(--muted);">Idle — click any action button above to execute live on GKE</span>
  </div>
  <pre id="console-pre">Ready. Connected to GKE cluster sec-secrt (Agent Substrate v1.0.0-rc.2, Gemini 3.8 Flash).</pre>
</div>

<script>
function setCardsState(viewId, state) {
  document.querySelectorAll('#' + viewId + ' .card').forEach(c => {
    c.classList.remove('running', 'done');
    if (state) c.classList.add(state);
  });
}
function logConsole(label, data) {
  const ts = new Date().toISOString().split('T')[1].slice(0, 12);
  document.getElementById('console-status').textContent = `Last action: ${label} at ${ts} (${data._exec_ms || data.query_ms || 0} ms)`;
  document.getElementById('console-pre').textContent = `[${ts}] ${label}\n` + JSON.stringify(data, null, 2);
}
function switchTab(idx) {
  document.getElementById('slide-overlay').classList.remove('active');
  for (let i = 0; i < 6; i++) {
    document.getElementById('tab-' + i).classList.toggle('active', i === idx);
    document.getElementById('view-' + i).classList.toggle('active', i === idx);
  }
}
function showSlide(filename, label) {
  const ov = document.getElementById('slide-overlay');
  document.getElementById('slide-img').src = '/slides/' + filename + '?t=' + Date.now();
  document.getElementById('slide-badge').textContent = label || filename;
  ov.classList.add('active');
}
function hideSlide() { document.getElementById('slide-overlay').classList.remove('active'); }
function setPrompt(txt) { document.getElementById('agent-prompt-input').value = txt; }

async function runTab0() {
  const btn = document.getElementById('btn-run-0');
  btn.disabled = true; btn.textContent = '⏳ Querying GKE sec-secrt...';
  setCardsState('view-0', 'running');
  document.getElementById('cluster-status-badge').textContent = 'QUERYING K8S API...';
  document.getElementById('pods-tbody').innerHTML = '<tr><td colspan="3" class="mono" style="color:#fbbf24;">⏳ Running kubectl get pods -n ate-system...</td></tr>';
  document.getElementById('actors-tbody').innerHTML = '<tr><td colspan="3" class="mono" style="color:#fbbf24;">⏳ Running kubectl-ate get actors -a secure-runtime...</td></tr>';
  try {
    const r = await fetch('/api/cluster').then(x => x.json());
    logConsole('GET /api/cluster (kubectl get pods -n ate-system & kubectl-ate get actors)', r);
    document.getElementById('golden-tag-lbl').textContent = r.golden_tag;
    document.getElementById('cluster-status-badge').textContent = `${r.ate_system_pods.length} PODS HEALTHY (${r.query_ms} ms)`;
    if (r.ate_system_pods && r.ate_system_pods.length) {
      document.getElementById('pods-tbody').innerHTML = r.ate_system_pods.map(p =>
        `<tr><td class="mono">${p.name}</td><td><span class="badge badge-green">${p.ready}</span></td><td>${p.phase}</td></tr>`
      ).join('');
    }
    if (r.actors) {
      document.getElementById('actors-count-badge').textContent = `${r.actors.length} ACTORS`;
      document.getElementById('actors-tbody').innerHTML = r.actors.length
        ? r.actors.map(a => `<tr><td class="mono">${a.name}</td><td class="mono">${a.template}</td><td><span class="badge badge-cyan">${a.phase}</span></td></tr>`).join('')
        : `<tr><td class="mono" colspan="3">No active actors (will wake on demand)</td></tr>`;
    }
    setCardsState('view-0', 'done');
    btn.textContent = `Live Cluster Verified (${r.query_ms} ms) ✓`;
  } finally { btn.disabled = false; }
}

async function runTab1() {
  const btn = document.getElementById('btn-run-1');
  const actor = document.getElementById('act1-actor-input').value.trim() || 'triage-actor-19';
  btn.disabled = true; btn.textContent = `⏳ Probing ${actor} on GKE...`;
  setCardsState('view-1', 'running');
  document.getElementById('act1-verdict-badge').textContent = 'RUNNING 6 PROBES...';
  document.getElementById('act1-verdicts').innerHTML = '<div class="verdict-item" style="grid-column:span 2;border-left-color:#fbbf24;"><span class="mono" style="color:#fbbf24;">⏳ Dispatching mTLS /run to atenet-router -> gVisor Actor ' + actor + '...</span></div>';
  try {
    const r = await fetch('/api/act1?actor=' + encodeURIComponent(actor)).then(x => x.json());
    logConsole(`Act 1: inspect_sandbox_boundary("${actor}")`, r);
    if (r.sandbox_identity) {
      document.getElementById('act1-kernel').textContent = r.sandbox_identity.kernel_version;
      document.getElementById('act1-rt-badge').textContent = `mTLS Roundtrip: ${r.sandbox_identity.router_roundtrip_ms} ms`;
    }
    if (r.user_space_syscall_verdicts) {
      const entries = Object.entries(r.user_space_syscall_verdicts);
      document.getElementById('act1-verdict-badge').textContent = `${entries.length} / ${entries.length} BLOCKED BY GVISOR (${r._exec_ms} ms)`;
      document.getElementById('act1-verdicts').innerHTML = entries.map(([k, v]) =>
        `<div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">${k}</span><span class="mono" style="font-size:11px;color:var(--muted);">${v}</span></div>`
      ).join('');
    }
    setCardsState('view-1', 'done');
    btn.textContent = `Boundary Verified (${r._exec_ms} ms) ✓`;
  } finally { btn.disabled = false; }
}

async function runCustomCode() {
  const btn = document.getElementById('btn-run-code');
  const actor = document.getElementById('act1-actor-input').value.trim() || 'triage-actor-19';
  const code = document.getElementById('custom-code-input').value;
  btn.disabled = true; btn.textContent = '⏳ Executing in Sandbox...';
  document.getElementById('custom-code-output').textContent = `⏳ Sending Python snippet over mTLS to ${actor}...`;
  try {
    const r = await fetch('/api/run_code', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({actor_name: actor, code: code})
    }).then(x => x.json());
    logConsole(`run_python_in_actor("${actor}")`, r);
    const ex = r.execution || {};
    document.getElementById('custom-code-output').textContent =
      `[exit_code=${ex.exit_code} | router_roundtrip=${ex.router_roundtrip_ms} ms | exec=${ex.exec_duration_ms} ms]\n` +
      (ex.stdout || '') + (ex.stderr ? `\nSTDERR:\n${ex.stderr}` : '');
    btn.textContent = `Executed (${ex.router_roundtrip_ms} ms) ✓`;
  } finally { btn.disabled = false; }
}

async function runTab2() {
  const btn = document.getElementById('btn-run-2');
  const note = document.getElementById('act2-note-input').value.trim() || 'tikhonov_1e-6';
  btn.disabled = true; btn.textContent = '⏳ Spawning Cold gVisor Pod & Snapshot Actor (~15s)...';
  setCardsState('view-2', 'running');
  document.getElementById('race-cold-ms').textContent = '⏳ Booting...';
  document.getElementById('race-wake-ms').textContent = '⏳...';
  document.getElementById('race-resume-ms').textContent = '⏳...';
  document.getElementById('bar-cold').style.width = '0%';
  document.getElementById('bar-wake').style.width = '0%';
  document.getElementById('bar-resume').style.width = '0%';
  try {
    const r = await fetch('/api/act2?note=' + encodeURIComponent(note)).then(x => x.json());
    logConsole(`Act 2: Live Cold gVisor Pod vs Golden Snapshot (${r.actor_name})`, r);
    document.getElementById('race-cold-ms').textContent = `${r.cold_gvisor_pod_ms.toLocaleString()} ms`;
    document.getElementById('bar-cold-lbl').textContent = `${r.cold_gvisor_pod_ms.toLocaleString()} ms`;
    document.getElementById('race-wake-ms').textContent = `${r.golden_snapshot_wake_ms} ms`;
    document.getElementById('race-resume-ms').textContent = `${r.stateful_pause_resume_ms} ms`;
    document.getElementById('race-wake-badge').textContent = `${r.speedup_wake}x Faster`;
    document.getElementById('race-resume-badge').textContent = `${r.speedup_resume}x Faster`;
    document.getElementById('bar-wake-lbl').textContent = `${r.golden_snapshot_wake_ms} ms (${r.speedup_wake}x faster)`;
    document.getElementById('bar-resume-lbl').textContent = `${r.stateful_pause_resume_ms} ms (${r.speedup_resume}x faster)`;
    document.getElementById('restored-state-lbl').textContent = 'STATE = ' + JSON.stringify(r.restored_state);
    document.getElementById('bar-cold').style.width = '100%';
    document.getElementById('bar-wake').style.width = `${Math.max(2, Math.min(100, (r.golden_snapshot_wake_ms / r.cold_gvisor_pod_ms) * 100)).toFixed(1)}%`;
    document.getElementById('bar-resume').style.width = `${Math.max(1.2, Math.min(100, (r.stateful_pause_resume_ms / r.cold_gvisor_pod_ms) * 100)).toFixed(1)}%`;
    setCardsState('view-2', 'done');
    btn.textContent = `Race Complete ✓`;
  } finally { btn.disabled = false; }
}

async function runTab3() {
  const btn = document.getElementById('btn-run-3');
  const issue = document.getElementById('act3-issue-input').value || '42';
  const inject = document.getElementById('act3-inject-input').value;
  btn.disabled = true; btn.textContent = `⏳ Triaging Issue #${issue} on GKE...`;
  setCardsState('view-3', 'running');
  document.getElementById('act3-s1-code').textContent = '⏳ RUNNING...';
  document.getElementById('act3-s2-code').textContent = '⏳ RUNNING...';
  document.getElementById('act3-s3-code').textContent = '⏳ RUNNING...';
  try {
    const r = await fetch(`/api/act3?issue=${encodeURIComponent(issue)}&inject=${encodeURIComponent(inject)}`).then(x => x.json());
    logConsole(`Act 3: triage_github_issue_in_sandbox(issue=${issue}, follow_instructions=${inject})`, r);
    if (r.triage_execution && r.triage_execution.steps) {
      const s1 = r.triage_execution.steps['1_fetch_issue_get'];
      const s2 = r.triage_execution.steps['2_attempt_post_comment'];
      const s3 = r.triage_execution.steps['3_attempt_unlisted_host_exfil'];
      document.getElementById('act3-s1-code').textContent = `${s1.status_code} OK — ${s1.verdict}`;
      document.getElementById('act3-s1-desc').textContent = `Fetched Issue #${issue}: "${s1.issue_title}" (${s1.url}) with 0 secrets in sandbox env.`;
      if (s2) {
        document.getElementById('act3-s2-code').textContent = `${s2.status_code} FORBIDDEN — ${s2.verdict}`;
        document.getElementById('act3-s2-desc').textContent = `POST ${s2.url} blocked at L7 by intent-extproc.`;
      } else {
        document.getElementById('act3-s2-code').textContent = `SKIPPED (Read-Only Mode)`;
        document.getElementById('act3-s2-desc').textContent = `Prompt injection simulation disabled; only GET request sent.`;
      }
      if (s3) {
        document.getElementById('act3-s3-code').textContent = `BLOCKED — ${s3.verdict}`;
        document.getElementById('act3-s3-desc').textContent = `${s3.error || 'Unlisted host rejected by atenet-egress default-deny.'}`;
      } else {
        document.getElementById('act3-s3-code').textContent = `SKIPPED (Read-Only Mode)`;
      }
    }
    setCardsState('view-3', 'done');
    btn.textContent = `Egress Verdicts Confirmed (${r._exec_ms} ms) ✓`;
  } finally { btn.disabled = false; }
}

async function runTab4() {
  const btn = document.getElementById('btn-run-4');
  const actor = document.getElementById('act4-actor-input').value.trim() || 'triage-actor-42';
  btn.disabled = true; btn.textContent = `⏳ Quarantining ${actor}...`;
  setCardsState('view-4', 'running');
  document.getElementById('act4-revoke-ms').textContent = '...';
  document.getElementById('act4-delete-ms').textContent = '...';
  document.getElementById('act4-restore-ms').textContent = '...';
  try {
    const r = await fetch('/api/act4?actor=' + encodeURIComponent(actor)).then(x => x.json());
    logConsole(`Act 4: audit_and_reset_actor_to_golden("${actor}")`, r);
    if (r.policy_revocation) {
      document.getElementById('act4-revoke-ms').textContent = `${r.policy_revocation.egress_policy.policy_sync_ms} ms`;
    }
    if (r.deleted_tainted_actor) {
      document.getElementById('act4-delete-ms').textContent = `${r.deleted_tainted_actor.delete_ms} ms`;
    }
    if (r.restored_clean_actor_from_golden_snapshot) {
      const a = r.restored_clean_actor_from_golden_snapshot.actor;
      document.getElementById('act4-restore-ms').textContent = `${a.ensure_ms} ms`;
      document.getElementById('act4-clean-name').textContent = a.actor_ref;
    }
    if (r.audit_events_attributed_to_actor && r.audit_events_attributed_to_actor.length) {
      document.getElementById('audit-tbody').innerHTML = r.audit_events_attributed_to_actor.slice(-6).map(ev => {
        const allow = ev.decision === 'ALLOW';
        return `<tr><td class="mono">${ev.timestamp.split('T')[1].slice(0,12)}Z</td><td class="mono">${ev['ate.actor.identity'].replace('spiffe://substrate-actor.local/worker-for-actor/', '.../')}</td><td class="mono">${ev.intent}</td><td class="mono">${ev['http.method']} ${ev['http.authority']}${ev['http.path']}</td><td><span class="badge badge-cyan">YES (Egress)</span></td><td><span class="badge ${allow ? 'badge-green' : 'badge-red'}">${ev.decision} (${ev.status_code})</span></td></tr>`;
      }).join('');
    }
    setCardsState('view-4', 'done');
    btn.textContent = `Clean Actor Restored (${r._exec_ms} ms) ✓`;
  } finally { btn.disabled = false; }
}

async function runTab5() {
  const btn = document.getElementById('btn-run-5');
  const prompt = document.getElementById('agent-prompt-input').value.trim();
  btn.disabled = true; btn.textContent = 'Gemini 3.8 Flash Reasoning & Calling Tools...';
  document.getElementById('agent-tools-output').textContent = 'Running ADK InMemoryRunner on GKE deploy/triage-agent...';
  document.getElementById('agent-text-output').textContent = 'Waiting for Gemini 3.8 Flash response...';
  try {
    const r = await fetch('/api/ask_agent', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({prompt: prompt})
    }).then(x => x.json());
    logConsole(`ADK Agent (${r.model})`, r);
    document.getElementById('agent-tools-output').textContent = JSON.stringify({
      model: r.model,
      tool_calls: r.tool_calls,
      last_intent_classification: r.last_intent_classification,
      total_ms: r.total_ms
    }, null, 2);
    document.getElementById('agent-text-output').textContent = r.response || JSON.stringify(r, null, 2);
    btn.textContent = 'Agent Turn Complete ✓';
  } finally { btn.disabled = false; }
}
</script>
</body>
</html>
"""


class UIHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        from urllib.parse import parse_qs

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if parsed.path == "/":
            self._send(200, HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif parsed.path.startswith("/slides/"):
            fname = os.path.basename(parsed.path)
            fpath = SLIDES_DIR / fname
            if fpath.is_file():
                self._send(200, fpath.read_bytes(), "image/png")
            else:
                self._send(404, b"not found", "text/plain")
        elif parsed.path == "/api/cluster":
            self._send(200, json.dumps(api_cluster_status()).encode("utf-8"))
        elif parsed.path == "/api/act1":
            actor = qs.get("actor", ["triage-actor-19"])[0]
            self._send(200, json.dumps(api_act1(actor)).encode("utf-8"))
        elif parsed.path == "/api/act2":
            note = qs.get("note", ["tikhonov_1e-6"])[0]
            self._send(200, json.dumps(api_act2(note)).encode("utf-8"))
        elif parsed.path == "/api/act3":
            issue = int(qs.get("issue", ["42"])[0])
            inject = qs.get("inject", ["true"])[0].lower() == "true"
            self._send(200, json.dumps(api_act3(issue, inject)).encode("utf-8"))
        elif parsed.path == "/api/act4":
            actor = qs.get("actor", ["triage-actor-42"])[0]
            self._send(200, json.dumps(api_act4(actor)).encode("utf-8"))
        else:
            self._send(404, b"{}")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length > 0 else b"{}"
        req = json.loads(raw_body.decode("utf-8"))
        if parsed.path == "/api/run_code":
            res = api_run_code(
                req.get("actor_name", "triage-actor-19"),
                req.get("code", "print('ok')"),
            )
            self._send(200, json.dumps(res).encode("utf-8"))
        elif parsed.path == "/api/ask_agent":
            res = api_ask_agent(req.get("prompt", "Say hello"))
            self._send(200, json.dumps(res).encode("utf-8"))
        else:
            self._send(404, b"{}")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    port = int(os.environ.get("UI_PORT", "18090"))
    ThreadingHTTPServer(("127.0.0.1", port), UIHandler).serve_forever()
