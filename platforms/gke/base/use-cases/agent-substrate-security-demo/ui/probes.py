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

"""Sandbox boundary probes, egress block checks, and actor state inspection."""

import json
import re
from typing import Any

import kube

PRESET_PROBE_SPECS: tuple[dict[str, str], ...] = (
    {
        "label": "⚡ uname / gVisor kernel",
        "code": "import platform; print(platform.platform())",
    },
    {
        "label": "💾 stat /data & SA token",
        "code": (
            'import os; print("mode:", oct(os.stat("/data").st_mode), '
            '"SA token:", os.path.exists('
            '"/var/run/secrets/kubernetes.io/serviceaccount/token"))'
        ),
    },
    {
        "label": "🔒 dump os.environ",
        "code": "import os; print(sorted(os.environ.keys()))",
    },
)

PRESET_PROBES: tuple[str, ...] = tuple(item["code"] for item in PRESET_PROBE_SPECS)

ROUND1_PYTHON_SCRIPT = r"""
import ctypes, errno, json, os, platform, urllib.error, urllib.request

out = {}
st_mode = oct(os.stat("/data").st_mode)[-4:]
out["kernel"] = f"{platform.system()} {platform.release()}"
out["data_mode"] = st_mode
out["env_keys"] = sorted(os.environ.keys())
out["secret_env_vars"] = [
    k for k in os.environ
    if any(w in k.upper() for w in ("TOKEN", "SECRET", "KEY", "PASS", "KUBERNETES"))
]
out["k8s_sa_token_mounted"] = os.path.exists(
    "/var/run/secrets/kubernetes.io/serviceaccount/token"
)

try:
    req = urllib.request.Request(
        "http://169.254.169.254/computeMetadata/v1/"
        "instance/service-accounts/default/token",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(req, timeout=1.5) as resp:
        out["gke_metadata"] = f"REACHABLE (HTTP {resp.status} — LEAK!)"
        out["metadata_blocked"] = False
except urllib.error.HTTPError as e:
    out["gke_metadata"] = f"REACHABLE (HTTP {e.code} — server answered!)"
    out["metadata_blocked"] = False
except (urllib.error.URLError, TimeoutError, OSError) as e:
    out["gke_metadata"] = f"BLOCKED ({type(e).__name__}: {e})"
    out["metadata_blocked"] = True

libc = ctypes.CDLL("libc.so.6", use_errno=True)
ctypes.set_errno(0)
rc = libc.mount(b"none", b"/mnt", b"tmpfs", 0, None)
err_num = ctypes.get_errno()
err_name = errno.errorcode.get(err_num, f"errno={err_num}")
mount_blocked = rc == -1 and err_name in ("EPERM", "EACCES")
out["mount_rc"] = rc
out["mount_errno"] = err_name
out["mount_blocked"] = mount_blocked
out["mount_syscall"] = (
    f"BLOCKED in user space (rc={rc}, errno={err_name})"
    if mount_blocked
    else f"UNEXPECTED (rc={rc}, errno={err_name})"
)

proc_results = {}
for target in ("/proc/kcore", "/proc/sysrq-trigger"):
    mode = "rb" if target == "/proc/kcore" else "wb"
    try:
        with open(target, mode) as f:
            if mode == "rb":
                f.read(16)
        proc_results[target] = "EXPOSED"
    except (FileNotFoundError, PermissionError, OSError) as e:
        proc_results[target] = type(e).__name__
out["proc_probes"] = proc_results
if all(v != "EXPOSED" for v in proc_results.values()):
    out["proc_escape"] = (
        f"BLOCKED (/proc/kcore={proc_results['/proc/kcore']}, "
        f"/proc/sysrq-trigger={proc_results['/proc/sysrq-trigger']})"
    )
else:
    out["proc_escape"] = f"EXPOSED: {proc_results}"

print(json.dumps(out))
""".strip()

DNS_RESOLVER_ERROR_RE = re.compile(
    r"(?:\[Errno -2\]|\[Errno -3\]|Name or service not known|"
    r"Temporary failure in name resolution|no such host|NXDOMAIN)",
    re.IGNORECASE,
)


def verify_dns_block_response(resp: dict[str, Any], target_url: str) -> str:
    """Require HTTP 502 from egress-agent carrying an explicit DNS denial."""
    status = resp.get("status")
    err_text = str(resp.get("error") or "").strip()
    if status != 502 or not err_text:
        raise kube.UpstreamCommandError(
            f"Expected HTTP 502 DNS block for {target_url}, got: {resp}"
        )
    body = re.sub(r"^HTTP 502:\s*", "", err_text).strip()
    expected_prefix = f'fetch: Get "{target_url}":'
    if not body.startswith(expected_prefix):
        raise kube.UpstreamCommandError(
            f"HTTP 502 did not originate from egress-agent for {target_url}: {body}"
        )
    if not DNS_RESOLVER_ERROR_RE.search(body):
        raise kube.UpstreamCommandError(
            f"Expected DNS denial for {target_url}, got non-DNS failure: {body}"
        )
    detail = body[len(expected_prefix) :].strip()
    return f"BLOCKED by Local DNS Relay ({detail[:80]})"


