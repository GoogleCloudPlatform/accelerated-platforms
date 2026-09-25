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

import os
import shlex
import time
import uuid

import httpx
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from kubernetes import client, config


def _load_k8s_custom_objects() -> client.CustomObjectsApi:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CustomObjectsApi()


def run_python_code(code: str) -> str:
    """Executes generated Python code inside an ephemeral, isolated gVisor GKE Agent Sandbox pod.

    Args:
        code: The complete Python script to execute inside the isolated sandbox.
    """
    api_url = os.environ.get(
        "SANDBOX_API_URL",
        "http://sandbox-router-svc.agent-sandbox.svc.cluster.local:8080",
    ).rstrip("/")
    namespace = os.environ.get("SANDBOX_NAMESPACE", "agent-sandbox")
    template_name = os.environ.get("SANDBOX_TEMPLATE", "python-runtime-template")
    router_token = os.environ.get("ROUTER_AUTH_TOKEN", "")

    claim_name = f"sandbox-claim-{uuid.uuid4().hex[:8]}"
    custom_api = _load_k8s_custom_objects()

    claim_body = {
        "apiVersion": "extensions.agents.x-k8s.io/v1alpha1",
        "kind": "SandboxClaim",
        "metadata": {
            "name": claim_name,
            "namespace": namespace,
        },
        "spec": {
            "sandboxTemplateRef": {
                "name": template_name,
            }
        },
    }

    try:
        # 1. Claim a pre-warmed gVisor pod from the SandboxWarmPool via SandboxTemplate
        custom_api.create_namespaced_custom_object(
            group="extensions.agents.x-k8s.io",
            version="v1alpha1",
            namespace=namespace,
            plural="sandboxclaims",
            body=claim_body,
        )

        # 2. Wait for the claimed Sandbox to report Ready=True (typically <50ms from WarmPool)
        pod_ip = None
        for _ in range(60):
            try:
                sb = custom_api.get_namespaced_custom_object(
                    group="agents.x-k8s.io",
                    version="v1alpha1",
                    namespace=namespace,
                    plural="sandboxes",
                    name=claim_name,
                )
                status = sb.get("status", {})
                conditions = status.get("conditions", [])
                is_ready = any(
                    c.get("type") == "Ready" and c.get("status") == "True"
                    for c in conditions
                )
                if is_ready:
                    pod_ips = status.get("podIPs") or []
                    if pod_ips:
                        pod_ip = pod_ips[0]
                    break
            except Exception:
                pass
            time.sleep(0.25)

        # 3. Route execution request through sandbox-router with Bearer authentication
        headers = {
            "X-Sandbox-ID": claim_name,
            "X-Sandbox-Namespace": namespace,
            "X-Sandbox-Port": "8888",
        }
        if pod_ip:
            headers["X-Sandbox-Pod-IP"] = pod_ip
        if router_token:
            headers["Authorization"] = f"Bearer {router_token}"

        cmd = f"python3 -c {shlex.quote(code)}"
        with httpx.Client(timeout=60.0) as http_client:
            resp = http_client.post(
                f"{api_url}/execute",
                headers=headers,
                json={"command": cmd},
            )
            resp.raise_for_status()
            data = resp.json()

        output = (data.get("stdout") or "").strip()
        errors = (data.get("stderr") or "").strip()
        exit_code = data.get("exit_code", 0)
        if errors or exit_code != 0:
            return (
                f"Execution Output:\n{output}\n\n"
                f"Execution Errors/Warnings (exit_code={exit_code}):\n{errors}"
            )
        return f"Execution Successful (Sandbox ID: {claim_name}):\n{output}"
    except Exception as e:
        return f"Sandbox System Error: {str(e)}"
    finally:
        # 4. Delete the SandboxClaim so the WarmPool immediately replenishes a fresh gVisor pod
        try:
            custom_api.delete_namespaced_custom_object(
                group="extensions.agents.x-k8s.io",
                version="v1alpha1",
                namespace=namespace,
                plural="sandboxclaims",
                name=claim_name,
            )
        except Exception:
            pass


api_base = os.environ.get("OPENAI_API_BASE")
if api_base:
    model_id = os.environ.get("OPENAI_MODEL_NAME", "openai/google/gemma-3-27b-it")
    agent_model = LiteLlm(
        model=model_id,
        api_base=api_base,
        api_key=os.environ.get("OPENAI_API_KEY", "none"),
    )
else:
    agent_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = LlmAgent(
    name="CodingAgent",
    model=agent_model,
    instruction=(
        "You are an autonomous Python software engineer running on GKE. "
        "When asked to solve a problem, write the Python code AND execute it using the "
        "`run_python_code` tool inside the isolated gVisor Agent Sandbox to verify the output. "
        "The sandbox is a minimal zero-trust environment: always prefer Python standard library "
        "modules (such as `urllib.request` or `socket` instead of third-party `requests`) unless "
        "otherwise needed. Always report the exact output and sandbox details returned by the tool."
    ),
    tools=[run_python_code],
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)
