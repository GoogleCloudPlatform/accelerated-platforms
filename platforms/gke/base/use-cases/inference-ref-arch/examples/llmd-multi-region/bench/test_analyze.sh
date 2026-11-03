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

# Runs analyze.py on the synthetic fixture in testdata/analyze and checks the
# results. Local only; no cloud access.

set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"
out="$(mktemp -d)"
trap 'rm -rf "${out}"' EXIT

python3 "${MY_PATH}/analyze.py" "${MY_PATH}/testdata/analyze" --out "${out}" --no-charts

python3 - "${out}" <<'EOF'
import csv
import os
import sys

out = sys.argv[1]
for name in ("report.md", "stages.csv", "summary.csv", "aggregate.csv", "relative.csv"):
    assert os.path.getsize(os.path.join(out, name)) > 0, name


def rows(name):
    with open(os.path.join(out, name), newline="") as f:
        return list(csv.DictReader(f))


stages = rows("stages.csv")
assert len(stages) == 12, len(stages)
row = next(r for r in stages if r["arm"] == "vllm" and r["client"] == "usc1" and float(r["requested_qps"]) == 4.0)
assert row["failures"] == "3", row
assert abs(float(row["ttft_p50_ms"]) - 2400.0) < 1e-6, row["ttft_p50_ms"]
assert abs(float(row["ttft_p90_ms"]) - 4320.0) < 1e-6, row["ttft_p90_ms"]
assert abs(float(row["error_rate"]) - 3 / 240) < 1e-9, row["error_rate"]

summary = {(r["arm"], r["client"]): r for r in rows("summary.csv")}
assert summary[("vllm", "usc1")]["max_qps_p90_ttft_slo"] == "2.0", summary[("vllm", "usc1")]
assert summary[("llmd", "usc1")]["max_qps_p90_ttft_slo"] == "4.0", summary[("llmd", "usc1")]

agg = [r for r in rows("aggregate.csv") if r["arm"] == "vllm" and float(r["requested_qps"]) == 4.0]
assert len(agg) == 1 and agg[0]["failures"] == "6", agg

rel = [r for r in rows("relative.csv") if r["arm"] == "llmd" and r["client"] == "usc1" and r["requested_qps"] == "4.0"]
assert len(rel) == 1, rel
assert abs(float(rel[0]["ttft_p90_ms_change_pct"]) - (-62.5)) < 1e-6, rel[0]["ttft_p90_ms_change_pct"]
cap = [r for r in rows("relative.csv") if r["requested_qps"] == "max-within-slo" and r["client"] == "usc1"]
assert abs(float(cap[0]["max_qps_p90_ttft_slo_change_pct"]) - 100.0) < 1e-6, cap
print("test_analyze: OK")
EOF
