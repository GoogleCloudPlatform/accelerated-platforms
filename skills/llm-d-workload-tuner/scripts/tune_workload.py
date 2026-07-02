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

import argparse
import json
import os
import sys

import yaml

# Define hardware capacities (in GB)
ACCELERATOR_CAPACITIES = {
    "rtx-pro-6000": 48.0,
    "nvidia-h100": 80.0,
    "h100": 80.0,
    "nvidia-h200": 141.0,
    "h200": 141.0,
    "v6e": 32.0,  # 32GB HBM per chip
}

# Sizing calculation constants
MEM_OVERHEAD_MULTIPLIER = 1.2
BYTES_PER_PARAM_BF16 = 2.0
BYTES_PER_PARAM_FP8 = 1.0
BYTES_PER_ELEMENT_BF16 = 2


def get_nested(d, keys):
    for k in keys:
        if not isinstance(d, dict) and not isinstance(d, list):
            return None
        try:
            d = d[k]
        except (KeyError, IndexError, TypeError):
            return None
    return d


def set_nested(d, keys, value):
    for k in keys[:-1]:
        if isinstance(d, dict):
            d = d.setdefault(k, {})
        elif isinstance(d, list) and isinstance(k, int) and k < len(d):
            d = d[k]
        else:
            return False
    try:
        d[keys[-1]] = value
        return True
    except (KeyError, IndexError, TypeError):
        return False


