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

let currentSlide = 0;
const totalSlides = 5;
let presetProbes = [];
const act4Timers = {};

function goSlide(idx) {
  if (idx < 0 || idx >= totalSlides) return;
  currentSlide = idx;
  for (let i = 0; i < totalSlides; i++) {
    document.getElementById('slide-' + i).classList.toggle('active', i === idx);
    const dot = document.getElementById('dot-' + i);
    dot.className =
      'step-dot' +
      (i === idx ? ' active ' + (i === 0 ? 'red-mode' : i === 3 ? 'green-mode' : '') : '');
  }
  document.getElementById('btn-prev').disabled = idx === 0;
  document.getElementById('btn-next').disabled = idx === totalSlides - 1;
}

function stepSlide(delta) {
  goSlide(currentSlide + delta);
}

function toggleModal() {
  document.getElementById('cli-modal').classList.toggle('open');
}

document.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA'].includes((e.target || {}).tagName)) return;
  if (e.key === 'ArrowRight') stepSlide(1);
  else if (e.key === 'ArrowLeft') stepSlide(-1);
  else if (e.key === 'u' || e.key === 'U') toggleModal();
  else if (e.key === 'Escape') document.getElementById('cli-modal').classList.remove('open');
});

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function showError(err) {
  const banner = document.getElementById('ui-error-banner');
  const msgEl = document.getElementById('ui-error-msg');
  if (!banner || !msgEl) return;
  const text = err instanceof Error ? err.message : String(err || 'Unknown error');
  msgEl.textContent = 'Error: ' + text;
  banner.classList.add('show');
}

function clearError() {
  const banner = document.getElementById('ui-error-banner');
  if (banner) banner.classList.remove('show');
}

function setFooterTelemetry(data) {
  if (data.summary_cmd) {
    document.getElementById('footer-cmd').textContent = data.summary_cmd;
  }
  if (data._exec_ms !== undefined) {
    document.getElementById('proof-ms').textContent = data._exec_ms + ' ms (Live GKE API)';
  }
  if (data.brain && data.brain.worker_pod) {
    document.getElementById('proof-pod').textContent = data.brain.worker_pod;
  }
  if (Array.isArray(data.under_the_hood)) {
    const body = document.getElementById('modal-body');
    body.innerHTML = data.under_the_hood
      .map(
        (item) => `
      <div class="modal-step">
        <div style="font-size:13px; font-weight:800; color:#f8fafc;">${escapeHtml(item.step || '')}</div>
        <div class="mono" style="font-size:12px; color:#67e8f9; margin-top:4px;">$ ${escapeHtml(item.cmd || '')}</div>
        <pre class="mono">${escapeHtml(item.output || '')}</pre>
      </div>
    `
      )
      .join('');
  }
}

async function postJson(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-Requested-With': 'MissionControl',
    },
    body: JSON.stringify(body || {}),
  });
  let d = {};
  try {
    d = await r.json();
  } catch (_) {
    throw new Error('HTTP ' + r.status + ' (non-JSON response)');
  }
  if (!r.ok || d.error) {
    throw new Error(d.error || 'HTTP ' + r.status);
  }
  return d;
}

function renderPresetProbeChips(probesList) {
  const container = document.getElementById('preset-probe-chips');
  if (!container || !Array.isArray(probesList)) return;
  presetProbes = probesList;
  container.innerHTML = '';
  probesList.forEach((spec) => {
    const btn = document.createElement('button');
    btn.className = 'shell-chip mono';
    btn.textContent = spec.label;
    btn.addEventListener('click', () => runLiveProbe(spec.id));
    container.appendChild(btn);
  });
}

function revealAct4Badge(idx, text, delayMs, isRed) {
  const el = document.getElementById('a4-val-' + idx);
  if (!el) return;
  if (act4Timers[idx]) {
    clearTimeout(act4Timers[idx]);
  }
  el.textContent = text;
  el.classList.toggle('red', Boolean(isRed));
  act4Timers[idx] = setTimeout(() => {
    el.style.display = 'inline-block';
    requestAnimationFrame(() => {
      el.style.opacity = '1';
      el.style.transform = 'translateX(0)';
    });
  }, delayMs);
}

function hideAct4Badges(indices) {
  indices.forEach((idx) => {
    if (act4Timers[idx]) {
      clearTimeout(act4Timers[idx]);
      delete act4Timers[idx];
    }
    const el = document.getElementById('a4-val-' + idx);
    if (!el) return;
    el.style.opacity = '0';
    el.style.transform = 'translateX(8px)';
    el.style.display = 'none';
  });
}

