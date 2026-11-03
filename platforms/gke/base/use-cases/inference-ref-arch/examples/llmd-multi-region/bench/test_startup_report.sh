#!/usr/bin/env bash
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

# Runs startup_report.py on the synthetic fixture in testdata/startup and
# checks the results. Local only; no cluster access.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
out="$(mktemp -d)"
trap 'rm -rf "${out}"' EXIT

python3 "${MY_PATH}/startup_report.py" "${MY_PATH}/testdata/startup" --out "${out}"

python3 - "${out}" <<'EOF'
import csv
import json
import os
import sys

out = sys.argv[1]
with open(os.path.join(out, "startup.csv"), newline="") as f:
    pods = {r["pod"]: r for r in csv.DictReader(f)}
assert set(pods) == {"vllm-0", "vllm-1"}, pods.keys()

expected = {
    "vllm-0": {
        "node_provisioned": "True",
        "apply_to_scheduled_s": 135.0,
        "apply_to_node_created_s": 40.0,
        "node_created_to_ready_s": 90.0,
        "node_ready_to_scheduled_s": 5.0,
        "scheduled_to_initialized_s": 65.0,
        "image_pull_s": 103.0,
        "image_pull_incl_wait_s": 104.5,
        "container_start_to_ready_s": 267.0,
        "container_start_to_app_startup_s": 257.0,
        "weights_load_s": 35.42,
        "model_load_s": 36.871,
        "dynamo_transform_s": 13.91,
        "torch_compile_s": 68.25,
        "cuda_graph_s": 29.0,
        "engine_init_s": 109.73,
        "kv_cache_tokens": 81088,
        "apply_to_ready_s": 560.0,
    },
    "vllm-1": {
        "node_provisioned": "False",
        "restarts": 1,
        "apply_to_scheduled_s": 6.0,
        "image_pull_s": 0.0,
        "images_cached": "True",
        "model_load_s": 40.1,
        "torch_compile_s": 31.5,
        "cuda_graph_s": 22.0,
        "engine_init_s": 95.2,
        "kv_cache_tokens": 79872,
        "apply_to_ready_s": 330.0,
    },
}
for pod, fields in expected.items():
    for key, want in fields.items():
        got = pods[pod][key]
        if isinstance(want, str):
            assert got == want, (pod, key, got, want)
        else:
            assert abs(float(got) - want) < 1e-6, (pod, key, got, want)

with open(os.path.join(out, "startup_summary.json")) as f:
    summary = json.load(f)[0]
assert summary["arm"] == "llmd", summary
assert summary["apply_to_all_pods_ready_s"] == 560.0, summary
assert summary["apply_to_first_ok_via_gateway_s"] == 575.0, summary
assert os.path.getsize(os.path.join(out, "startup.md")) > 0
print("test_startup_report: OK")
EOF
