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

"""Capture the live vLLM serving configuration for a benchmark run.

Records every vLLM model server in the namespace -- not just the first one --
so that disaggregated topologies such as the ``pd-disaggregation`` well-lit
path, which run separate prefill and decode deployments, are captured in full.

For each model server the script records the resolved container args and
environment, the parsed KV transfer configuration, any sidecars (including
native sidecars declared as ``initContainers`` with ``restartPolicy: Always``),
the scaling state, and the live pods backing it, with the image IDs actually
running on the nodes.

The top level of the emitted JSON keeps the original single-server keys, which
mirror the primary model server, so existing consumers keep working.
"""

import argparse
import datetime
import json
import re
import subprocess

# Node labels that identify the attached accelerator.
GPU_NODE_LABEL = "cloud.google.com/gke-accelerator"
TPU_NODE_LABEL = "cloud.google.com/gke-tpu-accelerator"
TPU_TOPOLOGY_LABEL = "cloud.google.com/gke-tpu-topology"
COMPUTE_CLASS_LABEL = "cloud.google.com/compute-class"

# Resource names that carry an accelerator count.
GPU_RESOURCE = "nvidia.com/gpu"
TPU_RESOURCES = ("google.com/tpu", "google.com/tpu-v6e")

# Labels applied by the llm-d guides.
ROLE_LABEL = "llm-d.ai/role"
GUIDE_LABEL = "llm-d.ai/guide"
ENGINE_LABEL = "llm-d.ai/engine-type"

# vLLM parameters with the largest effect on benchmark results, shown in the
# console summary. Everything parsed is still written to serving_parameters.
HEADLINE_PARAMETERS = (
    "max_model_len",
    "tensor_parallel_size",
    "data_parallel_size",
    "pipeline_parallel_size",
    "dtype",
    "kv_cache_dtype",
    "quantization",
    "max_num_seqs",
    "max_num_batched_tokens",
    "gpu_memory_utilization",
    "block_size",
    "enable_prefix_caching",
    "no_enable_prefix_caching",
    "enable_chunked_prefill",
    "swap_space",
    "load_format",
)


def run_kubectl(args: list) -> dict:
    """Run a kubectl command and return the parsed JSON.

    Args are passed as a list rather than through a shell so that namespaces
    and label selectors containing shell metacharacters cannot break or
    escape the command.
    """
    out = subprocess.check_output(["kubectl", *args], text=True)
    return json.loads(out)


def deep_get(d, keys: list, default=None):
    """Safely traverse a nested dictionary or list using a list of keys."""
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        elif isinstance(d, list) and isinstance(k, int) and -len(d) <= k < len(d):
            d = d[k]
        else:
            return default
    return d


def substitute_vars(text, env_map: dict):
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


def is_model_server(workload: dict) -> bool:
    """Report whether a workload runs a vLLM model server.

    Deliberately excludes the endpoint picker (EPP) and other router
    components, which are captured separately.
    """
    meta = workload.get("metadata", {})
    name = meta.get("name", "").lower()
    if name.endswith("-epp") or "-epp-" in name:
        return False

    labels = deep_get(workload, ["spec", "template", "metadata", "labels"], {}) or {}
    if labels.get(ENGINE_LABEL) == "vllm":
        return True

    containers = deep_get(workload, ["spec", "template", "spec", "containers"], []) or []
    if any("vllm" in c.get("image", "").lower() for c in containers):
        return True
    return "vllm" in name or labels.get("app") == "vllm"


def pick_model_server_container(containers: list) -> dict:
    """Return the container running vLLM from a pod template."""
    for c in containers:
        if "vllm" in c.get("image", "").lower():
            return c
    for c in containers:
        name = c.get("name", "").lower()
        if "vllm" in name or "modelserver" in name or "inference" in name:
            return c
    return containers[0] if containers else {}


