#!/usr/bin/env python3
#
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Makes the rendered model server Deployment GKE Pod snapshot ready.

Usage: podsnapshot_patch.py <rendered.yaml> <deployment> <checkpoint-wrapper.sh>
                            <memory-limit>

Changes to the Deployment's pod template (see
manifests/model-server/podsnapshot and the GKE Pod snapshots reference
architecture in this repository):
  - runtimeClassName: gvisor (Pod snapshots are implemented by GKE Sandbox),
  - enableServiceLinks: false (environment variables are captured in the
    snapshot, so don't inject Service addresses),
  - the model server runs `vllm serve <unchanged args>` through
    checkpoint-wrapper.sh, which triggers the checkpoint once vLLM is healthy,
  - VLLM_HOST_IP=127.0.0.1 (a restored pod gets a new IP, but resumes the
    source pod's memory),
  - no livenessProbe (the source pod is paused while it uploads its checkpoint,
    which would fail liveness checks and restart it),
  - a higher memory limit (checkpoint and restore stage GPU memory in host
    memory),
  - no pod-specific values in the container spec: GKE validates that a
    restored container has the same command and arguments as the snapshot
    source, and kubelet expands $(POD_IP) differently in every pod. So the
    `--kv-events-config` argument (its topic embeds the pod IP; only precise
    prefix cache routing uses KV events) and environment variables from
    status.podIP are removed. A restore with the pod IP in the arguments failed
    with "OCI runtime restore failed: starting sub-container".

It rewrites <rendered.yaml> in place and prints the SHA-256 of the resulting
pod template, so that callers can detect a changed pod spec (whose existing
snapshots no longer match).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any

import yaml

MODEL_SERVER_CONTAINER = "modelserver"
MODEL_SERVER_COMMAND = ["vllm", "serve"]
# Environment variables whose values differ in every pod.
POD_SPECIFIC_FIELD_PATHS = ("status.podIP", "metadata.name", "metadata.uid")
POD_SPECIFIC_ENV = ("POD_PORT", "KV_EVENTS_ENDPOINT", "KV_EVENTS_REPLAY_ENDPOINT")
KV_EVENTS_FLAG = "--kv-events-config"
MEMORY_QUANTITY = re.compile(r"^[0-9]+(\.[0-9]+)?(Ki|Mi|Gi|Ti|Pi|Ei|k|M|G|T|P|E)?$")


def patch_deployment_docs(
    docs: list[dict[str, Any]],
    name: str,
    wrapper: str,
    memory_limit: str,
) -> str:
    """Patches the Deployment `name` in `docs` in place for GKE Pod snapshots.

    Args:
        docs: Parsed Kubernetes YAML documents.
        name: Target Deployment `metadata.name`.
        wrapper: Shell script body of the Pod snapshot entrypoint wrapper.
        memory_limit: Memory limit quantity, for example `"140Gi"`.

    Returns:
        Hex SHA-256 digest of the patched `spec.template`.

    Raises:
        ValueError: If the memory limit is not a Kubernetes quantity; if the
            Deployment, its `modelserver` container, or that container's
            `vllm serve` command is missing; or if a remaining argument
            references a removed pod-specific environment variable.
    """
    if not MEMORY_QUANTITY.match(memory_limit):
        raise ValueError(
            f"memory limit {memory_limit!r} is not a Kubernetes quantity such as "
            "140Gi; check MR_POD_SNAPSHOT_MEMORY_LIMIT"
        )
    deployments = [
        d
        for d in docs
        if d.get("kind") == "Deployment" and d.get("metadata", {}).get("name") == name
    ]
    if not deployments:
        raise ValueError(f"Deployment {name} not found")
    template = deployments[0]["spec"]["template"]
    pod = template["spec"]
    containers = [
        c for c in pod.get("containers", []) if c.get("name") == MODEL_SERVER_CONTAINER
    ]
    if not containers:
        raise ValueError(
            f"container {MODEL_SERVER_CONTAINER!r} not found in Deployment {name}"
        )
    container = containers[0]
    command = container.get("command")
    if command != MODEL_SERVER_COMMAND:
        shown = command[:2] + ["..."] if isinstance(command, list) else command
        raise ValueError(
            f"Deployment {name}: expected the {MODEL_SERVER_CONTAINER} command "
            f"{MODEL_SERVER_COMMAND}, got {shown} (already patched?)"
        )

    pod["runtimeClassName"] = "gvisor"
    pod["enableServiceLinks"] = False
    container["command"] = ["/bin/sh", "-c", wrapper, "vllm-podsnapshot"]
    container.pop("livenessProbe", None)
    args = container.get("args", [])
    while KV_EVENTS_FLAG in args:
        idx = args.index(KV_EVENTS_FLAG)
        del args[idx : idx + 2]
    args[:] = [a for a in args if not a.startswith(f"{KV_EVENTS_FLAG}=")]
    env, removed = [], []
    for e in container.get("env", []):
        field_path = e.get("valueFrom", {}).get("fieldRef", {}).get("fieldPath")
        if field_path in POD_SPECIFIC_FIELD_PATHS or e.get("name") in POD_SPECIFIC_ENV:
            removed.append(e.get("name"))
        else:
            env.append(e)
    leftover = [a for a in args if any(f"$({n})" in a for n in removed)]
    if leftover:
        raise ValueError(
            f"Deployment {name}: model server arguments {leftover} reference "
            f"pod-specific variables ({', '.join(removed)}); GKE restores a "
            "container only if its arguments match the snapshot source pod's"
        )
    if not any(e.get("name") == "VLLM_HOST_IP" for e in env):
        env.append({"name": "VLLM_HOST_IP", "value": "127.0.0.1"})
    container["env"] = env
    container.setdefault("resources", {}).setdefault("limits", {})[
        "memory"
    ] = memory_limit
    # Hash after every change, so that a new memory limit (or wrapper) also
    # invalidates the existing snapshots.
    return hashlib.sha256(json.dumps(template, sort_keys=True).encode()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("rendered", help="rendered model server manifests (rewritten)")
    p.add_argument("deployment", help="model server Deployment name")
    p.add_argument("wrapper", help="path of checkpoint-wrapper.sh")
    p.add_argument("memory_limit", help="model server memory limit, e.g. 140Gi")
    args = p.parse_args(argv)

    with open(args.wrapper, encoding="utf-8") as f:
        wrapper = f.read()
    with open(args.rendered, encoding="utf-8") as f:
        docs = [d for d in yaml.safe_load_all(f) if d]
    try:
        template_sha = patch_deployment_docs(
            docs, args.deployment, wrapper, args.memory_limit
        )
    except ValueError as e:
        print(f"{args.rendered}: {e}", file=sys.stderr)
        return 1
    with open(args.rendered, "w", encoding="utf-8") as f:
        yaml.safe_dump_all(docs, f, sort_keys=False)
    print(template_sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
