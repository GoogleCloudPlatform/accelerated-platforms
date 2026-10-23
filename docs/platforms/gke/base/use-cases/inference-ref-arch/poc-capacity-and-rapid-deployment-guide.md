# AI inference proof-of-concept (PoC) and capacity-finding guide

> [!IMPORTANT]
>
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2026-10-20 (YYYY-MM-DD)

This guide provides an end-to-end **Proof of Concept (PoC) playbook** for
bringing up production-grade AI inference deployments on Google Kubernetes
Engine (GKE) as quickly and reliably as possible. It builds on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md),
the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md),
and the
[GKE Pod snapshots inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md).
For a copy-paste presenter script and talk track that provisions this stack from
scratch, see the companion
[15-minute live demo runbook](/docs/platforms/gke/base/use-cases/inference-ref-arch/poc-15min-demo-runbook.md).

## Purpose: Why inference PoCs stall and how to shorten time to value

When teams set out to run an AI inference PoC on GKE, the biggest delays rarely
come from Kubernetes manifests or model server flags. Instead, time-to-value is
dominated by three practical bottlenecks:

1. **Regional accelerator stock-outs and quota mismatches**: By default, single
   region configurations (such as `platform_default_region = "us-east4"`) target
   one region. If that region is experiencing temporary GPU or TPU stock-outs—or
   if the project lacks regional quota for the chosen consumption model—pods sit
   `Pending` with `ZONE_RESOURCE_POOL_EXHAUSTED` or `GCE quota exceeded` after
   you have already waited 15 to 20 minutes for cluster provisioning.
2. **Data gravity and cross-region storage friction**: Enterprise data estates
   already live in specific regions across **Cloud Storage (GCS)**, **Persistent
   Disk (PD) / Hyperdisk**, or **Google Cloud Managed Lustre**. Picking compute
   regions without accounting for where model weights, fine-tuned checkpoints,
   and evaluation datasets reside introduces slow weight transfers or
   cross-region egress costs.
3. **Compounding cold-start delays on every scale-out or preemption**: A
   conventional GPU replica spends several minutes pulling a multi-gigabyte
   container image, staging tens of gigabytes of weights onto local disk,
   loading tensors into GPU memory, and running `torch.compile` and CUDA graph
   capture. When using cost-optimized Spot VMs or Dynamic Workload Scheduler
   (DWS) Flex-Start nodes, every preemption or node recycle repeats this entire
   penalty unless fast-start and fast-restore primitives are enabled.

This guide solves all three problems by combining **pre-flight capacity
discovery and multi-region Fluid Compute** with every **fast-start and
fast-restore technique** in Accelerated Platforms:

```mermaid
%%{init: {"flowchart": {"htmlLabels": false, "padding": 20}, "themeVariables": {"fontFamily": "sans-serif"}}}%%
flowchart TD
  subgraph S1["Stage 1: Scope & Data Estate"]
    A["1. Select Model & GPU/TPU SKU"] --> B["2. Map Data Estate Locality"]
    B --> C["3. Pick Candidate Regions"]
  end

  subgraph S2["Stage 2: Capacity Discovery"]
    C --> D["Capacity Advisor APIs"]
    C --> E["Capacity Radar Probing"]
  end

  subgraph S3["Stage 3: Provision Topology"]
    D --> F(["Choose PoC Topology"])
    E --> F
    F -->|"Single Region"| G["Topology A: Single-Region"]
    F -->|"Multi-Region"| H["Topology B: Multi-Region Ring"]
  end

  subgraph S4["Stage 4: Fast-Start & Restore"]
    G --> I["1. GCFS Image Streaming"]
    H --> I
    I --> J["2. HNS GCS + Run:ai Streamer"]
    J --> K["3. GKE Pod Snapshots + HPA"]
    K --> L["4. llm-d GAIE Routing"]
  end
```

### Summary of acceleration techniques in this repository