def build_env_map(container: dict, configmaps: dict) -> dict:
    """Resolve the container environment from envFrom and env entries.

    Values sourced from the downward API or a Secret are recorded as an
    opaque marker rather than a value, so the capture never contains a secret
    and never claims to know a value that is only assigned at runtime.
    """
    env_map = {}
    for ef in container.get("envFrom", []):
        name = deep_get(ef, ["configMapRef", "name"])
        if name in configmaps:
            env_map.update(configmaps[name])

    for e in container.get("env", []):
        name = e.get("name")
        if "value" in e:
            env_map[name] = e["value"]
            continue
        value_from = e.get("valueFrom", {})
        if "configMapKeyRef" in value_from:
            ref = value_from["configMapKeyRef"]
            if ref.get("name") in configmaps:
                env_map[name] = configmaps[ref["name"]].get(ref.get("key"), "")
        elif "fieldRef" in value_from:
            path = deep_get(value_from, ["fieldRef", "fieldPath"], "")
            env_map[name] = f"<fieldRef:{path}>"
        elif "secretKeyRef" in value_from:
            ref = value_from["secretKeyRef"]
            env_map[name] = f"<secretKeyRef:{ref.get('name')}/{ref.get('key')}>"
        elif "resourceFieldRef" in value_from:
            res = deep_get(value_from, ["resourceFieldRef", "resource"], "")
            env_map[name] = f"<resourceFieldRef:{res}>"
    return env_map


def parse_kv_transfer(args: list) -> dict:
    """Extract and parse the vLLM --kv-transfer-config value.

    The flag appears either as ``--kv-transfer-config=<json>`` or as two
    separate argv entries. Both forms are handled.
    """
    raw = None
    for i, a in enumerate(args):
        if not isinstance(a, str):
            continue
        if a.startswith("--kv-transfer-config="):
            raw = a.split("=", 1)[1]
            break
        if a == "--kv-transfer-config" and i + 1 < len(args):
            raw = args[i + 1]
            break

    if raw is None:
        return {"enabled": False}

    parsed = None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        pass

    extra = (parsed or {}).get("kv_connector_extra_config", {}) or {}
    return {
        "enabled": True,
        "kv_connector": (parsed or {}).get("kv_connector"),
        "kv_role": (parsed or {}).get("kv_role"),
        "kv_connector_module_path": (parsed or {}).get("kv_connector_module_path"),
        "cpu_offload_buffer_bytes": extra.get("cpu_bytes_to_use"),
        "offloading": "OffloadingConnector" in str(raw),
        "raw": raw if parsed is None else None,
    }


def parse_vllm_args(args: list) -> dict:
    """Parse resolved vLLM CLI args into a ``name -> value`` mapping.

    Flags arrive as ``--flag=value``, as ``--flag value``, or as bare booleans.
    Names are normalized to snake_case so that ``--max-model-len`` is reachable
    as ``max_model_len``. ``--kv-transfer-config`` is dropped because
    :func:`parse_kv_transfer` already exposes it in structured form.
    """
    parsed = {}
    i = 0
    while i < len(args):
        arg = args[i]
        i += 1
        if not isinstance(arg, str) or not arg.startswith("--"):
            continue
        if "=" in arg:
            flag, value = arg[2:].split("=", 1)
        else:
            flag = arg[2:]
            following = args[i] if i < len(args) else None
            if isinstance(following, str) and not following.startswith("--"):
                value = following
                i += 1
            else:
                value = True
        parsed[flag.replace("-", "_")] = value

    parsed.pop("kv_transfer_config", None)
    return parsed


def tuning_env(env_map: dict) -> dict:
    """Return the environment variables that change serving behaviour.

    The engine reads a number of settings from the environment rather than the
    command line, for example ``VLLM_HTTP_TIMEOUT_KEEP_ALIVE`` and the TPU KV
    transfer ports, so they belong alongside the parsed CLI parameters.
    """
    return {
        k: v
        for k, v in env_map.items()
        if k.startswith(("VLLM_", "TPU_", "JAX_", "LIBTPU_", "PJRT_"))
    }


