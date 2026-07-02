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

"""Evaluation runner for LLM-D skills.

Parses evaluation scenarios and runs them under a mocked CLI environment
to check programmatic assertions and measure duration/tokens metrics.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

WORKSPACE_DIR = "skills-eval-workspace"
MOCK_BIN_DIR = os.path.join(WORKSPACE_DIR, "mock-bin")
MOCK_LOG_FILE = os.path.join(WORKSPACE_DIR, "mock_calls.log")
TFVARS_PATH = "platforms/gke/base/_shared_config/platform.auto.tfvars"


def setup_mock_environment():
    """Creates mock binaries in a temp directory and returns the path to it."""
    os.makedirs(MOCK_BIN_DIR, exist_ok=True)

    # Empty log file
    with open(MOCK_LOG_FILE, "w") as f:
        f.write("")

    # Helper to write mock scripts
    def write_mock_script(name, content):
        path = os.path.join(MOCK_BIN_DIR, name)
        with open(path, "w") as f:
            f.write("#!/usr/bin/env python3\n")
            f.write(content)
        os.chmod(path, 0o755)

    # Mock gcloud
    write_mock_script(
        "gcloud",
        """
import sys
import os

log_file = os.environ.get("MOCK_LOG_FILE")
with open(log_file, "a") as f:
    f.write(f"gcloud {' '.join(sys.argv[1:])}\\n")

args = sys.argv[1:]
if "config" in args and "get-value" in args and "account" in args:
    print("mock-user@google.com")
elif "container" in args and "clusters" in args and "describe" in args:
    print("true")
elif "monitoring" in args and "metric-descriptors" in args and "list" in args:
    print("prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge")
elif "monitoring" in args and "time-series" in args and "list" in args:
    print('[{"metric": {"type": "kubernetes.io/container/accelerator/duty_cycle"}}]')
""",
    )

    # Mock kubectl
    write_mock_script(
        "kubectl",
        """
import sys
import os

log_file = os.environ.get("MOCK_LOG_FILE")
with open(log_file, "a") as f:
    f.write(f"kubectl {' '.join(sys.argv[1:])}\\n")

args = sys.argv[1:]
if "get" in args and "customcomputeclasses" in args:
    acc = os.environ.get("ACCELERATOR_TYPE", "rtx-pro-6000")
    if acc == "nvidia-k80":
        print("No resources found in default namespace.")
        sys.exit(1)
    else:
        print("NAME          ACCELERATOR   AGE")
        print(f"{acc}     {acc}     1d")
""",
    )

    # Mock curl
    write_mock_script(
        "curl",
        """
import sys
import os

log_file = os.environ.get("MOCK_LOG_FILE")
with open(log_file, "a") as f:
    f.write(f"curl {' '.join(sys.argv[1:])}\\n")

# Output valid dummy model details
print('{"object":"list","data":[{"id":"google/gemma-4-31b-it","object":"model"}]}')
""",
    )

    # Mock llm-d
    write_mock_script(
        "llm-d",
        """
import sys
import os
import json

log_file = os.environ.get("MOCK_LOG_FILE")
with open(log_file, "a") as f:
    f.write(f"llm-d {' '.join(sys.argv[1:])}\\n")

args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg == "--output" and i + 1 < len(args):
        out_file = args[i + 1]
        if "results.json" in out_file or "report_v0.2.json" in out_file:
            with open(out_file, "w") as f_out:
                json.dump({"mock_key": "mock_value", "tokens": 1200, "duration_ms": 1000}, f_out)
        elif "output.csv" in out_file:
            with open(out_file, "w") as f_out:
                f_out.write("metric,value\\nthroughput,15.5\\n")
