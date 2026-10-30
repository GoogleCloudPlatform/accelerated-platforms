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

"""Dynamic intent classification for 'The Secure Runtime' agent harness.

Maps each tool call and prompt context to an explicit, least-privilege network
intent before any code executes inside the Agent Substrate actor sandbox.
"""

from dataclasses import dataclass, field
import os
from typing import List


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
    tool_name: str,
    declared_purpose: str = "",
    github_repo: str = "",
) -> IntentClassification:
    """Classifies the network policy required for the upcoming tool call.

    Even if untrusted content inside a fetched GitHub issue instructs the model
    to mutate issues, post comments, or send data to an external server, the
    harness never elevates the intent beyond read-only access for the configured
    GitHub repository.
    """
    repo = (github_repo or os.environ.get("GITHUB_REPO", "demo-org/demo-repo")).strip("/")
    secret_uri = os.environ.get(
        "GITHUB_SECRET_URI",
        "ate-secret://k8s.io/default/agent-credentials/github-readonly-token/token",
    )

    purpose_lower = (declared_purpose or "").lower()

    if tool_name == "triage_github_issue_in_sandbox" or any(
        kw in purpose_lower for kw in ("github", "issue", "triage", "fetch")
    ):
        return IntentClassification(
            intent_name="github_issue_read_only",
            requires_network=True,
            allowed_hosts=["api.github.com"],
            allowed_methods=["GET", "HEAD"],
            allowed_path_prefixes=[f"/repos/{repo}/"],
            secret_uri=secret_uri,
            rationale=(
                f"Issue triage requires read-only GET/HEAD access to "
                f"api.github.com/repos/{repo}/* with out-of-sandbox token injection. "
                f"All state-mutating methods (POST/PATCH/PUT/DELETE) and unlisted "
                f"hosts remain blocked at atenet-egress."
            ),
        )

    return IntentClassification(
        intent_name="offline_compute_only",
        requires_network=False,
        allowed_hosts=[],
        allowed_methods=[],
        allowed_path_prefixes=[],
        secret_uri="",
        rationale=(
            "Local scientific compute and reproducer execution require zero "
            "external network egress (default-deny)."
        ),
    )