def collect_sidecars(pod_spec: dict, model_server_name: str) -> list:
    """Return the sidecars running alongside the model server.

    Native sidecars are initContainers with ``restartPolicy: Always``; the
    disaggregation guides use one for the routing proxy on the decode pod.
    """
    sidecars = []
    for c in pod_spec.get("initContainers", []) or []:
        sidecars.append(
            {
                "name": c.get("name"),
                "image": c.get("image"),
                "args": c.get("args", []),
                "type": (
                    "native-sidecar"
                    if c.get("restartPolicy") == "Always"
                    else "init-container"
                ),
            }
        )
    for c in pod_spec.get("containers", []) or []:
        if c.get("name") == model_server_name:
            continue
        sidecars.append(
            {
                "name": c.get("name"),
                "image": c.get("image"),
                "args": c.get("args", []),
                "type": "sidecar",
            }
        )
    return sidecars


def accelerator_from_node(node: dict) -> dict:
    """Derive accelerator facts from a node's labels."""
    labels = deep_get(node, ["metadata", "labels"], {}) or {}
    tpu = labels.get(TPU_NODE_LABEL)
    gpu = labels.get(GPU_NODE_LABEL)
    return {
        "accelerator_type": tpu or gpu,
        "accelerator_topology": labels.get(TPU_TOPOLOGY_LABEL),
        "compute_class": labels.get(COMPUTE_CLASS_LABEL),
        "machine_type": labels.get("node.kubernetes.io/instance-type"),
        "platform": "tpu" if tpu else ("gpu" if gpu else None),
    }


def accelerator_from_compute_class(name) -> dict:
    """Derive accelerator facts from the ComputeClass the pod targets.

    Every llm-d overlay selects hardware with a
    ``cloud.google.com/compute-class`` nodeSelector rather than a raw
    accelerator label, so the ComputeClass is always resolvable -- even before
    any pod has been scheduled, and even where reading Node objects is not
    permitted. Its highest-priority rule declares the same ``type`` and
    ``topology`` strings that GKE later stamps onto the node labels.
    """
    if not name:
        return {}
    try:
        cc = run_kubectl(["get", "computeclass", name, "-o", "json"])
    except (subprocess.CalledProcessError, ValueError):
        return {}

    priority = deep_get(cc, ["spec", "priorities", 0], {}) or {}
    tpu = priority.get("tpu") or {}
    gpu = priority.get("gpu") or {}
    return {
        "accelerator_type": tpu.get("type") or gpu.get("type"),
        "accelerator_topology": tpu.get("topology"),
        "accelerator_count": tpu.get("count") or gpu.get("count"),
        "machine_type": priority.get("machineType"),
        "platform": "tpu" if tpu else ("gpu" if gpu else None),
    }


def merge_accelerator_facts(observed: dict, declared: dict) -> dict:
    """Prefer facts observed on the node, falling back to the ComputeClass."""
    keys = (
        "accelerator_type",
        "accelerator_topology",
        "accelerator_count",
        "machine_type",
        "platform",
        "compute_class",
    )
    merged = {k: observed.get(k) or declared.get(k) for k in keys}
    merged["source"] = "node" if observed.get("accelerator_type") else (
        "computeclass" if declared.get("accelerator_type") else "unknown"
    )
    return merged


def accelerator_count(container: dict) -> tuple:
    """Return the (count, platform) of accelerators requested by a container."""
    limits = deep_get(container, ["resources", "limits"], {}) or {}
    if GPU_RESOURCE in limits:
        return str(limits[GPU_RESOURCE]), "gpu"
    for res in TPU_RESOURCES:
        if res in limits:
            return str(limits[res]), "tpu"
    return None, None