# Define model specifications
MODEL_SPECS = {
    "google/gemma-4-31b-it": {
        "parameters": 32.0,  # in Billions
        "layers": 48,
        "kv_heads": 8,
        "head_dim": 256,
        "suffix": "gemma-4-31b-it",
    },
    "qwen/qwen3-32b": {
        "parameters": 32.5,
        "layers": 64,
        "kv_heads": 8,
        "head_dim": 128,
        "suffix": "qwen3-32b",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="LLM-D Workload Configuration Tuner")
    parser.add_argument(
        "--config", required=False, help="Path to config.json workload specifications"
    )
    parser.add_argument(
        "--perf-yaml",
        required=True,
        help="Path to inference-perf.yaml benchmark stages or full workload profile YAML",
    )
    parser.add_argument(
        "--accelerator-type",
        required=True,
        help="Accelerator type (e.g. rtx-pro-6000, nvidia-h100, nvidia-h200, v6e)",
    )
    parser.add_argument(
        "--strategy",
        default="precise-prefix-cache-routing",
        help="Routing strategy directory name (e.g., optimized-baseline, precise-prefix-cache-routing, predicted-latency-routing)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name override (e.g. google/gemma-4-31b-it)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates directly to the kustomize overlay files",
    )
    parser.add_argument(
        "--chunked-prefill-threshold",
        type=int,
        default=8000,
        help="Token threshold above which chunked prefill is enabled (default: 8000)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.config and not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.perf_yaml):
        print(f"Error: Perf YAML file not found: {args.perf_yaml}", file=sys.stderr)
        sys.exit(1)

    # 1. Parse Workload Specifications
    with open(args.perf_yaml, "r") as f:
        perf_data = yaml.safe_load(f)

    if args.config:
        with open(args.config, "r") as f:
            config_data = json.load(f)
        max_output_len = config_data.get("output_sequence_length", {}).get("max", 2048)
    else:
        # Try to parse from perf-yaml (assuming it's a full workload profile)
        max_output_len = (
            perf_data.get("data", {}).get("output_distribution", {}).get("max", 2048)
        )

    # Get max concurrency level from stages
    max_concurrency = 1
    for stage in perf_data.get("stages", []):
        concurrency = stage.get("concurrency_level", 1)
        if concurrency > max_concurrency:
            max_concurrency = concurrency

    # Get target model from perf-yaml or override
    model_id = args.model or perf_data.get("server", {}).get(
        "model_name", "google/gemma-4-31b-it"
    )

    # 2. Get Model and Accelerator Specifications
    model_spec = MODEL_SPECS.get(model_id)
    if not model_spec:
        # Fallback default
        model_spec = MODEL_SPECS["google/gemma-4-31b-it"]
        print(
            f"Warning: Model {model_id} specifications not registered. Using default Gemma-4-31B specs."
        )

    vram_capacity_gb = ACCELERATOR_CAPACITIES.get(args.accelerator_type.lower())
    if not vram_capacity_gb:
        print(
            f"Error: Unsupported accelerator type: {args.accelerator_type}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 3. Solves Sizing Equations
    # Model Weights Size in GB
    weights_size_gb = (
        model_spec["parameters"] * BYTES_PER_PARAM_BF16
    ) * MEM_OVERHEAD_MULTIPLIER  # Including overhead margins

    # Cache per token (in bytes)
    # Cache = 2 * Layers * KV_Heads * Head_Dim * 2 bytes (BF16)
    bytes_per_token = (
        2
        * model_spec["layers"]
        * model_spec["kv_heads"]
        * model_spec["head_dim"]
        * BYTES_PER_ELEMENT_BF16
    )

    # Cache needed for peak concurrency workload (in GB)
    cache_size_gb = (max_concurrency * max_output_len * bytes_per_token) / (1024**3)

    print("=== Workload Analysis ===")
    print(f"Target Model: {model_id}")
    print(f"Max Concurrency: {max_concurrency}")
    print(f"Max Output Length: {max_output_len} tokens")
    print(f"Estimated Weights Size: {weights_size_gb:.2f} GB")
    print(f"Estimated Cache Size Needed: {cache_size_gb:.2f} GB")

    # Solve for TP
    tp_size = 1
    quantization = "null"
    total_required_gb = weights_size_gb + cache_size_gb

    while tp_size * vram_capacity_gb < total_required_gb:
        if tp_size < 8:
            tp_size *= 2
        else:
            print(
                "\n[Error] Workload exceeds capacity limits even with max TP size of 8.",
                file=sys.stderr,
            )
            sys.exit(1)

    print("\n=== Sizing Recommendation ===")
    print(f"Recommended TENSOR_PARALLEL_SIZE: {tp_size}")
    print(f"Quantization: {quantization}")

    # Calculate Max Model Len (Upper limit safe bounds)
    # Max model len can fit within remaining VRAM
    available_cache_gb = (tp_size * vram_capacity_gb) - weights_size_gb
    max_safe_len = int(
        (available_cache_gb * (1024**3)) / (max_concurrency * bytes_per_token)
    )
    # Cap to model limits
    max_safe_len = min(max_safe_len, 32768)

    # Ensure it's at least greater than output tokens
    max_safe_len = max(max_safe_len, max_output_len + 1024)
    print(f"Calculated MAX_MODEL_LEN Limit: {max_safe_len}")

    # Determine Chunked Prefill setting (Recommended for context volumes)
    enable_chunked_prefill = "False"
    if max_output_len > args.chunked_prefill_threshold:
        enable_chunked_prefill = "True"

    # 4. Resolve Target Overlay Path
    platform_prefix = "tpu" if args.accelerator_type.lower() == "v6e" else "gpu"
    model_suffix = model_spec["suffix"]
    accel_dir = (
        f"v6e-{model_suffix}"
        if platform_prefix == "tpu"
        else f"{args.accelerator_type.lower()}-{model_suffix}"
    )

    overlay_path = f"platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-{platform_prefix}/llmd-{args.strategy}/vllm/{accel_dir}"

    if not os.path.isdir(overlay_path):
        print(
            f"Warning: Target overlay directory not found: {overlay_path}. Cannot compare configurations.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n=== Configuration Gap Analysis ===")

    # A. Analyze runtime.env
    env_file = os.path.join(overlay_path, "runtime.env")
    old_tp = "unknown"
    old_mml = "unknown"
    old_quant = "unknown"
    old_extra = "unknown"
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            lines = f.readlines()
        for line in lines:
            if line.startswith("TENSOR_PARALLEL_SIZE="):
                old_tp = line.split("=")[1].strip()
            elif line.startswith("MAX_MODEL_LEN="):
                old_mml = line.split("=")[1].strip()
            elif line.startswith("QUANTIZATION="):
                old_quant = line.split("=")[1].strip()
            elif line.startswith("EXTRA_ARGS="):
                old_extra = line.split("=")[1].strip()

    # B. Analyze patch-resources.yaml
    resource_file = os.path.join(overlay_path, "patch-resources.yaml")
    old_resources_limit = "unknown"
    if os.path.exists(resource_file):
        with open(resource_file, "r") as f:
            res_data = yaml.safe_load(f)
        limit_key = "nvidia.com/gpu" if platform_prefix == "gpu" else "google.com/tpu"
        val = get_nested(
            res_data,
            [
                "spec",
                "template",
                "spec",
                "containers",
                0,
                "resources",
                "limits",
                limit_key,
            ],
        )
        if val is not None:
            old_resources_limit = val

    # C. Analyze patch-nodeselector.yaml
    nodeselector_file = os.path.join(overlay_path, "patch-nodeselector.yaml")
    old_node_selector_val = "unknown"
    if os.path.exists(nodeselector_file):
        with open(nodeselector_file, "r") as f:
            node_data = yaml.safe_load(f)
        selector_key = (
            "cloud.google.com/gke-gpu-count"
            if platform_prefix == "gpu"
            else "cloud.google.com/compute-class"
        )
        val = get_nested(
            node_data, ["spec", "template", "spec", "nodeSelector", selector_key]
        )
        if val is not None:
            old_node_selector_val = val

    # Print analysis details
    print(f"runtime.env:")
    print(f"  * TENSOR_PARALLEL_SIZE: current={old_tp}, required={tp_size}")
    print(f"  * MAX_MODEL_LEN: current={old_mml}, required={max_safe_len}")
    print(f"  * QUANTIZATION: current={old_quant}, required={quantization}")
    recommended_extra = f"--enable-chunked-prefill={enable_chunked_prefill}"
    print(f'  * EXTRA_ARGS: current={old_extra}, required="{recommended_extra}"')

    print(f"\npatch-resources.yaml:")
    print(f"  * resource limits: current={old_resources_limit}, required={tp_size}")

    print(f"\npatch-nodeselector.yaml:")
    tpu_class = (
        "tpu-v6e-2x2" if tp_size == 4 else ("tpu-v6e-2x4" if tp_size == 8 else None)
    )
    if platform_prefix == "gpu":
        print(
            f"  * cloud.google.com/gke-gpu-count: current={old_node_selector_val}, required={tp_size}"
        )
    elif platform_prefix == "tpu":
        print(
            f"  * cloud.google.com/compute-class: current={old_node_selector_val}, required={tpu_class}"
        )

    # Propose update status
    needs_update = False
    if (
        str(old_tp) != str(tp_size)
        or str(old_mml) != str(max_safe_len)
        or str(old_quant) != str(quantization)
        or str(old_extra) != f'"{recommended_extra}"'
    ):
        needs_update = True
    if str(old_resources_limit) != str(tp_size):
        needs_update = True
    if platform_prefix == "gpu" and str(old_node_selector_val) != str(tp_size):
        needs_update = True
    elif platform_prefix == "tpu" and str(old_node_selector_val) != str(tpu_class):
        needs_update = True

    if needs_update:
        print("\n[Status] Gaps identified. Updates are proposed above.")
        if not args.apply:
            print(
                "Run with --apply to apply these changes directly to the overlay manifests."
            )
    else:
        print("\n[Status] No gaps identified. The target files are already optimized.")

    # 5. Apply Updates (Writes files only if --apply is set)
    if args.apply and needs_update:
        print("\n=== Applying Proposed Updates ===")
        # A. Write runtime.env
        if os.path.exists(env_file):
            new_lines = []
            for line in lines:
                if line.startswith("TENSOR_PARALLEL_SIZE="):
                    new_lines.append(f"TENSOR_PARALLEL_SIZE={tp_size}\n")
                elif line.startswith("MAX_MODEL_LEN="):
                    new_lines.append(f"MAX_MODEL_LEN={max_safe_len}\n")
                elif line.startswith("QUANTIZATION="):
                    new_lines.append(f"QUANTIZATION={quantization}\n")
                elif line.startswith("EXTRA_ARGS="):
                    new_lines.append(f'EXTRA_ARGS="{recommended_extra}"\n')
                else:
                    new_lines.append(line)
            with open(env_file, "w") as f:
                f.writelines(new_lines)
            print(f"Updated runtime environment variables in {env_file}")

        # B. Write patch-resources.yaml
        if os.path.exists(resource_file):
            try:
                with open(resource_file, "r") as f:
                    res_data = yaml.safe_load(f)
                limit_key = (
                    "nvidia.com/gpu" if platform_prefix == "gpu" else "google.com/tpu"
                )
                set_nested(
                    res_data,
                    [
                        "spec",
                        "template",
                        "spec",
                        "containers",
                        0,
                        "resources",
                        "limits",
                        limit_key,
                    ],
                    str(tp_size),
                )

                req_path = [
                    "spec",
                    "template",
                    "spec",
                    "containers",
                    0,
                    "resources",
                    "requests",
                    limit_key,
                ]
                if get_nested(res_data, req_path) is not None:
                    set_nested(res_data, req_path, str(tp_size))

                with open(resource_file, "w") as f:
                    yaml.dump(res_data, f, default_flow_style=False)
                print(f"Updated resource limits in {resource_file} to {tp_size}")
            except Exception as e:
                print(f"Error: Failed to write to {resource_file}: {e}")

        # C. Write patch-nodeselector.yaml
        if os.path.exists(nodeselector_file):
            try:
                with open(nodeselector_file, "r") as f:
                    node_data = yaml.safe_load(f)
                selector_key = (
                    "cloud.google.com/gke-gpu-count"
                    if platform_prefix == "gpu"
                    else "cloud.google.com/compute-class"
                )
                selector_val = str(tp_size) if platform_prefix == "gpu" else tpu_class
                if selector_val:
                    set_nested(
                        node_data,
                        ["spec", "template", "spec", "nodeSelector", selector_key],
                        selector_val,
                    )
                with open(nodeselector_file, "w") as f:
                    yaml.dump(node_data, f, default_flow_style=False)
                print(f"Updated nodeSelector in {nodeselector_file}")
            except Exception as e:
                print(f"Error: Failed to write to {nodeselector_file}: {e}")

    if needs_update and not args.apply:
        sys.exit(2)


if __name__ == "__main__":
    main()
