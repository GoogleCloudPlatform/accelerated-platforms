#!/bin/sh
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

# Runs `vllm serve "$@"` (the model server's unchanged arguments) and
# implements the cooperative checkpoint trigger of a PodSnapshotPolicy with
# `triggerConfig.type: workload` (modeled on
# kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore).
# scripts/podsnapshot_patch.py makes this the container command:
#   ["/bin/sh", "-c", <this script>, "vllm-podsnapshot", <vllm args>...]
vllm serve "$@" &
VLLM_PID=$!
# This shell is PID 1: when it exits, the container runtime kills vLLM. A
# trapped signal interrupts `wait`, so the trap forwards SIGTERM, waits for
# vLLM's graceful `--shutdown-timeout` drain, and exits with vLLM's exit status
# (so a pod that is stopping never goes on to write the checkpoint below).
trap 'kill -TERM "${VLLM_PID}" 2>/dev/null; wait "${VLLM_PID}"; exit $?' TERM INT
if [ ! -e /proc/gvisor/checkpoint ]; then
  echo "[podsnapshot] /proc/gvisor/checkpoint is absent (no matching PodSnapshotPolicy); serving without a checkpoint."
else
  echo "[podsnapshot] Waiting for the model server to become healthy..."
  until python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)' 2>/dev/null; do
    if ! kill -0 "${VLLM_PID}" 2>/dev/null; then
      wait "${VLLM_PID}"
      exit $?
    fi
    sleep 2
  done
  echo "[podsnapshot] Model server is healthy; triggering the checkpoint at $(date -u +%H:%M:%S)."
  # A restored pod resumes right as this write returns. If no snapshot is
  # pending for this pod (for example, it started cold while a snapshot was
  # already available), gVisor returns an error and the pod keeps serving.
  if ERR="$( (echo 1 > /proc/gvisor/checkpoint) 2>&1 )"; then
    echo "[podsnapshot] Checkpoint complete, or restored from a snapshot, at $(date -u +%H:%M:%S)."
  else
    echo "[podsnapshot] Checkpoint write returned non-zero (${ERR:-unknown}); continuing to serve."
  fi
fi
wait "${VLLM_PID}"
