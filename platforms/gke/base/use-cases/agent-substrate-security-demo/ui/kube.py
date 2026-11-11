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

"""Kubernetes, port-forward, Gateway HTTP, and Prometheus helpers."""

import base64
import http.client
import json
import math
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import IO, Any
from urllib.parse import urlencode, urlparse


def _default_use_case_dir() -> Path:
    return Path(__file__).resolve().parent.parent


USE_CASE_DIR = Path(
    os.environ.get("USE_CASE_DIR", str(_default_use_case_dir()))
).resolve()
STATE_DIR = USE_CASE_DIR / ".state"
MANIFESTS_DIR = USE_CASE_DIR / "manifests"
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")


def _load_staged_defaults(state_dir: Path) -> dict[str, str]:
    """Read key=value fallback defaults persisted by `stage.sh` in `.state/`."""
    env_file = state_dir / "staged.env"
    if not env_file.is_file():
        return {}
    parsed: dict[str, str] = {}
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            clean_val = val.strip().strip('"').strip("'")
            if key.strip() and clean_val:
                parsed[key.strip()] = clean_val
    except OSError:
        return {}
    return parsed


_STAGED = _load_staged_defaults(STATE_DIR)
ATESPACE = os.environ.get("ATESPACE", _STAGED.get("ATESPACE", "security-demo"))
NAMESPACE = os.environ.get("NAMESPACE", _STAGED.get("NAMESPACE", "agent-sandbox"))
SECRETS_NAMESPACE = os.environ.get(
    "SECRETS_NAMESPACE", _STAGED.get("SECRETS_NAMESPACE", "agent-secrets")
)
GATEWAY_URL = os.environ.get(
    "GATEWAY_URL", f"http://127.0.0.1:{os.environ.get('GATEWAY_LOCAL_PORT', '8081')}"
).rstrip("/")
PROMETHEUS_URL = os.environ.get(
    "PROMETHEUS_URL", f"http://127.0.0.1:{os.environ.get('PROM_LOCAL_PORT', '9090')}"
).rstrip("/")
GATEWAY_PORT = int(urlparse(GATEWAY_URL).port or 8081)
PROM_PORT = int(urlparse(PROMETHEUS_URL).port or 9090)
BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1").strip()
PORT = int(os.environ.get("PORT", "18090"))
UI_AUTH_TOKEN = os.environ.get("UI_AUTH_TOKEN", "").strip()
ALLOW_UNAUTHENTICATED_BIND = os.environ.get("ALLOW_UNAUTHENTICATED_BIND", "0") == "1"
ALLOW_CUSTOM_PYTHON = os.environ.get("ALLOW_CUSTOM_PYTHON", "0") == "1"
ALLOW_CUSTOM_PROMQL = os.environ.get("ALLOW_CUSTOM_PROMQL", "0") == "1"
EXTRA_ALLOWED_HOSTS = {
    h.strip().lower()
    for h in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if h.strip()
}

_PORT_FORWARD_LOCK = threading.Lock()
_CACHE_LOCK = threading.Lock()
_PF_PROCESSES: dict[int, subprocess.Popen[bytes]] = {}
_CACHED_CLUSTER_NAME: str | None = None
_CACHED_PROJECT_ID: str | None = None
_CACHED_ADMIN_TOKEN: str | None = None
_CACHED_CLUSTER_META: dict[str, str] | None = None


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Never follow 30x redirects so auth headers cannot leak off-origin."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        del req, fp, code, msg, headers, newurl
        return None


_HTTP_OPENER = urllib.request.build_opener(_NoRedirectHandler())


class UpstreamCommandError(RuntimeError):
    """Raised when a live GKE / Agent Substrate command or HTTP call fails."""


