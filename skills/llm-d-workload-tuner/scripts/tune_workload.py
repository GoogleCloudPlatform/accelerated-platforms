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
GPU_CAPACITIES = {
    "rtx-pro-6000": 48.0,
    "nvidia-h100": 80.0,
    "h100": 80.0,
    "v6e": 16.0  # Per-core capacity
}

# Define model specifications
MODEL_SPECS = {
    "google/gemma-4-31b-it": {
        "parameters": 32.0,  # in Billions
        "layers": 48,
        "kv_heads": 8,
        "head_dim": 256,
        "suffix": "gemma-4-31b-it"
    },
    "Qwen/Qwen3-32B-Instruct": {
        "parameters": 32.5,
        "layers": 64,
        "kv_heads": 8,
        "head_dim": 128,
        "suffix": "qwen3-32b"
    }
}

def parse_args():
    parser = argparse.ArgumentParser(description="LLM-D Workload Configuration Tuner")
    parser.add_argument("--config", required=True, help="Path to config.json workload specifications")
    parser.add_argument("--perf-yaml", required=True, help="Path to inference-perf.yaml benchmark stages")
    parser.add_argument("--gpu-type", required=True, help="Accelerator type (e.g. rtx-pro-6000, nvidia-h100, v6e)")
    parser.add_argument("--strategy", default="precise-prefix-cache-routing", help="Routing strategy directory sub-name")
    parser.add_argument("--apply", action="store_true", help="Apply updates directly to the kustomize overlay files")
    return parser.parse_args()

