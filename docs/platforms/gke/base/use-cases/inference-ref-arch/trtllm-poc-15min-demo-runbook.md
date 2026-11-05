# 15-minute Presenter Beat Sheet: Global open-model inference with TensorRT-LLM, NVIDIA Nemotron-3, and GKE Pod snapshots on RTX PRO 6000

> [!IMPORTANT]
>
> Dynamic Landscape: The field of AI inference is experiencing continuous, rapid
> evolution. This document is regularly updated to reflect the latest products,
> features, and architectural patterns across Google Cloud, NVIDIA TensorRT-LLM,
> and Google Kubernetes Engine (GKE).
>
> Last Update: 2026-11-05 (YYYY-MM-DD)

This Presenter Beat Sheet accompanies the
[NVIDIA TensorRT-LLM and Nemotron-3 reference architecture on multi-region GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/trtllm-nemotron3-reference-architecture.md).
Complete **Part 1 (Pre-Demo Cluster Provisioning)** in the
[Multi-region GKE inference foundation quick-start](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#quick-start-multi-region-provisioning-and-teardown)
with `NETWORK_MODE="shared-vpc"`, `ENABLE_POD_SNAPSHOTS="true"`,
`ACTIVE_MIGRATION_ENABLED="false"`, and:

```shell
export MIRROR_IMAGES="nvcr.io/nvidia/tensorrt-llm/release:1.4.0rc2@sha256:93a3eaf1fa574813d608a7147735134bcfbd06d18d1aa98e8ee0d5da09e51e3a=tensorrt-llm/release:1.4.0rc2"
```

---

## Pre-demo workload pre-warm (`~20–25 min` before screen share)

Stage `Nano-30B-NVFP4` (`18.03 GiB`) and `Super-120B-NVFP4` (`74.80 GiB`) in
`inf-americas`, replicate `Nano-30B-NVFP4` to `inf-europe` and `inf-apac`,
deploy Path A + Path B (`TRTLLM_VARIANT_SUFFIX="-podsnapshot"`), and register
the cross-region internal Application Load Balancer:

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
export ACCELERATOR_TYPE="rtx-pro-6000"

use_region "americas" "us-central1" 0
stage_hf_model "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
stage_hf_model "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4"
replicate_hf_model "americas" "europe" "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" &
rep_eu=$!
replicate_hf_model "americas" "apac" "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" &
rep_ap=$!

export TF_VAR_ira_online_gpu_trtllm_image_url="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/tensorrt-llm/release:1.4.0rc2"
for MODEL in "nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4" "nvidia/nvidia-nemotron-3-super-120b-a12b-nvfp4"; do
  HF_MODEL_ID="${MODEL}" \
    "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
done
HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4" TRTLLM_VARIANT_SUFFIX="-podsnapshot" \
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"

wait "${rep_eu}" && wait "${rep_ap}"
for TARGET in "europe:europe-west2:1" "apac:asia-southeast1:2"; do
  IFS=: read -r p r idx <<<"${TARGET}"
  use_region "${p}" "${r}" "${idx}"
  export TF_VAR_ira_online_gpu_trtllm_image_url="${r}-docker.pkg.dev/${PROJECT_ID}/inf-${p}/tensorrt-llm/release:1.4.0rc2"
  HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4" \
    "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
done

for TARGET in "americas:us-central1:0" "europe:europe-west2:1" "apac:asia-southeast1:2"; do
  IFS=: read -r p r idx <<<"${TARGET}"
  use_region "${p}" "${r}" "${idx}"
  kubectl rollout status -n "inf-${p}-online-gpu" deploy/trtllm-rtx6000-nemotron-3-nano-30b-nvfp4 --timeout=1800s
  expose_service_neg "${p}" "inf-${p}-online-gpu" "trtllm-rtx6000-nemotron-3-nano-30b-nvfp4" "8000" "trtllm"
done
cat > /tmp/trtllm-backends.json << 'EOF'
{"trtllm": {"health_check_path": "/health", "health_check_port": 8000, "max_in_flight_requests_per_endpoint": 16}}
EOF
NETWORK_MODE="shared-vpc" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh" \
  apply --backends /tmp/trtllm-backends.json --active trtllm
```

Confirm all Pods are `1/1 Running` and `PodSnapshot` reports
`AllSnapshotsAvailable` before starting the call:

```shell
use_region "americas" "us-central1" 0
kubectl get pods,podsnapshots -n inf-americas-online-gpu
```

---

## Beat 1 (`0:00 – 3:30`): Global `RTX PRO 6000` capacity & consumption diversity

> **Talk track**: _"Pairing **NVIDIA RTX PRO 6000 Blackwell (`g4-standard-48`,
> 96 GB GDDR7, `SM120`)** with **`NVFP4`** fits both **Nemotron-3 Nano 30B
> (`A3B`)** and **Super 120B (`A12B`)** on a **single GPU (`TP=1`)**, while
> GKE's `gpu-rtx-pro-6000-96gb-x1` `ComputeClass` cascades automatically across
> `Standard`, `DWS Flex-Start`, and `Spot` in each region."_

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
gcloud compute accelerator-types list --project="${PROJECT_ID}" \
  --filter="name=nvidia-rtx-pro-6000 AND zone:(us-central1-* europe-west2-* asia-southeast1-*)" \
  --format="table(name,zone.basename(),description)"

for TARGET in "americas:us-central1:0" "europe:europe-west2:1" "apac:asia-southeast1:2"; do
  IFS=: read -r p r idx <<<"${TARGET}"
  use_region "${p}" "${r}" "${idx}"
  echo "=== ${p^^} (${r}) ==="
  kubectl get nodes -l cloud.google.com/gke-accelerator=nvidia-rtx-pro-6000 \
    -o custom-columns='NODE:.metadata.name,ZONE:.metadata.labels.topology\.kubernetes\.io/zone,PROVISIONING:.metadata.labels.cloud\.google\.com/gke-provisioning,SANDBOX:.metadata.labels.sandbox\.gke\.io/runtime'
done
```

---

## Beat 2 (`3:30 – 7:30`): `~9.5s` weight streaming, `13.44M` KV tokens & `Super-120B` on 1 GPU

> **Talk track**: _"Each Pod streams weights from regional HNS Cloud Storage
> through a bounded RAM `gcsfuse` cache (`3.6–4.6s` for `Nano-30B`) into VRAM
> via `rank_striped_read_ahead` (`5.8s`). `Nano-30B-NVFP4` leaves **`63.71 GiB`
> (`13.44M` KV tokens)** free and reaches **`3,568 tok/s`** at `c=64` (`+30.9%`
> vs. `FP8`). `Super-120B-NVFP4` peaks at **`84.19 GiB`**—exceeding an `80 GB`
> GPU—yet fits on **`1× RTX PRO 6000` (`TP=1`)** with **`972,704` KV tokens**."_

```shell
for TARGET in "americas:us-central1:0" "europe:europe-west2:1" "apac:asia-southeast1:2"; do
  IFS=: read -r p r idx <<<"${TARGET}"
  use_region "${p}" "${r}" "${idx}"
  echo "=== ${p^^} (${r}) ==="
  kubectl get pods -n "inf-${p}-online-gpu" -o wide
done

use_region "americas" "us-central1" 0
for DEPLOY in "trtllm-rtx6000-nemotron-3-nano-30b-nvfp4" "trtllm-rtx6000-nemotron-3-super-120b-nvfp4"; do
  echo "=== ${DEPLOY} ==="
  kubectl logs -n inf-americas-online-gpu "deploy/${DEPLOY}" | grep -E "\[trtllm\] Pre-warmed|rank_striped_read_ahead|Peak memory during memory usage|Allocated |Max KV cache pages|workers_ready"
done
```

---

## Beat 3 (`7:30 – 11:30`): Reasoning control, `Super-120B` tool calling, GMP HPA & internal ALB VIP

> **Talk track**: _"Every overlay enables `--reasoning_parser nano-v3`
> (`enable_thinking: false` for **`~80 ms`** direct answers),
> `--tool_parser qwen3_coder`, dual-metric GMP HPA
> (`trtllm_num_requests_waiting` and `trtllm_num_requests_running`), and
> cross-region internal ALB routing (`WATERFALL_BY_REGION` + `LEAST_REQUEST`)."_

```shell
use_region "americas" "us-central1" 0
AMER_VIP="$(NETWORK_MODE=shared-vpc "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh" vips | jq -r '.americas')"

echo "=== 1. Non-thinking mode via cross-region Internal ALB VIP (${AMER_VIP}) ==="
kubectl exec -n inf-americas-online-gpu deploy/trtllm-rtx6000-nemotron-3-nano-30b-nvfp4 -- \
  curl -s -w "\n[ VIP Latency: %{time_total}s ]\n" "http://${AMER_VIP}/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4","messages":[{"role":"user","content":"Reply in one sentence: why does NVFP4 on RTX PRO 6000 accelerate MoE inference?"}],"max_tokens":64,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' \
  | jq -Rr '. as $l | try (fromjson | "reasoning_content: \(.choices[0].message.reasoning_content)\ncontent: \(.choices[0].message.content)") catch ($l | select(length > 0))'

echo "=== 2. Single-GPU Super-120B-NVFP4 reasoning + structured tool call ==="
kubectl exec -n inf-americas-online-gpu deploy/trtllm-rtx6000-nemotron-3-super-120b-nvfp4 -- \
  curl -s http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4","messages":[{"role":"user","content":"Check GPU availability for g4-standard-48 in asia-southeast1."}],"tools":[{"type":"function","function":{"name":"check_gpu_capacity","description":"Query regional GPU availability","parameters":{"type":"object","properties":{"machine_type":{"type":"string"},"region":{"type":"string"}},"required":["machine_type","region"]}}}],"max_tokens":256,"temperature":0}' \
  | jq '{reasoning: .choices[0].message.reasoning_content, tool_calls: .choices[0].message.tool_calls}'

echo "=== 3. Dual-metric GMP HPA & live Prometheus queue gauges ==="
kubectl get hpa -n inf-americas-online-gpu
kubectl exec -n inf-americas-online-gpu deploy/trtllm-rtx6000-nemotron-3-nano-30b-nvfp4 -- \
  sh -c 'curl -s http://127.0.0.1:8000/prometheus/metrics | grep -E "^trtllm_(num_requests_waiting|num_requests_running|kv_cache_utilization)\{"'
```

---

## Beat 4 (`11:30 – 15:00`): `3.885s` GCFS pull & `46.0s` (`7.83×` faster) GKE Pod snapshot restore

> **Talk track**: _"An uncached `nvcr.io` cold start takes **`360.4s`**,
> including `~121s` of Blackwell FMHA JIT, `90`-tactic `NVFP4`/MoE autotuning,
> and CUDA graph capture. With regional Artifact Registry GCFS Image Streaming
> (**`3.885s`**) and a **`23.06 GiB` GKE Pod snapshot**, `measure_restore.sh 2`
> raises HPA `minReplicas` to `2`, restores a new replica to `Ready` in
> **`23.0s`** and first HTTP `200` in **`46.0s`** (`LOADING=0`, **`7.83×`
> faster**), and restores `minReplicas` on exit."_

```shell
use_region "americas" "us-central1" 0
kubectl get podsnapshots -n inf-americas-online-gpu \
  -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].reason,AGE:.metadata.creationTimestamp'

APP="trtllm-snap-rtx6000-nemotron-3-nano-30b-nvfp4" \
SERVED_MODEL_NAME="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" \
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/measure_restore.sh" 2
```

<!-- cspell:ignore plnwn -->

```text
POD (suffix)             NODE_AGE IMAGE                READY POD_RESTORED  FIRST_RESPONSE   LATENCY  LOADING
b-nvfp4-856985859d-plnwn    32.0s in 3.885s            23.0s        45.0s           46.0s     22.8s        0
```

---

## Post-demo teardown

Destroy all `PodSnapshot` CRs, standalone NEGs, HNS buckets, `global_lb`,
regional clusters, and `shared_network` in parallel (see
[foundation Step 3](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#step-3-tear-down-all-regional-and-shared-multi-region-resources)):

```shell
unset TF_VAR_ira_online_gpu_trtllm_image_url TRTLLM_VARIANT_SUFFIX
NETWORK_MODE="shared-vpc" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/teardown.sh" \
  --parallel "americas:us-central1:0" "europe:europe-west2:1" "apac:asia-southeast1:2"
```