| Bottleneck                         | Accelerated Platforms Technique                                                                                                            | Measured Impact                                                                                                                                                 | Where It Is Configured                                                                                                                                                                                                                                |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Finding regional capacity**      | **Capacity Advisor APIs** + **[Capacity Radar](https://github.com/MG-Cafe/capacity_radar)** (passive advisory + active multi-zone probing) | Identifies zones with immediate Spot, DWS Flex-Start, DWS Calendar, or On-Demand obtainability before provisioning GKE                                          | [Stage 2](#stage-2-discover-and-secure-capacity-before-you-deploy)                                                                                                                                                                                    |
| **Single-region stock-outs**       | **Custom Compute Classes (CCC)** + **Multi-Region Fluid Compute Ring**                                                                     | Automatically cascades across Reservations, On-Demand, DWS Flex-Start (7d/1d), and Spot VMs; fails over across regions via Multi-Cluster Gateway                | [`platforms/gke/base/core/custom_compute_class`](/platforms/gke/base/core/custom_compute_class/templates/manifests/gpu)                                                                                                                               |
| **GPU node provisioning**          | **GKE Autopilot Fast-Starting Nodes** (eligible on `G2` L4 and `G4` RTX PRO 6000 on-demand/reserved nodes)                                 | Uses pre-initialized hardware on a best-effort basis at no extra cost to cut the 1–3 minute node bring-up window                                                | Enabled automatically on compatible GKE Autopilot clusters                                                                                                                                                                                            |
| **Container image pull**           | **Google Container File System (GCFS) Image Streaming** (`imageStreaming.enabled: true`)                                                   | Reduces multi-gigabyte vLLM image pull from **~4 minutes to 1.3–2.3 seconds** on new nodes                                                                      | Enabled in all GPU `ComputeClass` templates                                                                                                                                                                                                           |
| **Object storage QPS & egress**    | **Hierarchical Namespace (HNS) Cloud Storage** + **Zonal Rapid Cache** (`anywhere_cache`) + **`gcsfusecsi-serving` profile**               | Up to 8× higher initial QPS; **10.5–12.5s** per replica at 6× concurrent scale-out with **97–100% cache hit rate**; eliminates cross-region egress on cache hit | [`huggingface/initialize/storage.tf`](/platforms/gke/base/core/huggingface/initialize/storage.tf) and `terraform/online_gpu/storage.tf`                                                                                                               |
| **Model weight loading**           | **NVIDIA Run:ai Model Streamer** (`--load-format=runai_streamer` direct from `gs://` to GPU VRAM)                                          | Streams **Gemma 3 27B** (`51.54 GiB`) in **9.1s** and **Gemma 4 31B** (`58.99 GiB`) in **11.1–25.7s** on RTX PRO 6000 and **20.1–25.8s** on H100 with zero disk | [`online-inference-gpu/vllm-runai`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai)                                                                                                            |
| **Engine init & CUDA graphs**      | **GKE Pod Snapshots** (`runtimeClassName: gvisor` + cooperative `/proc/gvisor/checkpoint` trigger)                                         | Skips weight loading, `torch.compile`, and CUDA graph capture on scale-out; restores to first response in **28.2s (L4)**, **36–56s (H100)**, **35–105s (G4)**   | [`vllm-podsnapshot-fast-restore`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore)                                                                                           |
| **Reactive autoscaling & routing** | **Queue-Depth HPA (`vllm:num_requests_waiting`)** + **`llm-d` Well-Lit Paths (GAIE `InferencePool` + EPP Router)**                         | Scales immediately when requests queue in vLLM; routes traffic based on live KV-cache utilization, prefix cache hits, and predicted latency                     | [`vllm-runai/base/hpa.yaml`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/base/hpa.yaml) and [`llmd`](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/llmd-vllm-with-hf-model.md) |

---

## Stage 1: Scope your PoC hardware and align with your data estate

Before querying capacity or running Terraform, map your target model to the
appropriate accelerator SKU and identify the regions where your data estate
already resides.

### Step 1.1: Map your model to accelerator SKUs and Custom Compute Classes

The GKE Base Platform pre-installs Custom Compute Classes that encode fallback
priorities across consumption models. Choose the accelerator family that fits
your model's VRAM footprint and concurrency targets:

| Target Model Tier & Example Workloads                   | Accelerator Family                       | Machine Type(s)                    | Built-in `ComputeClass` Name                      | Consumption Models Supported                        | Fast-Start & Snapshot Capabilities                                                   |
| ------------------------------------------------------- | ---------------------------------------- | ---------------------------------- | ------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------ |
| **Gemma 2 9B**, **Gemma 3 4B / 12B** (8B–12B class)     | **NVIDIA L4 (24 GB)**                    | `g2-standard-4` to `96`            | `gpu-l4-24gb-s4-x1` .. `gpu-l4-24gb-x8`           | On-Demand, Reservation, DWS Flex-Start, Spot        | Autopilot Fast-Starting Nodes eligible; Pod snapshots (`TP=1`) restores in **28.2s** |
| **Gemma 3 27B**, **Gemma 4 31B** (27B–35B single-GPU)   | **NVIDIA RTX PRO 6000 (96 GB)**          | `g4-standard-48` (1 GPU)           | `gpu-rtx-pro-6000-96gb-x1` (and `x2`, `x4`, `x8`) | On-Demand, Reservation, DWS Flex-Start, Spot        | Autopilot Fast-Starting Nodes eligible; Run:ai Streamer (**9–25s**); Pod snapshots   |
| **Gemma 2 9B**, **Gemma 3 27B**, **Gemma 4 31B**        | **NVIDIA H100 (80 GB)**                  | `a3-highgpu-1g` (1 GPU)            | `gpu-h100-80gb-high-x1`                           | On-Demand, Reservation, DWS Calendar/Flex, Spot     | Run:ai Streamer (**20–25s**); Pod snapshots (`TP=1`) restores in **36–56s**          |
| **Multi-GPU Tensor Parallel (`TP=2` / `TP=4`)**         | **NVIDIA H100 (4 × 80 GB)**              | `a3-highgpu-4g` (4 GPUs)           | `gpu-h100-80gb-high-x4`                           | On-Demand, Reservation, DWS Calendar/Flex, Spot     | Run:ai Streamer + `llm-d` well-lit paths (`TP=4`)                                    |
| **Multi-Replica Bin-Packed Gemma Fleet or Large MoE**   | **NVIDIA H100 High / Mega (8 × 80 GB)**  | `a3-highgpu-8g` / `a3-megagpu-8g`  | `gpu-h100-80gb-high-x8` / `gpu-h100-80gb-mega-x8` | On-Demand, Reservation, DWS Calendar/Flex, Spot     | Use `a3-megagpu-8g` (1600 Gbps vs. 800 Gbps east-west) when scaling multi-node       |
| **Ultra-Large Frontier Models (100B–400B+ parameters)** | **NVIDIA H200 (8 × 141 GB)** or **B200** | `a3-ultragpu-8g` / `a4-highgpu-8g` | `gpu-h200-141gb-ultra-x8`                         | Reservation, DWS Calendar (`DENSE`), DWS Flex, Spot | High HBM capacity per node; pair with Run:ai Streamer and `llm-d`                    |
| **Gemma 2 / Gemma 3 / Gemma 4 on Cloud TPU**            | **Cloud TPU v6e (Trillium)**             | `ct6e-standard-4t` / `8t`          | `tpu-v6e-2x2` / `tpu-v6e-2x4`                     | On-Demand, DWS Calendar, DWS Flex (Queued), Spot    | vLLM on TPU and `llm-d` P/D disaggregation well-lit paths                            |

> [!TIP]
>
> **Single-GPU sweet spot for rapid PoCs**: If your model fits in 80–96 GB of
> VRAM (such as **Gemma 4 31B** or **Gemma 3 27B**), targeting a single **NVIDIA
> RTX PRO 6000 96GB (`g4-standard-48`)** or single **NVIDIA H100 80GB
> (`a3-highgpu-1g`)** gives you the highest probability of immediate capacity
> obtainability and unlocks **GKE Pod snapshots** (which require
> `--tensor-parallel-size=1`).

### Step 1.2: Design a "Ring Around the World" around your data estate

Rather than betting your PoC on a single region, define a **Capacity Ring** of 2
to 4 regions where you can farm capacity elastically. GPU and TPU availability
fluctuates throughout the day with regional business hours and batch training
schedules; a ring lets you place workloads wherever obtainability is highest and
Spot preemption rates are lowest.

#### Example regional rings

- **Americas Ring**: `us-central1` $\leftrightarrow$ `us-east4`
  $\leftrightarrow$ `us-west1` $\leftrightarrow$ `us-south1`
- **Europe Ring**: `europe-west4` $\leftrightarrow$ `europe-west1`
  $\leftrightarrow$ `europe-west9`
- **Asia-Pacific Ring**: `asia-southeast1` $\leftrightarrow$ `asia-northeast1`
  $\leftrightarrow$ `asia-east1`
- **Global Follow-the-Sun Ring**: `us-central1` $\leftrightarrow$ `europe-west4`
  $\leftrightarrow$ `asia-southeast1`

#### Aligning your ring with existing data estates (GCS, PD/Hyperdisk, Managed Lustre)

Your choice of primary and secondary regions in the ring should be anchored by
where your enterprise data estate lives—whether model checkpoints, adapters, or
evaluation datasets are stored in **Cloud Storage**, **Persistent Disk /
Hyperdisk**, or **Google Cloud Managed Lustre**:

| Data Estate Source                                         | Data Gravity Scope                                                           | How to Architect for a Multi-Region Capacity Ring                                                                                                                                                                                                     | Recommended Loader in GKE                                                                                                                                      |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Google Cloud Storage (GCS)**                             | Regional, Dual-Region (`NAM4`, `EUR4`), or Multi-Region (`US`, `EU`, `ASIA`) | Create a **Multi-Region or Dual-Region bucket with Hierarchical Namespace (HNS)** enabled (`huggingface_hub_models_bucket_location = "US"`), and enable **Zonal Rapid Cache** (`anywhere_cache`) in each compute zone of your ring.                   | **NVIDIA Run:ai Model Streamer** (`--load-format=runai_streamer` over `gs://`) or **GKE Cloud Storage FUSE Profiles** (`storageClassName: gcsfusecsi-serving`) |
| **Persistent Disk (PD) / Hyperdisk ML**                    | Zonal or Regional                                                            | Use **Hyperdisk ML** (`ReadOnlyMany` multi-attach across up to thousands of nodes at up to 1.2 TB/s) in your **Primary Anchor Zone**. For overflow regions in your ring, export checkpoints to a Multi-Region GCS bucket with Zonal Rapid Cache.      | Direct block mount in the anchor zone; **Run:ai Model Streamer** + **GKE Pod Snapshots** in overflow ring regions                                              |
| **Google Cloud Managed Lustre** (or Parallel File Systems) | Zonal                                                                        | Make the Lustre zone your **Primary Ring Anchor** so GKE pods in that zone mount Lustre directly at hundreds of GB/s for zero-copy evaluation of newly trained checkpoints. Tier promoted checkpoints to Multi-Region GCS + Rapid Cache for the ring. | CSI Lustre mount in the primary zone; **Run:ai Model Streamer** or `gcsfusecsi-serving` in secondary ring regions when the Lustre zone is out of GPU capacity  |

> [!NOTE]
>
> **How Zonal Rapid Cache eliminates the multi-region storage penalty**: When
> you store weights in a multi-region Cloud Storage bucket (for example, `US`)
> and enable **Rapid Cache** (formerly Anywhere Cache) in the specific compute
> zones where your GPU nodes run (such as `us-east4-a` and `us-west1-a`), the
> first read miss ingests the model shards into a zonal SSD-backed cache.
> Subsequent replica scale-outs read from the local zone cache at up to 2.5 TB/s
> with a **>90–99% cache hit rate**, avoiding cross-region data transfer charges
> until the model weights are refreshed.

---

## Stage 2: Discover and secure capacity before you deploy

Never wait 20 minutes for a GKE cluster to provision before checking whether
your target region has accelerators available. Use a two-pronged approach:

1. **Approach A (Native Google Cloud Advisory & Quota Pre-Flight)**: Check
   hardware availability, project quotas, Spot obtainability, preemption rates,
   and pricing across your candidate ring using `gcloud`, the Google Cloud
   Console, and the Compute Engine Capacity Advisory REST APIs.
2. **Approach B (Automated Probing & Reservation Hunting with Capacity Radar)**:
   Use **[Capacity Radar](https://github.com/MG-Cafe/capacity_radar)** to sweep
   all regions in your ring simultaneously and actively probe or reserve
   capacity across consumption models (`on_demand`, `dws_calendar`, `dws_flex`,
   `spot`).

### Approach A: Native Google Cloud capacity discovery (`gcloud`, Console, and REST APIs)

#### 1. Run a multi-region offering and quota pre-flight check

Run the following script in Cloud Shell to verify which zones in your candidate
ring offer your target GPU and whether your project has sufficient regional
quota (including the `C4_CPUS` or `C3_CPUS` quota required by the
[`model-download` compute class](/platforms/gke/base/core/custom_compute_class/templates/manifests/cpu/custom-compute-model-download.yaml)):

```shell
export PROJECT_ID="<YOUR_PROJECT_ID>"
# Define your candidate "Ring Around the World" regions
export CANDIDATE_REGIONS=("us-central1" "us-east4" "us-west1" "europe-west4" "asia-southeast1")
# Example accelerator: nvidia-rtx-pro-6000, nvidia-h100-80gb, nvidia-h100-mega-80gb, nvidia-l4
export TARGET_ACCELERATOR="nvidia-rtx-pro-6000"

for REGION in "${CANDIDATE_REGIONS[@]}"; do
  echo "=========================================================="
  echo "Region: ${REGION}"
  echo "----------------------------------------------------------"
  echo "Zones offering ${TARGET_ACCELERATOR}:"
  gcloud compute accelerator-types list \
    --project="${PROJECT_ID}" \
    --filter="name=${TARGET_ACCELERATOR} AND zone ~ ${REGION}-" \
    --format="  value(zone.basename())" \
    --sort-by=zone

  echo "Regional Host CPU & Legacy GPU Quotas (Usage / Limit):"
  gcloud compute regions describe "${REGION}" \
    --project="${PROJECT_ID}" \
    --format="table[box](quotas.metric:label=METRIC, quotas.usage:label=USED, quotas.limit:label=LIMIT)" \
    --flatten="quotas[]" \
    --filter="quotas.metric ~ '^(G4_CPUS|PREEMPTIBLE_G4_CPUS|NVIDIA_L4_GPUS|PREEMPTIBLE_NVIDIA_L4_GPUS|C4_CPUS|C3_CPUS)' AND quotas.limit > 0"
done

echo "=========================================================="
echo "Dimensional GPU Family Quotas (NVIDIA_RTX_PRO_6000, NVIDIA_H100, NVIDIA_H200, NVIDIA_B200):"
echo "----------------------------------------------------------"
gcloud alpha quotas info list \
  --project="${PROJECT_ID}" \
  --service="compute.googleapis.com" \
  --filter="metric ~ gpus_per_gpu_family" \
  --format="yaml(metric,dimensionsInfos)"
```

> [!IMPORTANT]
>
> **Why `gcloud compute regions describe` does not show RTX PRO 6000, H100,
> H200, or B200 GPU limits**: Newer accelerator families use dimensional Cloud
> Quotas (`compute.googleapis.com/gpus_per_gpu_family` and
> `compute.googleapis.com/preemptible_gpus_per_gpu_family` scoped by
> `gpu_family` and `region`) rather than legacy region-level quota fields.
> Always run the `gcloud alpha quotas info list` command above to confirm your
> regional `gpu_family` limit before deploying.

#### 2. Evaluate regional price vs. preemption trade-offs in Capacity Advisor

Before provisioning clusters, open Google Cloud Console's
**[Capacity Advisor](https://console.cloud.google.com/compute/capacityAdvisor)**
or the interactive chat interface in
**[Compute Advisor](https://console.cloud.google.com/compute/advisor/)** to
compare zonal obtainability, historical Spot preemption rates, and hourly Spot
pricing across your ring.

As demonstrated in the
[Fluid Compute reference guide](https://discuss.google.dev/t/how-to-build-an-elastic-scalable-llm-inference-platform-on-gke-using-fluid-compute/388108),
comparing two regions in an Americas ring (`us-east4` vs. `us-west1`) for an A3
Mega (`a3-megagpu-8g`, 8 × H100) Spot footprint reveals complementary
characteristics:

| Region         | Zonal Capacity Availability                 | Historical Spot Preemption Rate | Example Spot Price (`a3-megagpu-8g`) | Role in a "Ring Around the World" Architecture                                                |
| -------------- | ------------------------------------------- | ------------------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------- |
| **`us-east4`** | `us-east4-a` (High), `us-east4-c` (High)    | **6 – 10%** _(Moderate)_        | **`$21.70` / hr**                    | **Cost-Optimized Primary Fleet**: ~59% lower hourly cost, ideal for primary serving traffic   |
| **`us-west1`** | `us-west1-a` (High), `us-west1-b` (Limited) | **0 – 5%** _(Very Low)_         | **`$53.35` / hr**                    | **High-Stability Backup Fleet**: Low preemption risk, ideal for elastic cross-region failover |

By combining a cost-optimized primary region with a high-stability secondary
region in your ring, you capture Spot cost savings while insulating your PoC and
serving SLOs from regional preemptions.

#### 3. Query the Compute Engine Capacity & Calendar Advisory APIs directly

You can also query Google Cloud's Capacity Advisory endpoints programmatically
from your shell across your candidate ring:

- **Spot VM Capacity Advisory API (`advice/capacity`)** — returns per-zone
  `obtainability` scores (`0.0` to `1.0`) and `uptimeScore` (preemption risk):

  ```shell
  export PROJECT_ID="<YOUR_PROJECT_ID>"
  export MACHINE_TYPE="a3-highgpu-1g" # e.g., a3-highgpu-1g, a3-highgpu-8g, g4-standard-48

  for REGION in us-central1 us-east4 us-west1 europe-west4; do
    echo "=== Spot Advisory: ${REGION} (${MACHINE_TYPE}) ==="
    curl --silent -X POST \
      -H "Authorization: Bearer $(gcloud auth print-access-token)" \
      -H "Content-Type: application/json" \
      "https://compute.googleapis.com/compute/alpha/projects/${PROJECT_ID}/regions/${REGION}/advice/capacity" \
      -d '{
        "distributionPolicy": {"targetShape": "ANY_SINGLE_ZONE"},
        "instanceFlexibilityPolicy": {
          "instanceSelections": {
            "selection-1": {"machineTypes": ["'"${MACHINE_TYPE}"'"]}
          }
        },
        "instanceProperties": {
          "scheduling": {"provisioningModel": "SPOT"}
        },
        "size": 1
      }' | jq -r '.recommendations[]? | .scores as $s | .shards[]? | "  Zone: \(.zone | split("/")[-1]) | Obtainability: \($s.obtainability // "N/A") | UptimeScore: \($s.uptimeScore // "N/A")"'
  done
  ```

  > [!NOTE]
  >
  > For `G2` (`g2-standard-*` with `nvidia-l4`) and `N1` (`nvidia-tesla-t4`)
  > machine types, include
  > `"guestAccelerators": [{"acceleratorType": "nvidia-l4", "acceleratorCount": 1}]`
  > inside `instanceProperties` so the API checks GPU availability rather than
  > host CPU availability alone.

- **DWS Calendar Mode Advisory (`advice/calendarMode`)** — finds optimal zones
  and future reservation windows for `A3`, `A4`, and `TPU v5e/v5p/v6e` capacity:

  ```shell
  gcloud beta compute advice calendar-mode \
    --project="${PROJECT_ID}" \
    --region="us-central1" \
    --machine-type="a3-highgpu-8g" \
    --vm-count=1 \
    --start-time="$(date -u -d '+1 day' +%Y-%m-%dT00:00:00Z)" \
    --end-time="$(date -u -d '+8 days' +%Y-%m-%dT00:00:00Z)" \
    --format=json
  ```

---

### Approach B: Automated multi-region probing and reservation hunting with Capacity Radar

Advisory APIs provide statistical scores (and some endpoints such as DWS
Flex-Start wait-time advisory require Preview project allow-listing). When you
want an authoritative answer—or want to **automatically hunt for and lock in
capacity across multiple regions and consumption models**—use
**[Capacity Radar](https://github.com/MG-Cafe/capacity_radar)**.

Capacity Radar is an open-source tool built for Google Cloud GPU and TPU
workloads that provides two core capabilities:

1. **Multi-Region Capacity Advisories (Read-Only)**:
   - **Spot VM Advisory**: Queries obtainability and preemption risk across all
     candidate regions in parallel.
   - **DWS Calendar Advisory & Split-Plan Finder (`calendar-plan`)**: Queries
     Calendar Mode availability at **100%, 75%, 50%, 25%, and 1-VM levels** in
     parallel to show how a multi-node request can be split across smaller
     reservations or zones when a single contiguous block is unavailable.
   - **DWS Flex-Start Advisory** _(Preview for allow-listed projects)_:
     Estimates queue wait duration (`estimatedWaitDuration`) per zone shard.
2. **Priority-Based Active Scan & Deploy (`hunter.py`)**:
   - Attempts real allocations across candidate zones in **Sequential** or
     **Parallel** mode following a customizable priority chain (`on_demand`
     reservation $\rightarrow$ `dws_calendar` future reservation $\rightarrow$
     `dws_flex` $\rightarrow$ `spot`), polls the Compute Engine or TPU zone
     operations until `DONE`, and returns the exact zone and consumption model
     where capacity was secured.

#### Three ways to use Capacity Radar in your PoC workflow

You can run Capacity Radar from its **portable CLI**, its **interactive Web UI**
(locally or on Cloud Run), or as an **AI Agent Skill** alongside the skills in
this repository.

##### Option 1: Run the Capacity Radar CLI in Cloud Shell (Recommended for fast PoCs)

1. Clone Capacity Radar alongside `accelerated-platforms` and install its
   lightweight Python dependencies:

   ```shell
   git clone https://github.com/MG-Cafe/capacity_radar.git "${HOME}/capacity_radar"
   pip install -r "${HOME}/capacity_radar/backend/requirements.txt"
   ```

2. Verify authentication, project access, and supported zones for your target
   chip:

   ```shell
   export PROJECT_ID="<YOUR_PROJECT_ID>"
   export CR_CLI="${HOME}/capacity_radar/skills/capacity-radar/scripts/capacity_radar.py"

   # Verify ADC credentials and Compute Engine API status
   python3 "${CR_CLI}" auth check --project "${PROJECT_ID}"

   # List all supported GPU/TPU chips and machine types
   python3 "${CR_CLI}" catalog chips

   # List all zones offering your target machine type (e.g., g4-standard-48 or a3-highgpu-1g)
   python3 "${CR_CLI}" catalog zones --machine-type g4-standard-48
   ```

3. Sweep your "Ring Around the World" regions with read-only advisories:

   ```shell
   # 1. Multi-region Spot obtainability and preemption risk sweep
   python3 "${CR_CLI}" advise spot \
     --project "${PROJECT_ID}" \
     --machine-type g4-standard-48 \
     --regions us-central1,us-east4,europe-west4,asia-south2

   # 2. DWS Calendar availability + automatic Split-Plan (100%, 75%, 50%, 25%, 1 VM)
   # Note: DWS Calendar Mode supports A3 (a3-*), A4 (a4-*), and Cloud TPU families.
   python3 "${CR_CLI}" advise calendar-plan \
     --project "${PROJECT_ID}" \
     --machine-type a3-highgpu-8g \
     --vm-count 4 \
     --start-date "$(date -u -d '+1 day' +%Y-%m-%d)" \
     --flexibility-days 2 \
     --duration-days 7 \
     --regions us-central1,us-east4,us-west1,europe-west4

   # 3. DWS Flex-Start queue wait-time estimate (for Preview allow-listed projects;
   # DWS Flex-Start VM provisioning itself works on all projects without allow-listing)
   python3 "${CR_CLI}" advise flex \
     --project "${PROJECT_ID}" \
     --machine-type g4-standard-48 \
     --size 2 \
     --max-run-hours 24 \
     --regions us-central1,us-east4,europe-west4
   ```

   **Example output from `advise spot` (`g4-standard-48` / NVIDIA RTX
   PRO 6000)**: Running the command above reveals when the repository's default
   region (`us-east4`) is experiencing a temporary Spot stock-out while peer
   regions in the ring have high availability:

   | Region (`advise spot`) | Zones Returned                              | `spotAvailability` | `preemptionRate` | `obtainability` | `uptimeScore` (`estimatedUptime`) | PoC Placement Decision                                                        |
   | ---------------------- | ------------------------------------------- | ------------------ | ---------------- | --------------- | --------------------------------- | ----------------------------------------------------------------------------- |
   | **`us-east4`**         | `us-east4-a`, `us-east4-b`, `us-east4-c`    | `VERY_LOW`         | `HIGH`           | **`0.1`**       | `0.2` (`60s`)                     | **Avoid for this PoC window** (default region would stall in `Pending`)       |
   | **`us-central1`**      | `us-central1-b`, `us-central1-c` (`-a` low) | **`HIGH`**         | **`LOW`**        | **`0.9`**       | **`0.9`** (`86400s`)              | **Selected Primary Region** (paired with 32-GPU `NVIDIA_RTX_PRO_6000` quota)  |
   | **`europe-west4`**     | `europe-west4-a`, `europe-west4-c`          | **`HIGH`**         | **`LOW`**        | **`0.9`**       | **`0.9`** (`86400s`)              | **High-Availability Ring Peer** (request regional GPU family quota if needed) |
   | **`asia-south2`**      | `asia-south2-a`, `asia-south2-b`, `-c`      | **`HIGH`**         | **`LOW`**        | **`0.9`**       | **`0.9`** (`86400s`)              | **APAC Ring Peer**                                                            |

4. **Active Probing / Reservation Hunting (`deploy`)**: How you use `deploy`
   depends on whether you want to **reserve capacity for GKE** or **probe live
   Spot/Flex availability**:

   - **Workflow A — Reserve capacity for GKE Custom Compute Classes**: Run a
     priority scan with `on_demand` (immediate On-Demand Reservation) and/or
     `dws_calendar`. When Capacity Radar secures an On-Demand Reservation in a
     winning zone, **keep the reservation**! The Custom Compute Classes in
     `accelerated-platforms` specify `reservations.affinity: AnyBestEffort` as
     their top active rule (and include a Specific Reservation block), so your
     GKE cluster in that region will automatically consume the reservation to
     schedule your vLLM nodes.

     ```shell
     # Preview the deployment plan first (without --yes, no resources are created)
     python3 "${CR_CLI}" deploy \
       --project "${PROJECT_ID}" \
       --machine-type a3-highgpu-1g \
       --vm-count 2 \
       --priority on_demand:us-central1-a,us-central1-b,us-east4-a,us-east4-c,europe-west4-b \
       --name-prefix poc-ira

     # Add --yes once you are ready to lock in the reservation
     ```

   - **Workflow B — Active Spot / Flex-Start probe to pick your GKE region**: If
     your PoC relies on Spot VMs or DWS Flex-Start (or if Advisory APIs are not
     allow-listed on your project), run `deploy` with `--vm-count 1` and
     `--parallel` across candidate zones to see which zone provisions a real GPU
     VM first:

     ```shell
     python3 "${CR_CLI}" deploy \
       --project "${PROJECT_ID}" \
       --machine-type g4-standard-48 \
       --vm-count 1 \
       --priority spot:us-central1-a,us-east4-a,us-west1-a,europe-west4-b \
       --priority dws_flex:us-central1-a,us-east4-a,europe-west4-b \
       --parallel \
       --name-prefix poc-probe \
       --yes
     ```

     Once the output JSON reports `"status": "success"` and identifies the
     winning `zone` and `region` (for example, `europe-west4-b`), **delete the
     standalone probe VM** so it does not consume your GPU quota, and deploy
     your GKE cluster into that winning region:

     ```shell
     gcloud compute instances delete <PROBE_VM_NAME> \
       --zone="<WINNING_ZONE>" \
       --project="${PROJECT_ID}" \
       --quiet
     ```

##### Option 2: Run the Capacity Radar Web UI (Local or Cloud Run)

For interactive visual exploration across GPU/TPU families, start the FastAPI +
React application locally in Cloud Shell (with Web Preview on port `8000`) or
deploy it to Cloud Run in bring-your-own-credentials mode (`AUTH_MODE=user`,
where the Cloud Run service account holds zero IAM permissions and each user
pastes their own `gcloud auth print-access-token`):

```shell
cd "${HOME}/capacity_radar/frontend" && npm install && npm run build
cd "${HOME}/capacity_radar/backend" && python3 main.py
```

##### Option 3: Combine the Capacity Radar Agent Skill with Accelerated Platforms Skills

Both `capacity_radar` and `accelerated-platforms` ship with AI Agent Skills
(`SKILL.md`) designed for agentic IDEs (such as Google Antigravity, Gemini CLI,
or Claude Code):

- **`capacity_radar/skills/capacity-radar/SKILL.md`**: Authenticates, discovers
  GPU/TPU SKUs, runs multi-region advisories, and executes priority-based
  capacity hunts.
- **[`skills/gke-inference-stack-deploy/SKILL.MD`](/skills/gke-inference-stack-deploy/SKILL.MD)**:
  Configures `platform.auto.tfvars` and `cluster.auto.tfvars` and deploys the
  GKE Base Platform and `online_gpu` / `online_tpu` terraservices.
- **[`skills/llm-d-deploy-stack/SKILL.MD`](/skills/llm-d-deploy-stack/SKILL.MD)**,
  **[`skills/llm-d-workload-tuner/SKILL.MD`](/skills/llm-d-workload-tuner/SKILL.MD)**,
  and
  **[`skills/llm-d-benchmarking/SKILL.MD`](/skills/llm-d-benchmarking/SKILL.MD)**:
  Deploys, tunes, and benchmarks `llm-d` well-lit inference paths on the
  provisioned cluster.

Installing `capacity_radar/skills/capacity-radar` alongside the skills in this
repository allows your agent to find the region with the best GPU capacity and
immediately provision the GKE inference stack into that region in a single
conversation.

---

## Stage 3: Provision the GKE Inference Platform in your winning region(s)

Once Stage 2 identifies your target region(s) and zone(s), choose between two
deployment topologies:

- **[Topology A: Single-Region Fluid Compute PoC](#topology-a-single-region-fluid-compute-poc-fastest-setup)**:
  Deploy one regional GKE cluster in the highest-obtainability region, using
  Custom Compute Classes to cascade across Reservations, On-Demand, DWS
  Flex-Start, and Spot VMs across all zones in that region.
- **[Topology B: Multi-Region "Ring Around the World" Fluid Compute Fleet](#topology-b-multi-region-ring-around-the-world-fluid-compute-fleet)**:
  Deploy two or more regional GKE clusters across your ring (for example, a
  cost-optimized primary region + a low-preemption failover region) sharing a
  Multi-Region Cloud Storage bucket with Zonal Rapid Cache and fronted by a
  Multi-Cluster GKE Inference Gateway with `llm-d` Endpoint Picker routing.

### Topology A: Single-region Fluid Compute PoC (Fastest setup)

1. Set the repository path and your winning region and zones from Stage 2:

   ```shell
   export ACP_REPO_DIR="$(pwd)"
   export PROJECT_ID="<YOUR_PROJECT_ID>"
   export WINNING_REGION="<WINNING_REGION>" # e.g., europe-west4, us-central1, us-east4
   export PLATFORM_NAME="poc"
   ```

2. Configure the platform and cluster Terraform variables to use your winning
   region instead of the default `us-east4`:

   ```shell
   cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
   platform_default_project_id = "${PROJECT_ID}"
   platform_default_region     = "${WINNING_REGION}"
   platform_name               = "${PLATFORM_NAME}"
   EOF

   cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
   cluster_region = "${WINNING_REGION}"
   EOF
   ```

3. _(Optional)_ If you secured a **named Specific Reservation** with Capacity
   Radar in Stage 2:

   - By default, the Custom Compute Classes in
     [`platforms/gke/base/core/custom_compute_class/templates/manifests/gpu`](/platforms/gke/base/core/custom_compute_class/templates/manifests/gpu)
     use `reservations.affinity: AnyBestEffort` as their first active priority,
     which automatically consumes any matching unattached reservation in the
     zone.
   - If you created a `Specific` reservation
     (`--reservation-affinity=specific`), uncomment the top priority rule in the
     corresponding template (for example,
     [`custom-compute-gpu-h100-80gb-high-x1.yaml`](/platforms/gke/base/core/custom_compute_class/templates/manifests/gpu/h100-80gb/custom-compute-gpu-h100-80gb-high-x1.yaml#L28-L41))
     and set `name: <YOUR_RESERVATION_NAME>` before deploying.

4. Deploy the GKE Inference reference implementation (Autopilot is recommended
   for most PoCs and enables **Fast-Starting Nodes** for eligible `G2` L4 and
   `G4` RTX PRO 6000 workloads; use Standard if you need custom node-level
   DaemonSets or explicit Kubelet graceful shutdown configs):

   - **GKE Autopilot**:

     ```shell
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh"
     ```

   - **GKE Standard**:

     ```shell
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-standard.sh"
     ```

5. _(Optional)_ Configure **Zonal Rapid Cache** in the winning GPU zones before
   applying `terraform/online_gpu` (recommended if you will scale out to 4+
   concurrent replicas or use a multi-region bucket):

   ```shell
   # Replace with the winning zone(s) in your region from Stage 2
   export RAPID_CACHE_ZONES='["'"${WINNING_REGION}"'-a", "'"${WINNING_REGION}"'-b"]'
   sed -i "/^ira_online_gpu_rapid_cache_zones[[:blank:]]*=/{h;s|=.*|= ${RAPID_CACHE_ZONES}|};\${x;/^$/{s|.*|ira_online_gpu_rapid_cache_zones = ${RAPID_CACHE_ZONES}|;H};x}" \
     "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/inference-ref-arch.auto.tfvars"
   ```

6. Deploy the `online_gpu` (and/or `online_tpu`) terraservice (passing
   `-var="ira_online_gpu_pod_snapshots_enabled=true"` if you plan to use GKE Pod
   snapshots so Terraform creates the dedicated `*-pod-snapshots` HNS bucket
   with soft delete disabled and grants `roles/storage.objectUser` to the
   workload service account and GKE service agent):

   ```shell
   export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
   cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu" && \
   rm -rf .terraform/ terraform.tfstate* && \
   terraform init && \
   terraform plan -input=false -var="ira_online_gpu_pod_snapshots_enabled=true" -out=tfplan && \
   terraform apply -input=false tfplan && \
   rm tfplan
   ```

---

### Topology B: Multi-region "Ring Around the World" Fluid Compute fleet

When a single region cannot satisfy your capacity needs—or when you want to run
primarily on low-cost Spot VMs in a cheaper region (such as `us-east4`) with
automatic, zero-downtime failover to a low-preemption backup region (such as
`us-west1` or `europe-west4`)—combine the
[Fluid Compute multi-cluster pattern](https://discuss.google.dev/t/how-to-build-an-elastic-scalable-llm-inference-platform-on-gke-using-fluid-compute/388108)
with Accelerated Platforms:

```mermaid
%%{init: {"flowchart": {"htmlLabels": false, "padding": 20}, "themeVariables": {"fontFamily": "sans-serif"}}}%%
flowchart TD
  Client["Client Inference Traffic"] --> MCG["Multi-Cluster Gateway"]
  MCG --> EPP["llm-d GAIE Endpoint Picker"]

  subgraph Storage["Multi-Region HNS Storage"]
    GCS["Multi-Region HNS GCS Bucket"]
    RC1["Rapid Cache: us-east4-a"]
    RC2["Rapid Cache: us-west1-a"]
    GCS --> RC1
    GCS --> RC2
  end

  subgraph Ring1["Primary Region: us-east4"]
    CCC1["CCC: Res -> Spot -> Flex"]
    VLLM1["vLLM + Run:ai + Snapshots"]
    CCC1 --> VLLM1
  end

  subgraph Ring2["Failover Region: us-west1"]
    CCC2["CCC: Res -> Spot -> Flex"]
    VLLM2["vLLM + Run:ai + Snapshots"]
    CCC2 --> VLLM2
  end

  RC1 -.->|"Local Read"| VLLM1
  RC2 -.->|"Local Read"| VLLM2
  EPP -->|"Primary Route"| VLLM1
  EPP -->|"Failover Route"| VLLM2
```

#### Key primitives of the Multi-Region Ring

1. **Shared Multi-Region HNS Bucket + Zonal Rapid Caches**:

   - In `platforms/gke/base/_shared_config/huggingface.auto.tfvars`, set
     `huggingface_hub_models_bucket_location = "US"` (or `"EU"`, `"ASIA"`) when
     deploying the first cluster in your ring so the Hierarchical Namespace
     model bucket is created as a multi-region bucket.
   - When deploying subsequent clusters in the ring (using a distinct
     `platform_name` per region, such as `americas` and `europe`), set
     `huggingface_hub_models_bucket_name` to point to the existing shared
     multi-region bucket, and set `ira_online_gpu_rapid_cache_zones` to each
     cluster's local GPU zones.
   - Alternatively, if you mount the bucket via Cloud Storage FUSE instead of
     the Run:ai Model Streamer, use a `PersistentVolume` with
     `storageClassName: gcsfusecsi-serving` and
     `gcsfuseMetadataPrefetchOnMount: "true"`, which automatically applies the
     GKE `aiml-serving` FUSE profile tuned for your node's RAM and local NVMe.

2. **Extended 120-Second Graceful Node Shutdown for Spot VMs**:

   - By default, Spot VMs provide a 30-second preemption notice. On GKE Standard
     node pools, applying a `kubeletConfig` with
     `shutdownGracePeriodSeconds: 120` extends the preemption window to **2
     minutes**:

     ```yaml
     # kubelet-config.yaml
     kubeletConfig:
       shutdownGracePeriodSeconds: 120
       shutdownGracePeriodCriticalPodsSeconds: 30
     ```

   - **Why 120 seconds matters with GKE Pod snapshots**: A replacement vLLM
     replica restored from a GKE Pod snapshot answers its first request in **28
     to 56 seconds** once scheduled. Extending the Spot shutdown grace period to
     120 seconds gives GKE and the Multi-Cluster Inference Gateway substantially
     more runway to drain in-flight token streams and bring up a replacement
     replica on a fallback Spot, DWS Flex-Start, or secondary-region node before
     the preempting VM terminates.

3. **Custom Compute Class with `capacityCheckWaitTimeSeconds` for DWS
   Flex-Start**:

   - Inside each cluster in the ring, the `ComputeClass` cascades from
     Reservations to Spot and DWS Flex-Start (setting
     `capacityCheckWaitTimeSeconds: 300` so GKE waits up to 5 minutes in the DWS
     queue before falling back to the next priority or machine series, such as
     falling back from `a3-highgpu-8g` to `a3-megagpu-8g`).

4. **Multi-Cluster GKE Inference Gateway (`gke-l7-rilb-mc`) + `llm-d` GAIE
   Endpoint Picker**:
   - Allocate non-colliding `REGIONAL_MANAGED_PROXY` subnets in each ring region
     (for example, `172.23.1.0/24` in `us-west1` and `172.23.2.0/24` in
     `us-east4`).
   - Export the vLLM `Service` in each member cluster using
     `kind: ServiceExport` (`net.gke.io/v1`) and attach a `HealthCheckPolicy`
     (`/health` on port `8000`) and `GCPBackendPolicy` (`timeoutSec: 600`) to
     both `ServiceImport` and `ServiceExport`.
   - Deploy the Gateway API Inference Extension (`InferencePool` + Endpoint
     Picker `EPP`) and bind an `HTTPRoute` on the `gke-l7-rilb-mc` `Gateway` to
     the `InferencePool`. Traffic is routed with KV-cache and queue-depth
     awareness across healthy pods and automatically fails over across regions
     when Spot capacity in one region is reclaimed.

---

## Stage 4: Turn on all fast-start and fast-restore tricks

With your cluster running in a region that has verified accelerator capacity,
use the three workload patterns in this repository to eliminate startup,
scale-out, and routing bottlenecks.

### Trick 1: Stream weights directly to GPU VRAM with NVIDIA Run:ai Model Streamer (`vllm-runai`)

Instead of staging 50–70 GiB of safetensors onto local disk or streaming
sequentially through a filesystem, the
[Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md)
uses `--load-format=runai_streamer` to read tensors concurrently from your
Hierarchical Namespace Cloud Storage bucket (`gs://`) directly into host memory
buffers and across PCIe into GPU memory.

- **Measured weight load times**:
  - **Gemma 3 27B** (`google/gemma-3-27b-it`, `51.54 GiB`): **9.1 s** median on
    NVIDIA RTX PRO 6000 96GB
  - **Gemma 4 31B** (`google/gemma-4-31b-it`, `58.99 GiB`): **11.1 – 25.7 s** on
    NVIDIA RTX PRO 6000 96GB, **20.1 – 25.8 s** on NVIDIA H100 80GB

#### Quick-start deployment commands

1. Stage your chosen Gemma model into the Hierarchical Namespace Cloud Storage
   bucket using the in-cluster downloader Job:

   ```shell
   export HF_MODEL_ID="google/gemma-4-31b-it" # or google/gemma-3-27b-it
   source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
   "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
   kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
   kubectl --namespace="${huggingface_hub_downloader_kubernetes_namespace_name}" wait --for=condition=complete --timeout=1800s "job/${HF_MODEL_ID_HASH}-hf-model-to-gcs"
   kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
   ```

2. Deploy the `vllm-runai` overlay for your accelerator (`h100` or
   `rtx-pro-6000`), which includes the `HorizontalPodAutoscaler` scaling on
   `vllm:num_requests_waiting`:

   ```shell
   export ACCELERATOR_TYPE="rtx-pro-6000" # or h100
   "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh"
   kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/${ACCELERATOR_TYPE}-${HF_MODEL_NAME}"
   ```

For complete instructions, scale-out load generation, and Rapid Cache hit-rate
verification, see
[Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md).

---

### Trick 2: Restore warmed-up replicas in under a minute with GKE Pod snapshots (`vllm-podsnapshot-fast-restore`)

Even when weight loading takes only 11 to 25 seconds, vLLM still spends 2 to 3+
minutes profiling memory, running `torch.compile`, and capturing CUDA graphs on
every cold start. The
[GKE Pod snapshots inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md)
captures the complete CPU and GPU memory state of the first replica once it is
healthy (`/proc/gvisor/checkpoint`) and restores every subsequent replica from
Cloud Storage:

| Workload Tier & Accelerator               | Cold Start to `Ready` (`v0.26.0` / `v0.19.1`) | Snapshot Restore to First `/v1/completions` Response |
| ----------------------------------------- | --------------------------------------------- | ---------------------------------------------------- |
| **8B–9B Class Model, NVIDIA L4 24GB**     | 162 s / 433 s                                 | **28.2 s / 26 to 29 s**                              |
| **8B–9B Class Model, NVIDIA H100 80GB**   | 68 s / 168 s                                  | **41.0 s / 46 to 52 s**                              |
| **Gemma 4 31B, NVIDIA H100 80GB**         | 240 s / 224 s                                 | **53.3 to 56.3 s / 36 to 38 s**                      |
| **Gemma 4 31B, NVIDIA RTX PRO 6000 96GB** | 215 s / 210 s                                 | **104.9 s (cold node) / 35.0 to 43.0 s (warm node)** |

#### Two PoC paths for Pod snapshots

- **Path A (8B–9B single-GPU overlay on `L4` or `H100`) — Zero bucket staging**:
  Downloads weights directly from the Hugging Face Hub on the first replica,
  deletes the token files and large weight files (`*.safetensors`, `*.bin`,
  `*.pt`, `*.lock`) from `/root/.cache/huggingface` before triggering
  `/proc/gvisor/checkpoint` while keeping small tokenizer and configuration
  files, and restores subsequent replicas in **28 to 41 seconds**. Use Path A
  when you want to demonstrate sub-minute GPU snapshot restore in under 15
  minutes without running a model download job first.
- **Path B (`h100-gemma-4-31b-it` or `rtx-pro-6000-gemma-4-31b-it`) — Run:ai
  Model Streamer + Pod snapshots**: Streams **Gemma 4 31B** (`58.99 GiB`) from
  the HNS Cloud Storage bucket on the first replica (fast cold start, zero local
  disk copy) and restores every scale-out or preemption-replacement replica from
  the snapshot in **35 to 56 seconds** on a warm node.

#### Quick-start deployment and measurement commands

```shell
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

# 1. Enable Pod snapshots on the cluster (one-time per cluster)
gcloud beta container clusters update "${cluster_name}" \
  --enable-pod-snapshots \
  --location="${cluster_region}" \
  --project="${cluster_project_id}"

# 2. Configure and deploy the chosen overlay (e.g., Gemma 4 31B on H100 or RTX PRO 6000)
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
export VLLM_VARIANT="rtx-pro-6000-gemma-4-31b-it" # or h100-gemma-4-31b-it
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/${VLLM_VARIANT}"

# 3. After the snapshot reaches AllSnapshotsAvailable, scale to 2 replicas and measure time-to-first-response
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/measure_restore.sh" 2
```

For full details and troubleshooting, see
[Online inference using vLLM with GKE Pod snapshots and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-podsnapshots.md).

---

### Trick 3: Add AI-aware routing and benchmark with `llm-d` well-lit paths

When your PoC scales beyond a single replica—or spans multiple regions in a
Fluid Compute ring—standard round-robin load balancing degrades tail latency
because it ignores KV-cache prefix locality and per-replica queue depth.

Use the
[Intelligent inference scheduling with `llm-d`](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/llmd-vllm-with-hf-model.md)
well-lit paths to deploy the **GKE Inference Gateway (`InferencePool` + Endpoint
Picker `EPP`)**:

- **[Optimized Baseline](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-optimized-baseline-vllm-with-hf-model.md)**:
  KV-cache and queue-depth aware routing with vLLM.
- **[Precise Prefix-Cache Routing](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-precise-prefix-cache-routing-vllm-with-hf-model.md)**:
  Routes multi-turn conversations and shared system prompts to the replica
  holding the warm KV prefix cache.
- **[Predicted Latency Routing](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/well-lit-paths/llmd-predicted-latency-routing-vllm-with-hf-model.md)**:
  Dynamically scores replicas using predicted Time-to-First-Token (TTFT) and
  Time-Per-Output-Token (TPOT) SLOs.

To benchmark throughput, TTFT, and scale-out behavior during your PoC, use
[Benchmarking Online inference performance on GKE (`inference-perf`)](/docs/platforms/gke/base/use-cases/inference-ref-arch/inference-perf-bench/inf-perf-benchmarking-with-hf-model.md)
or invoke the [`llm-d-benchmarking` skill](/skills/llm-d-benchmarking/SKILL.MD).

---

## Stage 5: PoC decision matrix and pre-flight checklist

Use this quick-reference matrix to choose the fastest PoC path for your use
case:

| PoC Scenario                                                           | Capacity Discovery Method                                                            | Cluster Topology                                                         | Recommended Serving Pattern                                                                                                                              |
| ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Quickest 15-minute demo of sub-minute GPU scale-out (8B–9B model)**  | Check `L4` or `H100` Spot advisory via **Capacity Radar CLI** (`advise spot`)        | Single-Region GKE Autopilot in winning region                            | **Pod Snapshots Path A** — no GCS model staging required                                                                                                 |
| **Single-GPU 27B–31B model PoC (`Gemma 4 31B`, `Gemma 3 27B`)**        | Sweep `g4-standard-48` (RTX PRO 6000) & `a3-highgpu-1g` (H100) across regions        | Single-Region GKE Autopilot (enables Fast-Starting Nodes on `G4`)        | **Run:ai Model Streamer (`vllm-runai`)** for rapid tuning, then **Pod Snapshots Path B** (`vllm-podsnapshot-fast-restore`) once flags are frozen         |
| **Multi-GPU Tensor Parallel PoC (`TP >= 2`)**                          | Run **Capacity Radar** `advise calendar-plan` + `advise spot` for `a3-highgpu-4g/8g` | Single-Region or Dual-Region Ring with Custom Compute Class fallback     | **Run:ai Model Streamer** + **`llm-d` Well-Lit Path** (Note: Pod snapshots only support `TP=1`)                                                          |
| **Cost-optimized resilient serving on Spot / DWS Flex across regions** | Compare Spot price vs. preemption rate in **Capacity Advisor** + **Capacity Radar**  | **Multi-Region "Ring Around the World"** (cheap primary + stable backup) | Multi-Region HNS Bucket + **Zonal Rapid Cache** + **120s Spot Graceful Shutdown** + **Pod Snapshots Path B** + **Multi-Cluster GKE Inference Gateway**   |
| **Data estate anchored in Managed Lustre or Hyperdisk ML**             | Check GPU availability in the Lustre/Hyperdisk zone first; sweep ring for overflow   | Primary cluster in anchor zone + overflow cluster(s) in ring regions     | Direct Lustre / Hyperdisk ML mount in primary zone; tier promoted checkpoints to Multi-Region GCS + Rapid Cache for **Run:ai Streamer** in overflow ring |

### Common PoC pitfalls to avoid

- **`model-download` Job stays `Pending` (`GCE quota exceeded` or
  `NotTriggerScaleUp`)**: The Hugging Face model downloader Job uses the
  `model-download` compute class, which provisions `c4-standard-4-lssd` or
  `c3-standard-4-lssd` CPU nodes (4 vCPU, 15–16 GB RAM). Verify that your chosen
  region has `C4_CPUS` or `C3_CPUS` quota in Stage 2, and keep pod resource
  requests at `cpu: 2000m, memory: 10Gi` so GKE Autopilot daemonset overhead
  fits on a single 4-vCPU VM. To speed up model staging without increasing pod
  CPU requests, set `HF_MAX_WORKERS: "8"` and `HF_XET_HIGH_PERFORMANCE: "1"`.
- **Mixed-case Hugging Face IDs failing to load from `gs://`**: The
  `hf-model-to-gcs` script normalizes `MODEL_ID` to lowercase
  (`export MODEL_ID=${MODEL_ID,,}`) before uploading to Cloud Storage. For
  models with mixed-case repository names (`Organization/Model-Name`), pass the
  lowercase GCS path in `--model=gs://<bucket>/organization/model-name` and
  preserve the canonical model identifier via
  `--served-model-name=Organization/Model-Name`.
- **Hybrid Mamba / linear-attention architectures failing during CUDA graph
  capture**: Hybrid linear-attention + full-attention architectures allocate a
  dedicated recurrent state block per active decode sequence. In vLLM `v0.26.0`,
  the default `--max-num-seqs=1024` can exceed the available state blocks on a
  single GPU, causing startup to fail with
  `ValueError: max_num_seqs (1024) exceeds available Mamba cache blocks`. Pass
  `--max-num-seqs=512` (or `--max-num-seqs=256`) explicitly when serving hybrid
  linear-attention architectures.
- **`google/gemma-4-31b-it` (`58.99 GiB` weights) failing with KV cache
  `ValueError` or FlashInfer sampler OOM on a single `80 GB H100`
  (`a3-highgpu-1g`)**: On a `96 GB RTX PRO 6000`,
  `--gpu-memory-utilization=0.90` leaves `~24.9 GiB` for KV cache (`29,655`
  tokens), which easily supports `--max-model-len=16384`. On an `80 GB H100`
  (`79.1 GiB` usable VRAM), `0.90 × 79.1 GiB = 71.2 GiB` minus `58.99 GiB`
  weights leaves only `10.62 GiB` (`12,624–12,629` tokens), whereas
  `--max-model-len=16384` requires `13.76 GiB`
  (`ValueError: To serve at least one request with the model's max seq len (16384), 13.76 GiB KV cache is needed`).
  Conversely, raising `--gpu-memory-utilization=0.95` leaves insufficient
  unallocated VRAM for FlashInfer's `top_k_mask_logits` sampler (`994 MiB`
  scratch at CUDA graph batch size 512 / `--max-num-seqs=256`). On
  `1× H100 80GB`, always set:
  - `--gpu-memory-utilization=0.90` (leaves `7.9 GiB` unallocated VRAM headroom)
  - `--max-model-len=8192` (fits within the `10.62 GiB` / `12,629` token KV
    budget)
  - `--max-num-seqs=128` (reduces FlashInfer sampler scratch from `994 MiB` to
    `248 MiB`)
- **Changing pod flags when using Pod snapshots**: A `PodSnapshot` is matched to
  an exact pod template hash. Do all flag and `--max-model-len` tuning with
  `vllm-runai` first; enable `vllm-podsnapshot-fast-restore` once your
  configuration is stable.
- **Active migration evicting the cold-start replica during snapshot upload**:
  Uploading a 68–70 GiB snapshot takes 11 to 13.5 minutes. Always keep the
  included `PodDisruptionBudget` (`minAvailable: 1`) applied so GKE active
  migration does not drain the cold-start node mid-upload.
- **Rapid Cache warm-up and teardown timing**: Newly created Rapid Caches can
  take over an hour before they begin serving cached bytes, and destroying a
  Rapid Cache enforces a 1-hour grace period before the underlying model bucket
  can be deleted. Only enable `ira_online_gpu_rapid_cache_zones` when testing
  high-concurrency scale-outs (6+ simultaneous replica loads) or multi-region
  bucket caching.
- **Cleaning up Capacity Radar probe VMs or reservations**: If you used Capacity
  Radar's `deploy` command to probe Spot availability or create an On-Demand
  Reservation, remember to delete any standalone probe VMs before deploying GKE
  (so they do not occupy quota) and delete any reservations when tearing down
  your PoC.

---

## Stage 6: Real-world PoC case study & Inference Golden Signals — Gemma 4 31B on 2× NVIDIA RTX PRO 6000 96GB

To validate this guide end-to-end, we executed the full workflow on a GKE
Autopilot cluster (`us-central1`, chosen after Stage 2 Capacity Radar
`advise spot` flagged `us-east4` at `0.1` obtainability and `us-central1-b` /
`us-central1-c` at `0.9` obtainability) and benchmarked
**`google/gemma-4-31b-it`** (`Gemma4ForConditionalGeneration`, `bfloat16`, 31B
parameters) across **2 replicas (`1 × NVIDIA RTX PRO 6000 96GB` /
`g4-standard-48` per replica)**.

The deployment used `vllm/vllm-openai:v0.26.0`,
`cloud.google.com/compute-class: gpu-rtx-pro-6000-96gb-x1`,
`--load-format=runai_streamer` streaming from a regional Hierarchical Namespace
Cloud Storage bucket (`gs://`), `--gpu-memory-utilization=0.90`, and
`--max-model-len=16384`.

### 1. Cold-start breakdown & KV cache capacity (2 replicas)

| Metric (Per Replica / 2-Replica Total)                     | Measured Value (`google/gemma-4-31b-it` on `2 × RTX PRO 6000 96GB`) | Key Takeaway                                                                                                           |
| ---------------------------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Model Architecture & Precision**                         | Standard Transformer + Vision Encoder (`bfloat16`, 31B parameters)  | Served natively in `bfloat16` on a single 96 GB GPU (`TP=1`) without quantization loss                                 |
| **Model Weight Footprint in GPU VRAM**                     | **58.99 GiB**                                                       | Fits comfortably on a single 96 GB RTX PRO 6000 with ~37 GiB remaining before KV cache allocation                      |
| **Spot `g4-standard-48` Node Provisioning**                | **52 – 58 s** (`us-central1-b`, `us-central1-c`)                    | Stage 2 capacity discovery placed pods directly into high-obtainability zones with zero `ZONE_RESOURCE_POOL_EXHAUSTED` |
| **GCFS Container Image Pull (`v0.26.0`, 8.91 GB)**         | **1.58 s – 1.86 s**                                                 | Image Streaming eliminates the ~4 minute cold container pull on freshly scaled GPU nodes                               |
| **Run:ai Model Streamer Load (`gs://` $\rightarrow$ GPU)** | **25.67 s / 25.93 s** (`~2.29 GiB/s` per pod)                       | Zero local disk staging; both replicas stream weights concurrently from HNS Cloud Storage                              |
| **`torch.compile` Duration**                               | **29.66 s / 30.49 s**                                               | Eliminated on subsequent scale-outs when paired with GKE Pod snapshots (`35.0 s` warm-node restore)                    |
| **CUDA Graph Capture (51 graphs, `FULL+PIECEWISE`)**       | **12.0 s** (`0.86 GiB`)                                             | Captured once during cold start and persisted inside the GKE Pod snapshot                                              |
| **Available KV Cache Memory (per GPU / 2 GPUs)**           | **24.91 GiB** per GPU (**49.82 GiB** across 2 GPUs)                 | `96 GB` GDDR7 VRAM provides **`2.35×` more KV cache memory** than an `80 GB` GPU (`10.62 GiB`) for a `58.99 GiB` model |
| **KV Cache Token Capacity (per GPU / 2 GPUs)**             | **29,655 tokens** per GPU (**59,310 tokens** across 2 GPUs)         | Supports `--max-model-len=16384` (up to `32,768`) on a single GPU without tensor parallelism                           |

### 2. Inference Golden Signals under saturation (2 replicas, `~335` input tokens / `128` output tokens)

The 2-replica `google/gemma-4-31b-it` deployment was swept across concurrency
levels `1` to `128` using streaming `/v1/chat/completions` requests balanced
evenly across both replicas while scraping vLLM Prometheus metrics
(`vllm:num_requests_running`, `vllm:num_requests_waiting`,
`vllm:kv_cache_usage_perc`) every 500 ms:

| Concurrency (2 Replicas) | Traffic: Req/s | Traffic: Output Tok/s | Traffic: Total Tok/s | Latency: TTFT p50 / p90 / p99 (ms) | Latency: TPOT p50 / p90 / p99 (ms) | Latency: E2E p50 / p99 (s) | Saturation: Running Reqs (Mean / Peak) | Saturation: Waiting Queue (Mean / Peak) | Saturation: KV Cache % (Mean / Peak) | Errors (%) |
| ------------------------ | -------------- | --------------------- | -------------------- | ---------------------------------- | ---------------------------------- | -------------------------- | -------------------------------------- | --------------------------------------- | ------------------------------------ | ---------- |
| **1**                    | 0.18           | 22.5                  | 80.9                 | 85.3 / 87.5 / 89.5                 | 44.18 / 44.30 / 44.35              | 5.70 / 5.72                | 1.0 / 1.0                              | 0.0 / 0.0                               | 0.7% / 1.6%                          | 0.0%       |
| **4**                    | 0.69           | 88.7                  | 319.4                | 147.3 / 155.2 / 157.1              | 44.23 / 44.47 / 44.47              | 5.76 / 5.77                | 3.8 / 4.0                              | 0.0 / 0.0                               | 2.6% / 3.1%                          | 0.0%       |
| **16**                   | 2.44           | 312.3                 | 1,128.7              | 491.8 / 498.1 / 499.4              | 46.13 / 48.98 / 49.00              | 6.35 / 6.36                | 15.4 / 16.0                            | 0.0 / 0.0                               | 10.4% / 12.5%                        | 0.0%\*     |
| **32**                   | 4.49           | 575.2                 | 2,080.1              | 958.5 / 966.8 / 967.5              | 48.49 / 52.35 / 54.83              | 7.12 / 7.12                | 29.8 / 32.0                            | 0.0 / 0.0                               | 20.1% / 25.1%                        | 0.0%       |
| **64**                   | 7.34           | 939.2                 | 3,398.1              | 1,299.1 / 1,868.6 / 1,893.7        | 58.17 / 62.90 / 67.16              | 8.69 / 8.76                | 56.2 / 64.0                            | 0.0 / 0.0                               | 37.5% / 50.2%                        | 0.0%       |
| **128**                  | **10.42**      | **1,333.8**           | **4,840.9**          | **2,367.6 / 3,744.3 / 3,770.7**    | **73.16 / 83.29 / 89.47**          | **11.58 / 12.13**          | **108.4 / 128.0**                      | **3.3 / 37.0**                          | **72.2% / 98.8%**                    | **0.0%**   |

_\*Across 512 total benchmark requests, 511 succeeded (`99.8%` success rate; 1
request at Concurrency 16 experienced a transient client TCP socket reset)._

### 3. Interpreting the Golden Signals for PoC sizing and HPA configuration

1. **Linear Throughput Scaling & Interactive Decode Latency (`TPOT`)**: From
   `Concurrency=1` to `Concurrency=64`, `google/gemma-4-31b-it` scales output
   throughput by **`41.7×`** (`22.5 tok/s` $\rightarrow$ `939.2 tok/s`, or
   `3,398.1 total tok/s`) while keeping `TPOT p50` between **`44.2 ms` and
   `58.2 ms`** with **zero waiting queue (`vllm:num_requests_waiting = 0`)**. At
   `Concurrency=128`, the 2-replica deployment reaches **`1,333.8 output tok/s`
   (`4,840.9 total tok/s`)**.
2. **KV Cache Saturation Threshold on a Single 96 GB GPU**: At `Concurrency=128`
   (`64` concurrent requests per replica $\times$ `~463` tokens per request
   $\approx 29,632$ tokens), `google/gemma-4-31b-it` reaches **`98.8%` peak KV
   cache utilization** (`29,655` token ceiling per replica at
   `--gpu-memory-utilization=0.90`) and begins holding excess arrivals
   (`peak_waiting_reqs = 37`) in `vllm:num_requests_waiting` until active
   sequences finish decoding.
3. **Why `vllm:num_requests_waiting` is the right HPA signal**: As soon as KV
   cache utilization approaches saturation (`Concurrency > 64`), vLLM
   immediately increments `vllm:num_requests_waiting`. The
   `HorizontalPodAutoscaler` in `vllm-runai` (configured with `averageValue: 3`
   on `vllm:num_requests_waiting`) triggers scale-out at the exact knee of the
   latency curve (`Concurrency = 64–128`, where `TPOT p99` crosses `65–89 ms`),
   bringing up replacement or scale-out replicas via Run:ai Model Streamer or
   GKE Pod snapshots before client timeouts occur.

---

## Stage 7: Multi-Region "Follow-the-Sun" Capacity Hunt & Accelerator Architecture Case Study (`us-central1`, `europe-west4`, `asia-south2`)

When expanding a PoC across regions or comparing accelerator families
(`NVIDIA RTX PRO 6000 96GB` Blackwell vs. `NVIDIA H100 80GB` Hopper), a single
region rarely holds simultaneous quota and physical stock across every GPU SKU.
By combining **Stage 2 (`capacity_radar` + quota audit)** with **Stage 3
(Multi-Region Ring)**, we stood up a three-region GKE Autopilot ring across
**Americas (`us-central1` / `inf-americas`)**, **Europe (`europe-west4` /
`inf-europe`)**, and **Asia-Pacific (`asia-south2` / `inf-apac`)** to benchmark
**`google/gemma-4-31b-it`** and **`google/gemma-3-27b-it`** across Blackwell and
Hopper GPUs.

### 1. Multi-region capacity discovery & placement outcome

Sweeping `capacity_radar advise spot` alongside regional quota checks revealed
why multi-region capacity farming is essential:

| Region (`Cluster`)                 | GPU Quota (`On-Demand` / `Spot`)                    | `capacity_radar` Top Obtainability Score                          | Actual GKE Autopilot Provisioning Outcome                                                                                                                                               | Assigned Gemma Workloads & Accelerators                                                                                      |
| ---------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **`us-central1` (`inf-americas`)** | `RTX PRO 6000`: `8` OD / `8` Spot (`H100`: `0` OD)  | `g4-standard-48` (`1×`): `0.93`; `g4-standard-96` (`2×`): `0.85`  | Provisioned `2× g4-standard-48` (`us-central1-a/b`) and `1× g4-standard-96` (`us-central1-b`) in **52–95 s**                                                                            | **`Gemma 4 31B`** (`1× RTX PRO 6000 96GB`, Pod Snapshots + Run:ai Streamer) & **`Gemma 3 27B`** (`1× RTX PRO 6000 96GB`)     |
| **`europe-west4` (`inf-europe`)**  | `H100`: `0` OD / `16` Spot; `H100 Mega`: `16` Spot  | `a3-highgpu-2g`: `< 0.40` (stockout); **`a3-megagpu-8g`: `0.90`** | `a3-highgpu-2g` failed (`GCE out of resources` in `europe-west4-c`); pivoting to **`a3-megagpu-8g` (`8× H100 Mega`)** provisioned in **90 s** (`europe-west4-c`) and co-hosted replicas | **`Gemma 4 31B`** on `H100 80GB Mega` (`a3-megagpu-8g`, Hopper `FA4` + RAM-backed Cloud Storage FUSE prefetch)               |
| **`asia-south2` (`inf-apac`)**     | `H100`: `1` OD / `8` Spot (`RTX PRO 6000`: `0` all) | `a3-highgpu-1g`: **`0.94`** (`asia-south2-b`, `asia-south2-a`)    | Provisioned `a3-highgpu-1g` (`1× H100 80GB`) in **78–85 s**                                                                                                                             | **`Gemma 4 31B`** (`1× H100 80GB`, `--gpu-memory-utilization=0.90 --max-model-len=8192 --max-num-seqs=128`, Run:ai Streamer) |

### 2. Cross-region cold-start, KV cache capacity & saturation comparison (`google/gemma-4-31b-it` & `google/gemma-3-27b-it`)

| Region (`Cluster`)                 | Model                   | Accelerator (`TP`)                        | Attention Kernel Backend               | Weight Load Time (`gs://` $\rightarrow$ GPU)         | Model VRAM (`GiB/GPU`) | KV Cache (`GiB/GPU`) | KV Cache Capacity (Tokens) | `c=1` Decode `TPOT` p50 | `c=16` Out Tok/s (`TPOT` p50) | Peak Out Tok/s (`Total Tok/s`)             |
| ---------------------------------- | ----------------------- | ----------------------------------------- | -------------------------------------- | ---------------------------------------------------- | ---------------------- | -------------------- | -------------------------- | ----------------------- | ----------------------------- | ------------------------------------------ |
| **`us-central1` (`inf-americas`)** | `google/gemma-4-31b-it` | `2× (1× RTX PRO 6000 96GB)` (`2× TP=1`)   | `FLASH_ATTN` (`FA2` Blackwell SM 12.0) | **11.1 – 25.67 s** (`Run:ai`) / **33.24 s** (`FUSE`) | `58.99 GiB`            | **24.91 GiB**        | **29,655 / GPU** (`16K`)   | `28.59 ms`              | `552.8` (`35.67 ms`)          | **`1,434.2`** (`717.1/GPU` \| `3,872.0`)   |
| **`asia-south2` (`inf-apac`)**     | `google/gemma-4-31b-it` | `1× H100 80GB` (`TP=1`, `max_seqs=128`)\* | `FLASH_ATTN` (**`FA4` Hopper SM 9.0**) | **20.1 – 25.77 s** (`Run:ai`) / **40.34 s** (`FUSE`) | `58.99 GiB`            | **10.62 GiB**        | **12,629 / GPU** (`8K`)\*  | **`24.95 ms`**          | `1,303.6` (**`21.23 ms`**)    | **`2,033.6`** (`2,033.6/GPU` \| `3,520.1`) |
| **`us-central1` (`inf-americas`)** | `google/gemma-3-27b-it` | `1× RTX PRO 6000 96GB` (`TP=1`)           | `FLASH_ATTN` (`FA2` Blackwell SM 12.0) | **9.10 s** (`Run:ai Streamer`)                       | `51.54 GiB`            | **31.80 GiB**        | **>45,000 / GPU** (`16K`)  | `25.40 ms`              | `610.0` (`28.10 ms`)          | **`820.0+ / GPU`**                         |

_\*Measured with `--gpu-memory-utilization=0.90`, `--max-model-len=8192`, and
`--max-num-seqs=128` on `1× H100 80GB` (`~220` input tokens / `128` output
tokens)._

### 3. Key architectural findings from the multi-region Gemma PoC

1. **Built-in ComputeClass priorities (`[On-Demand, Flex-Start, Spot]`) stall
   GKE Autopilot in 0-On-Demand-quota regions**: When a region has `0` On-Demand
   GPU quota (such as `europe-west4` with `0` On-Demand `H100` but `16`
   `PREEMPTIBLE_NVIDIA_H100_GPUS`), the built-in `gpu-h100-80gb-*` ComputeClass
   causes Node Auto-Provisioning to repeatedly fail on Priority 1
   (`GCE quota exceeded`) before falling through to Spot. Creating a
   **Spot-first Custom Compute Class** (`spot: true` as the first priority rule,
   plus fallback from `a3-highgpu-8g` to `a3-megagpu-8g`) drops node
   provisioning time to **~90 seconds**.
2. **Up to 465× faster multi-shard GCS FUSE weight loading using a RAM-backed
   `gke-gcsfuse-cache` override**:

   - Setting `file-cache:max-size-mb:-1` without a local NVMe SSD writes the GCS
     FUSE file cache onto the node's boot disk and triggers kubelet
     `DiskPressure` eviction on models larger than `50 GiB`.
   - Conversely, capping `file-cache:max-size-mb:20480` (`20 GiB`) fails in two
     cases: (a) when a single shard exceeds `20 GiB` (for example,
     `google/gemma-4-31b-it` shard 1 is `49.9 GB`, causing
     `cache_file_for_range_read` to bypass the cache), or (b) when a multi-shard
     checkpoint (`50–70 GiB` across 10+ shards) scans or prefetches all shards
     upfront before loading weights shard-by-shard, thrashing the `20 GiB` LRU
     cache (`399 s per shard`).
   - **Fix**: When mounting via Cloud Storage FUSE (instead of
     `--load-format=runai_streamer`), override the CSI-injected
     `gke-gcsfuse-cache` volume in the Pod spec with a RAM-backed `emptyDir`
     (`medium: Memory, sizeLimit: 80Gi`), set
     `file-cache:max-size-mb:75000,file-cache:cache-file-for-range-read:true`,
     and pass `--safetensors-load-strategy=prefetch`:

     ```yaml
     volumes:
       - name: gke-gcsfuse-cache
         emptyDir:
           medium: Memory
           sizeLimit: 80Gi
       - name: gcs-fuse-csi-ephemeral
         csi:
           driver: gcsfuse.csi.storage.gke.io
           volumeAttributes:
             bucketName: <your-hns-model-bucket>
             mountOptions: "implicit-dirs,only-dir=google/gemma-4-31b-it,file-cache:enable-parallel-downloads:true,file-cache:max-size-mb:75000,file-cache:cache-file-for-range-read:true,read_ahead_kb=1024"
     ```

     With this configuration, vLLM prefetches `59–66 GiB` checkpoints into host
     RAM in **`4.8–7.5 s`** and loads tensors into GPU VRAM in **`11.2–20.3 s`**
     with zero boot-disk consumption.

3. **`Gemma 4 31B` (`58.99 GiB` BF16) — `H100 80GB` compute speed vs.
   `RTX PRO 6000 96GB` VRAM capacity**:
   - **Single-GPU compute & bandwidth (`H100 80GB`)**: A single `H100 80GB`
     delivers **`2.8×` higher single-GPU output throughput** on `Gemma 4 31B`
     (`2,033.6` vs. `717.1 out tok/s/GPU`, accelerated by `3.35 TB/s` HBM3
     bandwidth and Hopper's `FA4` attention backend) and **`13%` lower
     single-stream decode TPOT** (`24.95 ms` vs. `28.59 ms`).
   - **Single-GPU KV cache headroom (`RTX PRO 6000 96GB`)**: On an `80 GB H100`
     (`79.1 GiB` usable VRAM), `Gemma 4 31B`'s `58.99 GiB` weights leave only
     `10.62 GiB` (`12,629` tokens at `--gpu-memory-utilization=0.90`), which
     cannot fit `--max-model-len=16384` (requires `13.76 GiB`), and raising
     `--gpu-memory-utilization=0.95` on `v0.26.0` starves FlashInfer's
     `top_k_mask_logits` sampler (`994 MiB` scratch at CUDA graph batch size 512
     / `--max-num-seqs=256`). Tuning `Gemma 4 31B` on `1× H100 80GB` to
     `--gpu-memory-utilization=0.90`, `--max-model-len=8192`, and
     `--max-num-seqs=128` reduces sampler scratch to `248 MiB` and leaves
     `7.9 GiB` of unallocated VRAM headroom.
   - By contrast, `RTX PRO 6000`'s **`96 GiB` GDDR7 VRAM** provides
     **`24.91 GiB` (`29,655` tokens at `gpu_util=0.90`, and up to `197,888`
     tokens with tuned KV settings)** on a single GPU, supporting `16K–32K`
     context windows and high concurrency (`c=64..128`) without KV cache
     preemption (`0` waiting queue at `c=64`).

## Additional Reading

- [15-minute live demo runbook: Multi-region GPU capacity farming, fast-start model streaming, and sub-minute GKE Pod snapshot restore](/docs/platforms/gke/base/use-cases/inference-ref-arch/poc-15min-demo-runbook.md)
- [How to build an elastic, scalable LLM Inference Platform on GKE using Fluid Compute](https://discuss.google.dev/t/how-to-build-an-elastic-scalable-llm-inference-platform-on-gke-using-fluid-compute/388108)
- [Capacity Radar: Priority-based GPU/TPU capacity scanning and deployment tool](https://github.com/MG-Cafe/capacity_radar)
- [Fast-start inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-fast-start-reference-architecture.md)
- [GKE Pod snapshots inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md)
- [Online inference using vLLM with NVIDIA Run:ai Model Streamer and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md)
- [Online inference using vLLM with GKE Pod snapshots and GPUs on GKE](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-podsnapshots.md)
- [Optimizing GKE Workloads with Custom Compute Classes](/docs/guides/optimizing-gke-workloads-with-custom-compute-classes/README.md)
- [Intelligent inference scheduling with llm-d](/docs/platforms/gke/base/use-cases/inference-ref-arch/llmd/llmd-vllm-with-hf-model.md)
