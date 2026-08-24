#!/usr/bin/env python3
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

"""Capture vLLM runtime config, resolved envs, and scaling state for benchmarking."""

import argparse
import json
import re
import subprocess


def get_kubectl_json(cmd: str) -> dict:
    """Execute a kubectl command and return the parsed JSON dictionary."""
    return json.loads(subprocess.check_output(cmd, shell=True, text=True))


def deep_get(d: dict, keys: list, default=None):
    """Safely traverse a nested dictionary using a list of keys."""
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def substitute_vars(text: str, env_map: dict) -> str:
    """Resolve $(VAR) and ${VAR} in a string using up to 3 passes."""
    if not isinstance(text, str):
        return text

    def repl(m):
        var = m.group(1) or m.group(2)
        return str(env_map.get(var, m.group(0)))

    curr = text
    for _ in range(3):
        nxt = re.sub(r"\$\(([A-Za-z0-9_]+)\)|\$\{([A-Za-z0-9_]+)\}", repl, curr)
        if nxt == curr:
            break
        curr = nxt
    return curr


def get_vllm_workload_and_container(items: list) -> tuple:
    """Find the vLLM Deployment/StatefulSet and its target inference container."""
    for item in items:
        if item.get("kind") not in ("Deployment", "StatefulSet"):
            continue
        meta, containers = item.get("metadata", {}), deep_get(
            item, ["spec", "template", "spec", "containers"], []
        )
        is_vllm = (
            "vllm" in meta.get("name", "").lower()
            or meta.get("labels", {}).get("app") == "vllm"
        )
        if not is_vllm and not any(
            "vllm" in c.get("image", "").lower() for c in containers
        ):
            continue
        for c in containers:
            name, img = c.get("name", "").lower(), c.get("image", "").lower()
            if "vllm" in name or "vllm" in img or "inference" in name:
                return item, c
        if containers:
            return item, containers[0]
    return None, {}


def detect_architecture(namespace: str, dep: dict, env_map: dict, args: list) -> dict:
    """Identify GKE reference architecture pattern, model, and KV offloading."""
    kv_cfg = env_map.get("KV_TRANSFER_CONFIG", "")
    is_offload = "OffloadingConnector" in kv_cfg or any(
        "OffloadingConnector" in str(a) for a in args
    )
    node_sel = deep_get(dep, ["spec", "template", "spec", "nodeSelector"], {})
    cc, accel = node_sel.get("cloud.google.com/compute-class", ""), node_sel.get(
        "cloud.google.com/gke-accelerator", ""
    )

    match_labels = deep_get(dep, ["spec", "selector", "matchLabels"])
    if match_labels:
        try:
            sel = ",".join(f"{k}={v}" for k, v in match_labels.items())
            pods = get_kubectl_json(
                f"kubectl get pods -n {namespace} -l '{sel}' -o json"
            ).get("items", [])
            node_name = deep_get(pods[0], ["spec", "nodeName"]) if pods else None
            if node_name:
                labels = get_kubectl_json(f"kubectl get node {node_name} -o json").get(
                    "metadata", {}
                )["labels"]
                accel = labels.get("cloud.google.com/gke-accelerator", accel)
                cc = labels.get("cloud.google.com/compute-class", cc)
        except Exception:
            pass

    limits = deep_get(
        dep, ["spec", "template", "spec", "containers", 0, "resources", "limits"], {}
    )
    accel_count = str(
        limits.get(
            "nvidia.com/gpu",
            limits.get("google.com/tpu", limits.get("google.com/tpu-v6e", "1")),
        )
    )
    labels = deep_get(dep, ["spec", "template", "metadata", "labels"], {})
    model = (
        env_map.get("MODEL_NAME")
        or env_map.get("MODEL_ID")
        or labels.get("ai.gke.io/model", "unknown")
    )
    arch = (
        "online-inference-gpu/vllm-native-kv-cache-offloading/single-tier"
        if is_offload
        else "online-inference-gpu/standard"
    )

    cpu_bytes = None
    if is_offload and kv_cfg:
        try:
            cpu_bytes = deep_get(
                json.loads(kv_cfg),
                ["kv_connector_extra_config", "cpu_bytes_to_use"],
            )
        except Exception:
            pass

    return {
        "reference_architecture_manifest_pattern": arch,
        "compute_class": cc or "default-nap",
        "accelerator_type": accel or "unknown-accelerator",
        "accelerator_count": accel_count,
        "model": model,
        "kv_offloading_enabled": is_offload,
        "cpu_offload_buffer_bytes": cpu_bytes,
    }


