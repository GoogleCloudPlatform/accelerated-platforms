# Incident Report: Fast-Start Checkpoint Failures for Large LLMs

## Overview
While attempting to create a GKE PodSnapshot of large models (Qwen 3.5 35B and Gemma 4 31B), the checkpoint process consistently failed and froze indefinitely. This document details the root cause investigation, the true nature of the "Controller Deadlock," and the proposed mitigation strategy.

---

## 1. Symptoms & Observations
* **Symptom 1:** Checkpointing Gemma 4 31B and Qwen 3.5 35B consistently failed. The `PodSnapshot` object would remain stuck in the `AwaitingCheckpoint` phase forever.
* **Symptom 2:** The `runsc checkpoint` command on the host node could be observed running indefinitely (e.g., for 40+ minutes) without making any progress. No files were written to the GCS bucket by the `runsc-checkpointgofer`.
* **Symptom 3:** If the stuck pod was force-deleted and a new pod was scheduled on the same node, the node would inevitably suffer an Out-Of-Memory (OOM) crash and become `NotReady`.
* **Symptom 4:** Gemma 3 27B, despite having a massive 117GB memory footprint, successfully checkpointed in 28 minutes.

## 2. The Investigation
We launched a privileged node-debugger pod onto the node executing the frozen checkpoint.

* **Process Inspection:** We confirmed `runsc checkpoint` and `runsc-checkpointgofer` were actively running but deadlocked. `lsof` revealed that the gofer had no active network connections to GCS, confirming it was hung during the local memory buffering phase.
* **Kernel Logs (dmesg):** The host kernel logs revealed a catastrophic NVIDIA driver assertion failure occurring precisely when the checkpoint was triggered:
  ```
  NVRM: kchannelNotifyRc_IMPL: Failed to set error notifier for channel 0x00000006 with error 0x57.
  NVRM: nvAssertOkFailedNoLog: Assertion failed: Requested object not found [NV_ERR_OBJECT_NOT_FOUND] (0x00000057) returned from kchannelNotifyRc_HAL(pKernelChannel)
  ```
* **Node Crash:** The force-deletion of the Kubernetes pod failed to terminate the `runsc` kernel-level sandbox due to the driver deadlock. The zombie process retained its ~100GB RAM footprint. Starting a new pod subsequently exhausted the node's 192GB of RAM, causing a hard node crash.

## 3. The Root Cause
The "Persistent Checkpoint Deadlock" is caused by a memory exhaustion/mapping bug in the `gVisor` `nvproxy` kernel module when attempting to dump VRAM footprints exceeding a specific threshold. 

* Qwen 3.5 35B was configured with `GPU_MEMORY_UTILIZATION=0.90` (86.4GB VRAM).
* Gemma 4 31B was configured with `GPU_MEMORY_UTILIZATION=0.92` (88.3GB VRAM).
* Gemma 3 27B was configured with `GPU_MEMORY_UTILIZATION=0.80` (76.8GB VRAM).

When `runsc` coordinates with the NVIDIA driver to dump >80GB of VRAM directly, the driver hits an internal limit, crashes with `NV_ERR_OBJECT_NOT_FOUND`, and deadlocks the entire checkpoint process.

## 4. The Fix & Mitigation
To immediately unblock benchmarking, we reduced `GPU_MEMORY_UTILIZATION` for the Qwen 3.5 35B deployment from `0.90` down to `0.80`. This restricts the pre-allocated KV cache and keeps the total VRAM footprint comfortably below the crash threshold, matching the successful configuration used by Gemma 3 27B.

**Long-Term Resolution:**
As model weights continue to scale (e.g., towards massive models like "Inkling"), artificially constraining the KV cache via `GPU_MEMORY_UTILIZATION` is not a sustainable solution. The underlying `runsc` `nvproxy` checkpointing mechanism must be patched by the GKE/gVisor engineering team to support dumping near-100% VRAM capacities on 96GB+ GPUs without triggering kernel assertions.

## 5. Addendum: Missing `/proc/gvisor/checkpoint` Device

During subsequent testing, we encountered an issue where `/proc/gvisor/checkpoint` was inexplicably missing from the `vLLM` container, preventing cooperative checkpointing.

**The Fake Root Cause:**
We initially (and incorrectly) attributed this to a missing `podsnapshot.gke.io/allow-checkpoint-writes: "true"` annotation on the pod. This annotation does not exist and is a hallucination.

**The Real Root Cause:**
The device was missing because the pod was deployed with the `podsnapshot.gke.io/restore-from-policy` annotation on the `Deployment`. When the `pod-snapshot-agent` mutating webhook processes a pod with this annotation, it expects a snapshot in GCS. If no snapshot exists (because the previous snapshot failed due to the `nvproxy` deadlock), the webhook falls back to a cold start. However, as part of this fallback process, the GKE machinery explicitly disables checkpointing for this pod to avoid infinite loops of failed restores and corrupted states. Consequently, `runsc` intentionally skips mounting `/proc/gvisor/checkpoint`.

**The Fix:**
To capture a fresh checkpoint, the `podsnapshot.gke.io/restore-from-policy` annotation MUST be removed from the `Deployment` so the cluster treats it as a pure cold start, fully enabling the checkpoint device.