def get_live_pods(namespace: str, workload: dict) -> list:
    """Return the live pods backing a workload, with the images they run.

    ``imageID`` is the digest actually pulled onto the node, which is what
    makes a benchmark reproducible; the workload spec only records the tag.
    """
    match_labels = deep_get(workload, ["spec", "selector", "matchLabels"], {}) or {}
    if not match_labels:
        return []

    selector = ",".join(f"{k}={v}" for k, v in match_labels.items())
    try:
        pods = run_kubectl(
            ["get", "pods", "-n", namespace, "-l", selector, "-o", "json"]
        ).get("items", [])
    except (subprocess.CalledProcessError, ValueError):
        return []

    live = []
    for p in pods:
        statuses = deep_get(p, ["status", "containerStatuses"], []) or []
        live.append(
            {
                "name": deep_get(p, ["metadata", "name"]),
                "node": deep_get(p, ["spec", "nodeName"]),
                "phase": deep_get(p, ["status", "phase"]),
                "pod_ip": deep_get(p, ["status", "podIP"]),
                "start_time": deep_get(p, ["status", "startTime"]),
                "containers": [
                    {
                        "name": s.get("name"),
                        "image": s.get("image"),
                        "image_id": s.get("imageID"),
                        "ready": s.get("ready"),
                        "restart_count": s.get("restartCount"),
                        "state": next(iter(s.get("state", {})), None),
                    }
                    for s in statuses
                ],
            }
        )
    return live


def get_node(name) -> dict:
    """Fetch a node object, returning an empty dict on failure."""
    if not name:
        return {}
    try:
        return run_kubectl(["get", "node", name, "-o", "json"])
    except (subprocess.CalledProcessError, ValueError):
        return {}


def scaling_state(workload: dict, hpa_list: list) -> dict:
    """Return replicas and HPA target state for a workload."""
    name = deep_get(workload, ["metadata", "name"], "")
    hpa_info = next(
        (
            {
                "name": deep_get(h, ["metadata", "name"]),
                "min_replicas": deep_get(h, ["spec", "minReplicas"]),
                "max_replicas": deep_get(h, ["spec", "maxReplicas"]),
                "current_replicas": deep_get(h, ["status", "currentReplicas"], 0),
            }
            for h in hpa_list
            if deep_get(h, ["spec", "scaleTargetRef", "name"]) == name
        ),
        None,
    )
    return {
        "configured_replicas": deep_get(workload, ["spec", "replicas"], 1),
        "ready_replicas": deep_get(workload, ["status", "readyReplicas"], 0),
        "hpa_enabled": hpa_info is not None,
        "hpa_info": hpa_info,
    }


def describe_model_server(
    namespace: str, workload: dict, configmaps: dict, hpa_list: list
) -> dict:
    """Build the full record for a single vLLM model server workload."""
    pod_spec = deep_get(workload, ["spec", "template", "spec"], {}) or {}
    pod_labels = (
        deep_get(workload, ["spec", "template", "metadata", "labels"], {}) or {}
    )
    container = pick_model_server_container(pod_spec.get("containers", []) or [])

    env_map = build_env_map(container, configmaps)
    args = [substitute_vars(a, env_map) for a in container.get("args", [])]
    command = [substitute_vars(c, env_map) for c in container.get("command", [])]

    count, platform = accelerator_count(container)
    live_pods = get_live_pods(namespace, workload)
    node_selector = pod_spec.get("nodeSelector", {}) or {}

    observed = accelerator_from_node(
        get_node(live_pods[0]["node"] if live_pods else None)
    )
    compute_class = node_selector.get(COMPUTE_CLASS_LABEL) or observed.get(
        "compute_class"
    )
    accel = merge_accelerator_facts(
        observed, accelerator_from_compute_class(compute_class)
    )

    role = pod_labels.get(ROLE_LABEL)
    if not role:
        name = deep_get(workload, ["metadata", "name"], "").lower()
        role = next((r for r in ("prefill", "decode") if r in name), "monolithic")

    return {
        "role": role,
        "workload_name": deep_get(workload, ["metadata", "name"]),
        "workload_kind": workload.get("kind"),
        "container_name": container.get("name"),
        "image": container.get("image"),
        "guide_label": pod_labels.get(GUIDE_LABEL),
        "model": (
            env_map.get("MODEL_ID")
            or env_map.get("MODEL_NAME")
            or pod_labels.get("llm-d.ai/model")
            or pod_labels.get("ai.gke.io/model")
        ),
        "accelerator": {
            # The container resource limit is the count actually granted to
            # this pod; the ComputeClass count is the slice size.
            "count": count or accel.get("accelerator_count"),
            "platform": platform or accel.get("platform"),
            "type": accel.get("accelerator_type"),
            "topology": accel.get("accelerator_topology"),
            "machine_type": accel.get("machine_type"),
            "compute_class": compute_class or "default-nap",
            "source": accel.get("source"),
        },
        # The engine tuning knobs (max_model_len, tensor_parallel_size, dtype,
        # kv_cache_dtype, ...) pulled out of the arg list and the environment.
        "serving_parameters": parse_vllm_args(args),
        "tuning_env": tuning_env(env_map),
        "kv_transfer": parse_kv_transfer(container.get("args", [])),
        "scaling_state": scaling_state(workload, hpa_list),
        "resolved_container_args": args,
        "resolved_container_command": command,
        "resolved_runtime_env": env_map,
        "sidecars": collect_sidecars(pod_spec, container.get("name")),
        "live_pods": live_pods,
        "workload": workload,
    }


