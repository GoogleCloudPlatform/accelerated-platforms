# 15-minute Presenter Beat Sheet: Multi-region NVIDIA Dynamo KV routing, tiered KVBM offloading, disaggregated P/D, and cross-region failover on GKE

> [!IMPORTANT]
>
> Dynamic Landscape: The field of AI inference is experiencing continuous, rapid
> evolution. This document is regularly updated to reflect the latest products,
> features, and architectural patterns across Google Cloud, NVIDIA Dynamo,
> NVIDIA TensorRT-LLM, and Google Kubernetes Engine (GKE).
>
> Last Update: 2026-11-05 (YYYY-MM-DD)

This Presenter Beat Sheet accompanies the
[NVIDIA Dynamo and TensorRT-LLM reference architecture on multi-region GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/dynamo-trtllm-reference-architecture.md).
Complete **Part 1 (Pre-Demo Cluster Provisioning)** in the
[Multi-region GKE inference foundation quick-start](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#quick-start-multi-region-provisioning-and-teardown)
with `NETWORK_MODE="shared-vpc"` and `ACTIVE_MIGRATION_ENABLED="false"` across
`"americas:us-central1:0"`, `"europe:europe-west2:1"`, and
`"apac:asia-southeast1:2"`:

| Region (`platform_name`)  | Cluster (`Namespace`)                      | Pre-Warmed NVIDIA Dynamo Overlay(s) (`RTX PRO 6000`, `g4-standard-48`)                                                                                | Beat(s)     |
| ------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------- |
| **Americas (`americas`)** | `inf-americas` (`inf-americas-online-gpu`) | 1. `kv-routing/rtx-pro-6000-qwen3-32b-nvfp4` (`2` GPUs)<br>2. `disaggregated-pd/rtx-pro-6000-nvidia-nemotron-3-nano-30b-a3b-nvfp4` (`2P1D`, `3` GPUs) | **1, 3, 4** |
| **Europe (`europe`)**     | `inf-europe` (`inf-europe-online-gpu`)     | `kvbm-offloading/rtx-pro-6000-qwen3-32b-nvfp4` (`1` GPU + `80 GB` NUMA-pinned host DDR5)                                                              | **2, 4**    |
| **Asia-Pacific (`apac`)** | `inf-apac` (`inf-apac-online-gpu`)         | `kv-routing/rtx-pro-6000-qwen3-32b-nvfp4` (`2` GPUs)                                                                                                  | **4**       |

---

## Pre-demo workload pre-warm (`~25–30 min` before screen share)

Build `gpu/dynamo-trtllm:latest` once via
[`terraform/images/gpu/dynamo_trtllm`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/dynamo_trtllm/cloudbuild.tf),
mirror it to peer regions, stage `NVFP4` weights, deploy all four Dynamo stacks,
and attach the cross-region internal Application Load Balancer:

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
export ACCELERATOR_TYPE="rtx-pro-6000"

use_region "americas" "us-central1" 0
AMER_CHECKOUT="$(mr_worktree_dir americas)"
[[ -e "${AMER_CHECKOUT}/.git" ]] || AMER_CHECKOUT="${ACP_REPO_DIR}"
mr_terraform_apply "${AMER_CHECKOUT}/platforms/gke/base/use-cases/inference-ref-arch/terraform/images/gpu/dynamo_trtllm" "${AMER_CHECKOUT}"

SRC_IMG="us-central1-docker.pkg.dev/${PROJECT_ID}/inf-americas/gpu/dynamo-trtllm:latest"
bg_jobs=()
mirror_image_to_ar "europe-west2" "europe" "${SRC_IMG}" "gpu/dynamo-trtllm:latest" & bg_jobs+=($!)
mirror_image_to_ar "asia-southeast1" "apac" "${SRC_IMG}" "gpu/dynamo-trtllm:latest" & bg_jobs+=($!)
stage_hf_model "nvidia/Qwen3-32B-NVFP4"
stage_hf_model "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4"
replicate_hf_model "americas" "europe" "nvidia/Qwen3-32B-NVFP4" & bg_jobs+=($!)
replicate_hf_model "americas" "apac" "nvidia/Qwen3-32B-NVFP4" & bg_jobs+=($!)

DYNAMO_APPLY="${ACP_REPO_DIR}/test/scripts/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/dynamo-trtllm/deployment_apply.sh"
DYNAMO_MODE="kv-routing" HF_MODEL_ID="nvidia/qwen3-32b-nvfp4" "${DYNAMO_APPLY}"
DYNAMO_MODE="disaggregated-pd" HF_MODEL_ID="nvidia/nvidia-nemotron-3-nano-30b-a3b-nvfp4" "${DYNAMO_APPLY}"

for job_id in "${bg_jobs[@]}"; do wait "${job_id}"; done
use_region "europe" "europe-west2" 1 && DYNAMO_MODE="kvbm-offloading" HF_MODEL_ID="nvidia/qwen3-32b-nvfp4" "${DYNAMO_APPLY}"
use_region "apac" "asia-southeast1" 2 && DYNAMO_MODE="kv-routing" HF_MODEL_ID="nvidia/qwen3-32b-nvfp4" "${DYNAMO_APPLY}"

for TARGET in "americas:us-central1:0" "europe:europe-west2:1" "apac:asia-southeast1:2"; do
  IFS=: read -r p r idx <<<"${TARGET}" && use_region "${p}" "${r}" "${idx}"
  kubectl wait --for=condition=Available deploy --all -n "inf-${p}-online-gpu" --timeout=1800s
  echo "=== ${p^^} (${r}) ===" && kubectl get pods -n "inf-${p}-online-gpu" -o wide
done

expose_service_neg "americas" "inf-americas-online-gpu" "dynamo-frontend-rtx6000-qwen3-32b-nvfp4" "8000" "dynamo"
expose_service_neg "europe" "inf-europe-online-gpu" "dynamo-frontend-kvbm-rtx6000-qwen3-32b-nvfp4" "8000" "dynamo"
expose_service_neg "apac" "inf-apac-online-gpu" "dynamo-frontend-rtx6000-qwen3-32b-nvfp4" "8000" "dynamo"
printf '%s\n' '{"dynamo":{"health_check_path":"/health","health_check_port":8000,"max_in_flight_requests_per_endpoint":16}}' >/tmp/dynamo-backends.json
NETWORK_MODE="shared-vpc" "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh" \
  apply --backends /tmp/dynamo-backends.json --active dynamo
```

---

## Beat 1 (`0:00 – 3:45`): KV-cache-aware prefix routing (`11.68×` faster `p95` TTFT)

> **Talk track**: _"On 64-layer **`nvidia/Qwen3-32B-NVFP4`** (`128 KiB/tok`), an
> `8.35K`-token context needs `~1.02 GiB` of KV state (`~740 ms` prefill).
> Round-robin routing misses the warm GPU on half of follow-up turns
> (`789.57 ms` > `p95` TTFT); Dynamo's `--router-mode kv` tracks `32`-token
> `xxh3` hashes in a Rust radix tree, cutting follow-up `p95` TTFT to
> **`67.61 ms` (`11.68×` faster)**."_

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh"
use_region "americas" "us-central1" 0
kubectl get pods -n inf-americas-online-gpu -l app.kubernetes.io/part-of=dynamo-kv-rtx6000-qwen3-32b-nvfp4 -o wide

kubectl exec -i -n inf-americas-online-gpu deploy/dynamo-frontend-rtx6000-qwen3-32b-nvfp4 -- python3 - <<'PY'
import json, time, urllib.request
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

## Beat 2 (`3:45 – 7:30`): Tiered KVBM host DRAM offloading (`7.17×` faster recall TTFT)

> **Talk track**: _"Each `g4-standard-48` VM pairs `96 GB` GDDR7 (`G1`) with
> **`180 GiB` GCE VM memory**. `components/kvbm-offloading` pins **`80 GB` host
> DDR5 (`G2`, `~655K` KV tokens)** via our derived image (`/opt/nixl-plugins`
> pairing native `/usr/local/ucx/lib` with `libplugin_POSIX.so`;
> `/usr/local/nvidia/lib64` and `nixl_cu13.libs` appended to `LD_LIBRARY_PATH`),
> `DYN_KVBM_DISABLE_WRITE_COMBINED=true` (`7.43 GB/s` vs. `0.37 MB/s` `≈ 36h`
> x86 PAT TLB shootdown), and `DYN_KVBM_TRTLLM_ZMQ_PORT=20081` (avoiding
> `ZmqActiveMessageWorker` on `56001/56002`)—adding **no measurable cold-prefill
> penalty** and recalling evicted sessions **`7.17×` faster (`107 ms` vs.
> `768 ms`)**."_

```shell
use_region "europe" "europe-west2" 1
kubectl logs -n inf-europe-online-gpu deploy/dynamo-trtllm-worker-kvbm-rtx6000-qwen3-32b-nvfp4 \
  -c inference-server | grep -E "Allocating .* host memory|Allocated .* pinned memory|Backend \(POSIX|Backend \(UCX|KvbmWorker initialized|20081" | tail -n 10

kubectl exec -i -n inf-europe-online-gpu deploy/dynamo-frontend-kvbm-rtx6000-qwen3-32b-nvfp4 -- python3 - <<'PY'
import json, urllib.request
prompt = ("Tiered KVBM PCIe Gen5 host DRAM caching on GKE g4-standard-48. " * 220) + "Summarize KVBM in one sentence."
req = urllib.request.Request("http://127.0.0.1:8000/v1/chat/completions", headers={"Content-Type": "application/json"},
    data=json.dumps({"model": "nvidia/Qwen3-32B-NVFP4", "messages": [{"role": "user", "content": prompt}], "max_tokens": 32, "temperature": 0}).encode())
data = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
print(json.dumps({"content": data["choices"][0]["message"]["content"], "usage": data.get("usage")}, indent=2))
PY
kubectl exec -n inf-europe-online-gpu deploy/dynamo-trtllm-worker-kvbm-rtx6000-qwen3-32b-nvfp4 -c inference-server -- \
  sh -c 'curl -fsS http://127.0.0.1:6880/metrics | grep -E "^kvbm_(offload_blocks_d2h|onboard_blocks_h2d|matched_tokens|host_cache_hit_rate)"'
```

---

## Beat 3 (`7:30 – 11:30`): Disaggregated P/D (`28.21×` tighter `p99` ITL & hybrid Mamba-2 `UCX`)

> **Talk track**: _"Disaggregating Prefill and Decode isolates `Qwen3-32B`
> decode `p99` ITL at **`18.30 ms` vs. `516.30 ms` (`28.21×` tighter)** during
> `4 × 8.3K` bursts (`1P+1D` trades `2.89×` higher burst TTFT, so our overlay
> defaults to **`2P1D`**). **`Nemotron-3-Nano-30B-A3B-NVFP4`** (`6` GQA layers =
> **`3.00 KiB/tok`** raw KV, **`42.7×` smaller**) transfers KV + Mamba-2 SSM
> state via C++ `UCX` in **`199.15 ms` `p50` TTFT** (`4,309` tokens) and
> **`3.81 ms` `p50` ITL (`261.8 tok/s`)**."_

```shell
use_region "americas" "us-central1" 0
kubectl get pods -n inf-americas-online-gpu -l app.kubernetes.io/part-of=dynamo-pd-rtx6000-nemotron3-30b-nvfp4 -o wide
kubectl logs -n inf-americas-online-gpu deploy/dynamo-trtllm-prefill-pd-rtx6000-nemotron3-30b-nvfp4 \
  -c inference-server | grep -E "Max KV cache blocks|CacheTransBufferManager|RnnCacheTransBufferManager|Disagg server" | tail -n 8

kubectl exec -i -n inf-americas-online-gpu deploy/dynamo-frontend-pd-rtx6000-nemotron3-30b-nvfp4 -- python3 - <<'PY'
import json, time, urllib.request
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

> **Talk track**: _"Stretching one Dynamo layer over `114 ms` WAN RTT inflates
> warm TTFT `6.47×` (`389.34 ms` vs. `60.17 ms`) and stalls unconstrained
> `1.04 GiB` WAN P/D to `42.22s` (mitigated by `components/topology-region`).
> **Pattern A** fronts isolated islands (`0 B` steady-state East-West payload)
> with `global_lb.sh` (`WATERFALL_BY_REGION` + `LEAST_REQUEST`): draining
> `inf-americas` fails traffic over to a healthy peer island, re-hydrating Turn
> 1 locally and resuming warm KV hits on Turn 2."_

```shell
use_region "americas" "us-central1" 0
AMER_VIP="$(NETWORK_MODE=shared-vpc "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/global_lb.sh" vips | jq -r '.americas')"
LB_BS="${TF_VAR_resource_name_prefix:-inf}-${MR_ENVIRONMENT_NAME:-mr}-lb-dynamo"

probe_vip() {
  kubectl exec -i -n inf-americas-online-gpu deploy/dynamo-trtllm-worker-rtx6000-qwen3-32b-nvfp4 -c inference-server -- python3 - "${AMER_VIP}" <<'PY'
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
```

---

## Post-demo teardown

Destroy all standalone NEGs, HNS buckets, `global_lb`, regional clusters, and
`shared_network` in parallel (see
[foundation Step 3](/docs/platforms/gke/base/use-cases/inference-ref-arch/multi-region-gke-inference-foundation.md#step-3-tear-down-all-regional-and-shared-multi-region-resources)):

```shell
NETWORK_MODE="shared-vpc" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/teardown.sh" \
  --parallel "americas:us-central1:0" "europe:europe-west2:1" "apac:asia-southeast1:2"
```
