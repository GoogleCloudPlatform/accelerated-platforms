/*
 * Copyright 2026 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

let activeLogSource = 'intent-extproc';
let autoTailTimer = null;
let lastJsonString = '{}';

function esc(val) {
  const div = document.createElement('div');
  div.textContent = val == null ? '' : String(val);
  return div.innerHTML;
}

function switchTab(idx) {
  for (let i = 0; i < 6; i++) {
    document.getElementById('tab-' + i).classList.toggle('active', i === idx);
    document.getElementById('view-' + i).classList.toggle('active', i === idx);
  }
}

function switchTermTab(name) {
  for (const key of ['stream', 'logs', 'json']) {
    document.getElementById('ttab-' + key).classList.toggle('active', key === name);
    document.getElementById('tpane-' + key).classList.toggle('active', key === name);
  }
  if (name === 'logs') {
    fetchPodLogs();
  }
}

function toggleTerminalWidth() {
  const ws = document.getElementById('workspace');
  ws.classList.toggle('wide-terminal');
}

function setCardsState(viewId, state) {
  document.querySelectorAll('#' + viewId + ' .card').forEach(c => {
    c.classList.remove('running', 'done');
    if (state) c.classList.add(state);
  });
}

function recordPayload(label, data) {
  lastJsonString = JSON.stringify(data, null, 2);
  document.getElementById('json-status-lbl').textContent =
    `${label} (${data._exec_ms || data.query_ms || data.total_ms || 0} ms)`;
  document.getElementById('json-output').textContent = lastJsonString;
}

function copyJsonPayload() {
  navigator.clipboard.writeText(lastJsonString);
}

function appendStreamEvent(ev) {
  const box = document.getElementById('stream-output');
  const row = document.createElement('div');
  row.className = 't-line';
  const clsMap = {
    cmd: 't-cmd',
    http: 't-http',
    k8s: 't-k8s',
    verdict: 't-verdict',
    error: 't-error',
  };
  const cls = clsMap[ev.kind] || 't-http';
  let html = `<span class="t-ts">[${esc(ev.ts)}]</span><span class="${cls}">${esc(ev.text)}</span>`;
  if (ev.detail) {
    html += `<details style="margin-top:2px;margin-left:14px;"><summary style="color:#64748b;cursor:pointer;font-size:10.5px;">output / payload</summary><pre style="color:#94a3b8;white-space:pre-wrap;margin-top:3px;">${esc(ev.detail)}</pre></details>`;
  }
  row.innerHTML = html;
  box.appendChild(row);
  while (box.children.length > 250) {
    box.removeChild(box.firstChild);
  }
  box.scrollTop = box.scrollHeight;
}

function clearStream() {
  document.getElementById('stream-output').innerHTML = '';
}

function connectSSE() {
  const badge = document.getElementById('sse-badge');
  const es = new EventSource('/api/events');
  es.onopen = () => {
    badge.textContent = 'LIVE STREAM';
    badge.className = 'badge badge-green mono';
  };
  es.onmessage = msg => {
    try {
      appendStreamEvent(JSON.parse(msg.data));
    } catch (_) {}
  };
  es.onerror = () => {
    badge.textContent = 'RECONNECTING...';
    badge.className = 'badge badge-muted mono';
  };
}

async function fetchPodLogs() {
  const hdr = document.getElementById('pod-log-header');
  const out = document.getElementById('pod-log-output');
  try {
    const r = await fetch(`/api/logs?source=${encodeURIComponent(activeLogSource)}&lines=90`);
    const data = await r.json();
    if (!r.ok) {
      hdr.textContent = `Error (${r.status})`;
      out.textContent = data.detail || JSON.stringify(data);
      return;
    }
    hdr.textContent = `$ kubectl logs -n ate-system ${data.pod || activeLogSource} -c ${data.container || '-'} --tail=90`;
    out.textContent = (data.lines && data.lines.length)
      ? data.lines.join('\n')
      : '(no log lines emitted yet)';
    out.parentElement.scrollTop = out.parentElement.scrollHeight;
  } catch (err) {
    hdr.textContent = 'Log fetch failed';
    out.textContent = String(err);
  }
}

function selectLogSource(src) {
  activeLogSource = src;
  for (const key of ['intent-extproc', 'atenet-egress', 'atenet-router', 'ate-api-server']) {
    document.getElementById('logsrc-' + key).classList.toggle('active', key === src);
  }
  fetchPodLogs();
}

function toggleAutoTail() {
  const btn = document.getElementById('btn-autotail');
  if (autoTailTimer) {
    clearInterval(autoTailTimer);
    autoTailTimer = null;
    btn.textContent = 'Auto-Tail: OFF';
    btn.classList.remove('active');
  } else {
    fetchPodLogs();
    autoTailTimer = setInterval(fetchPodLogs, 3000);
    btn.textContent = 'Auto-Tail: 3s';
    btn.classList.add('active');
  }
}

async function apiPost(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await resp.json();
  if (!resp.ok) {
    throw new Error(data.detail || JSON.stringify(data));
  }
  return data;
}

async function runPart0() {
  const btn = document.getElementById('btn-run-0');
  btn.disabled = true;
  btn.textContent = 'Querying Cluster...';
  setCardsState('view-0', 'running');
  try {
    const r = await fetch('/api/cluster').then(x => x.json());
    recordPayload('GET /api/cluster', r);
    document.getElementById('cluster-dot').classList.add('ok');
    document.getElementById('hdr-cluster').textContent = r.cluster;
    document.getElementById('hdr-substrate').textContent = r.substrate_version;
    document.getElementById('hdr-model').textContent = r.gemini_model;
    document.getElementById('z1-model').textContent = r.gemini_model;
    document.getElementById('adk-model-lbl').textContent = r.gemini_model;
    document.getElementById('atespace-lbl').textContent = r.atespace;
    document.getElementById('golden-tag-lbl').textContent = r.golden_tag || 'building...';
    document.getElementById('p3-prefix-lbl').textContent =
      `Canonical Path Prefix: /repos/${r.github_repo}/ (rejects .. traversal)`;

    const badge = document.getElementById('cluster-status-badge');
    badge.className = 'badge badge-green';
    badge.textContent = `${r.ate_system_pods.length} PODS (${r.query_ms} ms)`;
    document.getElementById('pods-tbody').innerHTML = r.ate_system_pods.map(p =>
      `<tr><td class="mono">${esc(p.name)}</td><td><span class="badge badge-green">${esc(p.ready)}</span></td><td>${esc(p.phase)}</td></tr>`
    ).join('');

    document.getElementById('actors-count-badge').textContent = `${r.actors.length} ACTORS`;
    document.getElementById('actors-tbody').innerHTML = r.actors.length
      ? r.actors.map(a =>
          `<tr><td class="mono">${esc(a.name)}</td><td class="mono">${esc(a.template)}</td><td><span class="badge badge-cyan">${esc(a.phase)}</span></td></tr>`
        ).join('')
      : '<tr><td colspan="3" class="mono" style="color:var(--muted);">0 active actors (wake on demand from Golden Snapshot)</td></tr>';

    setCardsState('view-0', 'done');
    btn.textContent = `Cluster Verified (${r.query_ms} ms)`;
  } catch (err) {
    appendStreamEvent({ts: 'ERR', kind: 'error', text: String(err)});
    btn.textContent = 'Retry Cluster Query';
  } finally {
    btn.disabled = false;
  }
}

async function runPart1() {
  const btn = document.getElementById('btn-run-1');
  const actor = document.getElementById('p1-actor-input').value.trim() || 'triage-actor-19';
  btn.disabled = true;
  btn.textContent = `Probing ${actor}...`;
  setCardsState('view-1', 'running');
  try {
    const r = await apiPost('/api/part1', {actor_name: actor});
    recordPayload('POST /api/part1', r);
    if (r.sandbox_identity) {
      document.getElementById('p1-kernel').textContent = r.sandbox_identity.kernel_version;
      document.getElementById('p1-rt-badge').textContent =
        `mTLS Roundtrip: ${r.sandbox_identity.router_roundtrip_ms} ms`;
    }
    const entries = Object.entries(r.user_space_syscall_verdicts || {});
    const vBadge = document.getElementById('p1-verdict-badge');
    vBadge.className = 'badge badge-red';
    vBadge.textContent = `${entries.length} / ${entries.length} BLOCKED BY GVISOR (${r._exec_ms} ms)`;
    document.getElementById('p1-verdicts').innerHTML = entries.map(([k, v]) =>
      `<div class="verdict-item blocked"><span class="mono" style="font-weight:700;color:#f87171;">${esc(k)}</span><span class="mono" style="color:var(--muted);">${esc(v)}</span></div>`
    ).join('');
    setCardsState('view-1', 'done');
    btn.textContent = `Boundary Verified (${r._exec_ms} ms)`;
  } catch (err) {
    appendStreamEvent({ts: 'ERR', kind: 'error', text: String(err)});
    btn.textContent = 'Run #1 Boundary Probe';
  } finally {
    btn.disabled = false;
  }
}

async function runCustomCode() {
  const btn = document.getElementById('btn-run-code');
  const actor = document.getElementById('p1-actor-input').value.trim() || 'triage-actor-19';
  const code = document.getElementById('custom-code-input').value;
  btn.disabled = true;
  btn.textContent = 'Executing...';
  try {
    const r = await apiPost('/api/run_code', {actor_name: actor, code});
    recordPayload('POST /api/run_code', r);
    const ex = r.execution || {};
    document.getElementById('custom-code-output').textContent =
      `[exit_code=${ex.exit_code} | mTLS_roundtrip=${ex.router_roundtrip_ms} ms | exec=${ex.duration_ms} ms]\n` +
      (ex.stdout || '') + (ex.stderr ? `\nSTDERR:\n${ex.stderr}` : '');
    btn.textContent = `Executed (${ex.router_roundtrip_ms} ms)`;
  } catch (err) {
    document.getElementById('custom-code-output').textContent = String(err);
    btn.textContent = 'Execute in Sandbox';
  } finally {
    btn.disabled = false;
  }
}

async function runPart2() {
  const btn = document.getElementById('btn-run-2');
  const note = document.getElementById('p2-note-input').value.trim() || 'tikhonov_reg_1e-6';
  btn.disabled = true;
  btn.textContent = 'Racing Cold Pod vs Snapshot (watch Live Stream ->)...';
  setCardsState('view-2', 'running');
  switchTermTab('stream');
  document.getElementById('race-cold-ms').textContent = 'Booting...';
  document.getElementById('race-wake-ms').textContent = 'Waking...';
  document.getElementById('race-resume-ms').textContent = 'Resuming...';
  try {
    const r = await apiPost('/api/part2', {custom_note: note});
    recordPayload('POST /api/part2', r);
    document.getElementById('cold-pod-lbl').textContent = r.cold_gvisor_pod;
    document.getElementById('race-cold-ms').textContent = `${r.cold_gvisor_pod_ms.toLocaleString()} ms`;
    document.getElementById('bar-cold-lbl').textContent = `${r.cold_gvisor_pod_ms.toLocaleString()} ms`;
    document.getElementById('race-wake-ms').textContent = `${r.golden_snapshot_wake_ms} ms`;
    document.getElementById('race-resume-ms').textContent = `${r.stateful_pause_resume_ms} ms`;
    document.getElementById('race-wake-badge').textContent = `${r.speedup_wake}x Faster`;
    document.getElementById('race-resume-badge').textContent = `${r.speedup_resume}x Faster`;
    document.getElementById('bar-wake-lbl').textContent =
      `${r.golden_snapshot_wake_ms} ms (${r.speedup_wake}x faster)`;
    document.getElementById('bar-resume-lbl').textContent =
      `${r.stateful_pause_resume_ms} ms (${r.speedup_resume}x faster)`;
    document.getElementById('restored-state-lbl').textContent =
      `STATE = ${JSON.stringify(r.restored_state)}`;
    document.getElementById('bar-cold').style.width = '100%';
    document.getElementById('bar-wake').style.width =
      `${Math.max(1.5, Math.min(100, (r.golden_snapshot_wake_ms / r.cold_gvisor_pod_ms) * 100)).toFixed(2)}%`;
    document.getElementById('bar-resume').style.width =
      `${Math.max(1.0, Math.min(100, (r.stateful_pause_resume_ms / r.cold_gvisor_pod_ms) * 100)).toFixed(2)}%`;
    setCardsState('view-2', 'done');
    btn.textContent = 'Run #2 Cold-Start Race';
  } catch (err) {
    appendStreamEvent({ts: 'ERR', kind: 'error', text: String(err)});
    btn.textContent = 'Retry #2 Cold-Start Race';
  } finally {
    btn.disabled = false;
  }
}

async function runPart3() {
  const btn = document.getElementById('btn-run-3');
  const issue = parseInt(document.getElementById('p3-issue-input').value || '42', 10);
  const inject = document.getElementById('p3-inject-input').value === 'true';
  btn.disabled = true;
  btn.textContent = `Verifying Egress on Issue #${issue}...`;
  setCardsState('view-3', 'running');
  try {
    const r = await apiPost('/api/part3', {
      issue_number: issue,
      follow_instructions: inject,
      actor_name: 'triage-actor-42',
    });
    recordPayload('POST /api/part3', r);
    const te = r.triage_execution || {};
    const secrets = te.sandbox_credential_env_vars || [];
    document.getElementById('p3-env-secrets').textContent =
      secrets.length === 0 ? '0 secret env vars (clean)' : secrets.join(', ');
    document.getElementById('p3-status-badge').className = 'badge badge-green';
    document.getElementById('p3-status-badge').textContent = `VERIFIED (${r._exec_ms} ms)`;

    const steps = te.steps || {};
    const s1 = steps['1_fetch_issue_get'] || {};
    document.getElementById('p3-v1').className = 'verdict-item allow';
    document.getElementById('p3-s1-code').className = 'badge badge-green';
    document.getElementById('p3-s1-code').textContent = `${s1.status_code} — ${s1.verdict}`;
    document.getElementById('p3-s1-desc').textContent =
      `Title: "${s1.issue_title || 'n/a'}" (${s1.url})`;

    const s2 = steps['2_attempt_post_comment'];
    if (s2) {
      document.getElementById('p3-v2').className = 'verdict-item blocked';
      document.getElementById('p3-s2-code').className = 'badge badge-red';
      document.getElementById('p3-s2-code').textContent = `${s2.status_code} — ${s2.verdict}`;
      document.getElementById('p3-s2-desc').textContent = `POST ${s2.url} denied by Envoy intent-extproc`;
    } else {
      document.getElementById('p3-v2').className = 'verdict-item';
      document.getElementById('p3-s2-code').className = 'badge badge-muted';
      document.getElementById('p3-s2-code').textContent = 'SKIPPED';
      document.getElementById('p3-s2-desc').textContent = 'Read-only mode selected';
    }

    const s3 = steps['3_attempt_unlisted_host'];
    if (s3) {
      document.getElementById('p3-v3').className = 'verdict-item blocked';
      document.getElementById('p3-s3-code').className = 'badge badge-red';
      document.getElementById('p3-s3-code').textContent = s3.verdict;
      document.getElementById('p3-s3-desc').textContent = s3.error || 'Blocked by default-deny egress';
    } else {
      document.getElementById('p3-v3').className = 'verdict-item';
      document.getElementById('p3-s3-code').className = 'badge badge-muted';
      document.getElementById('p3-s3-code').textContent = 'SKIPPED';
      document.getElementById('p3-s3-desc').textContent = 'Read-only mode selected';
    }

    if (activeLogSource === 'intent-extproc') {
      fetchPodLogs();
    }
    setCardsState('view-3', 'done');
    btn.textContent = `Egress Verified (${r._exec_ms} ms)`;
  } catch (err) {
    appendStreamEvent({ts: 'ERR', kind: 'error', text: String(err)});
    btn.textContent = 'Run #3 Egress Verification';
  } finally {
    btn.disabled = false;
  }
}

async function runPart4() {
  const btn = document.getElementById('btn-run-4');
  const actor = document.getElementById('p4-actor-input').value.trim() || 'triage-actor-42';
  btn.disabled = true;
  btn.textContent = `Quarantining ${actor}...`;
  setCardsState('view-4', 'running');
  try {
    const r = await apiPost('/api/part4', {tainted_actor: actor});
    recordPayload('POST /api/part4', r);
    document.getElementById('p4-tainted-lbl').textContent = r.quarantined_actor;
    document.getElementById('p4-revoke-ms').textContent =
      `${r.policy_revocation.egress_policy.policy_sync_ms} ms`;
    document.getElementById('p4-delete-ms').textContent =
      `${r.deleted_tainted_actor.delete_ms} ms`;
    const cleanActor = r.restored_clean_actor_from_golden_snapshot.actor;
    document.getElementById('p4-restore-ms').textContent = `${cleanActor.ensure_ms} ms`;
    document.getElementById('p4-clean-name').textContent = cleanActor.actor_ref;

    const events = r.audit_events_attributed_to_actor || [];
    document.getElementById('audit-tbody').innerHTML = events.length
      ? events.slice(-8).map(ev => {
          const allow = ev.decision === 'ALLOW';
          const shortId = String(ev['ate.actor.identity'] || '').replace(
            'spiffe://substrate-actor.local/worker-for-actor/', '.../'
          );
          const ts = String(ev.timestamp || '').split('T')[1]?.slice(0, 12) || ev.timestamp;
          return `<tr>
            <td class="mono">${esc(ts)}Z</td>
            <td class="mono">${esc(shortId)}</td>
            <td class="mono">${esc(ev.intent)}</td>
            <td class="mono">${esc(ev['http.method'])} ${esc(ev['http.authority'])}${esc(ev['http.path'])}</td>
            <td><span class="badge ${allow ? 'badge-green' : 'badge-red'}">${esc(ev.decision)} (${esc(ev.status_code)})</span></td>
          </tr>`;
        }).join('')
      : '<tr><td colspan="5" class="mono" style="color:var(--muted);">No audit events recorded for this actor yet (run #3 first).</td></tr>';

    setCardsState('view-4', 'done');
    btn.textContent = `Clean Actor Restored (${r._exec_ms} ms)`;
  } catch (err) {
    appendStreamEvent({ts: 'ERR', kind: 'error', text: String(err)});
    btn.textContent = 'Run #4 Quarantine & Reset';
  } finally {
    btn.disabled = false;
  }
}

function setPrompt(txt) {
  document.getElementById('agent-prompt-input').value = txt;
}

async function runPart5() {
  const btn = document.getElementById('btn-run-5');
  const prompt = document.getElementById('agent-prompt-input').value.trim();
  if (!prompt) return;
  btn.disabled = true;
  btn.textContent = 'Reasoning & Calling Tools...';
  setCardsState('view-5', 'running');
  document.getElementById('agent-tools-output').textContent = 'Executing ADK InMemoryRunner...';
  document.getElementById('agent-text-output').textContent = 'Waiting for model response...';
  try {
    const r = await apiPost('/api/ask_agent', {prompt});
    recordPayload('POST /api/ask_agent', r);
    document.getElementById('agent-tools-output').textContent = JSON.stringify({
      model: r.model,
      tool_calls: r.tool_calls,
      last_intent_classification: r.last_intent_classification,
      total_ms: r.total_ms,
    }, null, 2);
    document.getElementById('agent-text-output').textContent = r.response || '(no text)';
    setCardsState('view-5', 'done');
    btn.textContent = `Completed (${r.total_ms} ms)`;
  } catch (err) {
    document.getElementById('agent-text-output').textContent = String(err);
    btn.textContent = 'Send Prompt to Agent';
  } finally {
    btn.disabled = false;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  connectSSE();
  runPart0();
});