def describe_router(workloads: list) -> dict:
    """Summarize the endpoint picker, which makes the routing decisions."""
    epp = next(
        (w for w in workloads if deep_get(w, ["metadata", "name"], "").endswith("-epp")),
        None,
    )
    if not epp:
        return {"epp_found": False}

    containers = deep_get(epp, ["spec", "template", "spec", "containers"], []) or []
    return {
        "epp_found": True,
        "name": deep_get(epp, ["metadata", "name"]),
        "configured_replicas": deep_get(epp, ["spec", "replicas"], 1),
        "ready_replicas": deep_get(epp, ["status", "readyReplicas"], 0),
        "containers": [
            {"name": c.get("name"), "image": c.get("image"), "args": c.get("args", [])}
            for c in containers
        ],
    }


def summarize_architecture(servers: list, spec_name: str) -> dict:
    """Roll the per-server facts up into a single architecture summary."""
    primary = servers[0]
    roles = sorted({s["role"] for s in servers})
    platform = next(
        (s["accelerator"]["platform"] for s in servers if s["accelerator"]["platform"]),
        None,
    )
    kv = primary["kv_transfer"]
    pattern = "online-inference-{}/{}".format(
        platform or "unknown",
        f"llmd-{spec_name}" if spec_name else "standard",
    )

    return {
        "reference_architecture_manifest_pattern": pattern,
        "platform": platform or "unknown",
        "disaggregated": {"prefill", "decode"}.issubset(set(roles)),
        "roles": roles,
        "model_server_count": len(servers),
        "model": primary["model"] or "unknown",
        "compute_class": primary["accelerator"]["compute_class"],
        "accelerator_type": primary["accelerator"]["type"] or "unknown-accelerator",
        "accelerator_topology": primary["accelerator"]["topology"],
        "accelerator_count": primary["accelerator"]["count"],
        "kv_connector": kv.get("kv_connector"),
        "kv_transfer_enabled": kv.get("enabled", False),
        "kv_offloading_enabled": kv.get("offloading", False),
        "cpu_offload_buffer_bytes": kv.get("cpu_offload_buffer_bytes"),
    }


