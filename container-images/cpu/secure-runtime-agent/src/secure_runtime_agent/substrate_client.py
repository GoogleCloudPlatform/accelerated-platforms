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

"""Client for Agent Substrate control plane (ate-api-server), data plane (atenet-router), and intent-extproc."""

from dataclasses import dataclass, field
import os
import ssl
import subprocess
import time
from typing import Any, Dict, List

import httpx
import yaml


@dataclass
class IntentClassification:
    """Least-privilege egress intent derived for a single tool execution turn."""

    intent_name: str
    requires_network: bool
    allowed_hosts: List[str] = field(default_factory=list)
    allowed_methods: List[str] = field(default_factory=list)
    allowed_path_prefixes: List[str] = field(default_factory=list)
    secret_uri: str = ""
    rationale: str = ""


def classify_tool_intent(
    tool_name: str, declared_purpose: str = "", github_repo: str = ""
) -> IntentClassification:
    """Classifies the network policy required for the upcoming tool call."""
    repo = (github_repo or os.environ.get("GITHUB_REPO", "demo-org/demo-repo")).strip("/")
    secret_uri = os.environ.get(
        "GITHUB_SECRET_URI",
        "ate-secret://k8s.io/default/agent-credentials/github-readonly-token/token",
    )
    if tool_name == "triage_github_issue_in_sandbox" or any(
        kw in (declared_purpose or "").lower() for kw in ("github", "issue", "triage", "fetch")
    ):
        return IntentClassification(
            intent_name="github_issue_read_only",
            requires_network=True,
            allowed_hosts=["api.github.com"],
            allowed_methods=["GET", "HEAD"],
            allowed_path_prefixes=[f"/repos/{repo}/"],
            secret_uri=secret_uri,
            rationale=f"Read-only GET/HEAD access to api.github.com/repos/{repo}/* with out-of-sandbox token injection.",
        )
    return IntentClassification(
        intent_name="offline_compute_only",
        requires_network=False,
        rationale="Local scientific compute requires zero external network egress (default-deny).",
    )


