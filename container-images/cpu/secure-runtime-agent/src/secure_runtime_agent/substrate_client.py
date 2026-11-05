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

"""Client for Agent Substrate control plane, mTLS router, and intent-extproc."""

import http.client
import json
import os
import shlex
import ssl
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlparse

import yaml

from .telemetry import TERMINAL_BUS


@dataclass
class IntentClassification:
    """Least-privilege egress intent derived for a single tool execution turn."""

    intent_name: str
    requires_network: bool
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_methods: list[str] = field(default_factory=list)
    allowed_path_prefixes: list[str] = field(default_factory=list)
    secret_uri: str = ""
    rationale: str = ""


def classify_tool_intent(
    tool_name: str, declared_purpose: str = "", github_repo: str = ""
) -> IntentClassification:
    """Classifies the network policy required for the upcoming tool call."""
    repo = (
        github_repo
        or os.environ.get("GITHUB_REPO", "GoogleCloudPlatform/accelerated-platforms")
    ).strip("/")
    secret_uri = os.environ.get(
        "GITHUB_SECRET_URI",
        "ate-secret://k8s.io/default/agent-credentials/github-readonly-token/token",
    )
    if tool_name == "triage_github_issue_in_sandbox" or any(
        kw in (declared_purpose or "").lower()
        for kw in ("github", "issue", "triage", "fetch")
    ):
        return IntentClassification(
            intent_name="github_issue_read_only",
            requires_network=True,
            allowed_hosts=["api.github.com"],
            allowed_methods=["GET", "HEAD"],
            allowed_path_prefixes=[f"/repos/{repo}/"],
            secret_uri=secret_uri,
            rationale=(
                f"Read-only GET/HEAD access to api.github.com/repos/{repo}/* "
                "with out-of-sandbox token injection."
            ),
        )
    return IntentClassification(
        intent_name="offline_compute_only",
        requires_network=False,
        rationale=(
            "Local scientific compute requires zero external network egress "
            "(default-deny)."
        ),
    )


def _json_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    ssl_context: ssl.SSLContext | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    conn: http.client.HTTPConnection
    if parsed.scheme == "https":
        if ssl_context is None:
            raise ValueError(f"HTTPS request to {url} requires an explicit SSLContext")
        conn = http.client.HTTPSConnection(
            host, port, context=ssl_context, timeout=timeout
        )
    else:
        conn = http.client.HTTPConnection(host, port, timeout=timeout)

    body_bytes = (
        json.dumps(json_body).encode("utf-8") if json_body is not None else None
    )
    req_headers = dict(headers or {})
    if body_bytes is not None:
        req_headers.setdefault("Content-Type", "application/json")
    try:
        conn.request(method, path, body=body_bytes, headers=req_headers)
        resp = conn.getresponse()
        raw = resp.read(1024 * 1024).decode("utf-8", errors="replace")
        data = json.loads(raw) if raw.strip().startswith("{") else {"raw": raw}
        return resp.status, data
    finally:
        conn.close()


