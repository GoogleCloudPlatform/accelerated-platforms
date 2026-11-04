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

"""Client for Agent Substrate control plane (ate-api-server) and data plane (atenet-router)."""

import os
import ssl
import subprocess
import time
from typing import Any, Dict

import httpx
import yaml

from .intent import IntentClassification


class SubstrateClient:
    """Manages Actor lifecycle, dynamic EgressPolicy, and mTLS routing via atenet-router."""

    def __init__(self) -> None:
        self.atespace = os.environ.get("SUBSTRATE_ATESPACE", "secure-runtime")
        self.template = os.environ.get("SUBSTRATE_ACTOR_TEMPLATE", "scientific-python")
        self.router_url = os.environ.get(
            "ATENET_ROUTER_URL", "https://atenet-router.ate-system.svc:443"
        ).rstrip("/")
        self.podidentity_cert = os.environ.get(
            "PODIDENTITY_CRED_BUNDLE",
            "/run/podidentity.podcert.ate.dev/credential-bundle.pem",
        )
        self.servicedns_ca = os.environ.get(
            "SERVICEDNS_TRUST_BUNDLE",
            "/run/servicedns.podcert.ate.dev/trust-bundle.pem",
        )
        self._applied_policies: Dict[str, str] = {}

    def _run_kubectl_ate(
        self, args: list[str], stdin_text: str | None = None
    ) -> subprocess.CompletedProcess:
        ate_api_addr = os.environ.get("ATE_API_ADDR") or (
            "api.ate-system.svc:443" if os.environ.get("KUBERNETES_SERVICE_HOST") else ""
        )
        flags = [f"--endpoint={ate_api_addr}"] if ate_api_addr else []
        return subprocess.run(
            ["kubectl-ate", *flags, *args],
            input=stdin_text,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )

    def ensure_actor(self, actor_name: str) -> Dict[str, Any]:
        """Creates the actor from the Golden Snapshot template if it does not exist."""
        t0 = time.monotonic()
        created = False
        if self._run_kubectl_ate(["get", "actor", actor_name, "-a", self.atespace]).returncode != 0:
            res = self._run_kubectl_ate(
                ["create", "actor", actor_name, "-a", self.atespace, "--template", self.template]
            )
            if res.returncode != 0 and "already exists" not in res.stderr:
                raise RuntimeError(f"kubectl-ate create actor {actor_name} failed: {res.stderr.strip()}")
            created = True
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "template": self.template,
            "created_from_golden_snapshot": created,
            "ensure_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def suspend_actor(self, actor_name: str) -> Dict[str, Any]:
        """Checkpoints the actor memory/filesystem to GCS and frees its worker."""
        t0 = time.monotonic()
        res = self._run_kubectl_ate(["suspend", "actor", actor_name, "-a", self.atespace])
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "suspended": res.returncode == 0,
            "suspend_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def delete_actor(self, actor_name: str) -> Dict[str, Any]:
        """Suspends (if running) and deletes an actor so the next turn starts from the Golden Snapshot."""
        t0 = time.monotonic()
        self._applied_policies.pop(actor_name, None)
        self._run_kubectl_ate(["suspend", "actor", actor_name, "-a", self.atespace])
        res = self._run_kubectl_ate(["delete", "actor", actor_name, "-a", self.atespace])
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "deleted": res.returncode == 0,
            "delete_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def apply_egress_policy(
        self, actor_name: str, classification: IntentClassification
    ) -> Dict[str, Any]:
        """Applies or deletes the per-actor EgressPolicy in ate-api-server."""
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

        https_rule: Dict[str, Any] = {
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
                ["delete", "egress-policy", actor_name, "-a", self.atespace]
            )
            res = self._run_kubectl_ate(
                ["create", "egress-policy", actor_name, "-a", self.atespace, "-f", "-"],
                stdin_text=policy_yaml,
            )
            if res.returncode != 0:
                raise RuntimeError(
                    f"kubectl-ate create egress-policy {actor_name} failed: {res.stderr.strip()}"
                )
            self._applied_policies[actor_name] = policy_yaml
        return {
            "actor_ref": f"{self.atespace}/{actor_name}",
            "egress_policy": classification.intent_name,
            "allowed_hosts": classification.allowed_hosts,
            "credential_injected_from": classification.secret_uri,
            "policy_sync_ms": round((time.monotonic() - t0) * 1000, 2),
        }

    def _build_router_http_client(self) -> httpx.Client:
        if os.path.exists(self.podidentity_cert) and os.path.exists(self.servicedns_ca):
            ssl_ctx = ssl.create_default_context(cafile=self.servicedns_ca)
            ssl_ctx.load_cert_chain(
                certfile=self.podidentity_cert, keyfile=self.podidentity_cert
            )
            return httpx.Client(verify=ssl_ctx, timeout=60.0)
        return httpx.Client(verify=False, timeout=60.0)

    def call_actor(
        self,
        actor_name: str,
        method: str,
        path: str,
        json_body: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Routes an HTTP request to the actor through atenet-router.

        If the actor is suspended, atenet-router automatically wakes it from
        its snapshot before forwarding the request.
        """
        actor_ref = f"{self.atespace}/{actor_name}"
        headers = {
            "ate-target-actor": actor_ref,
            "Content-Type": "application/json",
        }
        t0 = time.monotonic()
        with self._build_router_http_client() as client:
            resp = client.request(
                method=method,
                url=f"{self.router_url}{path}",
                headers=headers,
                json=json_body,
            )
            roundtrip_ms = round((time.monotonic() - t0) * 1000, 2)
            resp.raise_for_status()
            data = resp.json()
            data["router_roundtrip_ms"] = roundtrip_ms
            data["actor_ref"] = actor_ref
            return data