class SubstrateClient:
    """Manages Actor lifecycle, dynamic EgressPolicy, intent-extproc L7 rules, and mTLS routing."""

    def __init__(self) -> None:
        self.atespace = os.environ.get("SUBSTRATE_ATESPACE", "secure-runtime")
        self.template = os.environ.get("SUBSTRATE_ACTOR_TEMPLATE", "scientific-python")
        self.router_url = os.environ.get("ATENET_ROUTER_URL", "https://atenet-router.ate-system.svc:443").rstrip("/")
        self.extproc_url = os.environ.get("INTENT_EXTPROC_CONTROL_URL", "http://intent-extproc.ate-system.svc.cluster.local:8080").rstrip("/")
        self.podidentity_cert = os.environ.get("PODIDENTITY_CRED_BUNDLE", "/run/podidentity.podcert.ate.dev/credential-bundle.pem")
        self.servicedns_ca = os.environ.get("SERVICEDNS_TRUST_BUNDLE", "/run/servicedns.podcert.ate.dev/trust-bundle.pem")
        self._applied_policies: Dict[str, str] = {}

    def _run_kubectl_ate(self, args: list[str], stdin_text: str | None = None) -> subprocess.CompletedProcess:
        ate_api_addr = os.environ.get("ATE_API_ADDR") or (
            "api.ate-system.svc:443" if os.environ.get("KUBERNETES_SERVICE_HOST") else ""
        )
        flags = [f"--endpoint={ate_api_addr}"] if ate_api_addr else []
        return subprocess.run(["kubectl-ate", *flags, *args], input=stdin_text, text=True, capture_output=True, timeout=60, check=False)

    def ensure_actor(self, actor_name: str) -> Dict[str, Any]:
        t0 = time.monotonic()
        created = False
        if self._run_kubectl_ate(["get", "actor", actor_name, "-a", self.atespace]).returncode != 0:
            res = self._run_kubectl_ate(["create", "actor", actor_name, "-a", self.atespace, "--template", self.template])
            if res.returncode != 0 and "already exists" not in res.stderr:
                raise RuntimeError(f"kubectl-ate create actor {actor_name} failed: {res.stderr.strip()}")
            created = True
        return {"actor_ref": f"{self.atespace}/{actor_name}", "template": self.template, "created_from_golden_snapshot": created, "ensure_ms": round((time.monotonic() - t0) * 1000, 2)}

    def suspend_actor(self, actor_name: str) -> Dict[str, Any]:
        t0 = time.monotonic()
        res = self._run_kubectl_ate(["suspend", "actor", actor_name, "-a", self.atespace])
        return {"actor_ref": f"{self.atespace}/{actor_name}", "suspended": res.returncode == 0, "suspend_ms": round((time.monotonic() - t0) * 1000, 2)}

    def delete_actor(self, actor_name: str) -> Dict[str, Any]:
        t0 = time.monotonic()
        self._applied_policies.pop(actor_name, None)
        self._run_kubectl_ate(["suspend", "actor", actor_name, "-a", self.atespace])
        res = self._run_kubectl_ate(["delete", "actor", actor_name, "-a", self.atespace])
        return {"actor_ref": f"{self.atespace}/{actor_name}", "deleted": res.returncode == 0, "delete_ms": round((time.monotonic() - t0) * 1000, 2)}

    def apply_egress_policy(self, actor_name: str, classification: IntentClassification) -> Dict[str, Any]:
        t0 = time.monotonic()
        if not classification.requires_network or not classification.allowed_hosts:
            self._applied_policies.pop(actor_name, None)
            self._run_kubectl_ate(["delete", "egress-policy", actor_name, "-a", self.atespace])
            return {"actor_ref": f"{self.atespace}/{actor_name}", "egress_policy": "default-deny (no rules)", "policy_sync_ms": round((time.monotonic() - t0) * 1000, 2)}

        https_rule: Dict[str, Any] = {"hostnames": classification.allowed_hosts, "ports": {"numbers": [443]}}
        if classification.secret_uri:
            https_rule["effects"] = {"replaceHeaders": [{"header": "Authorization", "prefix": "Bearer ", "credentialUri": classification.secret_uri}]}
        policy_yaml = yaml.safe_dump({"rules": [{"https": https_rule}]})
        if self._applied_policies.get(actor_name) != policy_yaml:
            self._run_kubectl_ate(["delete", "egress-policy", actor_name, "-a", self.atespace])
            res = self._run_kubectl_ate(["create", "egress-policy", actor_name, "-a", self.atespace, "-f", "-"], stdin_text=policy_yaml)
            if res.returncode != 0:
                raise RuntimeError(f"kubectl-ate create egress-policy {actor_name} failed: {res.stderr.strip()}")
            self._applied_policies[actor_name] = policy_yaml
        return {"actor_ref": f"{self.atespace}/{actor_name}", "egress_policy": classification.intent_name, "allowed_hosts": classification.allowed_hosts, "credential_injected_from": classification.secret_uri, "policy_sync_ms": round((time.monotonic() - t0) * 1000, 2)}

    def apply_intent_extproc(self, actor_ref: str, classification: IntentClassification) -> Dict[str, Any]:
        if not classification.requires_network:
            return self.revoke_intent_extproc(actor_ref)
        payload = {"actor": actor_ref, "intent": classification.intent_name, "allowed_hosts": classification.allowed_hosts, "allowed_methods": classification.allowed_methods, "allowed_path_prefixes": classification.allowed_path_prefixes}
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{self.extproc_url}/v1/policies", json=payload)
            resp.raise_for_status()
            return resp.json()

    def revoke_intent_extproc(self, actor_ref: str) -> Dict[str, Any]:
        with httpx.Client(timeout=5.0) as client:
            resp = client.delete(f"{self.extproc_url}/v1/policies", params={"actor": actor_ref})
            return {"status": "revoked", "actor": actor_ref} if resp.status_code in (200, 404) else resp.json()

    def list_audit_events(self, actor_ref: str = "") -> List[Dict[str, Any]]:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{self.extproc_url}/v1/audit", params={"actor": actor_ref} if actor_ref else {})
            resp.raise_for_status()
            return resp.json().get("events") or []

    def call_actor(self, actor_name: str, method: str, path: str, json_body: Dict[str, Any] | None = None) -> Dict[str, Any]:
        actor_ref = f"{self.atespace}/{actor_name}"
        verify: ssl.SSLContext | bool = False
        if os.path.exists(self.podidentity_cert) and os.path.exists(self.servicedns_ca):
            verify = ssl.create_default_context(cafile=self.servicedns_ca)
            verify.load_cert_chain(certfile=self.podidentity_cert, keyfile=self.podidentity_cert)
        t0 = time.monotonic()
        with httpx.Client(verify=verify, timeout=60.0) as client:
            resp = client.request(method=method, url=f"{self.router_url}{path}", headers={"ate-target-actor": actor_ref, "Content-Type": "application/json"}, json=json_body)
            roundtrip_ms = round((time.monotonic() - t0) * 1000, 2)
            resp.raise_for_status()
            return {**resp.json(), "router_roundtrip_ms": roundtrip_ms, "actor_ref": actor_ref}