class SubstrateClient:
    """Manages Actor lifecycle, EgressPolicy, intent-extproc, and mTLS calls."""

    def __init__(self) -> None:
        self.atespace = os.environ.get("SUBSTRATE_ATESPACE", "secure-runtime")
        self.template = os.environ.get("SUBSTRATE_ACTOR_TEMPLATE", "scientific-python")
        self.router_url = os.environ.get(
            "ATENET_ROUTER_URL", "https://atenet-router.ate-system.svc:443"
        ).rstrip("/")
        self.extproc_url = os.environ.get(
            "INTENT_EXTPROC_CONTROL_URL",
            "http://intent-extproc.ate-system.svc:8080",
        ).rstrip("/")
        self.podidentity_cert = os.environ.get(
            "PODIDENTITY_CRED_BUNDLE",
            "/run/podidentity.podcert.ate.dev/credential-bundle.pem",
        )
        self.servicedns_ca = os.environ.get(
            "SERVICEDNS_TRUST_BUNDLE",
            "/run/servicedns.podcert.ate.dev/trust-bundle.pem",
        )
        self._applied_policies: dict[str, str] = {}

    def _build_mtls_context(self) -> ssl.SSLContext:
        """Builds a strict mTLS SSLContext; fails closed if certs are missing."""
        if not (
            os.path.isfile(self.podidentity_cert) and os.path.isfile(self.servicedns_ca)
        ):
            raise FileNotFoundError(
                "Missing Agent Substrate mTLS bundles: "
                f"cert={self.podidentity_cert!r}, ca={self.servicedns_ca!r}. "
                "Ensure podidentity and servicedns projected volumes are mounted "
                "on deploy/triage-agent."
            )
        ctx = ssl.create_default_context(cafile=self.servicedns_ca)
        ctx.load_cert_chain(
            certfile=self.podidentity_cert, keyfile=self.podidentity_cert
        )
        return ctx

    def _run_kubectl_ate(
        self,
        args: list[str],
        stdin_text: str | None = None,
        *,
        emit_log: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        ate_api_addr = os.environ.get("ATE_API_ADDR") or (
            "api.ate-system.svc:443"
            if os.environ.get("KUBERNETES_SERVICE_HOST")
            else ""
        )
        flags = [f"--endpoint={ate_api_addr}"] if ate_api_addr else []
        full_cmd = ["kubectl-ate", *flags, *args]
        t0 = time.monotonic()
        res = subprocess.run(
            full_cmd,
            input=stdin_text,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        ms = round((time.monotonic() - t0) * 1000, 1)
        if emit_log:
            pretty = " ".join(shlex.quote(p) for p in full_cmd)
            status = "OK" if res.returncode == 0 else f"rc={res.returncode}"
            TERMINAL_BUS.emit(
                "cmd",
                f"$ {pretty}  [{status} in {ms} ms]",
                duration_ms=ms,
                detail=(res.stdout or res.stderr).strip(),
            )
        return res

    def list_actors(self) -> list[dict[str, str]]:
        """Lists live Actors in the configured Atespace."""
        res = self._run_kubectl_ate(
            ["get", "actors", "-a", self.atespace, "-o", "json"], emit_log=False
        )
        if res.returncode != 0 or not res.stdout.strip().startswith("{"):
            return []
        raw = json.loads(res.stdout)
        items = raw.get("items") or raw.get("actors") or []
        return [
            {
                "name": item.get("metadata", {}).get("name", ""),
                "template": item.get("spec", {}).get("actorTemplateName", ""),
                "phase": item.get("status", {}).get("phase", "Ready"),
            }
            for item in items
            if item.get("metadata", {}).get("name")
        ]

    def get_golden_snapshot_tag(self) -> str:
        """Returns the live Golden Snapshot tag name for the ActorTemplate."""
        res = self._run_kubectl_ate(
            [
                "get",
                "actor-template",
                self.template,
                "-a",
                self.atespace,
                "-o",
                "json",
            ],
            emit_log=False,
        )
        if res.returncode != 0 or not res.stdout.strip().startswith("{"):
            return ""
        tmpl_data = json.loads(res.stdout)
        return str(
            tmpl_data.get("status", {})
            .get("goldenSnapshotStatus", {})
            .get("goldenTag", {})
            .get("name")
            or ""
        )

    def ensure_actor(self, actor_name: str) -> dict[str, Any]:
        t0 = time.monotonic()
        created = False
        check = self._run_kubectl_ate(
            ["get", "actor", actor_name, "-a", self.atespace], emit_log=False
        )
        if check.returncode != 0:
            res = self._run_kubectl_ate(
                [
                    "create",
                    "actor",
                    actor_name,
                    "-a",
                    self.atespace,
                    "--template",
                    self.template,
                ]
            )
            if res.returncode != 0 and "already exists" not in res.stderr:
                raise RuntimeError(
                    f"kubectl-ate create actor {actor_name} failed: "
                    f"{res.stderr.strip()}"
                )
            created = True
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "template": self.template,
            "created_from_golden_snapshot": created,
            "ensure_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def suspend_actor(self, actor_name: str) -> dict[str, Any]:
        t0 = time.monotonic()
        res = self._run_kubectl_ate(
            ["suspend", "actor", actor_name, "-a", self.atespace]
        )
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "suspended": res.returncode == 0,
            "suspend_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def delete_actor(self, actor_name: str) -> dict[str, Any]:
        t0 = time.monotonic()
        self._applied_policies.pop(actor_name, None)
        self._run_kubectl_ate(
            ["suspend", "actor", actor_name, "-a", self.atespace], emit_log=False
        )
        res = self._run_kubectl_ate(
            ["delete", "actor", actor_name, "-a", self.atespace]
        )
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "deleted": res.returncode == 0,
            "delete_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def apply_egress_policy(
        self, actor_name: str, classification: IntentClassification
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        if not classification.requires_network or not classification.allowed_hosts:
            self._applied_policies.pop(actor_name, None)
            self._run_kubectl_ate(
                ["delete", "egress-policy", actor_name, "-a", self.atespace]
            )
            return {
                "actor_ref": f"{self.atespace}/{actor_name}",
                "egress_policy": "default-deny (no rules)",
                "policy_sync_ms": round((time.monotonic() - t0) * 1000, 2),
            }

        https_rule: dict[str, Any] = {
            "hostnames": classification.allowed_hosts,
            "ports": {"numbers": [443]},
        }
        if classification.secret_uri:
            https_rule["effects"] = {
                "replaceHeaders": [
                    {
                        "header": "Authorization",
                        "prefix": "Bearer ",
                        "credentialUri": classification.secret_uri,
                    }
                ]
            }
        policy_yaml = yaml.safe_dump({"rules": [{"https": https_rule}]})
        if self._applied_policies.get(actor_name) != policy_yaml:
            self._run_kubectl_ate(
                ["delete", "egress-policy", actor_name, "-a", self.atespace],
                emit_log=False,
            )
            res = self._run_kubectl_ate(
                [
                    "create",
                    "egress-policy",
                    actor_name,
                    "-a",
                    self.atespace,
                    "-f",
                    "-",
                ],
                stdin_text=policy_yaml,
            )
            if res.returncode != 0:
                raise RuntimeError(
                    f"kubectl-ate create egress-policy {actor_name} failed: "
                    f"{res.stderr.strip()}"
                )
            self._applied_policies[actor_name] = policy_yaml
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "egress_policy": classification.intent_name,
            "allowed_hosts": classification.allowed_hosts,
            "credential_injected_from": classification.secret_uri,
            "policy_sync_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def apply_intent_extproc(
        self, actor_ref: str, classification: IntentClassification
    ) -> dict[str, Any]:
        if not classification.requires_network:
            return self.revoke_intent_extproc(actor_ref)
        payload = {
            "actor": actor_ref,
            "intent": classification.intent_name,
            "allowed_hosts": classification.allowed_hosts,
            "allowed_methods": classification.allowed_methods,
            "allowed_path_prefixes": classification.allowed_path_prefixes,
        }
        t0 = time.monotonic()
        status, data = _json_request(
            "POST", f"{self.extproc_url}/v1/policies", json_body=payload, timeout=5.0
        )
        ms = round((time.monotonic() - t0) * 1000, 1)
        TERMINAL_BUS.emit(
            "http",
            f"POST {self.extproc_url}/v1/policies [{classification.intent_name}] -> {status} ({ms} ms)",
            duration_ms=ms,
            detail=json.dumps(payload),
        )
        if status >= 400:
            raise RuntimeError(f"intent-extproc returned HTTP {status}: {data}")
        return data

    def revoke_intent_extproc(self, actor_ref: str) -> dict[str, Any]:
        qs = urlencode({"actor": actor_ref})
        t0 = time.monotonic()
        status, data = _json_request(
            "DELETE", f"{self.extproc_url}/v1/policies?{qs}", timeout=5.0
        )
        ms = round((time.monotonic() - t0) * 1000, 1)
        TERMINAL_BUS.emit(
            "http",
            f"DELETE {self.extproc_url}/v1/policies?actor={actor_ref} -> {status} ({ms} ms)",
            duration_ms=ms,
        )
        if status in (200, 404):
            return {"status": "revoked", "actor": actor_ref}
        raise RuntimeError(f"intent-extproc revoke failed HTTP {status}: {data}")

    def list_audit_events(self, actor_ref: str = "") -> list[dict[str, Any]]:
        qs = f"?{urlencode({'actor': actor_ref})}" if actor_ref else ""
        status, data = _json_request(
            "GET", f"{self.extproc_url}/v1/audit{qs}", timeout=5.0
        )
        if status >= 400:
            raise RuntimeError(f"intent-extproc audit query failed HTTP {status}")
        return list(data.get("events") or [])

    def call_actor(
        self,
        actor_name: str,
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        actor_ref = f"{self.atespace}/{actor_name}"
        ssl_ctx = self._build_mtls_context()
        t0 = time.monotonic()
        status, data = _json_request(
            method,
            f"{self.router_url}{path}",
            headers={"ate-target-actor": actor_ref},
            json_body=json_body,
            ssl_context=ssl_ctx,
            timeout=60.0,
        )
        roundtrip_ms = round((time.monotonic() - t0) * 1000, 2)
        TERMINAL_BUS.emit(
            "http",
            f"mTLS {method} {self.router_url}{path} [actor={actor_ref}] -> {status} ({roundtrip_ms} ms)",
            duration_ms=roundtrip_ms,
        )
        if status >= 400:
            raise RuntimeError(
                f"atenet-router {method} {path} returned HTTP {status}: {data}"
            )
        return {**data, "router_roundtrip_ms": roundtrip_ms, "actor_ref": actor_ref}
