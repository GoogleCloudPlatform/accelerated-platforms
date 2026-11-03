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
                            <memory-limit> [--replicas N]

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
  - optionally a replica count (1 to bootstrap the snapshot).

It prints the SHA-256 of the resulting pod template, so that callers can
detect a changed pod spec (whose existing snapshots no longer match).
"""

import hashlib
import json

import sys

import yaml


def main(argv):
    replicas = None
    if "--replicas" in argv:
        i = argv.index("--replicas")
        replicas = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    path, name, wrapper_path, memory_limit = argv[1:]
    with open(wrapper_path) as f:
        wrapper = f.read()
    with open(path) as f:
        docs = [d for d in yaml.safe_load_all(f) if d]
    found = False
    for d in docs:
        if d.get("kind") != "Deployment" or d["metadata"]["name"] != name:
            continue
        found = True
        if replicas is not None:
            d["spec"]["replicas"] = replicas
        pod = d["spec"]["template"]["spec"]
        pod["runtimeClassName"] = "gvisor"
        pod["enableServiceLinks"] = False
        container = next(c for c in pod["containers"] if c["name"] == "modelserver")
        if container.get("command") != ["vllm", "serve"]:
            raise SystemExit(f"unexpected model server command: {container.get('command')}")
        container["command"] = ["/bin/sh", "-c", wrapper, "vllm-podsnapshot"]
        env = container.setdefault("env", [])
        if not any(e["name"] == "VLLM_HOST_IP" for e in env):
            env.append({"name": "VLLM_HOST_IP", "value": "127.0.0.1"})
        container.pop("livenessProbe", None)
        args = container.get("args", [])
        if "--kv-events-config" in args:
            i = args.index("--kv-events-config")
            del args[i:i + 2]
        args[:] = [a for a in args if not a.startswith("--kv-events-config=")]
        container["env"] = [
            e for e in env
            if e.get("valueFrom", {}).get("fieldRef", {}).get("fieldPath") not in ("status.podIP", "metadata.name", "metadata.uid")
            and e["name"] not in ("POD_PORT", "KV_EVENTS_ENDPOINT", "KV_EVENTS_REPLAY_ENDPOINT")
        ]
        template_sha = hashlib.sha256(json.dumps(d["spec"]["template"], sort_keys=True).encode()).hexdigest()
        container.setdefault("resources", {}).setdefault("limits", {})["memory"] = memory_limit
    if not found:
        raise SystemExit(f"Deployment {name} not found in {path}")
    with open(path, "w") as f:
        yaml.safe_dump_all(docs, f, sort_keys=False)
    print(template_sha)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