def main():
    args = parse_args()
    
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(args.perf_yaml):
        print(f"Error: Perf YAML file not found: {args.perf_yaml}", file=sys.stderr)
        sys.exit(1)
        
    # 1. Parse Workload Specifications
    with open(args.config, "r") as f:
        config_data = json.load(f)
        
    with open(args.perf_yaml, "r") as f:
        perf_data = yaml.safe_load(f)
        
    # Get max output sequence length
    max_output_len = config_data.get("output_sequence_length", {}).get("max", 2048)
    
    # Get max concurrency level from stages
    max_concurrency = 1
    for stage in perf_data.get("stages", []):
        concurrency = stage.get("concurrency_level", 1)
        if concurrency > max_concurrency:
            max_concurrency = concurrency
            
    # Get target model from perf-yaml
    model_id = perf_data.get("server", {}).get("model_name", "google/gemma-4-31b-it")
    
    # 2. Get Model and GPU Specifications
    model_spec = MODEL_SPECS.get(model_id)
    if not model_spec:
        # Fallback default
        model_spec = MODEL_SPECS["google/gemma-4-31b-it"]
        print(f"Warning: Model {model_id} specifications not registered. Using default Gemma-4-31B specs.")
        
    gpu_vram = GPU_CAPACITIES.get(args.gpu_type.lower())
    if not gpu_vram:
        print(f"Error: Unsupported GPU type: {args.gpu_type}", file=sys.stderr)
        sys.exit(1)
        
    # 3. Solves Sizing Equations
    # Model Weights Size in GB (BF16 = 2 bytes/param)
    weights_size_gb = (model_spec["parameters"] * 2.0) * 1.2 # Including overhead margins
    
    # Cache per token (in bytes)
    # Cache = 2 * Layers * KV_Heads * Head_Dim * 2 bytes (BF16)
    bytes_per_token = 2 * model_spec["layers"] * model_spec["kv_heads"] * model_spec["head_dim"] * 2
    
    # Cache needed for peak concurrency workload (in GB)
    cache_size_gb = (max_concurrency * max_output_len * bytes_per_token) / (1024 ** 3)
    
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
    
    # If 2 GPUs is not enough to fit weights + cache, fall back to FP8 quantization to stay within TP <= 3 limits
    if 2 * gpu_vram < total_required_gb:
        print("\n[Warning] Peak memory exceeds 3 GPUs. Falling back to FP8 Quantization...")
        quantization = "fp8"
        # Recalculate weights size (FP8 cuts weights size in half)
        weights_size_gb_quantized = (model_spec["parameters"] * 1.0) * 1.2
        total_required_gb = weights_size_gb_quantized + cache_size_gb
        
    while tp_size * gpu_vram < total_required_gb:
        if tp_size < 4:
            tp_size *= 2
        else:
            print("\n[Error] Workload exceeds capacity limits even with FP8 quantization.", file=sys.stderr)
            sys.exit(1)
            
    print("\n=== Sizing Recommendation ===")
    print(f"Recommended TENSOR_PARALLEL_SIZE: {tp_size}")
    print(f"Quantization: {quantization}")
    
    # Calculate Max Model Len (Upper limit safe bounds)
    # Max model len can fit within remaining VRAM
    available_cache_gb = (tp_size * gpu_vram) - (weights_size_gb if quantization == "null" else (model_spec["parameters"] * 1.0 * 1.2))
    max_safe_len = int((available_cache_gb * (1024 ** 3)) / (max_concurrency * bytes_per_token))
    # Cap to model limits
    max_safe_len = min(max_safe_len, 32768)
    
    # Ensure it's at least greater than output tokens
    max_safe_len = max(max_safe_len, max_output_len + 1024)
    print(f"Calculated MAX_MODEL_LEN Limit: {max_safe_len}")
    
    # Determine Chunked Prefill setting (Recommended for context volumes)
    enable_chunked_prefill = "False"
    if max_output_len > 8000:
        enable_chunked_prefill = "True"
        
    # 4. Apply Overlays
    if args.apply:
        platform_prefix = "tpu" if args.gpu_type.lower() == "v6e" else "gpu"
        model_suffix = model_spec["suffix"]
        accel_dir = f"v6e-{model_suffix}" if platform_prefix == "tpu" else f"{args.gpu_type.lower()}-{model_suffix}"
        
        overlay_path = f"platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-{platform_prefix}/llmd-{args.strategy}/vllm/{accel_dir}"
        
        if not os.path.isdir(overlay_path):
            print(f"Error: Target overlay directory not found: {overlay_path}", file=sys.stderr)
            sys.exit(1)
            
        # A. Update runtime.env
        env_file = os.path.join(overlay_path, "runtime.env")
        if os.path.exists(env_file):
            with open(env_file, "r") as f:
                lines = f.readlines()
            
            old_tp = "unknown"
            old_mml = "unknown"
            old_quant = "unknown"
            old_extra = "unknown"
            for line in lines:
                if line.startswith("TENSOR_PARALLEL_SIZE="):
                    old_tp = line.split("=")[1].strip()
                elif line.startswith("MAX_MODEL_LEN="):
                    old_mml = line.split("=")[1].strip()
                elif line.startswith("QUANTIZATION="):
                    old_quant = line.split("=")[1].strip()
                elif line.startswith("EXTRA_ARGS="):
                    old_extra = line.split("=")[1].strip()
            
            new_lines = []
            for line in lines:
                if line.startswith("TENSOR_PARALLEL_SIZE="):
                    new_lines.append(f"TENSOR_PARALLEL_SIZE={tp_size}\n")
                elif line.startswith("MAX_MODEL_LEN="):
                    new_lines.append(f"MAX_MODEL_LEN={max_safe_len}\n")
                elif line.startswith("QUANTIZATION="):
                    new_lines.append(f"QUANTIZATION={quantization}\n")
                elif line.startswith("EXTRA_ARGS="):
                    # Inject chunked prefill or custom parameters
                    extra_args = f"--enable-chunked-prefill={enable_chunked_prefill}"
                    new_lines.append(f"EXTRA_ARGS=\"{extra_args}\"\n")
                else:
                    new_lines.append(line)
            
            with open(env_file, "w") as f:
                f.writelines(new_lines)
            
            print("\n=== Parameter Tuning Diff ===")
            print(f"  - TENSOR_PARALLEL_SIZE: {old_tp} -> {tp_size}")
            print(f"  - MAX_MODEL_LEN: {old_mml} -> {max_safe_len}")
            print(f"  - QUANTIZATION: {old_quant} -> {quantization}")
            extra_args = f"--enable-chunked-prefill={enable_chunked_prefill}"
            print(f"  - EXTRA_ARGS: {old_extra} -> \"{extra_args}\"")
            print(f"Updated runtime environment variables in {env_file}")
            
        # B. Patch patch-resources.yaml (if GPU)
        resource_file = os.path.join(overlay_path, "patch-resources.yaml")
        if os.path.exists(resource_file) and platform_prefix == "gpu":
            with open(resource_file, "r") as f:
                res_data = yaml.safe_load(f)
            
            # Navigate path: spec.template.spec.containers[0].resources.limits["nvidia.com/gpu"]
            try:
                limits = res_data["spec"]["template"]["spec"]["containers"][0]["resources"]["limits"]
                limits["nvidia.com/gpu"] = str(tp_size)
                
                with open(resource_file, "w") as f:
                    yaml.dump(res_data, f, default_flow_style=False)
                print(f"Updated GPU limits in {resource_file} to {tp_size}")
            except (KeyError, TypeError) as e:
                print(f"Warning: Failed to parse and patch resources in {resource_file}: {e}")
                
        # C. Patch patch-nodeselector.yaml (if GPU)
        nodeselector_file = os.path.join(overlay_path, "patch-nodeselector.yaml")
        if os.path.exists(nodeselector_file) and platform_prefix == "gpu":
            with open(nodeselector_file, "r") as f:
                node_data = yaml.safe_load(f)
            
            try:
                # GKE Standard custom compute class count label matching tensor parallelism size
                nodeSelector = node_data["spec"]["template"]["spec"]["nodeSelector"]
                # Update node pool selectors or count constraint labels if necessary
                nodeSelector["cloud.google.com/gke-gpu-count"] = str(tp_size)
                
                with open(nodeselector_file, "w") as f:
                    yaml.dump(node_data, f, default_flow_style=False)
                print(f"Updated NodeSelector constraints in {nodeselector_file} to {tp_size}")
            except (KeyError, TypeError) as e:
                print(f"Warning: Failed to parse and patch node selectors in {nodeselector_file}: {e}")
                
if __name__ == "__main__":
    main()
