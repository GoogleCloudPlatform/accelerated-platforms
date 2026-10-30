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

"""Client for the intent-extproc control API in ate-system."""

import os
from typing import Any, Dict, List

import httpx

from .intent import IntentClassification


class IntentExtProcClient:
    """Registers and revokes per-actor L7 HTTP rules on intent-extproc."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (
            base_url
            or os.environ.get(
                "INTENT_EXTPROC_CONTROL_URL",
                "http://intent-extproc.ate-system.svc.cluster.local:8080",
            )
        ).rstrip("/")

    def apply_intent(
        self, actor_ref: str, classification: IntentClassification
    ) -> Dict[str, Any]:
        """Registers or revokes the L7 rule for actor_ref based on classification."""
        if not classification.requires_network:
            return self.revoke_intent(actor_ref)

        payload = {
            "actor": actor_ref,
            "intent": classification.intent_name,
            "allowed_hosts": classification.allowed_hosts,
            "allowed_methods": classification.allowed_methods,
            "allowed_path_prefixes": classification.allowed_path_prefixes,
        }
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(f"{self.base_url}/v1/policies", json=payload)
            resp.raise_for_status()
            return resp.json()

    def revoke_intent(self, actor_ref: str) -> Dict[str, Any]:
        """Deletes the active L7 rule for actor_ref, restoring default-deny."""
        with httpx.Client(timeout=5.0) as client:
            resp = client.delete(
                f"{self.base_url}/v1/policies", params={"actor": actor_ref}
            )
            if resp.status_code in (200, 404):
                return {"status": "revoked", "actor": actor_ref}
            resp.raise_for_status()
            return resp.json()

    def list_audit_events(self, actor_ref: str = "") -> List[Dict[str, Any]]:
        """Fetches recent L7 egress decisions recorded by intent-extproc."""
        params = {"actor": actor_ref} if actor_ref else {}
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{self.base_url}/v1/audit", params=params)
            resp.raise_for_status()
            return resp.json().get("events") or []