def escape_promql_label(value: str) -> str:
    """Escape backslashes, double quotes, and newlines in a PromQL label."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def reset_caches() -> None:
    """Clear memoized cluster metadata (used by unit tests)."""
    global _CACHED_CLUSTER_NAME, _CACHED_PROJECT_ID
    global _CACHED_ADMIN_TOKEN, _CACHED_CLUSTER_META
    with _CACHE_LOCK:
        _CACHED_CLUSTER_NAME = _CACHED_PROJECT_ID = None
        _CACHED_ADMIN_TOKEN = _CACHED_CLUSTER_META = None


def _env() -> dict[str, str]:
    env = dict(os.environ)
    local_bin = Path.home() / ".local" / "bin"
    env["PATH"] = f"{USE_CASE_DIR / 'bin'}:{local_bin}:{env.get('PATH', '')}"
    return env


def run_cmd(
    args: list[str], timeout: int = 90, cwd: Path | None = None
) -> tuple[str, str, int]:
    """Invoke a subprocess without shell=True and return (stdout, stderr, rc)."""
    res = subprocess.run(
        args,
        cwd=str(cwd or USE_CASE_DIR),
        env=_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return res.stdout.strip(), res.stderr.strip(), res.returncode


def strip_ate_warnings(text: str) -> str:
    """Remove shared-client informational lines from kubectl-ate output."""
    return "\n".join(
        ln
        for ln in text.splitlines()
        if ln.strip() and not ln.lstrip().startswith("Warning:")
    ).strip()


def is_not_found_error(text: str) -> bool:
    """Return True if CLI stderr indicates the target resource does not exist."""
    lower = text.lower()
    tokens = ("not found", "not_found", "notfound", "404", "does not exist")
    return "has no egress policy" in lower or any(tok in lower for tok in tokens)


def _gke_ctx_parts() -> list[str]:
    ctx_out, _, rc = run_cmd(["kubectl", "config", "current-context"], timeout=5)
    parts = ctx_out.strip().split("_") if rc == 0 and ctx_out else []
    return parts if len(parts) >= 4 and parts[0] == "gke" else []


def get_cluster_name() -> str:
    """Resolve the active GKE cluster name lazily or fail fast if undetectable."""
    global _CACHED_CLUSTER_NAME
    env_cluster = os.environ.get("CLUSTER_NAME", "").strip()
    if env_cluster:
        return env_cluster
    with _CACHE_LOCK:
        if _CACHED_CLUSTER_NAME is not None:
            return _CACHED_CLUSTER_NAME
    parts = _gke_ctx_parts()
    resolved = (
        "_".join(parts[3:])
        if parts and "_".join(parts[3:])
        else _load_staged_defaults(STATE_DIR).get("CLUSTER_NAME", "")
    )
    if resolved:
        with _CACHE_LOCK:
            _CACHED_CLUSTER_NAME = resolved
        return resolved
    raise UpstreamCommandError(
        "Unable to determine GKE cluster name from CLUSTER_NAME or kubectl "
        "current-context; export CLUSTER_NAME=<name>."
    )


def detect_project_id() -> str:
    """Resolve the active GCP project ID from env, kubeconfig, or gcloud."""
    global _CACHED_PROJECT_ID
    env_proj = (
        os.environ.get("PROJECT_ID", "").strip()
        or os.environ.get("TF_VAR_platform_default_project_id", "").strip()
    )
    if env_proj:
        return env_proj
    with _CACHE_LOCK:
        if _CACHED_PROJECT_ID is not None:
            return _CACHED_PROJECT_ID
    parts = _gke_ctx_parts()
    proj = parts[1] if parts and parts[1] else ""
    if not proj:
        proj = _load_staged_defaults(STATE_DIR).get("PROJECT_ID", "")
    if not proj:
        out, _, rc = run_cmd(["gcloud", "config", "get-value", "project"], timeout=8)
        proj = out.strip() if rc == 0 and out.strip() != "(unset)" else ""
    if proj:
        with _CACHE_LOCK:
            _CACHED_PROJECT_ID = proj
    return proj


def detect_cluster_meta() -> dict[str, str]:
    """Query live GKE version, host node kernel, and installed Substrate tag."""
    global _CACHED_CLUSTER_META
    with _CACHE_LOCK:
        if _CACHED_CLUSTER_META is not None:
            return dict(_CACHED_CLUSTER_META)

    meta = {
        "gke_version": "unavailable",
        "host_kernel": "unavailable",
        "substrate_version": "unavailable",
    }
    node_jp = (
        "jsonpath={.items[0].status.nodeInfo.kubeletVersion}"
        "|{.items[0].status.nodeInfo.kernelVersion}"
    )
    node_out, _, node_rc = run_cmd(
        ["kubectl", "get", "nodes", "-o", node_jp], timeout=8
    )
    if node_rc == 0 and "|" in node_out:
        kv, kern = node_out.split("|", 1)
        if kv.strip():
            meta["gke_version"] = kv.strip().lstrip("v")
        if kern.strip():
            meta["host_kernel"] = kern.strip()

    api_jp = "jsonpath={.spec.template.spec.containers[0].image}"
    api_cmd = ["kubectl", "-n", "ate-system", "get", "deploy", "ate-api-server"]
    api_img, _, api_rc = run_cmd([*api_cmd, "-o", api_jp], timeout=8)
    if api_rc == 0 and api_img.strip():
        ref_part = api_img.strip().split("@", 1)[0]
        if ":" in ref_part:
            meta["substrate_version"] = ref_part.rsplit(":", 1)[1]

    if "unavailable" not in (meta["gke_version"], meta["substrate_version"]):
        with _CACHE_LOCK:
            _CACHED_CLUSTER_META = dict(meta)
    return meta


def _get_gateway_admin_token(force_refresh: bool = False) -> str:
    global _CACHED_ADMIN_TOKEN
    env_tok = os.environ.get("GATEWAY_ADMIN_TOKEN", "").strip()
    if env_tok:
        return env_tok
    with _CACHE_LOCK:
        if _CACHED_ADMIN_TOKEN is not None and not force_refresh:
            return _CACHED_ADMIN_TOKEN
    sec_cmd = ["kubectl", "-n", NAMESPACE, "get", "secret", "gateway-admin-token"]
    out, _, rc = run_cmd([*sec_cmd, "-o", "jsonpath={.data.token}"], timeout=8)
    if rc == 0 and out.strip():
        try:
            decoded = base64.b64decode(out.strip()).decode("utf-8").strip()
        except (ValueError, UnicodeDecodeError) as exc:
            raise UpstreamCommandError(
                f"Secret {NAMESPACE}/gateway-admin-token has invalid base64: {exc}"
            ) from exc
        if decoded:
            with _CACHE_LOCK:
                _CACHED_ADMIN_TOKEN = decoded
            return decoded
    return ""


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def _probe_http(port: int, path: str, expected: str) -> bool:
    try:
        with _HTTP_OPENER.open(f"http://127.0.0.1:{port}{path}", timeout=1.5) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.status == 200 and (not expected or expected in text)
    except (OSError, urllib.error.URLError):
        return False


def _pf_targets() -> dict[int, tuple[str, str, str, str, str, str]]:
    gw = (
        "gateway",
        NAMESPACE,
        "deploy/gateway",
        f"{GATEWAY_PORT}:8081",
        "/identity",
        "agent-substrate-gateway",
    )
    pr = (
        "prometheus",
        NAMESPACE,
        "deploy/prometheus-ui",
        f"{PROM_PORT}:9090",
        "/-/ready",
        "",
    )
    return {GATEWAY_PORT: gw, PROM_PORT: pr}


def _terminate_proc(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=1)


def _stop_pidfile(pidfile: Path) -> None:
    if not pidfile.exists():
        return
    try:
        pid = int(pidfile.read_text(encoding="utf-8").strip())
        cmd_p = Path(f"/proc/{pid}/cmdline")
        cmd_s = cmd_p.read_bytes().decode("utf-8", "replace") if cmd_p.exists() else ""
        if "kubectl" in cmd_s and "port-forward" in cmd_s:
            os.kill(pid, 15)
    except (ValueError, OSError):
        pass
    pidfile.unlink(missing_ok=True)


def _start_single_pf(local_port: int, force_restart: bool = False) -> None:
    targets = _pf_targets()
    if local_port not in targets:
        return
    name, ns, target, mapping, probe_path, expected = targets[local_port]
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    pidfile = STATE_DIR / f"pf-{name}.pid"
    if not force_restart and _probe_http(local_port, probe_path, expected):
        return
    _terminate_proc(_PF_PROCESSES.pop(local_port, None))
    _stop_pidfile(pidfile)
    for _ in range(10):
        if not _port_open("127.0.0.1", local_port):
            break
        time.sleep(0.05)
    if _port_open("127.0.0.1", local_port) and not _probe_http(
        local_port, probe_path, expected
    ):
        raise UpstreamCommandError(
            f"Local port 127.0.0.1:{local_port} is already occupied by another "
            "process; override GATEWAY_LOCAL_PORT / PROM_LOCAL_PORT."
        )
    pf_cmd = ["kubectl", "port-forward", "--address", "127.0.0.1", "-n", ns]
    proc = subprocess.Popen(
        [*pf_cmd, target, mapping],
        env=_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _PF_PROCESSES[local_port] = proc
    pidfile.write_text(f"{proc.pid}\n", encoding="utf-8")
    for _ in range(30):
        if proc.poll() is not None:
            break
        if _probe_http(local_port, probe_path, expected):
            return
        time.sleep(0.5)
    _PF_PROCESSES.pop(local_port, None)
    _terminate_proc(proc)
    pidfile.unlink(missing_ok=True)
    raise UpstreamCommandError(
        f"kubectl port-forward ({ns}/{target} -> 127.0.0.1:{local_port}) "
        "failed readiness check."
    )


def stop_spawned_port_forwards() -> None:
    """Terminate all port-forward subprocesses started by this UI server."""
    with _PORT_FORWARD_LOCK:
        targets = _pf_targets()
        for lport, proc in list(_PF_PROCESSES.items()):
            _PF_PROCESSES.pop(lport, None)
            _terminate_proc(proc)
            if lport in targets:
                (STATE_DIR / f"pf-{targets[lport][0]}.pid").unlink(missing_ok=True)


def ensure_port_forwards(force_port: int | None = None) -> None:
    """Ensure local port-forwards to gateway and prometheus-ui are live."""
    with _PORT_FORWARD_LOCK:
        targets = _pf_targets()
        if force_port in targets:
            _start_single_pf(force_port, force_restart=True)
            return
        gw_host = urlparse(GATEWAY_URL).hostname
        pr_host = urlparse(PROMETHEUS_URL).hostname
        for lport in targets:
            if lport == GATEWAY_PORT and gw_host not in _LOOPBACK_HOSTS:
                continue
            if lport == PROM_PORT and pr_host not in _LOOPBACK_HOSTS:
                continue
            _start_single_pf(lport, force_restart=False)


def _is_gateway_target(url: str) -> bool:
    base = GATEWAY_URL.rstrip("/")
    return url == base or url.startswith((f"{base}/", f"{base}?"))


def http_json(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Perform a non-redirecting HTTP request (attaching admin token to Gateway)."""
    ensure_port_forwards()
    parsed = urlparse(url)
    is_gw = _is_gateway_target(url)
    req_hdrs = dict(headers or {})
    tok = _get_gateway_admin_token() if is_gw else ""
    if tok:
        req_hdrs.setdefault("X-Gateway-Admin-Token", tok)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if data is not None:
        req_hdrs.setdefault("Content-Type", "application/json")
    net_errs = (
        urllib.error.URLError,
        ConnectionError,
        TimeoutError,
        http.client.RemoteDisconnected,
    )
    for attempt in range(2):
        req = urllib.request.Request(url, data=data, headers=req_hdrs, method=method)
        try:
            with _HTTP_OPENER.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    doc = json.loads(raw)
                    return (
                        doc
                        if isinstance(doc, dict)
                        else {"raw": raw, "status": resp.status}
                    )
                except json.JSONDecodeError:
                    return {"raw": raw, "status": resp.status}
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401 and is_gw and attempt == 0:
                new_tok = _get_gateway_admin_token(force_refresh=True)
                if new_tok:
                    req_hdrs["X-Gateway-Admin-Token"] = new_tok
                    continue
            return {"error": f"HTTP {exc.code}: {err_body}", "status": exc.code}
        except net_errs as exc:
            if (
                attempt == 0
                and parsed.hostname in _LOOPBACK_HOSTS
                and parsed.port in _pf_targets()
            ):
                ensure_port_forwards(force_port=parsed.port)
                continue
            return {"error": f"{type(exc).__name__}: {exc}"}
    return {"error": "Unreachable endpoint after port-forward retry"}