async function refreshClusterWhisper() {
  const dot = document.getElementById('live-status-dot');
  try {
    const r = await fetch('/api/status', {credentials: 'same-origin'});
    let d = {};
    try {
      d = await r.json();
    } catch (_) {
      throw new Error('HTTP ' + r.status + ' (non-JSON response)');
    }
    if (!r.ok || d.error) {
      throw new Error(d.error || 'HTTP ' + r.status);
    }
    if (dot) dot.classList.remove('err');
    const promCluster = document.getElementById('prom-cluster-name');
    if (promCluster) promCluster.textContent = d.cluster || 'n/a';
    if (d.host_kernel && d.host_kernel !== 'unavailable') {
      const hk = document.getElementById('host-kernel-label');
      if (hk) hk.textContent = 'Host Kernel ' + d.host_kernel;
    }
    if (Array.isArray(d.preset_probes)) {
      renderPresetProbeChips(d.preset_probes);
    }
    const shortGke =
      d.gke_version && d.gke_version !== 'unavailable'
        ? String(d.gke_version).split('-')[0]
        : 'n/a';
    const workerCount = Array.isArray(d.worker_pods) ? d.worker_pods.length : 0;
    document.getElementById('live-cluster-pill').textContent =
      `GKE ${shortGke} · ${d.substrate_version || 'n/a'} · ${d.total_actors ?? 'n/a'} Agents on ${workerCount} Pod(s) (${d.oversub_ratio || 'n/a'})`;
    document.getElementById('global-workerpool-pill').textContent =
      `${workerCount} warm GKE pod(s) hosting ${d.total_actors ?? 'n/a'} Security Demo Actors`;
    if (workerCount > 0) {
      document.getElementById('proof-pod').textContent =
        (d.namespace || 'n/a') + '/' + d.worker_pods[0];
    } else {
      document.getElementById('proof-pod').textContent = 'n/a';
    }
    setFooterTelemetry(d);
  } catch (err) {
    if (dot) dot.classList.add('err');
    document.getElementById('live-cluster-pill').textContent =
      'ERROR: ' + (err instanceof Error ? err.message : String(err));
    document.getElementById('global-workerpool-pill').textContent =
      'WorkerPool telemetry unavailable';
  }
}

function runPresetPromQL(kind) {
  runPrometheusQuery(kind || '');
}

async function runPrometheusQuery(customExpr) {
  clearError();
  const btn = document.getElementById('btn-prom');
  if (btn) {
    btn.disabled = true;
    btn.textContent = '🔄 Querying Google Managed Prometheus (:9090)...';
  }
  if (!customExpr) {
    for (let i = 0; i < 4; i++) {
      const el = document.getElementById('prom-val-' + i);
      el.style.opacity = '0';
      el.style.transform = 'translateX(8px)';
      el.style.display = 'none';
    }
  }
  try {
    const d = await postJson('/api/prometheus', {query: customExpr || ''});
    const ws = d.worker_states || {};
    const localAvg =
      d.restore_local_avg_ms != null ? `${d.restore_local_avg_ms} ms local` : 'n/a local';
    const gcsAvg =
      d.restore_latest_avg_ms != null ? `${d.restore_latest_avg_ms} ms GCS` : 'n/a GCS';
    const badges = [
      `idle=${ws.idle ?? 'n/a'} · partial=${ws.partial ?? 'n/a'} · at_capacity=${ws.at_capacity ?? 'n/a'}`,
      `⚡ ${localAvg} · ${gcsAvg} (${d.restore_total ?? 'n/a'} restores)`,
      `🌐 ${d.router_requests_total ?? 'n/a'} routed sandbox requests`,
      `🤖 ${d.gateway_chat_turns_ok ?? 'n/a'} turns · ${d.gateway_tokens_in ?? 'n/a'} in / ${d.gateway_tokens_out ?? 'n/a'} out`,
    ];
    badges.forEach((text, idx) => {
      const el = document.getElementById('prom-val-' + idx);
      el.textContent = text;
      setTimeout(() => {
        el.style.display = 'inline-block';
        requestAnimationFrame(() => {
          el.style.opacity = '1';
          el.style.transform = 'translateX(0)';
        });
      }, idx * 160);
    });
    if (d.cloud_monitoring_url) {
      document.getElementById('gcp-dash-link').href = d.cloud_monitoring_url;
    }
    if (customExpr) {
      const outEl = document.getElementById('prom-shell-out');
      outEl.classList.add('show');
      outEl.textContent =
        `PromQL: ${d.active_query}\n` + JSON.stringify(d.custom_result || [], null, 2);
    }
    setFooterTelemetry(d);
  } catch (err) {
    showError(err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '🔄 Refresh Live Prometheus Metrics (:9090)';
    }
  }
}

