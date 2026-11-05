#!/usr/bin/env bash

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

# Entrypoint wrapper for model servers that use GKE Pod snapshots. The
# gke-pod-snapshot Kustomize Component makes this script the container command
# and passes the engine's original command and args through as arguments.
#
# Cold start (no snapshot yet):
#   1. Stream the model from Cloud Storage into MODEL_CACHE_DIR (RAM-backed),
#      because gVisor does not support the Cloud Storage FUSE CSI driver.
#   2. Start the engine, wait until POD_SNAPSHOT_HEALTH_URL succeeds, and send
#      one chat completion so lazily compiled GPU kernels are in the snapshot.
#   3. Delete the weight files, which are already in GPU memory, so they are
#      not captured.
#   4. Write to /proc/gvisor/checkpoint. GKE captures the Pod and, because the
#      PodSnapshotPolicy uses `postCheckpoint: resume`, the Pod keeps serving.
# Restore: Pods created after the snapshot is available resume from inside the
# /proc/gvisor/checkpoint write, so steps 1-3 do not run again.
# In both cases the script then creates /tmp/pod-snapshot-ready, which the
# readiness probe requires.
#
# The engine must serve an OpenAI-compatible API, with POD_SNAPSHOT_HEALTH_URL
# and /v1/chat/completions on the same host and port.
set -o errexit
set -o nounset
set -o pipefail

MY_PATH="$(
  cd "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

: "${MODEL_BUCKET_NAME:?MODEL_BUCKET_NAME must be set; it comes from the deployment ConfigMap.}"
: "${MODEL_GCS_DIR:?MODEL_GCS_DIR must be set in the overlay runtime.env.}"
: "${MODEL_ID:?MODEL_ID must be set in the overlay runtime.env.}"
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/model}"
HEALTH_URL="${POD_SNAPSHOT_HEALTH_URL:-http://127.0.0.1:8000/health}"
WARMUP_URL="${HEALTH_URL%/health}/v1/chat/completions"
READY_FILE="/tmp/pod-snapshot-ready"

if (($# == 0)); then
  echo "Usage: checkpoint-wrapper.sh <model server command> [args...]" >&2
  exit 2
fi

# Re-exec from /tmp so bash's open script descriptor (fd 255) resides in the
# container rootfs rather than on the 9p ConfigMap mount (/etc/pod-snapshot),
# whose kubelet `..YYYY_MM_DD_...` symlink target differs across nodes and
# would otherwise fail gVisor's vfs.CompleteRestore() on restore.
if [[ "${POD_SNAPSHOT_RELOCATED:-}" != "1" ]]; then
  rm -rf /tmp/pod-snapshot
  mkdir -p /tmp/pod-snapshot
  cp "${MY_PATH}/checkpoint-wrapper.sh" "${MY_PATH}/gcs_model_streamer.py" /tmp/pod-snapshot/
  POD_SNAPSHOT_RELOCATED=1 exec /bin/bash /tmp/pod-snapshot/checkpoint-wrapper.sh "$@"
fi
unset POD_SNAPSHOT_RELOCATED

rm -f "${READY_FILE}"

# Under gVisor nvproxy, the host-matched libcuda.so.1 in /usr/local/nvidia/lib64
# must be found before the CUDA forward-compatibility libraries under
# /usr/local/cuda/compat. BASH_ENV is unset so that child `#!/bin/bash` scripts
# (for example trtllm-llmapi-launch) do not prepend the compat directory again.
clean_ld="$(printf '%s\n' "${LD_LIBRARY_PATH:-}" | tr ':' '\n' | { grep -v -e '^/usr/local/cuda/compat/' -e '^$' || true; } | paste -sd: -)"
export LD_LIBRARY_PATH="/usr/local/nvidia/lib64${clean_ld:+:${clean_ld}}:/usr/local/cuda/compat/lib"
unset BASH_ENV

export HF_HUB_OFFLINE=1
echo "[pod-snapshot] Streaming gs://${MODEL_BUCKET_NAME}/${MODEL_GCS_DIR} into ${MODEL_CACHE_DIR}..."
MODEL_CACHE_DIR="${MODEL_CACHE_DIR}" python3 "${MY_PATH}/gcs_model_streamer.py"

"$@" &
server_pid=$!
trap 'kill -TERM "${server_pid}" 2>/dev/null || true; wait "${server_pid}" 2>/dev/null || true' TERM INT

if [[ ! -e /proc/gvisor/checkpoint ]]; then
  echo "[pod-snapshot] /proc/gvisor/checkpoint is absent (the Pod is not running under gVisor); serving without a snapshot." >&2
else
  echo "[pod-snapshot] Waiting for ${HEALTH_URL}..."
  while ! curl --fail --silent --max-time 2 "${HEALTH_URL}" >/dev/null; do
    if ! kill -0 "${server_pid}" 2>/dev/null; then
      wait "${server_pid}"
      exit $?
    fi
    sleep 2
  done

  echo "[pod-snapshot] Model server is healthy; sending one warm-up request..."
  warmup_body="$(python3 -c 'import json, os; print(json.dumps({"model": os.environ["MODEL_ID"], "messages": [{"role": "user", "content": "Say OK."}], "max_tokens": 8, "temperature": 0, "chat_template_kwargs": {"enable_thinking": False}}))')"
  curl --fail --silent --show-error --max-time 180 \
    --header "Content-Type: application/json" \
    --data "${warmup_body}" \
    "${WARMUP_URL}" >/dev/null

  find "${MODEL_CACHE_DIR}" \( -name '*.safetensors' -o -name '*.bin' -o -name '*.pt' -o -name '*.lock' \) -delete
  echo "[pod-snapshot] Triggering the cooperative checkpoint..."
  if checkpoint_err="$( (echo 1 >/proc/gvisor/checkpoint) 2>&1)"; then
    echo "[pod-snapshot] Checkpoint complete (or the Pod was restored from a snapshot)."
  else
    echo "[pod-snapshot] WARNING: writing /proc/gvisor/checkpoint failed (${checkpoint_err:-unknown error}); serving without a snapshot." >&2
  fi
fi

touch "${READY_FILE}"
wait "${server_pid}"