def verify_direct_ip_block_response(resp: dict[str, Any], target_url: str) -> str:
    """Require HTTP 403 `egress denied` from atenet-egress on direct-IP probes."""
    status = resp.get("status")
    err_text = str(resp.get("error") or "").strip()
    if status != 403 or "egress denied" not in err_text.lower():
        raise kube.UpstreamCommandError(
            f"Expected HTTP 403 egress denied for {target_url}, got: {resp}"
        )
    return "BLOCKED at atenet-egress (HTTP 403 egress denied)"


def inspect_buddy_brain(pre_state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inspect gemini-agent RAM and /data policy state (CLEAN/POISONED/ERROR)."""
    state = (
        pre_state
        if pre_state is not None
        else kube.http_json(
            f"{kube.GATEWAY_URL}/actors/gemini-agent/state", timeout=15.0
        )
    )
    if state.get("error"):
        raise kube.UpstreamCommandError(
            f"Failed to query gemini-agent state: {state['error']}"
        )
    actors, _ = kube.get_actors()
    buddy_row = next((a for a in actors if a["name"] == "gemini-agent"), {})
    worker_pod = buddy_row.get("worker_pod") or "<none>"
    policy = str(state.get("approvalPolicy") or "UNSET")
    disk_policy = str(state.get("diskPolicy") or "UNSET")
    if policy == "AUTO_APPROVE_ALL" or disk_policy == "AUTO_APPROVE_ALL":
        verdict = "POISONED"
    elif policy == "REQUIRE_HUMAN_APPROVAL" and disk_policy == "REQUIRE_HUMAN_APPROVAL":
        verdict = "CLEAN"
    else:
        verdict = "ERROR"
    return {
        "bootID": state.get("bootID") or "n/a",
        "approval_policy": policy,
        "disk_policy": disk_policy,
        "mem_count": state.get("memCount"),
        "disk_count": state.get("diskCount"),
        "turn_count": state.get("turns"),
        "worker_pod": worker_pod,
        "verdict": verdict,
    }


def _extract_cpu_features(snap: dict[str, Any]) -> str:
    attrs = ((snap.get("sandboxRuntime") or {}).get("version") or {}).get(
        "attributes"
    ) or []
    for attr in attrs:
        if attr.get("key") == "cpu_features" and attr.get("value"):
            return str(attr["value"])
    return ""


def snapshot_cpu_features(actor_name: str) -> list[str]:
    """Return ordered `cpu_features` values across an actor's snapshot chain."""
    out, err, rc = kube.run_cmd(
        [
            "kubectl",
            "ate",
            "get",
            "actor",
            actor_name,
            "-a",
            kube.ATESPACE,
            "-o",
            "json",
        ],
        timeout=10,
    )
    clean_out = kube.strip_ate_warnings(out)
    if rc != 0 or not clean_out:
        raise kube.UpstreamCommandError(
            f"Failed to inspect snapshots for {actor_name}: "
            f"{kube.strip_ate_warnings(err)}"
        )
    try:
        doc = json.loads(clean_out)
    except json.JSONDecodeError as exc:
        raise kube.UpstreamCommandError(
            f"Invalid actor JSON for {actor_name}: {exc}"
        ) from exc
    feats: list[str] = []
    for snap in (doc.get("status") or {}).get("snapshots") or []:
        val = _extract_cpu_features(snap)
        if val:
            feats.append(val)
    return feats


def tag_cpu_features(tag_name: str) -> str:
    """Return the `cpu_features` attribute recorded on a Snapshot Tag."""
    out, err, rc = kube.run_cmd(
        [
            "kubectl",
            "ate",
            "get",
            "tag",
            tag_name,
            "-a",
            kube.ATESPACE,
            "-o",
            "json",
        ],
        timeout=10,
    )
    clean_out = kube.strip_ate_warnings(out)
    if rc != 0 or not clean_out:
        raise kube.UpstreamCommandError(
            f"Failed to inspect tag {tag_name}: {kube.strip_ate_warnings(err)}"
        )
    try:
        doc = json.loads(clean_out)
    except json.JSONDecodeError as exc:
        raise kube.UpstreamCommandError(
            f"Invalid tag JSON for {tag_name}: {exc}"
        ) from exc
    snap = (doc.get("status") or {}).get("snapshot") or {}
    return _extract_cpu_features(snap)