async function runAct2() {
  clearError();
  const btn = document.getElementById('btn-s0');
  btn.disabled = true;
  btn.textContent = '⚡ Running Live Snapshot Restore + Verifying Forensic Clone...';
  try {
    const d = await postJson('/api/act2-snapshots', {});
    const traceShort = d.trace_id ? d.trace_id.slice(0, 8) + '...' : 'n/a';
    const traceMed = d.trace_id ? d.trace_id.slice(0, 16) + '...' : 'n/a';
    const localMs = Number(d.local_restore_avg_ms ?? d.cli_roundtrip_resume_ms ?? 0);
    const gcsMs = Number(d.gcs_restore_avg_ms ?? 0);
    const maxMs = Math.max(localMs, gcsMs, 1);
    const localLabel =
      d.local_restore_avg_ms != null
        ? `${d.local_restore_avg_ms} ms avg`
        : `${d.cli_roundtrip_resume_ms ?? 'n/a'} ms CLI`;
    const gcsLabel =
      d.gcs_restore_avg_ms != null ? `${d.gcs_restore_avg_ms} ms avg` : 'no revert yet';
    const localFill = document.getElementById('s0-restore-fill');
    const gcsFill = document.getElementById('s0-gcs-fill');
    document.getElementById('s0-restore-label').textContent =
      `${localLabel} (Trace: ${traceShort})`;
    localFill.textContent = localLabel;
    localFill.style.width = `${Math.min(100, Math.max(18, Math.round((localMs / maxMs) * 92)))}%`;
    document.getElementById('s0-gcs-label').textContent = `${gcsLabel} (kind="latest")`;
    gcsFill.textContent = gcsLabel;
    gcsFill.style.width =
      gcsMs > 0 ? `${Math.min(100, Math.max(18, Math.round((gcsMs / maxMs) * 92)))}%` : '18%';
    document.getElementById('s0-stat-line').textContent =
      `CLI round-trip: ${d.cli_roundtrip_resume_ms ?? 'n/a'} ms · Live OpenTelemetry Trace ID: ${traceMed}`;

    const clonePill = document.getElementById('act2-clone-pill');
    if (d.boot_ids_match === true) {
      clonePill.innerHTML =
        `🔬 <strong>Forensic Clone Verified:</strong> <code class="mono">gemini-agent-forensic</code> cloned from <code class="mono">clean-checkpoint-tag</code> (bootID=<code class="mono">${escapeHtml(d.forensic_boot_id || 'n/a')}</code> preserved)`;
    } else if (d.cross_cpu_durable_fallback === true) {
      clonePill.innerHTML =
        `⚠️ <strong>Cross-CPU Fallback:</strong> <code class="mono">gemini-agent-forensic</code> restored <code class="mono">/data</code> from <code class="mono">clean-checkpoint-tag</code> (new bootID=<code class="mono">${escapeHtml(d.forensic_boot_id || 'n/a')}</code> vs <code class="mono">${escapeHtml(d.buddy_boot_id || 'n/a')}</code>)`;
    } else {
      clonePill.innerHTML =
        `🚨 <strong>Clone Mismatch:</strong> bootID=<code class="mono">${escapeHtml(d.forensic_boot_id || 'n/a')}</code> vs <code class="mono">${escapeHtml(d.buddy_boot_id || 'n/a')}</code>`;
    }
    setFooterTelemetry(d);
  } catch (err) {
    showError(err);
  } finally {
    btn.disabled = false;
    btn.textContent = '⚡ Re-Run Act 2: Live Snapshot Restore + Verify Forensic Clone';
  }
}

