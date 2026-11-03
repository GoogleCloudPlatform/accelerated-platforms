# 15-minute live demo runbook: Global open-model inference with TensorRT-LLM, NVIDIA Nemotron-3, and GKE Pod snapshots on RTX PRO 6000

> [!IMPORTANT]
>
> Dynamic Landscape: The field of AI inference is experiencing continuous, rapid
> evolution. This document is regularly updated to reflect the latest products,
> features, and architectural patterns, ensuring it remains current with the
> advancements in AI, Google Cloud, NVIDIA TensorRT-LLM, and Google Kubernetes
> Engine.
>
> Last Update: 2026-11-04 (YYYY-MM-DD)

This runbook is a companion to
[Getting started quickly with open models and TensorRT-LLM on multi-region GKE clusters](/docs/platforms/gke/base/use-cases/inference-ref-arch/trtllm-multi-region-open-models-guide.md)
and the
[AI inference proof-of-concept (PoC) and capacity-finding guide](/docs/platforms/gke/base/use-cases/inference-ref-arch/poc-capacity-and-rapid-deployment-guide.md).
It assumes **zero pre-existing GKE clusters, buckets, or snapshots** and
**nothing pre-installed** on the presenter's machine beyond a standard Linux or
Google Cloud Shell terminal with `gcloud`. Every resource needed for the
15-minute live demo is built from scratch using
[`terraform/multi-region/`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/provision.sh)
and the Kustomize overlays in this repository.

Each regional island uses the repository's default
`resource_name_prefix = "inf"` and an isolated regional `platform_name` (`1–9`
characters per Terraform validation) without modifying tracked `*.auto.tfvars`
or `${HOME}/.kube/config`:

| Global Ring Region                   | `platform_name` | Provisioned GKE Cluster Name | Online GPU Workload Namespace | Provisioning Strategy Showcased               | Isolated Kubeconfig Path (`KUBECONFIG`)                                     |
| ------------------------------------ | --------------- | ---------------------------- | ----------------------------- | --------------------------------------------- | --------------------------------------------------------------------------- |
| **Americas (`us-central1`)**         | `americas`      | **`inf-americas`**           | **`inf-americas-online-gpu`** | **DWS `FLEX_START` + `SPOT` (`PodSnapshot`)** | `${ACP_PLATFORM_BASE_DIR}/kubernetes/kubeconfig/${PROJECT_ID}-inf-americas` |
| **Europe (`europe-west2`)**          | `europe`        | **`inf-europe`**             | **`inf-europe-online-gpu`**   | **`STANDARD` (On-Demand)**                    | `${ACP_PLATFORM_BASE_DIR}/kubernetes/kubeconfig/${PROJECT_ID}-inf-europe`   |
| **Asia-Pacific (`asia-southeast1`)** | `apac`          | **`inf-apac`**               | **`inf-apac-online-gpu`**     | **`SPOT`**                                    | `${ACP_PLATFORM_BASE_DIR}/kubernetes/kubeconfig/${PROJECT_ID}-inf-apac`     |

---

## Overview of the runbook

