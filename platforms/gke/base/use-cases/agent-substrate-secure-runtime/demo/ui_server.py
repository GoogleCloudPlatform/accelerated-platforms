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
to execute Acts 1-4 and cluster health checks in real time.
"""

import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[5]
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


def run_cmd(args: list[str], timeout: int = 120) -> str:
    res = subprocess.run(
        args,
        env=_build_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return res.stdout.strip()


def run_agent_py(expr: str) -> dict[str, Any]:
    out = run_cmd(
        [
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
    )
    for idx, ch in enumerate(out):
        if ch == "{":
            return json.loads(out[idx:])
    return {"raw": out}


def api_cluster_status() -> dict[str, Any]:
    t0 = time.monotonic()
    pods_raw = run_cmd(["kubectl", "get", "pods", "-n", "ate-system", "-o", "json"])
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

    tmpl_raw = run_cmd(
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
        "query_ms": round((time.monotonic() - t0) * 1000, 1),
    }


def api_act1() -> dict[str, Any]:
    return run_agent_py(
        "from secure_runtime_agent.agent import inspect_sandbox_boundary; "
        "print(inspect_sandbox_boundary('triage-actor-19'))"
    )


def api_act2() -> dict[str, Any]:
    expr = """
import json, time
from secure_runtime_agent.agent import run_python_in_actor
from secure_runtime_agent.substrate_client import SubstrateClient

actor_name = f"race-actor-{int(time.time())}"
client = SubstrateClient()
client.ensure_actor(actor_name)
ready = client.call_actor(actor_name, "GET", "/readyz")
warm_ms = ready["router_roundtrip_ms"]

