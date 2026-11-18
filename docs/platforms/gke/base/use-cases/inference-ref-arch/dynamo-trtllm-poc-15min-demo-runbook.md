# 15-minute Presenter Beat Sheet: Multi-region NVIDIA Dynamo KV routing, host KV cache offloading, disaggregated P/D, and cross-region failover on GKE

> [!IMPORTANT]
>
> Dynamic Landscape: The field of AI inference is experiencing continuous, rapid
> evolution. This document is regularly updated to reflect the latest products,
> features, and architectural patterns across Google Cloud, NVIDIA Dynamo,
> NVIDIA TensorRT-LLM, and Google Kubernetes Engine (GKE).
>
> Last Update: 2026-11-08 (YYYY-MM-DD)

This Presenter Beat Sheet accompanies the
[NVIDIA Dynamo and TensorRT-LLM reference architecture on multi-region GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md).
Complete **Part 1 (Pre-Demo Cluster Provisioning)** in the
[Multi-region GKE inference foundation quick-start](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#quick-start-multi-region-provisioning-and-teardown)
with `NETWORK_MODE="shared-vpc"` and `ACTIVE_MIGRATION_ENABLED="false"` across
`"americas:us-central1:0"` and `"europe:europe-west2:1"` (`6` GPUs total, as
shown in the live demo; optionally add `"apac:asia-southeast1:2"` for a third
island, which the pre-warm and teardown blocks below detect automatically):

| Region (`platform_name`)            | Cluster (`Namespace`)                         | Pre-Warmed NVIDIA Dynamo Overlay(s) (`RTX PRO 6000`, `g4-standard-48`)                                                                                | Beat(s)     |
| ----------------------------------- | --------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| **Americas (`americas`)**           | Americas cluster (`online-gpu` namespace)     | 1. `kv-routing/rtx-pro-6000-qwen3-32b-nvfp4` (`2` GPUs)<br>2. `disaggregated-pd/rtx-pro-6000-nvidia-nemotron-3-nano-30b-a3b-nvfp4` (`2P1D`, `3` GPUs) | **1, 3, 4** |
| **Europe (`europe`)**               | Europe cluster (`online-gpu` namespace)       | `host-offloading/rtx-pro-6000-qwen3-32b-nvfp4` (`1` GPU + `80 GB` pinned host memory)                                                                 | **2, 4**    |
| **Asia-Pacific (`apac`, optional)** | Asia-Pacific cluster (`online-gpu` namespace) | `kv-routing/rtx-pro-6000-qwen3-32b-nvfp4` (`2` GPUs)                                                                                                  | **4**       |

---

## Pre-demo workload pre-warm (`~25–30 min` before screen share)

Build `gpu/dynamo-trtllm:latest` once via
[`terraform/images/gpu/dynamo_trtllm`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/dynamo_trtllm/cloudbuild.tf),
mirror it to peer regions, stage `NVFP4` weights, deploy the Dynamo stacks, and
attach the cross-region internal Application Load Balancer:

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
export ACCELERATOR_TYPE="rtx-pro-6000"
RING_TARGETS=("americas:us-central1:0" "europe:europe-west2:1")
[[ -f "$(mr_kubeconfig apac)" ]] && RING_TARGETS+=("apac:asia-southeast1:2")

use_region "americas" "us-central1" 0
AMER_CHECKOUT="$(mr_worktree_dir americas)"
[[ -e "${AMER_CHECKOUT}/.git" ]] || AMER_CHECKOUT="${ACP_REPO_DIR}"
mr_terraform_apply "${AMER_CHECKOUT}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/dynamo_trtllm" "${AMER_CHECKOUT}"

SRC_IMG="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/gpu/dynamo-trtllm:latest"
bg_jobs=()
mirror_image_to_ar "europe-west2" "europe" "${SRC_IMG}" "gpu/dynamo-trtllm:latest" & bg_jobs+=($!)
if [[ -f "$(mr_kubeconfig apac)" ]]; then
  mirror_image_to_ar "asia-southeast1" "apac" "${SRC_IMG}" "gpu/dynamo-trtllm:latest" & bg_jobs+=($!)
fi
stage_hf_model "nvidia/Qwen3-32B-NVFP4"
stage_hf_model "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
replicate_hf_model "americas" "europe" "nvidia/Qwen3-32B-NVFP4" & bg_jobs+=($!)
if [[ -f "$(mr_kubeconfig apac)" ]]; then
  replicate_hf_model "americas" "apac" "nvidia/Qwen3-32B-NVFP4" & bg_jobs+=($!)
fi

DYNAMO_APPLY="${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/dynamo-trtllm/deployment_apply.sh"
DYNAMO_MODE="kv-routing" HF_MODEL_ID="nvidia/qwen3-32b-nvfp4" "${DYNAMO_APPLY}"
DYNAMO_MODE="disaggregated-pd" HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4" "${DYNAMO_APPLY}"

for job_id in "${bg_jobs[@]}"; do wait "${job_id}"; done
use_region "europe" "europe-west2" 1 && DYNAMO_MODE="host-offloading" HF_MODEL_ID="nvidia/qwen3-32b-nvfp4" "${DYNAMO_APPLY}"
if [[ -f "$(mr_kubeconfig apac)" ]]; then
  use_region "apac" "asia-southeast1" 2 && DYNAMO_MODE="kv-routing" HF_MODEL_ID="nvidia/qwen3-32b-nvfp4" "${DYNAMO_APPLY}"
fi

for TARGET in "${RING_TARGETS[@]}"; do
  IFS=: read -r p r idx <<<"${TARGET}" && use_region "${p}" "${r}" "${idx}"
  kubectl wait --for=condition=Available deploy --all -n "inf-${p}-online-gpu" --timeout=1800s
  echo "=== ${p^^} (${r}) ===" && kubectl get pods -n "inf-${p}-online-gpu" -o wide
done

expose_service_neg "americas" "inf-americas-online-gpu" "dynamo-frontend-rtx6000-qwen3-32b-nvfp4" "8000" "dynamo"
expose_service_neg "europe" "inf-europe-online-gpu" "dynamo-frontend-host-rtx6000-qwen3-32b-nvfp4" "8000" "dynamo"
if [[ -f "$(mr_kubeconfig apac)" ]]; then
  expose_service_neg "apac" "inf-apac-online-gpu" "dynamo-frontend-rtx6000-qwen3-32b-nvfp4" "8000" "dynamo"
fi
# Health-check the model, not the frontend: /v1/models/<model>/ready answers 503 while the model has
# no usable worker and 404 once its last worker is gone, so a region that lost its GPUs fails the
# check and traffic fails over. The frontend's /health stays 200 with zero workers.
printf '%s\n' '{"dynamo":{"health_check_path":"/v1/models/nvidia/Qwen3-32B-NVFP4/ready","health_check_port":8000,"max_in_flight_requests_per_endpoint":16}}' >/tmp/dynamo-backends.json
NETWORK_MODE="shared-vpc" "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh" \
  apply --backends /tmp/dynamo-backends.json --active dynamo
```

---

## Beat 1 (`0:00 – 3:45`): KV-cache-aware prefix routing (warm follow-ups `~20×` faster than cold)

> **Talk track**: _"On `nvidia/Qwen3-32B-NVFP4` (`128 KiB` of KV cache per
> token), a `~10.7K`-token document is `~1.3 GiB` of KV state. Two documents
> arrive cold on two workers. Dynamo's KV router (`--router-mode kv`) tracks
> which worker holds which `32`-token blocks, so every follow-up turn lands on
> the worker that already has its prefix and skips the prefill."_
>
> In our validation run (`us-central1`, `2` workers), the cold turns took
> `946.8 ms` and `1,192.7 ms`, and all four follow-up turns took `48.8–53.2 ms`
> with `10,683–10,705` of `~10,720` prompt tokens served from cache. The
> comparison with round-robin routing (`11.68×` faster `p95` TTFT) is a
> reference benchmark from the
> [reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md#3-summary-of-measured-benchmarks-on-gke-g4-standard-48);
> this beat doesn't measure it.

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
use_region "americas" "us-central1" 0
kubectl get pods -n inf-americas-online-gpu -l app.kubernetes.io/part-of=dynamo-kv-rtx6000-qwen3-32b-nvfp4 -o wide

kubectl exec -i -n inf-americas-online-gpu deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 -- python3 - <<'PY'
import json, random, time, urllib.request
docs = [f"[SPEC-{i}] " + ("NVIDIA Dynamo on GKE streams 32-token KV block hashes from TensorRT-LLM workers on RTX PRO 6000 96GB GPUs to a Rust radix-tree router. " * 260) for i in range(2)]
def ask(msgs):
    req = urllib.request.Request("http://127.0.0.1:8000/v1/chat/completions", headers={"Content-Type": "application/json"},
        data=json.dumps({"model": "nvidia/Qwen3-32B-NVFP4", "messages": msgs, "max_tokens": 24, "temperature": 0.0, "stream": True, "stream_options": {"include_usage": True}}).encode())
    t0, ttft, u = time.perf_counter(), None, {}
    for raw in urllib.request.urlopen(req, timeout=120):
        s = raw.decode().strip()
        if s.startswith("data: ") and s != "data: [DONE]":
            c = json.loads(s[6:])
            if c.get("choices") and c["choices"][0].get("delta", {}).get("content") and ttft is None:
                ttft = (time.perf_counter() - t0) * 1000.0
            u = c.get("usage") or u
    return ttft, u.get("prompt_tokens", 0), (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
for i, d in enumerate(docs):
    t, p, c = ask([{"role": "user", "content": d + "\nSummarize the router in one sentence."}])
    print(f"Doc {i} | Turn 1 (Cold): TTFT={t:6.1f} ms | prompt={p} | cached={c}")
for turn in (2, 3):
    for i, d in enumerate(docs):
        t, p, c = ask([{"role": "user", "content": d + "\nSummarize the router in one sentence."},
                       {"role": "assistant", "content": "Dynamo routes via a radix tree of 32-token KV hashes."},
                       {"role": "user", "content": f"Turn {turn}: Which GPU and block size are used?"}])
        print(f"Doc {i} | Turn {turn} (Warm): TTFT={t:6.1f} ms | prompt={p} | cached={c}")
PY
kubectl exec -n inf-americas-online-gpu deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 -- \
  sh -c 'curl -fsS http://127.0.0.1:8000/metrics | grep -E "^dynamo_frontend_(cached_tokens_sum|requests_total)"'
```

---

## Beat 2 (`3:45 – 7:30`): Host KV cache offloading (evicted sessions come back `22–30×` faster)

> **Talk track**: _"Each `g4-standard-48` VM pairs `96 GB` GDDR7 with `180 GiB`
> of VM memory. The `host-offloading` overlay gives TensorRT-LLM an `80 GB`
> pinned host KV cache (`host_cache_size`), so blocks evicted from GPU memory
> move to host memory instead of being dropped: `470,016` KV tokens on the GPU
> plus `610,336` in host memory. We prefill a `~22K`-token session, push it out
> of GPU memory with `~630K` tokens of other sessions, and ask again:
> TensorRT-LLM copies the blocks back over PCIe instead of recomputing them."_
>
> In our validation run (`europe-west2`), this block measured `2,532.7 ms` cold
> and `84.3 ms` on recall after eviction (`21,713` of `21,714` prompt tokens
> served from cache, `~30×`). Two earlier runs with `14,110`-token sessions
> measured `1,457.8 ms` and `1,385.2 ms` cold against `64.1 ms` and `63.8 ms` on
> recall. Your numbers depend on the prompt length and the GPU's load.

Show the two KV cache tiers that the worker allocated (`primary` = GPU,
`secondary` = host memory, in `32`-token blocks):

```shell
use_region "europe" "europe-west2" 1
kubectl logs -n inf-europe-online-gpu deploy/dynamo-trtllm-worker-host-rtx6000-qwen3-32b-nvfp4 \
  -c inference-server | grep -E "primary blocks=[0-9]+, secondary blocks=[1-9]" | tail -n 1
```

Measure cold, GPU-resident, and recalled-from-host Time to First Token (`~2`
minutes, most of it filling the GPU with other sessions):

```shell
kubectl exec -i -n inf-europe-online-gpu deploy/dynamo-frontend-host-rtx6000-qwen3-32b-nvfp4 -- python3 - <<'PY'
import json, random, time, urllib.request
URL = "http://127.0.0.1:8000/v1/chat/completions"
def ttft(tag):
    doc = f"[{tag}] " + " ".join(f"{tag}-token-{i}" for i in range(1900)) + "\nSummarize in one sentence."
    body = json.dumps({"model": "nvidia/Qwen3-32B-NVFP4", "messages": [{"role": "user", "content": doc}],
                       "max_tokens": 8, "temperature": 0, "stream": True,
                       "stream_options": {"include_usage": True}}).encode()
    t0, first, usage = time.perf_counter(), None, {}
    for raw in urllib.request.urlopen(urllib.request.Request(URL, body, {"Content-Type": "application/json"}), timeout=600):
        line = raw.decode().strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        chunk = json.loads(line[6:])
        if first is None and chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
            first = time.perf_counter()
        usage = chunk.get("usage") or usage
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
    return (first - t0) * 1000, usage.get("prompt_tokens"), cached
run = "%04x" % random.randrange(16**4)  # new prompts on every run, so the first one is cold
session = f"SESSION-{run}"
cold = ttft(session)
print("cold     : TTFT=%7.1f ms prompt=%s cached=%s" % cold)
print("GPU hit  : TTFT=%7.1f ms prompt=%s cached=%s" % ttft(session))
fillers = int(1.3 * 470016 / cold[1]) + 1  # 1.3x the 470,016-token GPU KV cache
for i in range(fillers):
    ttft(f"FILL-{run}-{i}")
print(f"evicted with {fillers} other sessions")
print("recall   : TTFT=%7.1f ms prompt=%s cached=%s" % ttft(session))
PY
```

---

## Beat 3 (`7:30 – 11:30`): Disaggregated P/D on hybrid Mamba-2 Nemotron-3 (`2P1D`, KV and SSM state over `UCX`)

> **Talk track**: _"Disaggregation runs prefill and decode on separate GPUs, so
> long prompts don't stall the token stream of requests that are already
> decoding. `Nemotron-3-Nano-30B-A3B-NVFP4` has only `6` attention layers
> (`3.00 KiB` of KV cache per token, `42.7×` less than `Qwen3-32B`), so two
> prefill workers hand KV cache and Mamba-2 state to one decode worker over
> standard VPC networking with TensorRT-LLM's C++ `UCX` transceiver."_
>
> This beat shows the transfer managers in the prefill logs and sends one
> tool-calling request through the `2P1D` stack. In our validation run
> (`us-central1`), it returned the expected `check_gpu_availability` tool call
> in `3.4 s` end to end (up to `512` tokens, including reasoning). The burst
> numbers (`28.21×` tighter `p99` ITL for `Qwen3-32B` under `4 × 8.3K` prefills,
> `199.15 ms` `p50` TTFT and `3.81 ms` `p50` ITL for `Nemotron-3`) are reference
> benchmarks from the
> [reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md#3-summary-of-measured-benchmarks-on-gke-g4-standard-48);
> this beat doesn't measure them.

```shell
use_region "americas" "us-central1" 0
kubectl get pods -n inf-americas-online-gpu -l app.kubernetes.io/part-of=dynamo-pd-rtx6000-nemotron3-30b-nvfp4 -o wide
kubectl logs -n inf-americas-online-gpu deploy/dynamo-trtllm-prefill-pd-rtx6000-nemotron3-30b-nvfp4 \
  -c inference-server | grep -E "Max KV cache blocks|CacheTransBufferManager|RnnCacheTransBufferManager|Disagg server" | tail -n 8

kubectl exec -i -n inf-americas-online-gpu deploy/dynamo-frontend-pd-rtx6000-nemotron3-30b-nvfp4 -- python3 - <<'PY'
import json, random, time, urllib.request
payload = {"model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4", "max_tokens": 512, "temperature": 0,
           "messages": [{"role": "user", "content": "Check Spot GPU availability for g4-standard-48 in us-central1 and europe-west2."}],
           "tools": [{"type": "function", "function": {"name": "check_gpu_availability",
               "parameters": {"type": "object", "properties": {"machine_type": {"type": "string"}, "regions": {"type": "array", "items": {"type": "string"}}}, "required": ["machine_type", "regions"]}}}]}
t0 = time.perf_counter()
req = urllib.request.Request("http://127.0.0.1:8000/v1/chat/completions", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
msg = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())["choices"][0]["message"]
print("reasoning:", (msg.get("reasoning_content") or "").strip(), "\ntool_calls:", json.dumps(msg.get("tool_calls")), f"\n[ 2P1D Latency: {time.perf_counter()-t0:.3f}s ]")
PY
```

---

## Beat 4 (`11:30 – 15:00`): Live cross-region internal ALB failover & local KV re-hydration

> **Talk track**: _"Each region is an independent Dynamo island: its own router,
> workers, and KV cache, with no cross-region state in steady state.
> `global_lb.sh` puts one cross-region internal Application Load Balancer in
> front of all islands (`WATERFALL_BY_REGION` + `LEAST_REQUEST`) and
> health-checks each region's model, not just its frontend. When we drain the
> Americas island, the same Americas VIP fails over to a healthy island: Turn 1
> rebuilds the KV cache there, and Turn 2 is a cache hit again."_
>
> In our validation run (`us-central1` and `europe-west2`), the Americas VIP
> served Turn 1 in `311.7 ms` and Turn 2 in `53.2 ms` (`3,969` tokens cached)
> from the Americas island. After the drain, the same VIP served Turn 1 in
> `618.2 ms` (cold) and Turn 2 in `417.1 ms` (`3,969` tokens cached) from the
> Europe island, including the cross-region round trip. The Stretched Layer
> comparisons (`6.47×` slower warm TTFT, `42.22 s` WAN P/D) are reference
> benchmarks from the
> [reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md#6-multi-region-gke-architectural-trade-offs);
> this beat doesn't measure them.

```shell
use_region "americas" "us-central1" 0
AMER_VIP="$(NETWORK_MODE=shared-vpc "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh" vips | jq -r '.americas')"
LB_BS="${TF_VAR_resource_name_prefix:-inf}-${MR_ENVIRONMENT_NAME:-mr}-lb-dynamo"

# Ensure a lightweight CPU client Pod exists in inf-americas-online-gpu so VIP
# probes stay independent of Americas GPU capacity and worker scale-downs.
if ! kubectl get deploy/vip-probe -n inf-americas-online-gpu >/dev/null 2>&1; then
  kubectl create deployment vip-probe -n inf-americas-online-gpu --image=python:3.12-slim -- sleep infinity
fi
kubectl rollout status deploy/vip-probe -n inf-americas-online-gpu --timeout=180s

probe_vip() {
  kubectl exec -i -n inf-americas-online-gpu deploy/vip-probe -- python3 - "${AMER_VIP}" <<'PY'
import json, sys, time, urllib.request
doc = "[VIP-SESSION] " + ("Regional GKE islands pair local Dynamo KV routing with cross-region internal ALB failover. " * 220)
for label, q in [("Turn 1", "Summarize regional island isolation in one sentence."), ("Turn 2", "How does Turn 2 achieve warm KV hits after failover?")]:
    req = urllib.request.Request(f"http://{sys.argv[1]}/v1/chat/completions", headers={"Content-Type": "application/json"},
        data=json.dumps({"model": "nvidia/Qwen3-32B-NVFP4", "messages": [{"role": "user", "content": f"{doc}\n{q}"}], "max_tokens": 24, "temperature": 0.0, "stream": True, "stream_options": {"include_usage": True}}).encode())
    t0, ttft, u = time.perf_counter(), None, {}
    for raw in urllib.request.urlopen(req, timeout=120):
        s = raw.decode().strip()
        if s.startswith("data: ") and s != "data: [DONE]":
            c = json.loads(s[6:])
            if c.get("choices") and c["choices"][0].get("delta", {}).get("content") and ttft is None:
                ttft = (time.perf_counter() - t0) * 1000.0
            u = c.get("usage") or u
    print(f"  {label}: TTFT={ttft:6.1f} ms | prompt={u.get('prompt_tokens',0)} | cached={(u.get('prompt_tokens_details') or {}).get('cached_tokens',0)}")
PY
}

echo "=== 1. Steady-state via Americas VIP (${AMER_VIP}) -> local inf-americas island ===" && probe_vip
(
  # Tip: to test GPU-worker loss with the frontend still up (verifying the
  # /v1/models/<model>/ready health check), scale deploy/dynamo-trtllm-worker-rtx6000-qwen3-32b-nvfp4
  # to 0 instead of deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 (and back to 2 on EXIT).
  trap 'kubectl scale deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 -n inf-americas-online-gpu --replicas=1 >/dev/null 2>&1 || true' EXIT
  echo "=== 2. Draining inf-americas frontend to trigger cross-region Internal ALB failover ==="
  kubectl scale deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 -n inf-americas-online-gpu --replicas=0
  for _ in {1..24}; do
    us_h="$(gcloud compute backend-services get-health "${LB_BS}" --global --project="${PROJECT_ID}" --format=json \
      | jq '[.[] | select(.backend | contains("/zones/us-central1-")) | .status.healthStatus[]? | select(.healthState=="HEALTHY")] | length')"
    [[ "${us_h}" == "0" ]] && { sleep 5; break; }
    sleep 5
  done
  echo "=== 3. Failover via same Americas VIP (${AMER_VIP}) -> peer regional island ===" && probe_vip
)
kubectl rollout status deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 -n inf-americas-online-gpu --timeout=120s
kubectl delete deploy/vip-probe -n inf-americas-online-gpu --ignore-not-found
```

---

## Post-demo teardown

Destroy all standalone NEGs, HNS buckets, `global_lb`, regional clusters, and
`shared_network` in parallel (see
[foundation Step 3](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#step-3-tear-down-all-regional-and-shared-multi-region-resources);
if replacing individual frontend `Service`s without full teardown, detach or
destroy `global_lb.sh` first so standalone NEGs do not stay stuck in deletion):

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
RING_TARGETS=("americas:us-central1:0" "europe:europe-west2:1")
[[ -f "$(mr_kubeconfig apac)" ]] && RING_TARGETS+=("apac:asia-southeast1:2")

NETWORK_MODE="shared-vpc" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/teardown.sh" \
  --parallel "${RING_TARGETS[@]}"
```