- **Part 1 (Automated end-to-end provisioning from scratch — start ~90–120
  minutes before the demo for all three regions, or ~40 minutes for single
  region)**:
  - **Prep Step 1 (~2 min)**: Installs pinned CLI tools (`terraform` `1.14.8`,
    `kustomize` `v5.8.3`, `sponge`, `jq`, `envsubst`) with SHA-256 checksum
    verification and clones `accelerated-platforms`.
  - **Prep Step 2 (~1 min)**: Verifies zonal `nvidia-rtx-pro-6000`
    (`g4-standard-48`, `48` vCPUs, `180 GB` DDR5 RAM, `96 GB` GDDR7)
    availability across Americas (`us-central1`), Europe (`europe-west2`), and
    Asia-Pacific (`asia-southeast1`).
  - **Prep Step 3 (~20 min per region)**: Runs
    [`terraform/multi-region/provision.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/provision.sh)
    with `ENABLE_POD_SNAPSHOTS="true"`, `ACTIVE_MIGRATION_ENABLED="false"`, and
    digest-pinned `nvcr.io/nvidia/tensorrt-llm/release:1.4.0rc2` mirroring into
    each region's Artifact Registry repository via Cloud Build `crane copy`
    (`~152s`) so GKE Image Streaming (`GCFS`) pulls it onto scale-out nodes in
    **`3.885s`**.
  - **Prep Step 4 (~20–25 min)**: Uses
    [`terraform/multi-region/helpers.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh)
    to stage **`NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4`** (`18.03 GiB`, `101s`)
    and **`NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4`** (`74.80 GiB`, `383s`) once
    into HNS Cloud Storage in `inf-americas`, replicates `Nano-30B-NVFP4`
    server-side to `inf-europe` (`191s`) and `inf-apac` (`381s`), deploys
    `trtllm` across all 3 continents, and captures a `23.06 GiB` GKE
    `PodSnapshot` (`AllSnapshotsAvailable` in `41s`).
- **Part 2 (15-minute live presentation — copy-paste & talk track)**: Four timed
  demo beats (`3.5–4 min` each) with exact copy-paste commands and a verbatim
  **Presenter Talk Track**.
- **Part 3 (Post-demo teardown)**: Runs
  [`terraform/multi-region/teardown.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/teardown.sh)
  to destroy all `PodSnapshot` CRs, HNS buckets, `online_gpu` resources,
  clusters, and Artifact Registry repositories.

---

## Part 1: Automated end-to-end provisioning from scratch (zero existing clusters)

> [!IMPORTANT]
>
> Run **Prep Steps 1–4** ahead of your live call so that all regional `trtllm`
> pods are `1/1 Running` and your `PodSnapshot` in `inf-americas` reports
> `AllSnapshotsAvailable` before you share your screen.

### Prep Step 1: Clone repository & bootstrap pinned CLI tools (`terraform`, `kustomize`, `sponge`, `jq`)

Run
[`terraform/multi-region/bootstrap_tools.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/bootstrap_tools.sh)
to install SHA-256 verified `terraform` (`1.14.8`), `kustomize` (`v5.8.3`),
`jq`, `sponge`, and `envsubst` into `${HOME}/.local/bin`:

```shell
if [[ -f "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh" ]]; then
  ACP_REPO_DIR="$(pwd)"
else
  ACP_REPO_DIR="${HOME}/accelerated-platforms"
  if [[ ! -d "${ACP_REPO_DIR}" ]]; then
    command -v git >/dev/null 2>&1 || (sudo apt-get update -qq && sudo apt-get install -y -qq git ca-certificates)
    git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git "${ACP_REPO_DIR}"
  fi
  cd "${ACP_REPO_DIR}"
fi
export ACP_REPO_DIR
export PATH="${HOME}/bin:${HOME}/.local/bin:${HOME}/google-cloud-sdk/bin:${PATH}"

"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/bootstrap_tools.sh"
```

---

### Prep Step 2: Set your project & Hugging Face token, and verify global `RTX PRO 6000` availability

```shell
export PROJECT_ID="<YOUR_PROJECT_ID>"           # <-- Replace with your Google Cloud Project ID
export HF_TOKEN="<YOUR_HUGGINGFACE_READ_TOKEN>" # <-- Replace with your hf_... read token

gcloud compute accelerator-types list \
  --project="${PROJECT_ID}" \
  --filter="name=nvidia-rtx-pro-6000 AND zone:(us-central1-* europe-west2-* asia-southeast1-*)" \
  --format="table(name,zone.basename(),description)"
```

---

### Prep Step 3: Provision regional GKE Autopilot islands & mirror TensorRT-LLM `1.4.0rc2`

