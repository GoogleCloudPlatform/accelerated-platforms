#!/usr/bin/env python3
"""
Python conversion script for Qwen3-14B base checkpoint conversion using MaxText 0.2.3.
"""
import os
import sys
import subprocess
from maxtext.utils.globals import MAXTEXT_PKG_DIR

def convert_qwen3_14b(output_directory: str, hf_token: str):
    base_config = os.path.join(MAXTEXT_PKG_DIR, "configs", "base.yml")
    cmd = [
        sys.executable,
        "-m",
        "maxtext.checkpoint_conversion.to_maxtext",
        base_config,
        "model_name=qwen3-14b",
        f"hf_access_token={hf_token}",
        f"base_output_directory={output_directory}",
        "scan_layers=True",
        "use_multimodal=False",
        "skip_jax_distributed_system=True",
        "checkpoint_storage_use_zarr3=0",
        "checkpoint_storage_use_ocdbt=0",
        "hardware=cpu",
    ]
    env = os.environ.copy()
    env["JAX_PLATFORMS"] = "cpu"
    print(f"Executing conversion: {' '.join(cmd)}")
    subprocess.run(cmd, env=env, check=True)

if __name__ == "__main__":
    out_dir = os.getenv("BASE_OUTPUT_DIRECTORY", "gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models/qwen3_14b_fresh_v023/")
    token = os.getenv("HF_TOKEN", "")
    convert_qwen3_14b(out_dir, token)
