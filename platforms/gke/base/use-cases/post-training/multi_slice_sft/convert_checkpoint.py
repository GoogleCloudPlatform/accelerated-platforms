# Copyright 2026 Google LLC
# MaxText v0.2.3 Checkpoint Conversion Script for Qwen/Qwen3-14B Base Model

import os
import sys
from maxtext.checkpoint_conversion import to_maxtext
from maxtext.utils.globals import MAXTEXT_PKG_DIR

if __name__ == "__main__":
    print("Executing MaxText v0.2.3 Checkpoint Conversion for Qwen/Qwen3-14B...", flush=True)

    config_path = f"{MAXTEXT_PKG_DIR}/configs/models/qwen3-14b.yml"
    hf_token = os.environ.get("HF_TOKEN")
    output_dir = os.environ.get(
        "BASE_OUTPUT_DIRECTORY",
        "gs://accelerated-platforms-dev-rl-kr-single-hf-hub-models/qwen3_14b_fresh_v023/"
    )

    args = [
        "",
        config_path,
        "model_name=qwen3-14b",
        f"hf_access_token={hf_token}",
        "hf_model_path=Qwen/Qwen3-14B",
        f"base_output_directory={output_dir}",
        "scan_layers=True",
        "use_multimodal=False",
        "skip_jax_distributed_system=True",
        "checkpoint_storage_use_zarr3=0",
        "checkpoint_storage_use_ocdbt=0",
        "hardware=tpu",
        "lazy_load_tensors=True",
    ]

    sys.argv = args
    to_maxtext.main(sys.argv)
    print("Qwen/Qwen3-14B Conversion Completed Successfully!", flush=True)