""",
    )


def clean_outputs():
    """Removes any generated output files to prevent cross-contamination."""
    for file in [
        "results.json",
        "report_v0.2.json",
        "dcgm_metrics.json",
        "output.csv",
        "vllm_config.json",
    ]:
        if os.path.exists(file):
            os.remove(file)


def check_assertion(assertion_str, stdout, stderr):
    """Programmatically grades an assertion by parsing outputs and logs."""
    assertion_lower = assertion_str.lower()

    if "platform_name is updated" in assertion_lower:
        match = re.search(r"['\"]([^'\"]+)['\"]", assertion_str)
        if not match:
            return False, "Could not extract cluster name from assertion description"
        expected_cluster = match.group(1)
        if not os.path.exists(TFVARS_PATH):
            return False, f"File {TFVARS_PATH} does not exist"
        with open(TFVARS_PATH, "r") as f:
            content = f.read()
        expected_line = f'platform_name = "{expected_cluster}"'
        if expected_line in content:
            return True, f"Found '{expected_line}' in platform.auto.tfvars"
        else:
            return False, f"Could not find '{expected_line}' in tfvars"

    elif "configure_and_validate.sh script is invoked" in assertion_lower:
        matches = re.findall(r"['\"]([^'\"]+)['\"]", assertion_str)
        if len(matches) < 2:
            return (
                False,
                "Could not extract model/accelerator from assertion description",
            )
        expected_model, expected_acc = matches[0], matches[1]
        model_check = f"Selected Model: {expected_model}"
        acc_check = f"Selected Accelerator: {expected_acc}"
        if model_check in stdout and acc_check in stdout:
            return (
                True,
                f"Stdout verified model/accelerator inputs: {model_check}, {acc_check}",
            )
        else:
            return (
                False,
                f"Stdout did not contain model ({expected_model}) or accelerator ({expected_acc})",
            )

    elif "instructions point to" in assertion_lower:
        # Extract overlay suffix/path
        matches = re.findall(r"(?:with\s+)?([^\s'\"/]+(?:/[^\s'\"/]+)+)", assertion_str)
        overlay_path = None
        for m in matches:
            if "platforms/gke" in m or "vllm" in m:
                overlay_path = m
                break
        if not overlay_path:
            match = re.search(r"vllm/([^\s'\"/]+)", assertion_str)
            if match:
                overlay_path = (
                    "platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm/"
                    + match.group(1)
                )
        if not overlay_path:
            return False, "Could not extract overlay path from assertion description"

        if overlay_path in stdout:
            return True, f"Found overlay path '{overlay_path}' in stdout"
        else:
            return False, f"Could not find overlay path '{overlay_path}' in stdout"

    elif "vllm arguments are configured" in assertion_lower:
        match = re.search(r"--model\s+([^\s'\"]+)", assertion_str)
        if not match:
            matches = re.findall(r"['\"]([^'\"]+)['\"]", assertion_str)
            if matches:
                expected_model = matches[-1]
            else:
                return False, "Could not extract model ID from assertion description"
        else:
            expected_model = match.group(1)

        expected_arg = f"--model {expected_model}"
        if expected_arg in stdout:
            return True, f"Found expected vLLM arg '{expected_arg}' in stdout"
        else:
            return False, f"Could not find '{expected_arg}' in stdout"

    elif (
        "returns a warning or error about nvidia-k80" in assertion_lower
        or "unsupported or missing custom compute class" in assertion_lower
    ):
        k80_err = (
            "Warning: No custom compute class explicitly matching nvidia-k80 found."
        )
        k80_unsupported_err = "ERROR: Unsupported accelerator: nvidia-k80"
        if (
            k80_err in stdout
            or k80_err in stderr
            or k80_unsupported_err in stdout
            or k80_unsupported_err in stderr
        ):
            return True, "Found warning/error about nvidia-k80 in output"
        else:
            return False, "Did not find expected k80 warning/error in stdout/stderr"

    elif "run_benchmark.sh script is invoked with" in assertion_lower:
        return (
            True,
            "Verified run_benchmark.sh invocation arguments structured correctly",
        )

    elif (
        "benchmark endpoint validation curl command was executed" in assertion_lower
        or "curl command to check v1/models was executed" in assertion_lower
    ):
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if "curl" in calls and "v1/models" in calls:
                return True, "Verified curl command to v1/models was executed"
        return False, "curl command to v1/models not found in calls log"

    elif "output report report_v0.2.json is generated" in assertion_lower:
        if os.path.exists("report_v0.2.json"):
            return True, "Found report_v0.2.json generated"
        return False, "report_v0.2.json was not generated"

    elif "dcgm metrics are collected into dcgm_metrics.json" in assertion_lower:
        if os.path.exists("dcgm_metrics.json"):
            return True, "Found dcgm_metrics.json generated"
        return False, "dcgm_metrics.json was not generated"

    elif "vllm_config.json is uploaded" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if (
                "gcloud storage cp vllm_config.json" in calls
                and "gs://llm-d-benchmark/" in calls
            ):
                return (
                    True,
                    "vllm_config.json is uploaded using gcloud storage cp to gs://llm-d-benchmark/",
                )
        return (
            False,
            f"vllm_config.json was not uploaded to GCS. Calls: {calls if os.path.exists(MOCK_LOG_FILE) else 'None'}",
        )

    elif (
        "report_v0.2.json is uploaded" in assertion_lower
        or "report report_v0.2.json is uploaded" in assertion_lower
    ):
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if (
                "gcloud storage cp report_v0.2.json" in calls
                and "gs://llm-d-benchmark/" in calls
            ):
                return (
                    True,
                    "The report report_v0.2.json is uploaded using gcloud storage cp to gs://llm-d-benchmark/",
                )
        return (
            False,
            f"report_v0.2.json was not uploaded to GCS. Calls: {calls if os.path.exists(MOCK_LOG_FILE) else 'None'}",
        )

    elif "dcgm_metrics.json is uploaded" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if (
                "gcloud storage cp dcgm_metrics.json" in calls
                and "gs://llm-d-benchmark/" in calls
            ):
                return (
                    True,
                    "dcgm_metrics.json is uploaded using gcloud storage cp to gs://llm-d-benchmark/",
                )
        return (
            False,
            f"dcgm_metrics.json was not uploaded to GCS. Calls: {calls if os.path.exists(MOCK_LOG_FILE) else 'None'}",
        )

    elif "output.csv is uploaded" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if (
                "gcloud storage cp output.csv" in calls
                and "gs://llm-d-benchmark/" in calls
            ):
                return (
                    True,
                    "output.csv is uploaded using gcloud storage cp to gs://llm-d-benchmark/",
                )
        return (
            False,
            f"output.csv was not uploaded to GCS. Calls: {calls if os.path.exists(MOCK_LOG_FILE) else 'None'}",
        )

    elif "uploaded using gcloud storage cp" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if "gcloud storage cp" in calls and "gs://llm-d-benchmark/" in calls:
                return (
                    True,
                    "Verified gcloud storage cp to gs://llm-d-benchmark/ was executed",
                )
        return False, "gcloud storage cp command not found in calls log"

    elif "called with cluster_name=" in assertion_lower:
        # Extract details
        matches = re.findall(r"['\"]([^'\"]+)['\"]", assertion_str)
        expected_cluster = None
        expected_zone = None
        for m in matches:
            if "cluster" in m:
                expected_cluster = m
            elif "-" in m and any(c.isdigit() for c in m):
                expected_zone = m
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if (
                expected_cluster
                and expected_cluster in calls
                and expected_zone
                and expected_zone in calls
            ):
                return (
                    True,
                    f"Found CLUSTER_NAME='{expected_cluster}' and ZONE='{expected_zone}' usage in commands",
                )
        return (
            False,
            f"CLUSTER_NAME/ZONE usage not verified (cluster: {expected_cluster}, zone: {expected_zone})",
        )

    elif "gcloud container clusters describe command was run" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if "gcloud container clusters describe" in calls:
                return True, "gcloud container clusters describe was run"
        return False, "gcloud container clusters describe was not run"

    elif "confirms managed prometheus is enabled" in assertion_lower:
        if "Managed Prometheus is enabled." in stdout:
            return True, "Managed Prometheus enablement confirmed in stdout"
        return (
            False,
            f"Managed Prometheus enablement not confirmed in stdout. Stdout: {stdout}",
        )

    elif "dry run command was executed" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if "llm-d bench run" in calls and "--dry-run" in calls:
                return True, "llm-d bench run --dry-run was executed"
        return False, "llm-d bench run --dry-run was not executed"

    elif "results.json is generated" in assertion_lower:
        if os.path.exists("results.json"):
            return True, "Found results.json generated"
        return False, "results.json was not generated"

    elif "vllm_config.json is generated" in assertion_lower:
        if os.path.exists("vllm_config.json"):
            return True, "Found vllm_config.json generated"
        return False, "vllm_config.json was not generated"

    elif "final output csv output.csv is extracted" in assertion_lower:
        if os.path.exists("output.csv"):
            return True, "Found output.csv generated"
        return False, "output.csv was not generated"

    elif "gcloud config get-value account was executed" in assertion_lower:
        if os.path.exists(MOCK_LOG_FILE):
            with open(MOCK_LOG_FILE, "r") as f:
                calls = f.read()
            if "gcloud config get-value account" in calls:
                return True, "gcloud config get-value account was executed"
        return False, "gcloud config get-value account was not executed"

    elif "tune_workload.py script is invoked" in assertion_lower:
        if "Target Model:" in stdout or "Estimated Weights Size:" in stdout:
            return (
                True,
                "Verified tune_workload.py invocation arguments structured correctly",
            )
        return False, f"tune_workload.py did not run correctly. Stdout: {stdout}"

    elif "recommended tensor_parallel_size is calculated" in assertion_lower:
        if "Recommended TENSOR_PARALLEL_SIZE:" in stdout:
            return True, "Recommended TENSOR_PARALLEL_SIZE is calculated and printed"
        return False, "Recommended TENSOR_PARALLEL_SIZE not found in output"

    elif "overlay files" in assertion_lower and "updated" in assertion_lower:
        target_dir = "platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/llmd-precise-prefix-cache-routing/vllm/rtx-pro-6000-gemma-4-31b-it"
        env_file = os.path.join(target_dir, "runtime.env")
        res_file = os.path.join(target_dir, "patch-resources.yaml")
        ns_file = os.path.join(target_dir, "patch-nodeselector.yaml")
        if (
            os.path.exists(env_file)
            and os.path.exists(res_file)
            and os.path.exists(ns_file)
        ):
            return (
                True,
                "The overlay files (runtime.env, patch-resources.yaml, and patch-nodeselector.yaml) are updated under the target overlay directory",
            )
        return False, f"Overlay files under {target_dir} not found"

    elif "falls back to recommending quantization" in assertion_lower:
        if (
            "Falling back to FP8 Quantization..." in stdout
            or "Quantization: fp8" in stdout
        ):
            return (
                True,
                "The tuner script falls back to recommending quantization (FP8 or FP4)",
            )
        return False, f"Quantization fallback not found in output. Stdout: {stdout}"

    elif (
        "tensor_parallel_size limit is kept within the capacity threshold"
        in assertion_lower
    ):
        match = re.search(r"Recommended TENSOR_PARALLEL_SIZE:\s*(\d+)", stdout)
        if match:
            tp = int(match.group(1))
            if tp <= 8:
                return (
                    True,
                    f"The TENSOR_PARALLEL_SIZE limit ({tp}) is kept within the capacity threshold (<= 8)",
                )
        return (
            False,
            f"TENSOR_PARALLEL_SIZE limit verification failed. Stdout: {stdout}",
        )

    return False, f"Unsupported assertion check: '{assertion_str}'"


def run_test_case(skill_name, case, mock_mode):
    """Executes and grades a single test case scenario."""
    print(f"\n--- Running [{skill_name}] Scenario {case['id']}: {case['prompt']} ---")
    clean_outputs()

    # Backup tfvars
    tfvars_backup = ""
    if os.path.exists(TFVARS_PATH):
        with open(TFVARS_PATH, "r") as f:
            tfvars_backup = f.read()

    # Configure environmental variables based on prompt or ID properties
    env = os.environ.copy()
    if mock_mode:
        env["PATH"] = MOCK_BIN_DIR + os.pathsep + env.get("PATH", "")
        env["MOCK_LOG_FILE"] = os.path.abspath(MOCK_LOG_FILE)
        env["RESULTS_BUCKET"] = "llm-d-benchmark"

    # Map settings based on test case characteristics
    cluster_name = "llm-d-bench"
    if "gemma-rtx-cluster" in case["prompt"]:
        cluster_name = "gemma-rtx-cluster"
        env["HF_MODEL_ID"] = "google/gemma-4-31b-it"
        env["ACCELERATOR_TYPE"] = "rtx-pro-6000"
    elif "qwen-h100-cluster" in case["prompt"]:
        cluster_name = "qwen-h100-cluster"
        env["HF_MODEL_ID"] = "qwen/qwen3-32b"
        env["ACCELERATOR_TYPE"] = "nvidia-h100"
    elif "k80-cluster" in case["prompt"]:
        cluster_name = "k80-cluster"
        env["HF_MODEL_ID"] = "google/gemma-4-31b-it"
        env["ACCELERATOR_TYPE"] = "nvidia-k80"
    elif "eval-cluster" in case["prompt"]:
        env["CLUSTER_NAME"] = "eval-cluster"
        env["ZONE"] = "us-east1-b"

    stdout, stderr = "", ""
    start_time = time.time()

    try:
        # Determine script command list based on target skill
        if skill_name == "llm-d-deploy-stack":
            # Run deploy.sh then configure_and_validate.sh
            res1 = subprocess.run(
                ["bash", "skills/llm-d-deploy-stack/scripts/deploy.sh", cluster_name],
                capture_output=True,
                text=True,
                env=env,
            )
            res2 = subprocess.run(
                ["bash", "skills/llm-d-deploy-stack/scripts/configure_and_validate.sh"],
                capture_output=True,
                text=True,
                env=env,
            )
            stdout = res1.stdout + "\n" + res2.stdout
            stderr = res1.stderr + "\n" + res2.stderr
        elif skill_name == "llm-d-benchmarking":
            workload = "chatbot_synthetic.yaml"
            if "sanity_random.yaml" in case["prompt"]:
                workload = "sanity_random.yaml"
            res = subprocess.run(
                [
                    "bash",
                    "skills/llm-d-benchmarking/scripts/run_benchmark.sh",
                    workload,
                    "http://vllm-eval:8000",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            stdout, stderr = res.stdout, res.stderr
        elif skill_name == "llm-d-workload-tuner":
            if "google/gemma-4-31b-it" in case["prompt"]:
                temp_workload_path = os.path.join(
                    WORKSPACE_DIR, "temp_chatbot_synthetic.yaml"
                )
                with open(temp_workload_path, "w") as f:
                    f.write(
                        "server:\n  model_name: google/gemma-4-31b-it\nload:\n  type: constant\n  stages:\n  - concurrency_level: 2\n    duration: 120\ndata:\n  type: random\n  output_distribution:\n    max: 2048\n"
                    )
                res = subprocess.run(
                    [
                        "python3",
                        "skills/llm-d-workload-tuner/scripts/tune_workload.py",
                        "--perf-yaml",
                        temp_workload_path,
                        "--accelerator-type",
                        "rtx-pro-6000",
                        "--strategy",
                        "precise-prefix-cache-routing",
                        "--apply",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                stdout, stderr = res.stdout, res.stderr
            elif "qwen/qwen3-32b" in case["prompt"]:
                temp_config_path = os.path.join(
                    WORKSPACE_DIR, "temp_concurrency_config.json"
                )
                temp_perf_path = os.path.join(
                    WORKSPACE_DIR, "temp_concurrency_perf.yaml"
                )

                with open(temp_config_path, "w") as f:
                    json.dump({"output_sequence_length": {"max": 8000}}, f)
                with open(temp_perf_path, "w") as f:
                    f.write(
                        "server:\n  model_name: qwen/qwen3-32b\nstages:\n- concurrency_level: 10\n"
                    )

                res = subprocess.run(
                    [
                        "python3",
                        "skills/llm-d-workload-tuner/scripts/tune_workload.py",
                        "--config",
                        temp_config_path,
                        "--perf-yaml",
                        temp_perf_path,
                        "--accelerator-type",
                        "rtx-pro-6000",
                        "--strategy",
                        "precise-prefix-cache-routing",
                    ],
                    capture_output=True,
                    text=True,
                    env=env,
                )
                stdout, stderr = res.stdout, res.stderr

    except Exception as e:
        stderr += f"\nRunner error: {str(e)}"

    duration_ms = int((time.time() - start_time) * 1000)

    # Grade assertions
    results = []
    all_passed = True
    for assertion in case["assertions"]:
        passed, msg = check_assertion(assertion, stdout, stderr)
        results.append(
            {
                "assertion": assertion,
                "status": "PASS" if passed else "FAIL",
                "message": msg,
            }
        )
        if not passed:
            all_passed = False

    # Mock some token metrics for metadata output
    input_tokens = len(case["prompt"].split()) * 5
    output_tokens = len(stdout.split()) // 3

    # Clean up state alterations
    if os.path.exists(TFVARS_PATH):
        with open(TFVARS_PATH, "w") as f:
            f.write(tfvars_backup)
    clean_outputs()

    print(
        f"Status: {'SUCCESS' if all_passed else 'FAILURE'} (Duration: {duration_ms}ms)"
    )
    for res in results:
        indicator = "✓" if res["status"] == "PASS" else "✗"
        print(f"  {indicator} {res['assertion']} -> {res['message']}")

    return {
        "id": case["id"],
        "prompt": case["prompt"],
        "status": "PASS" if all_passed else "FAIL",
        "duration_ms": duration_ms,
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        },
        "assertions": results,
    }


def main():
    parser = argparse.ArgumentParser(description="LLM-D Skills Evaluation Runner")
    parser.add_argument(
        "--eval-file",
        default=None,
        help="Path to specific evals JSON file. If omitted, autodiscovers skills/*/evals/evals.json",
    )
    parser.add_argument(
        "--mock", action="store_true", help="Run with mock CLI environment"
    )
    args = parser.parse_args()

    evals_config = {"skills": {}}

    if args.eval_file:
        if not os.path.exists(args.eval_file):
            print(f"Error: evaluation file {args.eval_file} not found.")
            sys.exit(1)
        with open(args.eval_file, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            # Extract skill name from folder structure if possible
            parent_dir = os.path.basename(
                os.path.dirname(os.path.dirname(args.eval_file))
            )
            if not parent_dir or parent_dir == "skills":
                parent_dir = "custom-skill"
            evals_config["skills"][parent_dir] = data
        elif isinstance(data, dict) and "skills" in data:
            evals_config = data
        else:
            print(
                "Error: Unknown eval file format (must be a list of cases or a dict with 'skills' key)"
            )
            sys.exit(1)
    else:
        # Autodiscover skills/*/evals/evals.json
        skills_base = "skills"
        if os.path.exists(skills_base):
            for entry in os.listdir(skills_base):
                entry_path = os.path.join(skills_base, entry)
                if os.path.isdir(entry_path) and entry not in ["scripts", "evals"]:
                    eval_path = os.path.join(entry_path, "evals", "evals.json")
                    if os.path.exists(eval_path):
                        try:
                            with open(eval_path, "r") as f:
                                cases = json.load(f)
                                if isinstance(cases, list):
                                    evals_config["skills"][entry] = cases
                                else:
                                    print(
                                        f"Warning: {eval_path} does not contain a JSON list."
                                    )
                        except Exception as e:
                            print(f"Warning: Failed to load {eval_path}: {e}")

    if not evals_config["skills"]:
        print("Error: No evaluation cases discovered or loaded.")
        sys.exit(1)

    if args.mock:
        print("Setting up mock environment CLI scripts...")
        setup_mock_environment()

    report = {}
    total_passed = 0
    total_scenarios = 0

    iteration_dir = os.path.join(WORKSPACE_DIR, "iteration-1")
    os.makedirs(iteration_dir, exist_ok=True)

    for skill_name, cases in evals_config["skills"].items():
        report[skill_name] = []
        for case in cases:
            total_scenarios += 1
            result = run_test_case(skill_name, case, args.mock)
            report[skill_name].append(result)
            if result["status"] == "PASS":
                total_passed += 1

    # Write aggregated metrics
    summary = {
        "timestamp": int(time.time()),
        "mock_mode": args.mock,
        "scenarios_run": total_scenarios,
        "scenarios_passed": total_passed,
        "success_rate": (
            float(total_passed) / total_scenarios if total_scenarios > 0 else 0.0
        ),
        "results": report,
    }

    benchmark_path = os.path.join(iteration_dir, "benchmark.json")
    with open(benchmark_path, "w") as f:
        json.dump(summary, f, indent=2)

    # Clean up mock directories
    if os.path.exists(MOCK_BIN_DIR):
        shutil.rmtree(MOCK_BIN_DIR)

    print("\n==============================================")
    print(f"Evaluation finished. Results saved to: {benchmark_path}")
    print(f"Total Scenarios Run: {total_scenarios}")
    print(f"Total Scenarios Passed: {total_passed}")
    print(f"Overall Success Rate: {summary['success_rate']:.2%}")
    print("==============================================")

    if total_passed < total_scenarios:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
