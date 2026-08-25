#!/bin/bash
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

set -e

ACCESS_TOKEN=$(python3 -c "import google.auth, google.auth.transport.requests; c, _ = google.auth.default(); c.refresh(google.auth.transport.requests.Request()); print(c.token)")
PROJECT_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/project/project-id")

START=${START_TIME}
END=${END_TIME}
NS=${TARGET_NAMESPACE:-default}

LATEST_DIR=$(ls -td /requests/inference-perf-* 2>/dev/null | head -n 1 || true)
if [ -z "$LATEST_DIR" ]; then
  echo '{"error": "No results directory found on PVC"}'
  exit 1
fi
echo "Collecting DCGM telemetry for run dir: $LATEST_DIR"

FILTER="(metric.type=\"kubernetes.io/container/accelerator/duty_cycle\" OR metric.type=\"kubernetes.io/container/accelerator/memory_used\" OR metric.type=\"kubernetes.io/container/accelerator/memory_total\" OR metric.type=\"kubernetes.io/container/accelerator/memory_bandwidth_utilization\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_GR_ENGINE_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_SM_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_FB_USED/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_FB_FREE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_FB_TOTAL/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_MEM_COPY_UTIL/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_DRAM_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_PIPE_TENSOR_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_PIPE_FP16_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_PIPE_FP32_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_PROF_PIPE_FP64_ACTIVE/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_GPU_TEMP/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_MEMORY_TEMP/gauge\" OR metric.type=\"prometheus.googleapis.com/DCGM_FI_DEV_SM_CLOCK/gauge\") AND (resource.labels.namespace_name=\"${NS}\" OR resource.labels.namespace=\"${NS}\") AND (resource.labels.pod_name = monitoring.regex.full_match(\".*vllm.*|.*modelservice.*|.*prefill.*|.*decode.*\") OR resource.labels.pod = monitoring.regex.full_match(\".*vllm.*|.*modelservice.*|.*prefill.*|.*decode.*\"))"

ENCODED_FILTER=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$FILTER'''))")
URL="https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}/timeSeries?filter=${ENCODED_FILTER}&interval.startTime=${START}&interval.endTime=${END}"

OUT_PATH="${LATEST_DIR}/dcgm_metrics.json"
curl -s -H "Authorization: Bearer $ACCESS_TOKEN" "$URL" | tee "$OUT_PATH" > /dev/null

echo "Saved timeSeries to $OUT_PATH"
