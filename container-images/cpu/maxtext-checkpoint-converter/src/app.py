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
import subprocess
import sys

# Try to import MaxText to check installation and get PKG DIR
try:
    from maxtext.utils.globals import MAXTEXT_PKG_DIR
except ImportError as e:
    print(
        f"❌ ERROR: MaxText is not installed correctly or not available in Python path: {e}",
        flush=True,
    )
    sys.exit(1)

# --- Configuration & Input Parsing ---
# 1. Base Parameters
COMMAND = os.environ.get("COMMAND", "to_maxtext")
MODEL_NAME = os.environ.get("MODEL_NAME", "llama3.1-8b-Instruct")
BASE_OUTPUT_DIRECTORY = os.environ.get("BASE_OUTPUT_DIRECTORY")
HF_TOKEN = os.environ.get("HF_TOKEN") or os.environ.get("HF_ACCESS_TOKEN")
HF_MODEL_PATH = os.environ.get("HF_MODEL_PATH") or os.environ.get("HF_IDS")

# Fallback: Load HF token from mounted file if not present in environment variables
if not HF_TOKEN:
    token_path = "/var/run/secrets/huggingface.co/token"
    if os.path.exists(token_path):
        try:
            with open(token_path, "r") as f:
                HF_TOKEN = f.read().strip()
            print(
                f"📖 Loaded Hugging Face token from mounted file: {token_path}",
                flush=True,
            )
        except Exception as e:
            print(
                f"⚠️ Warning: Could not read mounted token from {token_path}: {e}",
                flush=True,
            )


# 2. Advanced Flags (Boolean settings with string fallback)
SCAN_LAYERS = os.environ.get("SCAN_LAYERS", "false").lower() == "true"
USE_MULTIMODAL = os.environ.get("USE_MULTIMODAL", "false").lower() == "true"
PREFUSE_MOE_WEIGHTS = os.environ.get("PREFUSE_MOE_WEIGHTS", "false").lower() == "true"
USE_PATHWAYS = os.environ.get("USE_PATHWAYS", "false").lower() in ("true", "1")

# 3. Escape hatch for custom commands
CUSTOM_COMMAND = os.environ.get("CUSTOM_COMMAND")


def run_command(cmd_args, shell=False):
    """Runs a subprocess command, streaming its output to stdout in real-time."""
    if shell:
        print(f"🚀 Executing shell command:\n{cmd_args}", flush=True)
    else:
        print(f"🚀 Executing command:\n{' '.join(cmd_args)}", flush=True)

    try:
        process = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=shell,
            text=True,
            bufsize=1,
        )

        for line in process.stdout:
            print(line, end="", flush=True)

        process.wait()
        return process.returncode
    except Exception as exc:
        print(f"❌ Exception occurred while running command: {exc}", flush=True)
        return -1


def main():
    print("=" * 60, flush=True)
    print("🌟 MaxText Checkpoint Converter Tool 🌟", flush=True)
    print("=" * 60, flush=True)
    print(f"MaxText installation found at: {MAXTEXT_PKG_DIR}", flush=True)
    print("-" * 60, flush=True)

    # If the user has provided a custom command, we bypass our standard generation
    # and execute the custom command directly. This allows running test scripts,
    # logit checkers, or manual python commands directly in the image.
    if CUSTOM_COMMAND:
        print("💡 Custom command detected. Running in shell mode.", flush=True)
        rc = run_command(CUSTOM_COMMAND, shell=True)
        if rc == 0:
            print("🎉 Custom command finished successfully!", flush=True)
            sys.exit(0)
        else:
            print(f"❌ Error: Custom command failed with exit code {rc}", flush=True)
            sys.exit(rc)

    # Otherwise, execute the standard MaxText checkpoint converter
    if not BASE_OUTPUT_DIRECTORY:
        print(
            "❌ ERROR: Required environment variable 'BASE_OUTPUT_DIRECTORY' is not set.",
            flush=True,
        )
        print(
            "Please set 'BASE_OUTPUT_DIRECTORY' to a valid GCS path (e.g. gs://bucket/path/to/output).",
            flush=True,
        )
        sys.exit(1)

    # HF Token check
    if not HF_TOKEN:
        print(
            "⚠️ Warning: HF_TOKEN is not set. This might fail if the model is gated or private.",
            flush=True,
        )
    else:
        # Authenticate with huggingface-hub CLI if login token is set
        print("🔑 Logging into Hugging Face Hub...", flush=True)
        run_command(
            [
                sys.executable,
                "-c",
                f"from huggingface_hub import login; login(token='{HF_TOKEN}')",
            ]
        )

    base_yml = f"{MAXTEXT_PKG_DIR}/configs/base.yml"
    print(f"📄 Using MaxText base config: {base_yml}", flush=True)

    # Build the standard command-line parameters for to_maxtext.py
    cmd = [
        sys.executable,
        "-m",
        f"maxtext.checkpoint_conversion.{COMMAND}",
        base_yml,
        f"model_name={MODEL_NAME}",
        f"base_output_directory={BASE_OUTPUT_DIRECTORY}",
        f"scan_layers={str(SCAN_LAYERS).lower()}",
        f"use_pathways={str(USE_PATHWAYS).lower()}",
    ]

    # Additional standard MaxText parameter overrides
    if HF_TOKEN:
        cmd.append(f"hf_access_token={HF_TOKEN}")
    if HF_MODEL_PATH:
        # Some versions/models use hf_model_path, some use hf_ids. We supply both to be safe
        cmd.append(f"hf_model_path={HF_MODEL_PATH}")
        cmd.append(f"hf_ids={HF_MODEL_PATH}")
    if USE_MULTIMODAL:
        cmd.append("use_multimodal=true")
    if PREFUSE_MOE_WEIGHTS:
        cmd.append("prefuse_moe_weights=true")

    # Support extra custom flags via EXTRA_ARGS env var (e.g. "key1=val1 key2=val2")
    extra_args = os.environ.get("EXTRA_ARGS")
    if extra_args:
        print(f"➕ Adding extra arguments: {extra_args}", flush=True)
        cmd.extend(extra_args.split())

    rc = run_command(cmd)

    if rc == 0:
        print("\n🎉 Checkpoint conversion completed successfully!", flush=True)
        print(f"Weights are available at: {BASE_OUTPUT_DIRECTORY}", flush=True)
        sys.exit(0)
    else:
        print(
            f"\n❌ Error: Checkpoint conversion failed with exit code {rc}", flush=True
        )
        sys.exit(rc)


if __name__ == "__main__":
    main()