Run
[`terraform/multi-region/provision.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/provision.sh)
to stand up all three regional islands (`inf-americas`, `inf-europe`,
`inf-apac`) with non-overlapping CIDRs, `optimizeRulePriority: false` on custom
`ComputeClass` resources, GKE Pod snapshots enabled, `HF_TOKEN` stored in Secret
Manager, and digest-pinned `tensorrt-llm/release:1.4.0rc2` mirrored into each
regional Artifact Registry repository:

```shell
# Tip: For a single-region demo, keep only "americas:us-central1"
RING_TARGETS=(
  "americas:us-central1"
  "europe:europe-west2"
  "apac:asia-southeast1"
)

ENABLE_POD_SNAPSHOTS="true" \
ACTIVE_MIGRATION_ENABLED="false" \
MIRROR_IMAGES="nvcr.io/nvidia/tensorrt-llm/release:1.4.0rc2@sha256:93a3eaf1fa574813d608a7147735134bcfbd06d18d1aa98e8ee0d5da09e51e3a=tensorrt-llm/release:1.4.0rc2" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/provision.sh" \
  "${RING_TARGETS[@]}"
```

---

### Prep Step 4: Stage Nemotron-3 checkpoints & deploy `trtllm` + `PodSnapshot` workloads

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
export ACCELERATOR_TYPE="rtx-pro-6000"

# 1. Stage Nano-30B-NVFP4 (18.03 GiB) and Super-120B-NVFP4 (74.80 GiB) once in inf-americas
use_region "americas" "us-central1"
stage_hf_model "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
stage_hf_model "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4"

# 2. Replicate Nano-30B-NVFP4 server-side to Europe (~191s) and Asia-Pacific (~381s)
replicate_hf_model "americas" "europe" "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" &
rep_eu_pid=$!
replicate_hf_model "americas" "apac" "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" &
rep_ap_pid=$!

# 3. Deploy Americas Path A (Nano-30B-NVFP4 + Super-120B-NVFP4) and Path B (PodSnapshot fast restore)
export TF_VAR_ira_online_gpu_trtllm_image_url="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/tensorrt-llm/release:1.4.0rc2"
export TF_VAR_ira_online_gpu_trtllm_podsnapshot_image_url="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/tensorrt-llm/release:1.4.0rc2"

for MODEL in \
  "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" \
  "nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4"; do
  HF_MODEL_ID="${MODEL}" \
    "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
done

HF_MODEL_ID="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" \
  "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm-podsnapshot-fast-restore/deployment_apply.sh"

# 4. Wait for replication (fail-fast on error) and deploy Nano-30B-NVFP4 in Europe & Asia-Pacific
wait "${rep_eu_pid}"
wait "${rep_ap_pid}"

for TARGET in "europe:europe-west2" "apac:asia-southeast1"; do
  platform_name="${TARGET%%:*}"
  region="${TARGET##*:}"
  use_region "${platform_name}" "${region}"
  export TF_VAR_ira_online_gpu_trtllm_image_url="${region}-docker.pkg.dev/${PROJECT_ID}/inf-${platform_name}/tensorrt-llm/release:1.4.0rc2"
  HF_MODEL_ID="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4" \
    "${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/trtllm/deployment_apply.sh"
done
```

#### Pre-flight readiness & `AllSnapshotsAvailable` gate (run before starting the 15-min call)

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"

for TARGET in "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"; do
  platform_name="${TARGET%%:*}"
  region="${TARGET##*:}"
  use_region "${platform_name}" "${region}"
  echo "=== ${platform_name} (${region}) ==="
  kubectl get pods -n "inf-${platform_name}-online-gpu"
done

use_region "americas" "us-central1"
kubectl get podsnapshots -n inf-americas-online-gpu
```

---

## Part 2: 15-minute live demo & presenter talk track

---

### Beat 1 (Minutes 0:00 – 3:30): Global `RTX PRO 6000` capacity farming & Fluid Compute consumption diversity

#### Presenter talk track

> _"When teams deploy open-weight reasoning models on TensorRT-LLM, they often
> encounter two operational bottlenecks: single-region GPU stockouts and 8-GPU
> node placement constraints._
>
> _This architecture addresses both. First, by pairing **NVIDIA RTX PRO 6000
> Blackwell Server Edition (`g4-standard-48`, 96 GB GDDR7, `SM120`)** with
> Blackwell-native **`NVFP4` quantization**, both **NVIDIA Nemotron-3 Nano 30B
> (`A3B`)** and **Nemotron-3 Super 120B (`A12B`)** fit on a **single 96 GB GPU
> (`TP=1`)**._
>
> _Second, instead of relying on a single zone or consumption model, we deploy a
> 3-continent GKE ring across `us-central1`, `europe-west2`, and
> `asia-southeast1` where GKE's `gpu-rtx-pro-6000-96gb-x1` `ComputeClass`
> cascades across `On-Demand`, `DWS Flex-Start`, and `Spot`. Let's inspect the
> zonal SKU footprint and the live node provisioning modes across all three
> clusters."_

#### Copy-paste command 1A (verify zonal `RTX PRO 6000` availability across the ring)

```shell
gcloud compute accelerator-types list \
  --project="${PROJECT_ID}" \
  --filter="name=nvidia-rtx-pro-6000 AND zone:(us-central1-* europe-west2-* asia-southeast1-*)" \
  --format="table(name,zone.basename(),description)"
```

#### Copy-paste command 1B (show all 3 consumption models running simultaneously)

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"

for TARGET in "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"; do
  platform_name="${TARGET%%:*}"
  region="${TARGET##*:}"
  use_region "${platform_name}" "${region}"
  echo "=== ${platform_name^^} (${region}) ==="
  kubectl get nodes -l cloud.google.com/gke-accelerator=nvidia-rtx-pro-6000 \
    -o custom-columns='NODE:.metadata.name,ZONE:.metadata.labels.topology\.kubernetes\.io/zone,PROVISIONING:.metadata.labels.cloud\.google\.com/gke-provisioning,SPOT:.metadata.labels.cloud\.google\.com/gke-spot,SANDBOX:.metadata.labels.sandbox\.gke\.io/runtime'
done
```

#### What to point out in the output

- **`asia-southeast1`**: Provisioned on low-cost **`Spot`**
  (`PROVISIONING=spot`).
- **`europe-west2`**: Where Spot was constrained, GKE Autopilot automatically
  used **`Standard` (On-Demand)** in `123s`.
- **`us-central1`**: Where On-Demand hit a transient zonal stockout, GKE
  cascaded into **DWS `flex-start`** for standard pods and **`spot` (`gvisor`)**
  for the `PodSnapshot` pool with zero manual YAML changes.

---

### Beat 2 (Minutes 3:30 – 7:30): Fast weight streaming (`~9.5s`), `13.44M`-token hybrid Mamba-2 cache & `Super-120B` on 1 GPU

#### Presenter talk track

> _"Let's inspect the live TensorRT-LLM `1.4.0rc2` pods across all three
> continents._
>
> _In Path A (`trtllm/`), each pod mounts its regional **Hierarchical Namespace
> Cloud Storage** bucket through a **RAM-backed Cloud Storage FUSE file cache**
> (`180 GB` DDR5 host RAM on `g4-standard-48`), pre-warms all `.safetensors`
> shards in parallel into RAM at **4 to 5 GiB/s** (`3.6–4.6 seconds` for
> `Nano-30B-NVFP4`), and loads them into GPU VRAM via TensorRT-LLM's
> `rank_striped_read_ahead` loader in **`5.8 seconds`**._
>
> _Look at the single-GPU memory headroom with `96 GB` GDDR7 + `NVFP4`:_
>
> - _On **`Nemotron-3-Nano-30B-A3B-NVFP4`** (`31.6B` total, `3.2B` active
>   parameters per token), weights occupy **`20.01 GiB`**, leaving
>   **`63.71 GiB`** for `MambaHybridCacheManagerV2`—**`13.44 million` attention
>   KV tokens** on a single GPU and **`3,568 tokens/sec`** at concurrency 64
>   (`+30.9%` higher throughput than `FP8`, with `3.9 ms` single-stream TPOT)._
> - _On **`Nemotron-3-Super-120B-A12B-NVFP4`** (`120.6B` total / `12.6B` active
>   LatentMoE) in `inf-americas`, memory profiling peaks at **`84.19 GiB`**,
>   exceeding an `80 GB H100`, yet runs on **1 `RTX PRO 6000` (`TP=1`)** with
>   **`972,704` KV tokens** of cache headroom and **`74 tokens/sec`**
>   single-stream (`714 tok/s` at `c=32`)."_

#### Copy-paste command 2A (show live pods across Americas, Europe, and Asia-Pacific)

```shell
for TARGET in "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"; do
  platform_name="${TARGET%%:*}"
  region="${TARGET##*:}"
  use_region "${platform_name}" "${region}"
  echo "=== ${platform_name^^} (${region}) ==="
  kubectl get pods -n "inf-${platform_name}-online-gpu" -o wide
done
```

#### Copy-paste command 2B (inspect live RAM pre-warm, `rank_striped_read_ahead` & `MambaHybridCacheManagerV2` logs)

```shell
use_region "americas" "us-central1"

for DEPLOY in \
  "trtllm-rtx6000-nemotron-3-nano-30b-nvfp4" \
  "trtllm-rtx6000-nemotron-3-super-120b-nvfp4"; do
  echo "=== ${DEPLOY} ==="
  kubectl logs -n inf-americas-online-gpu "deploy/${DEPLOY}" | python3 - << 'EOF'
import sys
keys = (
    "[trtllm] Pre-warmed",
    "rank_striped_read_ahead",
    "Peak memory during memory usage profiling",
    "Allocated ",
    "Max KV cache pages",
    "workers_ready",
)
for line in sys.stdin:
    if any(k in line for k in keys):
        sys.stdout.write(line)
EOF
done
```

---

### Beat 3 (Minutes 7:30 – 11:30): Reasoning control, agentic tool calling, GMP queue-depth HPA & multi-region health

#### Presenter talk track

> _"Every TensorRT-LLM overlay in this repository is pre-configured for agentic
> serving:_
>
> 1. _**Controllable reasoning (`--reasoning_parser nano-v3`)**: Nemotron-3
>    emits chain-of-thought in `reasoning_content` by default, or accepts
>    `enable_thinking: false` for **`80 ms` non-thinking responses**._
> 2. _**Structured tool calling (`--tool_parser qwen3_coder`)**: Native OpenAI
>    function calling on both `Nano-30B` and single-GPU `Super-120B`._
> 3. _**Dual-metric GMP HPA (`enable_iter_perf_stats: true`)**: TensorRT-LLM
>    `1.4.0rc2` requires both `return_perf_metrics: true` and
>    `enable_iter_perf_stats: true` in `extra-llm-api-config.yaml` to export
>    `trtllm_num_requests_waiting` and `trtllm_num_requests_running` gauges to
>    Google Cloud Managed Service for Prometheus._
> 4. _**Multi-region active-active islands**: Each regional island serves
>    independently and exposes `/health` and `/prometheus/metrics` for queue-
>    and RTT-aware global routing."_

#### Copy-paste command 3A (instant non-thinking mode + structured tool call on `Super-120B`)

```shell
use_region "americas" "us-central1"

echo "=== 1. Nano-30B-NVFP4 Instant Non-Thinking Mode (enable_thinking: false) ==="
kubectl exec -n inf-americas-online-gpu deploy/trtllm-rtx6000-nemotron-3-nano-30b-nvfp4 -- \
  curl -s -w "\n[ Pod Latency: %{time_total}s ]\n" http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4","messages":[{"role":"user","content":"Reply in one sentence: why does NVFP4 on RTX PRO 6000 accelerate MoE inference?"}],"max_tokens":64,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}' \
  | python3 - << 'EOF'
import json, sys
raw = sys.stdin.read()
body, lat = raw.rsplit("\n[", 1)
data = json.loads(body)
msg = data["choices"][0]["message"]
print("reasoning_content:", msg.get("reasoning_content"))
print("content:", msg["content"].strip())
print("[" + lat.strip())
EOF

echo "=== 2. Single-GPU Super-120B-NVFP4 Reasoning + Structured Tool Calling ==="
kubectl exec -n inf-americas-online-gpu deploy/trtllm-rtx6000-nemotron-3-super-120b-nvfp4 -- \
  curl -s http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4","messages":[{"role":"user","content":"Check GPU availability for g4-standard-48 in asia-southeast1."}],"tools":[{"type":"function","function":{"name":"check_gpu_capacity","description":"Query regional GPU availability","parameters":{"type":"object","properties":{"machine_type":{"type":"string"},"region":{"type":"string"}},"required":["machine_type","region"]}}}],"max_tokens":256,"temperature":0}' \
  | jq '{reasoning: .choices[0].message.reasoning_content, tool_calls: .choices[0].message.tool_calls}'
```

#### Copy-paste command 3B (inspect live GMP HPA & Prometheus queue gauges across all 3 islands)

```shell
use_region "americas" "us-central1"
echo "=== Dual-Metric GMP HorizontalPodAutoscaler Status (inf-americas) ==="
kubectl get hpa -n inf-americas-online-gpu

for TARGET in "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"; do
  platform_name="${TARGET%%:*}"
  region="${TARGET##*:}"
  use_region "${platform_name}" "${region}"
  echo "=== [${platform_name^^} / ${region}] Live Queue Metrics + Inference ==="
  kubectl exec -n "inf-${platform_name}-online-gpu" deploy/trtllm-rtx6000-nemotron-3-nano-30b-nvfp4 -- sh -c '
    curl -s http://127.0.0.1:8000/prometheus/metrics | grep -E "^trtllm_(num_requests_waiting|num_requests_running|kv_cache_utilization)\{"
    curl -s http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" \
      -d "{\"model\":\"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4\",\"messages\":[{\"role\":\"user\",\"content\":\"Say hello from TensorRT-LLM in one short sentence.\"}],\"max_tokens\":32,\"temperature\":0,\"chat_template_kwargs\":{\"enable_thinking\":false}}"
  ' | python3 - << 'EOF'
import json, sys
lines = [l for l in sys.stdin.read().splitlines() if l.strip()]
for m in lines[:-1]:
    print(m)
print("Response:", json.loads(lines[-1])["choices"][0]["message"]["content"].strip())
EOF
done
```

---

### Beat 4 (Minutes 11:30 – 15:00): `3.885s` GCFS image pull & `46.0s` (`7.83×` faster) horizontal scale-out with GKE Pod snapshots

#### Presenter talk track

> _"Now let's demonstrate sub-minute horizontal scale-out for TensorRT-LLM._
>
> _An unoptimized TensorRT-LLM cold start takes **`360.4 seconds`
> (`6 minutes`)**: **`182.9s`** to pull the `17.26 GB` NGC container from
> `nvcr.io`, plus **`~177s`** to stream weights and run Blackwell
> `sampling_prewarm` (`46s`), `TRTLLM-Gen FMHA` JIT (`16s`), `90`-tactic
> `NVFP4`/MoE `autotuner` (`33s`), Mamba warmup (`25s`), and CUDA graph
> capture._
>
> _When we combine **regional Artifact Registry + GCFS Image Streaming** with
> **GKE Pod snapshots** (`23.06 GiB` in HNS Cloud Storage, captured after one
> warm-up completion and `/model-cache` cleanup), scaling from `1` to `2`
> replicas onto a new `g4-standard-48` node streams the `17.26 GB` image in
> **`3.885 seconds` (`47.1×` faster)**, reaches `Ready` in **`23.0s`**,
> `PodRestored` in **`45.0s`**, and returns its first `/v1/chat/completions`
> response in **`46.0s`** (`LOADING=0`, **`7.83×` faster** end-to-end, followed
> by `78.9 ms` steady-state latency)."_

#### Copy-paste command 4A (verify `AllSnapshotsAvailable` in `inf-americas`)

```shell
use_region "americas" "us-central1"
kubectl --namespace=inf-americas-online-gpu get podsnapshots \
  --output=custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].reason,CHECKPOINT:.status.conditions[?(@.type=="Checkpoint")].reason,AGE:.metadata.creationTimestamp'
```

#### Copy-paste command 4B (live scale-out `1 -> 2` with `measure_restore.sh 2`)

> [!TIP]
>
> Always test GKE `PodSnapshot` restore on a 1-GPU node via horizontal scale-out
> (`measure_restore.sh 2`) or `--replicas=0` -> wait `6s` -> `--replicas=1`
> rather than `kubectl delete pod --wait=false`, which can race on
> `/dev/nvidia0` while the terminating pod is still releasing the GPU.

```shell
use_region "americas" "us-central1"
export TF_VAR_ira_online_gpu_trtllm_podsnapshot_image_url="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/tensorrt-llm/release:1.4.0rc2"
export TRTLLM_VARIANT="rtx6000-nemotron-3-nano-30b-nvfp4"
export SERVED_MODEL_NAME="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/trtllm-podsnapshot-fast-restore/measure_restore.sh" 2
```

#### Expected live output (`measure_restore.sh 2`)

<!-- cspell:ignore plnwn -->

```text
POD (suffix)             NODE_AGE IMAGE                READY POD_RESTORED  FIRST_RESPONSE   LATENCY  LOADING
b-nvfp4-856985859d-plnwn    32.0s in 3.885s            23.0s        45.0s           46.0s     22.8s        0
```

#### Copy-paste command 4C (confirm `78.9 ms` steady-state latency on the newly restored pod)

```shell
use_region "americas" "us-central1"
NEW_POD="$(kubectl get pods -n inf-americas-online-gpu \
  -l app=trtllm-snap-rtx6000-nemotron-3-nano-30b-nvfp4 \
  --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')"
echo "Sending follow-up completion to restored pod ${NEW_POD}..."
kubectl exec -n inf-americas-online-gpu "${NEW_POD}" -- \
  curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s (pre-warmed inside snapshot)\n" \
  http://127.0.0.1:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4","messages":[{"role":"user","content":"The capital of France is"}],"max_tokens":8,"temperature":0,"chat_template_kwargs":{"enable_thinking":false}}'
```

---

## Part 3: Post-demo teardown

Run
[`terraform/multi-region/teardown.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/teardown.sh)
to delete all `PodSnapshot` CRs, empty regional HNS buckets (failing fast on IAM
or authentication errors while skipping already-deleted `404` buckets), reuse
`core/initialize` backend generation to destroy `online_gpu`, and tear down each
regional GKE Autopilot cluster and Artifact Registry repository:

```shell
unset TF_VAR_ira_online_gpu_trtllm_image_url TF_VAR_ira_online_gpu_trtllm_podsnapshot_image_url

RING_TARGETS=(
  "americas:us-central1"
  "europe:europe-west2"
  "apac:asia-southeast1"
)

"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/teardown.sh" \
  "${RING_TARGETS[@]}"
```