def get_scaling_state(dep: dict, hpa_list: list) -> dict:
    """Return replicas and HPA target state for the workload."""
    dep_name = deep_get(dep, ["metadata", "name"], "")
    hpa_info = next(
        (
            {
                "name": deep_get(h, ["metadata", "name"]),
                "min_replicas": deep_get(h, ["spec", "minReplicas"]),
                "max_replicas": deep_get(h, ["spec", "maxReplicas"]),
                "current_replicas": deep_get(h, ["status", "currentReplicas"], 0),
            }
            for h in hpa_list
            if deep_get(h, ["spec", "scaleTargetRef", "name"]) == dep_name
        ),
        None,
    )
    return {
        "configured_replicas": deep_get(dep, ["spec", "replicas"], 1),
        "ready_replicas": deep_get(dep, ["status", "readyReplicas"], 0),
        "hpa_enabled": hpa_info is not None,
        "hpa_info": hpa_info,
    }


def capture_vllm_config(namespace: str, spec_name: str, output_path: str):
    """Retrieve runtime state and write self-contained vllm_config.json."""
    try:
        items = get_kubectl_json(
            f"kubectl get deployments,statefulsets,configmaps,hpa -n {namespace} -o json"
        ).get("items", [])
        configmaps = {
            i["metadata"]["name"]: i.get("data", {})
            for i in items
            if i.get("kind") == "ConfigMap"
        }
        hpa_list = [i for i in items if i.get("kind") == "HorizontalPodAutoscaler"]

        dep, container = get_vllm_workload_and_container(items)
        if not dep:
            raise ValueError(
                f"No vLLM Deployment/StatefulSet found in namespace {namespace}"
            )

        env_map = {
            k: v
            for ef in container.get("envFrom", [])
            if "configMapRef" in ef and ef["configMapRef"].get("name") in configmaps
            for k, v in configmaps[ef["configMapRef"]["name"]].items()
        }
        for e in container.get("env", []):
            if "value" in e:
                env_map[e["name"]] = e["value"]
            elif "configMapKeyRef" in e.get("valueFrom", {}):
                ref = e["valueFrom"]["configMapKeyRef"]
                if ref.get("name") in configmaps:
                    env_map[e["name"]] = configmaps[ref["name"]].get(ref.get("key"), "")

        resolved_args = [substitute_vars(a, env_map) for a in container.get("args", [])]
        resolved_cmd = [
            substitute_vars(c, env_map) for c in container.get("command", [])
        ]

        result = {
            "well_lit_path_guide": spec_name,
            "detected_architecture": detect_architecture(
                namespace, dep, env_map, resolved_args
            ),
            "scaling_state": get_scaling_state(dep, hpa_list),
            "resolved_runtime_env": env_map,
            "resolved_container_args": resolved_args,
            "resolved_container_command": resolved_cmd,
            "deployment": dep,
        }
    except Exception as exc:
        result = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "well_lit_path_guide": spec_name,
        }

    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Capture vLLM deployment config, resolved envs, and scaling state."
    )
    parser.add_argument("--namespace", required=True, help="K8s namespace")
    parser.add_argument("--spec", default="", help="Well-lit path guide name")
    parser.add_argument(
        "--output", default="./vllm_config.json", help="Output JSON path"
    )
    args = parser.parse_args()
    capture_vllm_config(args.namespace, args.spec, args.output)


if __name__ == "__main__":
    main()