def summarize_text(result: dict) -> str:
    """Render a short human-readable summary of a capture."""
    if "error" in result:
        return f"vllm-config: FAILED ({result['error_type']}): {result['error']}"

    arch = result["detected_architecture"]
    lines = [
        "vllm-config: guide={} namespace={}".format(
            result["well_lit_path_guide"] or "-", result["namespace"]
        ),
        "  model={} platform={} accel={} topology={} count={} ({})".format(
            arch["model"],
            arch["platform"],
            arch["accelerator_type"],
            arch["accelerator_topology"] or "-",
            arch["accelerator_count"] or "-",
            arch["compute_class"],
        ),
        "  disaggregated={} servers={} kv_connector={}".format(
            arch["disaggregated"],
            arch["model_server_count"],
            arch["kv_connector"] or "-",
        ),
    ]
    for s in result["model_servers"]:
        scale = s["scaling_state"]
        lines.append(
            "  [{}] {} {}/{} ready | kv_role={} | image={}".format(
                s["role"],
                s["workload_name"],
                scale["ready_replicas"],
                scale["configured_replicas"],
                s["kv_transfer"].get("kv_role") or "-",
                s["image"],
            )
        )
        params = s["serving_parameters"]
        headline = [
            f"{name}={params[name]}"
            for name in HEADLINE_PARAMETERS
            if name in params
        ]
        if headline:
            lines.append("      " + " ".join(headline))
        for name, value in sorted(s["tuning_env"].items()):
            lines.append(f"      env {name}={value}")
        for sc in s["sidecars"]:
            lines.append(f"      + {sc['type']}: {sc['name']} ({sc['image']})")

    router = result["router"]
    if router.get("epp_found"):
        lines.append(
            "  [router] {} {}/{} ready".format(
                router["name"], router["ready_replicas"], router["configured_replicas"]
            )
        )
    return "\n".join(lines)


def capture_vllm_config(
    namespace: str, spec_name: str, output_path: str, include_raw: bool = False
) -> dict:
    """Retrieve the live serving state and write vllm_config.json."""
    try:
        items = run_kubectl(
            [
                "get",
                "deployments,statefulsets,configmaps,hpa",
                "-n",
                namespace,
                "-o",
                "json",
            ]
        ).get("items", [])

        configmaps = {
            i["metadata"]["name"]: i.get("data", {})
            for i in items
            if i.get("kind") == "ConfigMap"
        }
        hpa_list = [i for i in items if i.get("kind") == "HorizontalPodAutoscaler"]
        workloads = [i for i in items if i.get("kind") in ("Deployment", "StatefulSet")]

        candidates = [w for w in workloads if is_model_server(w)]
        if not candidates:
            raise ValueError(
                f"No vLLM Deployment/StatefulSet found in namespace {namespace}"
            )

        servers = [
            describe_model_server(namespace, w, configmaps, hpa_list)
            for w in candidates
        ]
        # Order deterministically, and make decode primary for disaggregated
        # topologies since it owns the request lifecycle end to end.
        rank = {"decode": 0, "monolithic": 0, "prefill": 1}
        servers.sort(key=lambda s: (rank.get(s["role"], 2), s["workload_name"]))
        primary_workload = servers[0]["workload"]

        result = {
            "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "namespace": namespace,
            "well_lit_path_guide": spec_name,
            "detected_architecture": summarize_architecture(servers, spec_name),
            "model_servers": servers,
            "router": describe_router(workloads),
            # Legacy single-server keys, mirroring the primary model server.
            "scaling_state": servers[0]["scaling_state"],
            "resolved_runtime_env": servers[0]["resolved_runtime_env"],
            "resolved_container_args": servers[0]["resolved_container_args"],
            "resolved_container_command": servers[0]["resolved_container_command"],
        }

        # The raw manifests trebled the file size and are rarely read, so they
        # are opt-in. Everything derived from them is already summarized above.
        if include_raw:
            result["deployment"] = primary_workload
        else:
            for s in servers:
                s.pop("workload", None)
    except Exception as exc:  # noqa: BLE001 - capture must never fail a benchmark
        result = {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "well_lit_path_guide": spec_name,
            "namespace": namespace,
        }

    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(result, fp, indent=2)
    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Capture the live vLLM serving configuration, including every "
            "model server in a disaggregated topology."
        )
    )
    parser.add_argument("--namespace", required=True, help="K8s namespace")
    parser.add_argument("--spec", default="", help="Well-lit path guide name")
    parser.add_argument(
        "--output", default="./vllm_config.json", help="Output JSON path"
    )
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Embed the raw Deployment manifest (roughly triples the file size)",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress the summary")
    args = parser.parse_args()

    result = capture_vllm_config(
        args.namespace, args.spec, args.output, args.include_raw
    )
    if not args.quiet:
        print(summarize_text(result))


if __name__ == "__main__":
    main()