async function runAct3Egress() {
  clearError();
  const btn = document.getElementById('btn-act3');
  btn.disabled = true;
  btn.textContent = '🛡️ Executing Live Egress Suite on egress-agent...';
  for (let i = 0; i < 4; i++) {
    const el = document.getElementById('eg-val-' + i);
    if (!el) continue;
    el.style.opacity = '0';
    el.style.transform = 'translateX(8px)';
    el.style.display = 'none';
  }
  try {
    const d = await postJson('/api/act3-egress', {});
    const verdicts = [
      '🔑 ' + (d.verification_badge || 'ERROR: missing verification_badge'),
      '🛡️ ' + (d.dns_block_summary || 'ERROR: missing dns_block_summary'),
      '🛡️ ' + (d.direct_ip_block_summary || 'ERROR: missing direct_ip_block_summary'),
      '🔒 ' + (d.credential_uri || 'ERROR: missing credential_uri'),
    ];
    verdicts.forEach((text, idx) => {
      const el = document.getElementById('eg-val-' + idx);
      if (!el) return;
      el.textContent = text;
      setTimeout(() => {
        el.style.display = 'inline-block';
        requestAnimationFrame(() => {
          el.style.opacity = '1';
          el.style.transform = 'translateX(0)';
        });
      }, idx * 160);
    });
    setFooterTelemetry(d);
  } catch (err) {
    showError(err);
  } finally {
    btn.disabled = false;
    btn.textContent = '🛡️ Re-Run Act 3 Live on egress-agent (Tests A–C + Audit)';
  }
}

function setProbeCell(idx, ok, text) {
  const el = document.getElementById('p-val-' + idx);
  if (!el) return;
  el.classList.toggle('red', !ok);
  el.textContent = (ok ? '🛡️ ' : '🚨 ') + text;
}

async function runRound1() {
  clearError();
  const btn = document.getElementById('btn-s1');
  btn.disabled = true;
  btn.textContent = '💥 Detonating 6-Point gVisor Probe Inside py-detonation-agent...';
  const feed = document.getElementById('s1-feed');
  feed.style.display = 'flex';
  for (let i = 0; i < 6; i++) {
    document.getElementById('p-row-' + i).classList.remove('visible');
  }
  try {
    const d = await postJson('/api/round1-detonate', {});
    const p = d.probes || {};
    const hostKern =
      d.host_kernel && d.host_kernel !== 'unavailable' ? String(d.host_kernel) : '';
    if (hostKern) {
      const hk = document.getElementById('host-kernel-label');
      if (hk) hk.textContent = 'Host Kernel ' + hostKern;
    }
    if (p.kernel) {
      document.getElementById('proof-sandbox').textContent =
        'ateworker-gvisor (' + p.kernel + ')';
    }
    const sandboxKern = String(p.kernel || '');
    const kernelOk =
      Boolean(sandboxKern) &&
      (hostKern ? !sandboxKern.includes(hostKern) : sandboxKern.startsWith('Linux 4.'));
    const mountOk = p.mount_blocked === true;
    const procOk = Boolean(p.proc_escape) && !String(p.proc_escape).startsWith('EXPOSED');
    const secretsList = Array.isArray(p.secret_env_vars) ? p.secret_env_vars : null;
    const envOk = secretsList !== null && secretsList.length === 0;
    const saOk = p.k8s_sa_token_mounted === false;
    const metaOk = p.metadata_blocked === true;

    setProbeCell(0, kernelOk, `${p.kernel || 'n/a'} · /data ${p.data_mode || 'n/a'}`);
    setProbeCell(1, mountOk, p.mount_syscall || 'n/a');
    setProbeCell(2, procOk, p.proc_escape || 'n/a');
    setProbeCell(
      3,
      envOk,
      envOk ? '0 Secrets Found in Environment' : 'LEAK: ' + (secretsList || ['n/a']).join(',')
    );
    setProbeCell(4, saOk, saOk ? 'NOT MOUNTED (SA Token: False)' : 'EXPOSED / UNKNOWN');
    setProbeCell(5, metaOk, p.gke_metadata || 'n/a');
    setFooterTelemetry(d);

    for (let i = 0; i < 6; i++) {
      setTimeout(() => {
        document.getElementById('p-row-' + i).classList.add('visible');
      }, i * 200);
    }
  } catch (err) {
    showError(err);
  } finally {
    btn.disabled = false;
    btn.textContent = '💥 Re-Detonate Act 1: 6-Point gVisor Probe';
  }
}

async function runLiveProbe(idx) {
  clearError();
  const spec = presetProbes.find((item) => item.id === idx);
  const pyCode = spec ? spec.code : `probe_id=${idx}`;
  const outEl = document.getElementById('s1-shell-out');
  outEl.classList.add('show');
  outEl.textContent = '$ python3 -c "' + pyCode + '" -> running inside py-detonation-agent...';
  try {
    const d = await postJson('/api/custom-python', {probe_id: idx});
    const combined = [d.stdout, d.stderr].map((s) => (s || '').trim()).filter(Boolean).join('\n');
    outEl.textContent = '$ python3 -c "' + (d.code || pyCode) + '"\n' + combined;
    setFooterTelemetry(d);
  } catch (err) {
    outEl.textContent = 'Error: ' + (err instanceof Error ? err.message : String(err));
    showError(err);
  }
}