def suspend_actor_checked(actor: str, timeout: int = 20) -> str:
    """Suspend an actor and raise UpstreamCommandError on non-zero exit."""
    out, err, rc = run_cmd(
        ["kubectl", "ate", "suspend", "actor", actor, "-a", ATESPACE], timeout=timeout
    )
    cleaned = strip_ate_warnings(f"{out}\n{err}")
    if rc != 0:
        raise UpstreamCommandError(
            f"Failed to suspend {ATESPACE}/{actor} (exit {rc}): {cleaned}"
        )
    return cleaned or f"Actor {ATESPACE}/{actor} transitioned to ACTOR_STATE_SUSPENDED."


def get_actors(include_table: bool = False) -> tuple[list[dict[str, str]], str]:
    """Return structured actor metadata (and optional table text)."""
    json_out, json_err, rc = run_cmd(
        ["kubectl", "ate", "get", "actors", "-a", ATESPACE, "-o", "json"], timeout=15
    )
    clean_json = strip_ate_warnings(json_out)
    if rc != 0 or not clean_json:
        raise UpstreamCommandError(
            f"kubectl ate get actors failed (exit {rc}): {strip_ate_warnings(json_err)}"
        )
    clean_table = ""
    if include_table:
        table_out, table_err, t_rc = run_cmd(
            ["kubectl", "ate", "get", "actors", "-a", ATESPACE], timeout=15
        )
        if t_rc != 0:
            detail = strip_ate_warnings(table_err)
            raise UpstreamCommandError(
                f"kubectl ate get actors table failed (exit {t_rc}): {detail}"
            )
        clean_table = strip_ate_warnings(table_out)
    try:
        payload = json.loads(clean_json)
    except json.JSONDecodeError as exc:
        raise UpstreamCommandError(
            f"Invalid JSON from kubectl ate get actors: {exc}"
        ) from exc

    actors: list[dict[str, str]] = []
    for item in payload.get("actors") or []:
        meta = item.get("metadata") or {}
        tpl = item.get("actorTemplate") or {}
        status = item.get("status") or {}
        wa = status.get("workerAssignment") or {}
        w_ns, w_pod = wa.get("workerNamespace", ""), wa.get("workerPod", "")
        actors.append(
            {
                "atespace": meta.get("atespace", ATESPACE),
                "name": meta.get("name", ""),
                "template": f"{tpl.get('atespace', ATESPACE)}/{tpl.get('name', '')}",
                "state": str(status.get("state", "UNKNOWN")).replace(
                    "ACTOR_STATE_", ""
                ),
                "worker_pod": f"{w_ns}/{w_pod}" if w_ns and w_pod else "<none>",
                "version": str(meta.get("version", "")),
            }
        )
    return actors, clean_table