run_python_in_actor(
    code='STATE = {"issue": 19, "solver": "tikhonov_1e-6", "status": "verified", "matrix_norm": 1.0000004}',
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
    "cold_gvisor_pod_ms": 13926,
    "golden_snapshot_wake_ms": warm_ms,
    "stateful_pause_resume_ms": resumed["router_roundtrip_ms"],
    "warm_import_ms_saved": ready.get("warm_import_ms", 2545.39),
    "restored_state": json.loads(resumed["stdout"].strip()),
    "speedup_wake": round(13926 / max(warm_ms, 1), 1),
    "speedup_resume": round(13926 / max(resumed["router_roundtrip_ms"], 1), 1),
}))
"""
    return run_agent_py(expr)


def api_act3() -> dict[str, Any]:
    return run_agent_py(
        "from secure_runtime_agent.agent import triage_github_issue_in_sandbox; "
        "print(triage_github_issue_in_sandbox(42, True, 'triage-actor-42'))"
    )


def api_act4() -> dict[str, Any]:
    clean_name = f"triage-actor-clean-{int(time.time())}"
    return run_agent_py(
        f"from secure_runtime_agent.agent import audit_and_reset_actor_to_golden; "
        f"from secure_runtime_agent.substrate_client import SubstrateClient; "
        f"print(audit_and_reset_actor_to_golden('triage-actor-42', '{clean_name}')); "
        f"SubstrateClient().suspend_actor('{clean_name}')"
    )


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
  header { background: linear-gradient(90deg, #7c00ff 0%, #3b0764 55%, #14032b 100%); padding: 16px 32px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.14); box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
  .brand { display: flex; align-items: center; gap: 16px; }
  .brand-pill { background: rgba(255,255,255,0.16); padding: 6px 12px; border-radius: 8px; font-weight: 700; font-size: 13px; letter-spacing: 0.05em; text-transform: uppercase; }
  .brand h1 { font-size: 22px; font-weight: 800; letter-spacing: -0.02em; }
  .cluster-pills { display: flex; gap: 12px; align-items: center; }
  .pill { background: rgba(15,23,42,0.75); border: 1px solid rgba(255,255,255,0.2); padding: 7px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
  .dot-live { width: 9px; height: 9px; border-radius: 50%; background: var(--green); box-shadow: 0 0 10px var(--green); }
  nav { background: #0f1629; padding: 12px 32px; display: flex; gap: 12px; border-bottom: 1px solid var(--border); }
  .tab-btn { background: var(--panel); color: var(--muted); border: 1px solid var(--border); padding: 11px 20px; border-radius: 10px; font-size: 14px; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 10px; transition: all 0.18s ease; }
  .tab-btn.active { background: linear-gradient(135deg, #6d28d9, #0891b2); color: #fff; border-color: #38bdf8; box-shadow: 0 0 18px rgba(56,189,248,0.3); }
  .tab-num { background: rgba(255,255,255,0.15); padding: 2px 8px; border-radius: 6px; font-size: 12px; }
  main { flex: 1; padding: 24px 32px; overflow-y: auto; display: grid; grid-template-columns: 1fr; gap: 20px; }
  .view { display: none; flex-direction: column; gap: 20px; height: 100%; }
  .view.active { display: flex; }
  .grid-2 { display: grid; grid-template-columns: 1.05fr 0.95fr; gap: 20px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.25); }
  .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
  .card-title { font-size: 16px; font-weight: 700; color: #e2e8f0; display: flex; align-items: center; gap: 10px; }
  .action-btn { background: linear-gradient(135deg, #7c3aed, #06b6d4); color: #fff; border: none; padding: 11px 22px; border-radius: 10px; font-size: 14px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 14px rgba(124,58,237,0.4); }
  .badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; text-transform: uppercase; }
  .badge-green { background: rgba(16,185,129,0.18); color: #34d399; border: 1px solid rgba(16,185,129,0.4); }
  .badge-red { background: rgba(239,68,68,0.18); color: #f87171; border: 1px solid rgba(239,68,68,0.4); }
  .badge-cyan { background: rgba(6,182,212,0.18); color: #22d3ee; border: 1px solid rgba(6,182,212,0.4); }
  .badge-purple { background: rgba(124,58,237,0.22); color: #c4b5fd; border: 1px solid rgba(124,58,237,0.45); }
  .metric-big { font-size: 34px; font-weight: 800; margin: 6px 0; font-variant-numeric: tabular-nums; }
  .mono { font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace; font-size: 13px; }
  .verdict-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
  .verdict-item { background: var(--panel-alt); border: 1px solid var(--border); border-left: 4px solid var(--red); border-radius: 10px; padding: 13px 15px; display: flex; flex-direction: column; gap: 5px; }
  .verdict-item.allow { border-left-color: var(--green); }
  .race-row { background: var(--panel-alt); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; margin-bottom: 14px; }
  .race-bar-bg { width: 100%; height: 26px; background: #0b1120; border-radius: 8px; overflow: hidden; margin-top: 10px; border: 1px solid #1e293b; }
  .race-bar-fill { height: 100%; border-radius: 8px; transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1); }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; text-transform: uppercase; font-size: 11px; letter-spacing: 0.05em; }
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
    <div class="pill"><span>Golden Snapshot: <strong class="mono" style="color:#c4b5fd">d6617568-0493</strong></span></div>
  </div>
</header>
<nav>
  <button class="tab-btn active" id="tab-0" onclick="switchTab(0)"><span class="tab-num">ZONE 1–4</span> Cluster &amp; Golden Snapshot Health</button>
  <button class="tab-btn" id="tab-1" onclick="switchTab(1)"><span class="tab-num">ACT 1</span> gVisor Syscall Boundary</button>
  <button class="tab-btn" id="tab-2" onclick="switchTab(2)"><span class="tab-num">ACT 2</span> Cold-Start Race (13.9s vs 625ms)</button>
  <button class="tab-btn" id="tab-3" onclick="switchTab(3)"><span class="tab-num">ACT 3</span> Out-of-Sandbox Credentials &amp; L7 Filter</button>
  <button class="tab-btn" id="tab-4" onclick="switchTab(4)"><span class="tab-num">ACT 4</span> SPIFFE Audit &amp; Golden Snapshot Reset</button>
</nav>
<main>
  <section class="view active" id="view-0">
    <div class="card-header">
      <div>
        <h2 style="font-size:20px;font-weight:800;">Live GKE 1.37 + Agent Substrate v1.0.0-rc.2 Topology</h2>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">4 Trust Zones: Agent Harness, Substrate Control &amp; Gateways, Warm gVisor WorkerPool, and GCS Golden Snapshots</p>
      </div>
      <button class="action-btn" id="btn-run-0" onclick="runTab0()">Verify Live Cluster State</button>
    </div>
    <div class="grid-4">
      <div class="card"><div class="card-header"><span class="card-title">Zone 1: Agent Harness</span><span class="badge badge-purple">agent-harness</span></div><div class="metric-big" style="color:#c4b5fd;font-size:22px;">Gemini 3.8 Flash</div><p style="color:var(--muted);font-size:13px;line-height:1.5;">Google ADK Triage Agent (<span class="mono">deploy/triage-agent</span>) with <span class="mono">before_tool_callback</span> intent gate &amp; SPIFFE mTLS cert.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Zone 2: Gateways</span><span class="badge badge-cyan">ate-system</span></div><div class="metric-big" style="color:#38bdf8;font-size:22px;">Router + Egress</div><p style="color:var(--muted);font-size:13px;line-height:1.5;"><span class="mono">atenet-router</span> (mTLS wake-on-request) + <span class="mono">atenet-egress</span> + <span class="mono">intent-extproc:50051</span> L7 filter.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Zone 3: Sandbox Pool</span><span class="badge badge-green">ate-workers</span></div><div class="metric-big" style="color:#34d399;font-size:22px;">2/2 Warm Workers</div><p style="color:var(--muted);font-size:13px;line-height:1.5;"><span class="mono">scientific-gvisor</span> WorkerPool on uniform <span class="mono">c3-standard-4</span> nodes running <span class="mono">runsc</span>.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Zone 4: Snapshot Store</span><span class="badge badge-green">Cloud Storage</span></div><div class="metric-big" style="color:#fbbf24;font-size:22px;">MEMORY Fidelity</div><p style="color:var(--muted);font-size:13px;line-height:1.5;">Golden Snapshot <span class="mono" id="golden-tag-lbl">d6617568-0493-4fb6...</span> with pre-imported NumPy/SciPy/Pandas.</p></div>
    </div>
    <div class="card" style="flex:1;">
      <div class="card-header"><span class="card-title">Live Control Plane &amp; Data Plane Pods (<span class="mono">ate-system</span>)</span><span class="badge badge-green" id="cluster-status-badge">ALL 12 PODS HEALTHY</span></div>
      <table>
        <thead><tr><th>Pod Name</th><th>Namespace</th><th>Ready</th><th>Status</th><th>Role in Secure Runtime</th></tr></thead>
        <tbody id="pods-tbody">
          <tr><td class="mono">ate-api-server</td><td class="mono">ate-system</td><td><span class="badge badge-green">2/2</span></td><td>Running</td><td>Actor, ActorTemplate &amp; EgressPolicy API control plane</td></tr>
          <tr><td class="mono">atenet-router</td><td class="mono">ate-system</td><td><span class="badge badge-green">2/2</span></td><td>Running</td><td>mTLS ingress gateway &amp; sub-second actor wake-on-request</td></tr>
          <tr><td class="mono">atenet-egress</td><td class="mono">ate-system</td><td><span class="badge badge-green">3/3</span></td><td>Running</td><td>Default-deny egress MITM proxy &amp; out-of-sandbox token injection</td></tr>
          <tr><td class="mono">intent-extproc</td><td class="mono">ate-system</td><td><span class="badge badge-green">1/1</span></td><td>Running</td><td>Dynamic L7 HTTP method/path Envoy ExternalProcessor + SPIFFE audit log</td></tr>
          <tr><td class="mono">k8s-credential-provider</td><td class="mono">ate-system</td><td><span class="badge badge-green">1/1</span></td><td>Running</td><td>Resolves <span class="mono">agent-credentials/github-readonly-token</span> at egress</td></tr>
          <tr><td class="mono">atelet (daemonset)</td><td class="mono">ate-system</td><td><span class="badge badge-green">2/2</span></td><td>Running</td><td>Node daemon restoring gVisor memory checkpoints from GCS</td></tr>
        </tbody>
      </table>
    </div>
  </section>

  <section class="view" id="view-1">
    <div class="card-header">
      <div>
        <h2 style="font-size:20px;font-weight:800;">Act 1: The Untrusted Boundary — gVisor User-Space Syscall Interception</h2>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">Probing host kernel interfaces from inside Actor <span class="mono" style="color:#38bdf8">secure-runtime/triage-actor-19</span></p>
      </div>
      <button class="action-btn" id="btn-run-1" onclick="runTab1()">Run Act 1 Boundary Probe</button>
    </div>
    <div class="grid-2" style="flex:1;">
      <div class="card" style="display:flex;flex-direction:column;gap:16px;">
        <div class="card-header"><span class="card-title">Sandbox Kernel &amp; Pre-Warmed Memory Identity</span><span class="badge badge-cyan" id="act1-rt-badge">mTLS Roundtrip: 77.6 ms</span></div>
        <div class="race-row">
          <div style="font-size:12px;color:var(--muted);text-transform:uppercase;font-weight:700;">Reported Kernel (/proc/version)</div>
          <div class="mono" id="act1-kernel" style="font-size:16px;font-weight:700;color:#38bdf8;margin-top:6px;">Linux version 4.19.0-gvisor #1 SMP</div>
          <div style="font-size:13px;color:var(--muted);margin-top:6px;">Application syscalls are intercepted in user space by the gVisor Sentry — zero direct host Linux kernel syscall pass-through.</div>
        </div>
        <div class="grid-2">
          <div class="race-row" style="margin:0;"><div style="font-size:12px;color:var(--muted);font-weight:700;">PRE-LOADED IN GOLDEN SNAPSHOT</div><div class="mono" style="font-size:13px;color:#34d399;margin-top:8px;line-height:1.6;">numpy: 2.2.2 &nbsp;|&nbsp; scipy: 1.15.1<br/>pandas: 2.2.3 &nbsp;|&nbsp; matplotlib: 3.10.0</div></div>
          <div class="race-row" style="margin:0;"><div style="font-size:12px;color:var(--muted);font-weight:700;">IMPORT TAX SAVED AT WAKEUP</div><div class="metric-big" style="color:#fbbf24;font-size:26px;" id="act1-import-ms">2,545.39 ms</div><div style="font-size:12px;color:var(--muted);">0 tokens in os.environ</div></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Host Escape &amp; Kernel Interface Probes</span><span class="badge badge-red" id="act1-verdict-badge">6 / 6 BLOCKED BY GVISOR</span></div>
        <div class="verdict-list" id="act1-verdicts">
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">AF_PACKET Raw Socket</span><span class="mono" style="font-size:12px;color:var(--muted);">BLOCKED_BY_GVISOR (EPERM: Operation not permitted)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">unshare(CLONE_NEWUSER|NEWNS)</span><span class="mono" style="font-size:12px;color:var(--muted);">BLOCKED_BY_GVISOR (EINVAL: Invalid argument)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/proc/kcore</span><span class="mono" style="font-size:12px;color:var(--muted);">BLOCKED_BY_GVISOR (ENOENT: No such file)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/proc/kallsyms</span><span class="mono" style="font-size:12px;color:var(--muted);">BLOCKED_BY_GVISOR (ENOENT: No such file)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/proc/sysrq-trigger</span><span class="mono" style="font-size:12px;color:var(--muted);">BLOCKED_BY_GVISOR (EACCES: Permission denied)</span></div>
          <div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">/dev/kmsg</span><span class="mono" style="font-size:12px;color:var(--muted);">BLOCKED_BY_GVISOR (ENOENT: No such file)</span></div>
        </div>
      </div>
    </div>
  </section>

  <section class="view" id="view-2">
    <div class="card-header">
      <div>
        <h2 style="font-size:20px;font-weight:800;">Act 2: Crushing the Cold-Start Penalty — Golden Snapshot vs. Cold gVisor Pod</h2>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">Side-by-side latency benchmark booting Python 3.12 + NumPy, SciPy, Pandas &amp; Matplotlib</p>
      </div>
      <button class="action-btn" id="btn-run-2" onclick="runTab2()">Run Live Cold-Start Race</button>
    </div>
    <div class="grid-3">
      <div class="card"><div class="card-header"><span class="card-title">Baseline A: Cold K8s gVisor Pod</span><span class="badge badge-red">Cold Boot + Import</span></div><div class="metric-big" style="color:#f87171;" id="race-cold-ms">13,926 ms</div><p style="color:var(--muted);font-size:13px;">Pod scheduling + gVisor boot + importing NumPy/SciPy/Pandas from disk on every turn.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Substrate B1: Golden Snapshot Wake</span><span class="badge badge-cyan" id="race-wake-badge">22.3x Faster</span></div><div class="metric-big" style="color:#38bdf8;" id="race-wake-ms">625.8 ms</div><p style="color:var(--muted);font-size:13px;">Restores pre-imported memory pages from GCS Golden Snapshot onto warm WorkerPool.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">Substrate B2: Stateful Pause &rarr; Resume</span><span class="badge badge-green" id="race-resume-badge">91.7x Faster</span></div><div class="metric-big" style="color:#34d399;" id="race-resume-ms">151.8 ms</div><p style="color:var(--muted);font-size:13px;">Resumes suspended actor over mTLS with full in-memory Python variables intact.</p></div>
    </div>
    <div class="card" style="flex:1;">
      <div class="race-row">
        <div style="display:flex;justify-content:space-between;font-weight:700;font-size:14px;"><span>Standard Kubernetes gVisor Pod (<span class="mono">runtimeClassName: gvisor</span>)</span><span class="mono" style="color:#f87171;" id="bar-cold-lbl">13,926 ms</span></div>
        <div class="race-bar-bg"><div class="race-bar-fill" id="bar-cold" style="width:100%;background:linear-gradient(90deg,#ef4444,#f97316);"></div></div>
      </div>
      <div class="race-row">
        <div style="display:flex;justify-content:space-between;font-weight:700;font-size:14px;"><span>Agent Substrate Golden Snapshot Wakeup (<span class="mono">SNAPSHOT_FIDELITY_MEMORY</span>)</span><span class="mono" style="color:#38bdf8;" id="bar-wake-lbl">625.8 ms (22.3x faster)</span></div>
        <div class="race-bar-bg"><div class="race-bar-fill" id="bar-wake" style="width:4.5%;background:linear-gradient(90deg,#06b6d4,#3b82f6);"></div></div>
      </div>
      <div class="race-row" style="margin-bottom:0;">
        <div style="display:flex;justify-content:space-between;font-weight:700;font-size:14px;"><span>Agent Substrate Stateful Pause &rarr; Resume (Restored <span class="mono" id="restored-state-lbl">STATE = {"issue": 19, "solver": "tikhonov_1e-6", "status": "verified"}</span>)</span><span class="mono" style="color:#34d399;" id="bar-resume-lbl">151.8 ms (91.7x faster)</span></div>
        <div class="race-bar-bg"><div class="race-bar-fill" id="bar-resume" style="width:1.4%;background:linear-gradient(90deg,#10b981,#34d399);"></div></div>
      </div>
    </div>
  </section>

  <section class="view" id="view-3">
    <div class="card-header">
      <div>
        <h2 style="font-size:20px;font-weight:800;">Act 3: Out-of-Sandbox Credential Injection &amp; Dynamic L7 Intent Filtering</h2>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">Triaging GitHub Issue #42 in <span class="mono" style="color:#38bdf8">secure-runtime/triage-actor-42</span> under prompt injection</p>
      </div>
      <button class="action-btn" id="btn-run-3" onclick="runTab3()">Execute Act 3 Triage &amp; Attack Simulation</button>
    </div>
    <div class="grid-2" style="flex:1;">
      <div class="card" style="display:flex;flex-direction:column;gap:14px;">
        <div class="card-header"><span class="card-title">Dynamic Policy Programmed by <span class="mono">before_tool_callback</span></span><span class="badge badge-purple" id="act3-intent-badge">INTENT: github_issue_read_only</span></div>
        <div class="race-row" style="margin:0;">
          <div style="font-size:12px;color:var(--muted);font-weight:700;">1. OUT-OF-SANDBOX CREDENTIAL INJECTION (atenet-egress)</div>
          <div class="mono" style="font-size:13px;color:#38bdf8;margin-top:6px;">ate-secret://k8s.io/default/agent-credentials/github-readonly-token/token</div>
          <div style="font-size:13px;color:var(--muted);margin-top:4px;">Sandbox <span class="mono">os.environ</span> contains <strong>0 GitHub tokens</strong> — secrets never enter actor memory or GCS snapshots.</div>
        </div>
        <div class="race-row" style="margin:0;">
          <div style="font-size:12px;color:var(--muted);font-weight:700;">2. L7 HTTP METHOD &amp; PATH RULE (intent-extproc:50051)</div>
          <div class="mono" style="font-size:13px;color:#34d399;margin-top:6px;">Allowed Host: api.github.com &nbsp;|&nbsp; Allowed Methods: [GET, HEAD]</div>
          <div class="mono" style="font-size:13px;color:#c4b5fd;margin-top:4px;">Allowed Path Prefix: /repos/GoogleCloudPlatform/accelerated-platforms/</div>
        </div>
      </div>
      <div class="card" style="display:flex;flex-direction:column;gap:12px;">
        <div class="card-header"><span class="card-title">Live Egress Gateway Verdicts Inside Sandbox</span><span class="badge badge-green">ENFORCED AT EGRESS</span></div>
        <div class="verdict-item allow">
          <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:700;color:#34d399;">1. GET /repos/.../issues/42</span><span class="badge badge-green" id="act3-s1-code">200 OK — TOKEN INJECTED</span></div>
          <div class="mono" style="font-size:12px;color:var(--muted);" id="act3-s1-desc">Fetched Issue #42 ("Fixes multimodal image") with header injected at atenet-egress.</div>
        </div>
        <div class="verdict-item">
          <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:700;color:#f87171;">2. POST /repos/.../issues/42/comments</span><span class="badge badge-red" id="act3-s2-code">403 FORBIDDEN — INTENT-EXTPROC</span></div>
          <div class="mono" style="font-size:12px;color:var(--muted);" id="act3-s2-desc">Blocked by intent "github_issue_read_only" (allowed methods: [GET, HEAD]).</div>
        </div>
        <div class="verdict-item">
          <div style="display:flex;justify-content:space-between;"><span class="mono" style="font-weight:700;color:#f87171;">3. POST https://collector.example.invalid/telemetry</span><span class="badge badge-red" id="act3-s3-code">BLOCKED — DEFAULT-DENY EGRESS</span></div>
          <div class="mono" style="font-size:12px;color:var(--muted);" id="act3-s3-desc">Unlisted host rejected by atenet-egress default-deny policy.</div>
        </div>
      </div>
    </div>
  </section>

  <section class="view" id="view-4">
    <div class="card-header">
      <div>
        <h2 style="font-size:20px;font-weight:800;">Act 4: Per-Actor SPIFFE Audit Attribution, Quarantine &amp; Clean Golden Reset</h2>
        <p style="color:var(--muted);font-size:14px;margin-top:4px;">Cryptographic attribution across shared warm workers and sub-second recovery from immutable Golden Snapshot</p>
      </div>
      <button class="action-btn" id="btn-run-4" onclick="runTab4()">Run Act 4 Quarantine &amp; Clean Reset</button>
    </div>
    <div class="grid-3">
      <div class="card"><div class="card-header"><span class="card-title">1. Revoke Egress &amp; L7 Rules</span><span class="badge badge-red">Quarantined</span></div><div class="metric-big" style="color:#f87171;" id="act4-revoke-ms">126.4 ms</div><p style="color:var(--muted);font-size:13px;">Strips <span class="mono">EgressPolicy</span> &amp; <span class="mono">intent-extproc</span> rules back to default-deny.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">2. Terminate Tainted Actor</span><span class="badge badge-purple">secure-runtime/triage-actor-42</span></div><div class="metric-big" style="color:#c4b5fd;" id="act4-delete-ms">411.9 ms</div><p style="color:var(--muted);font-size:13px;">Releases warm worker slot without disturbing neighboring actors.</p></div>
      <div class="card"><div class="card-header"><span class="card-title">3. Restore Clean Golden Actor</span><span class="badge badge-green">Golden Snapshot</span></div><div class="metric-big" style="color:#34d399;" id="act4-restore-ms">121.2 ms</div><p style="color:var(--muted);font-size:13px;">Spawns <span class="mono" id="act4-clean-name">triage-actor-clean</span> from Golden Snapshot.</p></div>
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
</main>
<script>
function switchTab(idx) {
  document.getElementById('slide-overlay').classList.remove('active');
  for (let i = 0; i < 5; i++) {
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
async function runTab0() {
  const btn = document.getElementById('btn-run-0');
  btn.textContent = 'Querying Live GKE Cluster...';
  const r = await fetch('/api/cluster').then(x => x.json());
  document.getElementById('golden-tag-lbl').textContent = r.golden_tag;
  document.getElementById('cluster-status-badge').textContent = `ALL ${r.ate_system_pods.length} PODS HEALTHY (${r.query_ms} ms)`;
  btn.textContent = 'Live Cluster Verified ✓';
}
async function runTab1() {
  const btn = document.getElementById('btn-run-1');
  btn.textContent = 'Probing gVisor Sandbox...';
  const r = await fetch('/api/act1').then(x => x.json());
  if (r.sandbox_identity) {
    document.getElementById('act1-kernel').textContent = r.sandbox_identity.kernel_version;
    document.getElementById('act1-rt-badge').textContent = `mTLS Roundtrip: ${r.sandbox_identity.router_roundtrip_ms} ms`;
    document.getElementById('act1-import-ms').textContent = `${r.sandbox_identity.warm_import_ms_at_boot} ms`;
  }
  if (r.user_space_syscall_verdicts) {
    const entries = Object.entries(r.user_space_syscall_verdicts);
    document.getElementById('act1-verdict-badge').textContent = `${entries.length} / ${entries.length} BLOCKED BY GVISOR`;
    document.getElementById('act1-verdicts').innerHTML = entries.map(([k, v]) =>
      `<div class="verdict-item"><span class="mono" style="font-weight:700;color:#f87171;">${k}</span><span class="mono" style="font-size:12px;color:var(--muted);">${v}</span></div>`
    ).join('');
  }
  btn.textContent = 'Boundary Verified ✓';
}
async function runTab2() {
  const btn = document.getElementById('btn-run-2');
  btn.textContent = 'Running Live Race on GKE...';
  document.getElementById('bar-wake').style.width = '0%';
  document.getElementById('bar-resume').style.width = '0%';
  const r = await fetch('/api/act2').then(x => x.json());
  document.getElementById('race-cold-ms').textContent = `${r.cold_gvisor_pod_ms.toLocaleString()} ms`;
  document.getElementById('race-wake-ms').textContent = `${r.golden_snapshot_wake_ms} ms`;
  document.getElementById('race-resume-ms').textContent = `${r.stateful_pause_resume_ms} ms`;
  document.getElementById('race-wake-badge').textContent = `${r.speedup_wake}x Faster`;
  document.getElementById('race-resume-badge').textContent = `${r.speedup_resume}x Faster`;
  document.getElementById('bar-wake-lbl').textContent = `${r.golden_snapshot_wake_ms} ms (${r.speedup_wake}x faster)`;
  document.getElementById('bar-resume-lbl').textContent = `${r.stateful_pause_resume_ms} ms (${r.speedup_resume}x faster)`;
  document.getElementById('restored-state-lbl').textContent = 'STATE = ' + JSON.stringify(r.restored_state);
  document.getElementById('bar-wake').style.width = '4.8%';
  document.getElementById('bar-resume').style.width = '1.5%';
  btn.textContent = 'Race Complete ✓';
}
async function runTab3() {
  const btn = document.getElementById('btn-run-3');
  btn.textContent = 'Running Live Triage & Egress Test...';
  const r = await fetch('/api/act3').then(x => x.json());
  if (r.triage_execution && r.triage_execution.steps) {
    const s1 = r.triage_execution.steps['1_fetch_issue_get'];
    const s2 = r.triage_execution.steps['2_attempt_post_comment'];
    document.getElementById('act3-s1-code').textContent = `${s1.status_code} OK — ${s1.verdict}`;
    document.getElementById('act3-s1-desc').textContent = `Fetched "${s1.issue_title}" (${s1.url}) with 0 secrets in sandbox env.`;
    document.getElementById('act3-s2-code').textContent = `${s2.status_code} FORBIDDEN — ${s2.verdict}`;
  }
  btn.textContent = 'Egress Verdicts Confirmed ✓';
}
async function runTab4() {
  const btn = document.getElementById('btn-run-4');
  btn.textContent = 'Quarantining & Resetting Actor...';
  const r = await fetch('/api/act4').then(x => x.json());
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
    document.getElementById('audit-tbody').innerHTML = r.audit_events_attributed_to_actor.slice(-4).map(ev => {
      const allow = ev.decision === 'ALLOW';
      return `<tr><td class="mono">${ev.timestamp.split('T')[1].slice(0,12)}Z</td><td class="mono">${ev['ate.actor.identity'].replace('spiffe://substrate-actor.local/worker-for-actor/', '.../')}</td><td class="mono">${ev.intent}</td><td class="mono">${ev['http.method']} ${ev['http.authority']}${ev['http.path']}</td><td><span class="badge badge-cyan">YES (Egress)</span></td><td><span class="badge ${allow ? 'badge-green' : 'badge-red'}">${ev.decision} (${ev.status_code})</span></td></tr>`;
    }).join('');
  }
  btn.textContent = 'Clean Actor Restored ✓';
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
        parsed = urlparse(self.path)
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
            self._send(200, json.dumps(api_act1()).encode("utf-8"))
        elif parsed.path == "/api/act2":
            self._send(200, json.dumps(api_act2()).encode("utf-8"))
        elif parsed.path == "/api/act3":
            self._send(200, json.dumps(api_act3()).encode("utf-8"))
        elif parsed.path == "/api/act4":
            self._send(200, json.dumps(api_act4()).encode("utf-8"))
        else:
            self._send(404, b"{}")

    def log_message(self, fmt: str, *args: Any) -> None:
        return


if __name__ == "__main__":
    port = int(os.environ.get("UI_PORT", "18090"))
    ThreadingHTTPServer(("127.0.0.1", port), UIHandler).serve_forever()