async function runSeedClean() {
  clearError();
  const btn = document.getElementById('btn-s2');
  const btn3 = document.getElementById('btn-s3');
  btn.disabled = true;
  btn.textContent = '🌱 Verifying Clean Checkpoint...';
  hideAct4Badges([0, 1, 2, 3]);
  try {
    const d = await postJson('/api/seed-clean-buddy', {});
    const b = d.brain || {};
    const isClean = b.verdict === 'CLEAN';
    revealAct4Badge(
      0,
      `${isClean ? '🟢' : '🚨'} ${b.approval_policy ?? 'n/a'} · RAM=${b.mem_count ?? 'n/a'} · /data=${b.disk_count ?? 'n/a'}`,
      0,
      !isClean
    );
    btn3.textContent = '⏪ 2. Revert + OTel Trace (--trace)';
    setFooterTelemetry(d);
  } catch (err) {
    showError(err);
  } finally {
    btn.disabled = false;
    btn.textContent = '🧪 1. Detonate Prompt Injection (Flip ADK Policy)';
  }
}

async function runRound2() {
  clearError();
  const btn = document.getElementById('btn-s2');
  const btn3 = document.getElementById('btn-s3');
  btn.disabled = true;
  btn.textContent = '🧪 Executing ADK Tool Hijack in RAM & /data...';
  hideAct4Badges([0, 1, 2, 3]);
  btn3.textContent = '⏪ 2. Revert + OTel Trace (--trace)';
  try {
    const d = await postJson('/api/round2-poison', {});
    const b = d.brain || {};
    const baseClean =
      d.baseline_policy === 'REQUIRE_HUMAN_APPROVAL' &&
      (d.baseline_disk_policy === undefined ||
        d.baseline_disk_policy === 'REQUIRE_HUMAN_APPROVAL');
    revealAct4Badge(
      0,
      `${baseClean ? '🟢' : '🚨'} ${d.baseline_policy ?? 'n/a'} · RAM=${d.baseline_mem ?? 'n/a'} · /data=${d.baseline_disk ?? 'n/a'}`,
      0,
      !baseClean
    );
    revealAct4Badge(
      1,
      `🚨 HIJACKED: ${b.approval_policy ?? 'n/a'} · RAM=${b.mem_count ?? 'n/a'} · /data=${b.disk_count ?? 'n/a'}`,
      200,
      true
    );
    setFooterTelemetry(d);
    btn.textContent = '🚨 1. Policy Hijacked! (Click 2 to Revert)';
  } catch (err) {
    btn.textContent = '🧪 1. Detonate Prompt Injection (Flip ADK Policy)';
    showError(err);
  } finally {
    btn.disabled = false;
  }
}

async function runRound3Revert() {
  clearError();
  const btn = document.getElementById('btn-s3');
  const btn2 = document.getElementById('btn-s2');
  btn.disabled = true;
  btn.textContent = '⏪ Rewinding RAM + /data via kubectl ate revert...';
  hideAct4Badges([2, 3]);
  try {
    const dRev = await postJson('/api/round3-revert-and-trace', {});
    const b = dRev.brain || {};
    const isClean = b.verdict === 'CLEAN';
    const msText = dRev.restore_label || `${dRev.cli_resume_ms ?? 'n/a'} ms CLI`;
    const traceShort = (dRev.trace_id || '').slice(0, 12);
    revealAct4Badge(
      2,
      `${isClean ? '🟢 HEALED:' : '🚨 ERROR:'} ${b.approval_policy ?? 'n/a'} · RAM=${b.mem_count ?? 'n/a'} · /data=${b.disk_count ?? 'n/a'}`,
      0,
      !isClean
    );
    revealAct4Badge(
      3,
      `⚡ ${msText} · Trace: ${traceShort ? traceShort + '...' : 'n/a'}`,
      200,
      false
    );
    setFooterTelemetry(dRev);
    btn2.textContent = '🧪 1. Detonate Prompt Injection (Flip ADK Policy)';
    btn.textContent = `⏪ 2. Reverted (${msText})`;
  } catch (err) {
    btn.textContent = '⏪ 2. Revert + OTel Trace (--trace)';
    showError(err);
  } finally {
    btn.disabled = false;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  refreshClusterWhisper();
});