def promql_query(prom_expr: str) -> list[dict[str, Any]]:
    """Execute a PromQL instant query against prometheus-ui (:9090)."""
    url = f"{PROMETHEUS_URL}/api/v1/query?" + urlencode({"query": prom_expr})
    resp = http_json(url, method="GET", timeout=8.0)
    if resp.get("error"):
        raise UpstreamCommandError(
            f"Prometheus query failed ({PROMETHEUS_URL}): {resp['error']}"
        )
    if resp.get("status") != "success":
        err_detail = resp.get("error") or resp.get("raw") or resp
        raise UpstreamCommandError(f"Prometheus returned non-success: {err_detail}")
    return (resp.get("data") or {}).get("result") or []


def query_restore_ms(
    kind: str, phase: str = "total", strict: bool = False
) -> float | None:
    """Query average restore latency (ms) from GMP for `kind` and `phase`."""
    c, sp = escape_promql_label(get_cluster_name()), escape_promql_label(ATESPACE)
    ph, kd = escape_promql_label(phase), escape_promql_label(kind)
    sel = (
        f'cluster="{c}", "ate.template.atespace"="{sp}", '
        f'"ate.snapshot.phase"="{ph}", "ate.snapshot.kind"="{kd}"'
    )
    q = (
        f'sum({{"ate.actor.restore.duration_sum", {sel}}}) / '
        f'sum({{"ate.actor.restore.duration_count", {sel}}})'
    )
    try:
        res = promql_query(q)
    except UpstreamCommandError:
        if strict:
            raise
        return None
    try:
        sec = float((res[0].get("value") or [0, "nan"])[1]) if res else float("nan")
    except (ValueError, TypeError):
        return None
    return round(sec * 1000.0, 1) if math.isfinite(sec) and sec >= 0.0 else None
