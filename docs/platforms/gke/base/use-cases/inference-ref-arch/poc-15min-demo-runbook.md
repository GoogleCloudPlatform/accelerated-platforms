# 15-minute live demo runbook: Multi-region GPU capacity farming, fast-start model streaming, and sub-minute GKE Pod snapshot restore

> [!IMPORTANT]
>
> 🚀 Dynamic Landscape 🚀: The field of AI inference is experiencing continuous,
> rapid evolution. This document is regularly updated to reflect the latest
> products, features, and architectural patterns, ensuring it remains current
> with the advancements in AI, Google Cloud and Google Kubernetes Engine.
>
> Last Update: 2026-10-26 (YYYY-MM-DD)

This runbook is a companion to the
[AI inference proof-of-concept (PoC) and capacity-finding guide](/docs/platforms/gke/base/use-cases/inference-ref-arch/poc-capacity-and-rapid-deployment-guide.md).
It assumes **zero pre-existing GKE clusters, buckets, or snapshots** and
**nothing pre-installed** on the presenter's machine beyond a standard Linux or
Google Cloud Shell terminal with `gcloud`. Every resource needed for the
15-minute live demo is built from scratch using the scripts, Terraform modules,
and Kustomize overlays in this repository.

Each regional copy of the platform uses the repository's default
`resource_name_prefix = "inf"` and a clean, stage-ready regional `platform_name`
(`1–9` characters per Terraform validation):

| Global Ring Region               | `platform_name` (or Region-Code Alternative) | Provisioned GKE Cluster Name | Online GPU Workload Namespace | Isolated Kubeconfig Path |
| -------------------------------- | -------------------------------------------- | ---------------------------- | ----------------------------- | ------------------------ |
| **Americas (`us-central1`)**     | `americas` _(or `us-cent1`)_                 | **`inf-americas`**           | **`inf-americas-online-gpu`** | `/tmp/kc_inf-americas`   |
| **Europe (`europe-west4`)**      | `europe` _(or `eu-west4`)_                   | **`inf-europe`**             | **`inf-europe-online-gpu`**   | `/tmp/kc_inf-europe`     |
| **Asia-Pacific (`asia-south2`)** | `apac` _(or `ap-south2`)_                    | **`inf-apac`**               | **`inf-apac-online-gpu`**     | `/tmp/kc_inf-apac`       |

---

## Overview of the runbook

- **Part 1 (Automated end-to-end provisioning from scratch — start ~2 hours
  before the demo for all three regions)**:
  - **Prep Step 1 (~2 min)**: Installs required CLI tools (`terraform`,
    `kustomize`, `sponge`, `jq`, `kubectl`, `capacity_radar`) and clones
    `accelerated-platforms`.
  - **Prep Step 2 (~1 min — PoC Guide Stage 2)**: Audits project GPU quotas and
    runs `capacity_radar advise spot` to select high-obtainability regions
    (`us-central1`, `europe-west4`, `asia-south2`).
  - **Prep Step 3 (~20 min — PoC Guide Stage 3)**: Runs the repository's
    `deploy-ap.sh` and `terraform/online_gpu` (with
    `-var="ira_online_gpu_pod_snapshots_enabled=true"`) across each region
    (`americas`, `europe`, `apac`) to stand up the GKE Autopilot clusters
    (`inf-americas`, `inf-europe`, `inf-apac`), Hierarchical Namespace (HNS)
    Cloud Storage model and snapshot buckets, and Custom Compute Classes, and
    stores your Hugging Face token in Secret Manager.
  - **Prep Step 4 (~15–20 min — PoC Guide Stage 4)**: Stages **Gemma 4 31B**
    (`google/gemma-4-31b-it`) and **Gemma 3 27B** (`google/gemma-3-27b-it`)
    model weights into HNS Cloud Storage using `configure_huggingface.sh`
    (staged once in one region and replicated to the other regions with
    `gcloud storage rsync`), and deploys `vllm-runai` +
    `vllm-podsnapshot-fast-restore` across `NVIDIA RTX PRO 6000 96GB` and
    `NVIDIA H100 80GB` / `H100 Mega`.
- **Part 2 (15-minute live presentation — copy-paste & talk track)**: Four timed
  demo beats (`3–4 min` each) with exact copy-paste commands and a verbatim
  **Presenter Talk Track**.
- **Part 3 (Post-demo teardown)**: Cleanly destroys all provisioned clusters and
  buckets using the repository's `teardown-ap.sh`.

---

## Part 1: Automated end-to-end provisioning from scratch (zero existing clusters)

> [!IMPORTANT]
>
> Because GKE Autopilot cluster creation (`~20 min` per region, run
> sequentially), Hugging Face-to-GCS model staging (`~5–7 min` per model),
> cross-region replication (`30+ min` for `Gemma 4 31B` across continents), and
> initial GKE Pod snapshot creation (`~11–13 min` for a 31B model) add up to
> roughly 2 hours for all three regions, run **Prep Steps 1–4** well before your
> live presentation begins so that all pods are `1/1 Running` and your
> `PodSnapshot` is `AllSnapshotsAvailable` when you share your screen.

### Prep Step 1: Bootstrap CLI tools (`terraform`, `kustomize`, `sponge`, `jq`, `capacity_radar`) & clone repositories

Copy and paste this block into your terminal:

```shell
mkdir -p "${HOME}/bin" "${HOME}/.local/bin"
export PATH="${HOME}/bin:${HOME}/.local/bin:${HOME}/google-cloud-sdk/bin:${PATH}"

if ! grep -q '\.local/bin' "${HOME}/.bashrc" 2>/dev/null; then
  echo 'export PATH="${HOME}/bin:${HOME}/.local/bin:${HOME}/google-cloud-sdk/bin:${PATH}"' >> "${HOME}/.bashrc"
fi

# 1. Install system utilities (jq, sponge from moreutils, git, curl, python3, gettext-base for envsubst)
for cmd in jq sponge git curl python3 envsubst; do
  command -v "${cmd}" >/dev/null 2>&1 || (sudo apt-get update -qq && sudo apt-get install -y -qq jq moreutils git curl python3 python3-venv python3-pip gettext-base unzip)
done

# 2. Install kustomize if not present
if ! command -v kustomize >/dev/null 2>&1; then
  curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash -s -- "${HOME}/.local/bin"
fi

# 3. Install terraform if not present
if ! command -v terraform >/dev/null 2>&1; then
  TF_VER="1.9.8"
  curl -fsSL "https://releases.hashicorp.com/terraform/${TF_VER}/terraform_${TF_VER}_linux_amd64.zip" -o /tmp/terraform.zip
  unzip -qo /tmp/terraform.zip -d "${HOME}/.local/bin" && rm -f /tmp/terraform.zip
fi

# 4. Clone Capacity Radar and install the `capacity_radar` CLI into ~/.local/bin
if [ ! -d "${HOME}/capacity_radar" ]; then
  git clone --depth 1 https://github.com/MG-Cafe/capacity_radar.git "${HOME}/capacity_radar"
fi
if command -v uv >/dev/null 2>&1; then
  uv venv "${HOME}/capacity_radar/.venv" --quiet
  uv pip install --python "${HOME}/capacity_radar/.venv/bin/python" --quiet -r "${HOME}/capacity_radar/backend/requirements.txt"
  CR_PYTHON="${HOME}/capacity_radar/.venv/bin/python"
elif python3 -m venv "${HOME}/capacity_radar/.venv" >/dev/null 2>&1; then
  "${HOME}/capacity_radar/.venv/bin/pip" install --quiet -r "${HOME}/capacity_radar/backend/requirements.txt"
  CR_PYTHON="${HOME}/capacity_radar/.venv/bin/python"
else
  pip3 install --user --break-system-packages --quiet -r "${HOME}/capacity_radar/backend/requirements.txt"
  CR_PYTHON="python3"
fi
cat <<EOF > "${HOME}/.local/bin/capacity_radar"
#!/usr/bin/env bash
exec "${CR_PYTHON}" "\${HOME}/capacity_radar/skills/capacity-radar/scripts/capacity_radar.py" "\$@"
EOF
chmod +x "${HOME}/.local/bin/capacity_radar"
ln -sf "${HOME}/.local/bin/capacity_radar" "${HOME}/bin/capacity_radar"

# 5. Clone Accelerated Platforms if not already inside a checkout
if [ -f "platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh" ]; then
  export ACP_REPO_DIR="$(pwd)"
else
  export ACP_REPO_DIR="${HOME}/accelerated-platforms"
  if [ ! -d "${ACP_REPO_DIR}" ]; then
    git clone https://github.com/GoogleCloudPlatform/accelerated-platforms.git "${ACP_REPO_DIR}"
  fi
  cd "${ACP_REPO_DIR}"
fi

# 6. Verify all tools
echo "Tools ready: terraform=$(terraform version -json | jq -r .terraform_version), kustomize=$(kustomize version), capacity_radar_chips=$(capacity_radar catalog chips | jq '(.gpuChips | length) + (.tpuChips | length)')"
```

---

### Prep Step 2: Set your project & Hugging Face token, and run Stage 2 capacity discovery

Set your Google Cloud project ID and Hugging Face token (with access to
`google/gemma-4-31b-it` and `google/gemma-3-27b-it` accepted on Hugging Face),
and run the Stage 2 multi-region capacity sweep:

```shell
export PROJECT_ID="<YOUR_PROJECT_ID>"           # <-- Replace with your Google Cloud Project ID
export HF_TOKEN="<YOUR_HUGGINGFACE_READ_TOKEN>" # <-- Replace with your hf_... token

# Verify Spot obtainability across Americas (us-central1), Europe (europe-west4), and Asia-Pacific (asia-south2)
for MT in g4-standard-48 g4-standard-96 a3-megagpu-8g a3-highgpu-1g; do
  echo "=== Capacity Radar Spot Advisory: ${MT} ==="
  capacity_radar advise spot \
    --project "${PROJECT_ID}" \
    --machine-type "${MT}" \
    --regions us-central1,europe-west4,asia-south2 | \
    jq -r '(["REGION","ZONE","MACHINE_TYPE","OBTAINABILITY","UPTIME_SCORE","AVAILABILITY"] | @tsv), (.recommendations[] | [.region, .zone, .machineType, (.obtainability|tostring), (.uptimeScore|tostring), .spotAvailability] | @tsv)' | column -t
  echo ""
done
```

---

### Prep Step 3: Provision the regional copies of the platform from scratch (PoC Guide Stage 3)

You can spin up copies of the platform across **all 3 regions (`americas` in
`us-central1`, `europe` in `europe-west4`, `apac` in `asia-south2`)** for the
full multi-region "Follow-the-Sun" showcase, or in **a single region
(`americas:us-central1`)** if you only want to demo a single cluster.

The script below uses the repository's
[`deploy-ap.sh`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh)
and
[`terraform/online_gpu`](/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu)
(passing `-var="ira_online_gpu_pod_snapshots_enabled=true"` so Terraform creates
the dedicated `*-pod-snapshots` HNS bucket with soft delete disabled and grants
`roles/storage.objectUser` to the workload KSA and GKE service agent) to
provision each regional copy (`inf-americas`, `inf-europe`, `inf-apac`), adds
your `HF_TOKEN` to Secret Manager, enables GKE Pod snapshots on each cluster,
and saves isolated `--dns-endpoint` kubeconfigs (`/tmp/kc_inf-americas`,
`/tmp/kc_inf-europe`, `/tmp/kc_inf-apac`):

```shell
export TF_VAR_resource_name_prefix="inf"
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
mkdir -p "${TF_PLUGIN_CACHE_DIR}"
export SHARED_CONFIG_DIR="${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
export CORE_INIT_DIR="${ACP_REPO_DIR}/platforms/gke/base/core/initialize"

# Define (PLATFORM_NAME:REGION) pairs for each regional copy of the platform
# Note: platform_name must be 1-9 characters (e.g., americas/europe/apac or us-cent1/eu-west4/ap-south2)
# Tip: For a single-region demo, keep only "americas:us-central1"
export RING_TARGETS=("americas:us-central1" "europe:europe-west4" "apac:asia-south2")

for TARGET in "${RING_TARGETS[@]}"; do
  PLATFORM_NAME="${TARGET%%:*}"
  REGION="${TARGET##*:}"
  CLUSTER_NAME="${TF_VAR_resource_name_prefix}-${PLATFORM_NAME}"
  echo "=================================================================="
  echo "Provisioning Platform Copy '${CLUSTER_NAME}' in ${REGION} (Stage 3)..."
  echo "=================================================================="

  # 1. Point the shared config at this region (PoC Guide Stage 3.2).
  #    cluster.auto.tfvars is generated by core/initialize (and container_cluster_ap
  #    sets cluster_autopilot_enabled = true in it), so only its cluster_region line
  #    is updated in place instead of overwriting the file.
  cat <<EOF > "${SHARED_CONFIG_DIR}/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "${REGION}"
platform_name               = "${PLATFORM_NAME}"
resource_name_prefix        = "${TF_VAR_resource_name_prefix}"
EOF
  sed -i "s/^\(cluster_region[[:blank:]]*=\).*/\1 \"${REGION}\"/" "${SHARED_CONFIG_DIR}/cluster.auto.tfvars"

  # 2. Point core/initialize at THIS region's Terraform state instead of the
  #    previous region's: reuse this region's state bucket if it already holds
  #    core/initialize state (for example, when retrying a region), otherwise
  #    remove backend.tf so core/deploy.sh creates the bucket and migrates state.
  TF_STATE_BUCKET="${PROJECT_ID}-${CLUSTER_NAME}-terraform"
  rm -rf "${CORE_INIT_DIR}/.terraform" "${CORE_INIT_DIR}/terraform.tfstate"*
  if gcloud storage ls "gs://${TF_STATE_BUCKET}/terraform/core/initialize/default.tfstate" >/dev/null 2>&1; then
    sed "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${TF_STATE_BUCKET}\"/" \
      "${CORE_INIT_DIR}/backend.tf.bucket" >"${CORE_INIT_DIR}/backend.tf"
  else
    rm -f "${CORE_INIT_DIR}/backend.tf"
  fi

  # 3. Deploy GKE Autopilot base platform + inference-ref-arch core services (PoC Guide Stage 3.4).
  #    If this fails (for example, a CREATE_CLUSTER stockout), skip the rest of this
  #    region and re-run the loop for it later (see the tip below).
  if ! "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh"; then
    echo "ERROR: deploy-ap.sh failed for ${CLUSTER_NAME}; skipping the rest of ${REGION}."
    continue
  fi

  # 4. Deploy the online_gpu terraservice with Pod snapshot storage enabled
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu"
  rm -rf .terraform/ terraform.tfstate*
  if ! (terraform init &&
    terraform plan -input=false -var="ira_online_gpu_pod_snapshots_enabled=true" -out=tfplan &&
    terraform apply -input=false tfplan); then
    echo "ERROR: online_gpu failed for ${CLUSTER_NAME}; skipping the rest of ${REGION}."
    continue
  fi
  rm -f tfplan

  # 5. Source generated environment variables and add HF_TOKEN to Secret Manager
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  printf '%s' "${HF_TOKEN}" | gcloud secrets versions add "${huggingface_hub_access_token_read_secret_manager_secret_name}" \
    --data-file=- \
    --project="${huggingface_secret_manager_project_id}"

  # 6. Wait for GKE Autopilot to finish post-deploy cluster operations (such as
  #    RESIZE_CLUSTER), otherwise the update fails with CLUSTER_ALREADY_HAS_OPERATION
  #    (stops early if the cluster is in ERROR or does not exist)
  for _ in $(seq 1 90); do
    CLUSTER_STATUS="$(gcloud container clusters describe "${cluster_name}" --location="${cluster_region}" --project="${cluster_project_id}" --format='value(status)' 2>/dev/null)"
    if [ "${CLUSTER_STATUS}" = "RUNNING" ] || [ "${CLUSTER_STATUS}" = "ERROR" ] || [ -z "${CLUSTER_STATUS}" ]; then
      break
    fi
    echo "Waiting for ${cluster_name} to return to RUNNING (currently ${CLUSTER_STATUS})..."
    sleep 10
  done

  # 7. Enable GKE Pod snapshots on the cluster (PoC Guide Stage 4, Trick 2)
  gcloud beta container clusters update "${cluster_name}" \
    --enable-pod-snapshots \
    --location="${cluster_region}" \
    --project="${cluster_project_id}" \
    --quiet

  # 8. Save isolated DNS-endpoint kubeconfig for the live demo
  KUBECONFIG="/tmp/kc_${CLUSTER_NAME}" gcloud container clusters get-credentials "${cluster_name}" \
    --region="${cluster_region}" \
    --project="${cluster_project_id}" \
    --dns-endpoint
done

# Set default kubeconfig to Americas (inf-americas) for measure_restore.sh
cp /tmp/kc_inf-americas "${HOME}/.kube/config"
```

> [!TIP]
>
> Capacity Advisor scores describe accelerator obtainability, not regional
> control-plane or general-purpose CPU capacity. If `CREATE_CLUSTER` fails in a
> region with
> `Google Compute Engine does not have enough resources available to fulfill request`
> (`code: 14`), the loop skips the rest of that region. Wait a few minutes and
> re-run the loop with `RING_TARGETS` set to only that region (Terraform retries
> the cluster creation), or drop the region from the ring. The
> `gcloud beta container clusters update --enable-pod-snapshots` step can fail
> with the same stockout error; re-run that command for the cluster a few
> minutes later and confirm it with
> `gcloud beta container clusters describe <CLUSTER> --location=<REGION> --format='value(addonsConfig.podSnapshotConfig.enabled)'`
> (prints `True`). For example, if `europe-west4` is unavailable, re-run the
> Beat 1 sweep and, if another ring region (such as `us-central1`) currently
> scores `HIGH` for `a3-megagpu-8g` and has Spot `H100 Mega` quota, run Prep
> Step 4B against `inf-americas` instead (`use_region americas us-central1`,
> after applying the `gpu-h100-80gb-mega-x8` `ComputeClass` from Prep Step 4.0
> to `/tmp/kc_inf-americas`).

---

### Prep Step 4: Patch `ComputeClass` priorities, stage Gemma models to HNS Cloud Storage & deploy fast-start workloads (PoC Guide Stage 4)

Now use the repository's `configure_huggingface.sh`, `configure_vllm_runai.sh`,
and `configure_vllm_podsnapshot.sh` scripts to stage **Gemma 4 31B**
(`google/gemma-4-31b-it`) and **Gemma 3 27B** (`google/gemma-3-27b-it`) weights
and deploy the workloads. The weights are downloaded from Hugging Face **once**
into one staging region's Hierarchical Namespace bucket (Step 4.1,
`inf-americas` by default) and then replicated to the other regional buckets
with `gcloud storage rsync`.

> [!NOTE]
>
> - **Spot-first GPU `ComputeClass` priority**: As documented in Stage 7 Finding
>   #4 of the PoC Guide, built-in GPU `ComputeClass` priorities try
>   `[Reservation, On-Demand, Flex-Start, Spot]` in order, which stalls GKE
>   Autopilot when a region has `0` On-Demand GPU quota (`europe-west4`). Step
>   4.0 replaces the regional GPU `ComputeClass` priorities so `spot: true` is
>   Priority 1 with fallback to On-Demand. Every priority keeps its `gpu:` rule
>   (Autopilot rejects GPU Pods whose compute class has no GPU rule), and
>   `g4-standard-48` uses `hyperdisk-balanced` boot disks (`pd-balanced` is not
>   supported on `G4`). Re-applying the `custom_compute_class` Terraform
>   terraservice restores the repository defaults.
> - **Why the weights are staged once and replicated**: The `model-download` >
>   `ComputeClass` provisions `c4-standard-4-lssd` (Priority 1) or
>   `c3-standard-4-lssd` (Priority 2) nodes. `asia-south2` offers no `C3` >
>   `-lssd` machine types, so the downloader Job stays `Pending` there unless
>   the project has `C4_CPUS` quota. In addition,
>   `activeMigration.optimizeRulePriority: true` can scale down a
>   `c3-standard-4-lssd` node mid-download to retry Priority 1, which kills the
>   `backoffLimit: 0` Job. Step 4.0 removes `activeMigration` from
>   `model-download` in the candidate staging clusters, and the
>   `wait_for_hf_job` helper fails fast (with logs and events) instead of
>   waiting 30 minutes on a failed or unschedulable Job.

#### 4.0. Define helper functions and patch `ComputeClass` resources

```shell
# use_region <platform_name> <region>: point the shared Terraform config and
# KUBECONFIG at one regional copy without overwriting the generated
# cluster.auto.tfvars, then load that region's environment variables.
use_region() {
  cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "$2"
platform_name               = "$1"
resource_name_prefix        = "inf"
EOF
  sed -i "s/^\(cluster_region[[:blank:]]*=\).*/\1 \"$2\"/" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
  export KUBECONFIG="/tmp/kc_inf-$1"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
}

# start_replication <model-path> <platform_name>...: start copying a staged model
# from STAGING_BUCKET (set in Step 4.1) to other regional buckets in the
# background (nohup, so they survive a closed terminal). Copies run server-side;
# progress is logged to /tmp/replicate-*.log.
start_replication() {
  local model="$1" platform dest tag
  shift
  for platform in "$@"; do
    dest="${PROJECT_ID}-inf-${platform}-hf-hub-models"
    [ "${dest}" = "${STAGING_BUCKET}" ] && continue
    tag="inf-${platform}-$(basename "${model}")"
    nohup gcloud storage rsync --recursive "gs://${STAGING_BUCKET}/${model}" "gs://${dest}/${model}" \
      >"/tmp/replicate-${tag}.log" 2>&1 </dev/null &
    echo $! >"/tmp/replicate-${tag}.pid"
    echo "Replicating ${model} to gs://${dest} in the background (PID $!)"
  done
}

# replicate_model <model-path>: wait for any background replication of the
# model into the current region's bucket, then run a final (incremental) sync.
replicate_model() {
  local pid_file="/tmp/replicate-${cluster_name}-$(basename "$1").pid"
  [ "${huggingface_hub_models_bucket_name}" = "${STAGING_BUCKET}" ] && return 0
  while [ -f "${pid_file}" ] && kill -0 "$(cat "${pid_file}")" 2>/dev/null; do
    echo "Waiting for $1 to finish replicating to gs://${huggingface_hub_models_bucket_name}..."
    sleep 30
  done
  gcloud storage rsync --recursive \
    "gs://${STAGING_BUCKET}/$1" \
    "gs://${huggingface_hub_models_bucket_name}/$1"
}

# wait_for_hf_job: wait for the hf-model-to-gcs Job, failing fast on Job failure
# and timing out after 30 minutes (for example, if the Pod stays Pending).
wait_for_hf_job() {
  local ns="${huggingface_hub_downloader_kubernetes_namespace_name}"
  local job="job/${HF_MODEL_ID_HASH}-hf-model-to-gcs"
  local deadline=$((SECONDS + 1800))
  until kubectl -n "${ns}" wait --for=condition=complete --timeout=15s "${job}" >/dev/null 2>&1; do
    if kubectl -n "${ns}" wait --for=condition=failed --timeout=1s "${job}" >/dev/null 2>&1; then
      echo "${job} failed:"
      kubectl -n "${ns}" logs "${job}" --tail=30 || true
      return 1
    fi
    if ((SECONDS > deadline)); then
      echo "${job} did not complete within 30 minutes:"
      kubectl -n "${ns}" get pods -l app=hf-model-to-gcs -o wide
      kubectl -n "${ns}" get events --sort-by=.lastTimestamp | tail -n 15
      return 1
    fi
    kubectl -n "${ns}" get pods -l app=hf-model-to-gcs --no-headers
  done
  echo "${job} complete"
}

# 1. Americas (us-central1): Spot-first for 1x RTX PRO 6000
cat <<'EOF' | KUBECONFIG=/tmp/kc_inf-americas kubectl apply -f -
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-rtx-pro-6000-96gb-x1
spec:
  nodePoolConfig:
    imageStreaming:
      enabled: true
  nodePoolAutoCreation:
    enabled: true
  priorities:
    - gpu:
        count: 1
        driverVersion: latest
        type: nvidia-rtx-pro-6000
      machineType: g4-standard-48
      maxPodsPerNode: 32
      spot: true
      storage:
        bootDiskType: hyperdisk-balanced
    - gpu:
        count: 1
        driverVersion: latest
        type: nvidia-rtx-pro-6000
      machineType: g4-standard-48
      maxPodsPerNode: 32
      spot: false
      storage:
        bootDiskType: hyperdisk-balanced
  whenUnsatisfiable: DoNotScaleUp
EOF

# Keep the model-download node until the downloader Job finishes (no active
# migration) in both candidate staging clusters
for KC in /tmp/kc_inf-americas /tmp/kc_inf-europe; do
  KUBECONFIG="${KC}" kubectl patch computeclass model-download \
    --type=merge -p='{"spec":{"activeMigration":null}}'
done

# 2. Europe (europe-west4) & Asia-Pacific (asia-south2): Spot-first for 1x H100
for KC in /tmp/kc_inf-europe /tmp/kc_inf-apac; do
  cat <<'EOF' | KUBECONFIG="${KC}" kubectl apply -f -
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-h100-80gb-high-x1
spec:
  nodePoolConfig:
    imageStreaming:
      enabled: true
  nodePoolAutoCreation:
    enabled: true
  priorities:
    - gpu:
        count: 1
        driverVersion: latest
        type: nvidia-h100-80gb
      machineType: a3-highgpu-1g
      maxPodsPerNode: 32
      spot: true
    - gpu:
        count: 1
        driverVersion: latest
        type: nvidia-h100-80gb
      machineType: a3-highgpu-1g
      maxPodsPerNode: 32
      spot: false
  whenUnsatisfiable: DoNotScaleUp
EOF
done

# 3. Europe (europe-west4) only: Spot-first for 8x H100 Mega (a3-megagpu-8g is
#    not offered in asia-south2, so the class stays unhealthy there by design)
cat <<'EOF' | KUBECONFIG=/tmp/kc_inf-europe kubectl apply -f -
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-h100-80gb-mega-x8
spec:
  nodePoolConfig:
    imageStreaming:
      enabled: true
  nodePoolAutoCreation:
    enabled: true
  priorities:
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h100-mega-80gb
      machineType: a3-megagpu-8g
      maxPodsPerNode: 32
      spot: true
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h100-80gb
      machineType: a3-highgpu-8g
      maxPodsPerNode: 32
      spot: true
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h100-mega-80gb
      machineType: a3-megagpu-8g
      maxPodsPerNode: 32
      spot: false
  whenUnsatisfiable: DoNotScaleUp
EOF

# 4. Verify that every patched ComputeClass reports HEALTH=True (MISCONFIGURED
#    explains any failure, for example an unavailable machine type)
for TARGET in "inf-americas:gpu-rtx-pro-6000-96gb-x1 model-download" \
  "inf-europe:gpu-h100-80gb-high-x1 gpu-h100-80gb-mega-x8 model-download" \
  "inf-apac:gpu-h100-80gb-high-x1"; do
  echo "=== ${TARGET%%:*} ==="
  # shellcheck disable=SC2086 # word splitting of the class list is intended
  KUBECONFIG="/tmp/kc_${TARGET%%:*}" kubectl get computeclass ${TARGET#*:} \
    -o custom-columns='NAME:.metadata.name,HEALTH:.status.conditions[?(@.type=="Health")].status,MISCONFIGURED:.status.conditions[?(@.type=="CrdMisconfigured")].message'
done
```

#### 4.1. Stage `Gemma 4 31B` & `Gemma 3 27B` once in a staging region

The downloader Job needs a `c4-standard-4-lssd` or `c3-standard-4-lssd` node. If
`wait_for_hf_job` keeps printing a `Pending` Pod, check the class with
`kubectl get computeclass model-download -o yaml`: a `CapacityConstrained`
condition means the region is temporarily out of those machines. In that case,
delete the Job and re-run this step with
`STAGING_PLATFORM="europe" STAGING_REGION="europe-west4"`; Steps 4A–4C copy the
weights from whichever bucket you staged into.

```shell
export STAGING_PLATFORM="americas" STAGING_REGION="us-central1"
use_region "${STAGING_PLATFORM}" "${STAGING_REGION}"

for MODEL in "google/gemma-4-31b-it" "google/gemma-3-27b-it"; do
  export HF_MODEL_ID="${MODEL}"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  wait_for_hf_job || break
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
done
export STAGING_BUCKET="${huggingface_hub_models_bucket_name}"
gcloud storage ls "gs://${STAGING_BUCKET}/google/"

# Start replicating to the other regional buckets right away, in the background
start_replication google/gemma-4-31b-it americas europe
start_replication google/gemma-3-27b-it americas
```

> [!NOTE]
>
> Replication runs server-side, but throughput is limited per object. In our
> runs, `Gemma 3 27B` (twelve `~5 GB` shards) copied between US and European
> buckets in about 4 minutes, whereas `Gemma 4 31B`'s `12.7 GB` shard took about
> 8 minutes to `us-central1` and 36 minutes to `asia-south2`, and its `49.9 GB`
> shard takes proportionally longer. Start Step 4.1 early, and if a region has
> `C4_CPUS` or `C3_CPUS` quota and `-lssd` capacity, staging directly in that
> region (re-run Step 4.1 with its `STAGING_PLATFORM`/`STAGING_REGION`) is
> usually faster than replicating across continents. Steps 4A and 4B wait for
> the background copies before deploying. Step 4C doesn't copy the weights to
> `asia-south2` at all (see the note in Step 4C).

#### 4A. Americas (`us-central1` / `inf-americas`): Deploy Pod snapshots + Run:ai Streamer on `NVIDIA RTX PRO 6000 96GB`

```shell
use_region americas us-central1

# 1. Wait for Gemma 4 31B and Gemma 3 27B to replicate into the Americas HNS bucket (no-op if Americas is the staging region)
replicate_model google/gemma-4-31b-it
replicate_model google/gemma-3-27b-it

# 2. Deploy Gemma 4 31B with GKE Pod snapshots + Run:ai Streamer (Kustomize overlay)
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/rtx-pro-6000-gemma-4-31b-it"

# 3. Deploy Gemma 3 27B with Run:ai Streamer + Queue-Depth HPA on 1x RTX PRO 6000 96GB
export HF_MODEL_ID="google/gemma-3-27b-it"
export ACCELERATOR_TYPE="rtx-pro-6000"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/rtx-pro-6000-gemma-3-27b-it"
```

#### 4B. Europe (`europe-west4` / `inf-europe`): Replicate `Gemma 4 31B` and deploy on `a3-megagpu-8g` (`H100 80GB Mega`) with Run:ai Model Streamer

> [!NOTE]
>
> This Deployment passes a `gs://` model URI with
> `--load-format=runai_streamer`, so the Run:ai Model Streamer reads the weights
> directly from Cloud Storage; no Cloud Storage FUSE volume or RAM-backed file
> cache is mounted. It requests `1` of the `8` GPUs on the `a3-megagpu-8g` node.
> To use the remaining GPUs, scale it out
> (`kubectl scale deploy/vllm-h100-mega-gemma4-31b --replicas=8`): eight
> single-GPU replicas request `128` vCPU and `768Gi` of memory in total, which
> fits within the `208` vCPU and `1,872 GB` of an `a3-megagpu-8g`. If
> `a3-highgpu-1g` is obtainable in your region, use the `gpu-h100-80gb-high-x1`
> compute class instead.

```shell
use_region europe europe-west4

# 1. Wait for Gemma 4 31B to replicate into the Europe HNS bucket (no-op if Europe is the staging region)
replicate_model google/gemma-4-31b-it

# 2. Deploy Gemma 4 31B on H100 Mega (a3-megagpu-8g), streaming from gs:// with Run:ai Model Streamer
cat <<EOF | kubectl apply -n "${ira_online_gpu_kubernetes_namespace_name}" -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-h100-mega-gemma4-31b
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-h100-mega-gemma4-31b
  template:
    metadata:
      labels:
        app: vllm-h100-mega-gemma4-31b
    spec:
      serviceAccountName: ${ira_online_gpu_kubernetes_service_account_name}
      nodeSelector:
        cloud.google.com/compute-class: gpu-h100-80gb-mega-x8
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.26.0
          command: ["python3", "-m", "vllm.entrypoints.openai.api_server"]
          args:
            - "--model=gs://${huggingface_hub_models_bucket_name}/google/gemma-4-31b-it"
            - "--served-model-name=google/gemma-4-31b-it"
            - "--load-format=runai_streamer"
            - '--model-loader-extra-config={"distributed":true}'
            - "--tensor-parallel-size=1"
            - "--gpu-memory-utilization=0.90"
            - "--max-model-len=8192"
            - "--trust-remote-code"
            - "--no-enable-log-requests"
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: "16"
              memory: "96Gi"
              nvidia.com/gpu: "1"
            limits:
              cpu: "16"
              memory: "140Gi"
              nvidia.com/gpu: "1"
          volumeMounts:
            - name: dshm
              mountPath: /dev/shm
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: 16Gi
EOF
```

#### 4C. Asia-Pacific (`asia-south2` / `inf-apac`): Deploy `PodSnapshot` + `Run:ai Streamer` on `1× H100 80GB` (`a3-highgpu-1g`), streaming from the staging bucket

> [!NOTE]
>
> - **No local copy needed for a Pod snapshot workload**: The weights are read
>   only once, by the first (cold-start) replica; restored replicas resume from
>   the Pod snapshot and never read the model bucket. Instead of waiting for a
>   slow cross-continent copy, this step grants the `inf-apac` workload identity
>   read access to the staging bucket and points the overlay's
>   `MODEL_BUCKET_NAME` at it, so the first replica streams `Gemma 4 31B` across
>   regions once (cross-region data transfer applies to that one read). The read
>   is latency-bound: with the Run:ai Model Streamer's default concurrency it
>   ran at about `16 MB/s` from `europe-west4` to `asia-south2` (about 65
>   minutes, longer than the overlay's 60-minute startup probe), whereas
>   `RUNAI_STREAMER_CONCURRENCY=64` (step 4 below) loaded the model in about 13
>   minutes. To use a local copy instead, run
>   `start_replication google/gemma-4-31b-it apac && replicate_model google/gemma-4-31b-it`
>   after `use_region apac asia-south2` and skip the two `MODEL_BUCKET_NAME`
>   lines below. Keep the staging bucket until the snapshot is
>   `AllSnapshotsAvailable`; a later cold start (for example, after changing the
>   Pod template) reads it again.
> - As documented in **Stage 5** of the PoC Guide, `google/gemma-4-31b-it`
>   (`58.99 GiB` weights) on `1× H100 80GB` (`79.1 GiB` usable VRAM) leaves
>   `10.61 GiB` (`12,629` tokens) of KV cache at
>   `--gpu-memory-utilization=0.90`, so `--max-model-len` must stay at or below
>   `8192`. The repository's `h100-gemma-4-31b-it` >
>   `vllm-podsnapshot-fast-restore` overlay sets both values in its
>   `runtime.env` (`GPU_MEMORY_UTILIZATION=0.90`, `MAX_MODEL_LEN=8192`).

```shell
use_region apac asia-south2

# 1. Grant the inf-apac workload identity read access to the staging bucket. The
#    Run:ai Model Streamer reads bucket metadata (storage.buckets.get) before it
#    lists and streams objects, so grant both bucket- and object-level read roles.
PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
APAC_WORKLOAD="principal://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${PROJECT_ID}.svc.id.goog/subject/ns/${ira_online_gpu_kubernetes_namespace_name}/sa/${ira_online_gpu_kubernetes_service_account_name}"
for ROLE in roles/storage.legacyBucketReader roles/storage.objectViewer; do
  gcloud storage buckets add-iam-policy-binding "gs://${STAGING_BUCKET}" \
    --member="${APAC_WORKLOAD}" --role="${ROLE}" --format=none
done

# 2. Generate the overlay configuration, then point MODEL_BUCKET_NAME at the staging bucket
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
sed -i "s|^MODEL_BUCKET_NAME=.*|MODEL_BUCKET_NAME=${STAGING_BUCKET}|" \
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/base/deployment.env"

# 3. Deploy Gemma 4 31B on 1x H100 80GB with GKE Pod snapshots + Run:ai Streamer
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/h100-gemma-4-31b-it"

# 4. Immediately (while the first Pod waits for its GPU node, before any Pod
#    snapshot exists) raise Run:ai Model Streamer concurrency for the
#    cross-region read, and replace rather than surge the single GPU replica
kubectl -n "${ira_online_gpu_kubernetes_namespace_name}" patch deployment vllm-fast-restore-h100-gemma-4-31b-it \
  --type=strategic \
  -p '{"spec":{"strategy":{"rollingUpdate":{"maxSurge":0,"maxUnavailable":1}},"template":{"spec":{"containers":[{"name":"inference-server","env":[{"name":"RUNAI_STREAMER_CONCURRENCY","value":"64"}]}]}}}}'
```

#### 4D. Pre-flight readiness, snapshot verification & warm-up gate (run before starting the 15-min call)

Point the active Terraform config back at `us-central1` (`inf-americas`) for
`measure_restore.sh`, verify that all deployments across the 3 regions are
`1/1 Running` and the `PodSnapshot` resources in `inf-americas` and `inf-apac`
are `AllSnapshotsAvailable`, and send one warm-up request to each
`PodSnapshot`-backed deployment.

> [!NOTE]
>
> The workload triggers the Pod snapshot as soon as vLLM's `/health` endpoint
> returns `200 OK`, before the server has handled any inference request. On
> `RTX PRO 6000` (Blackwell), the first `/v1/chat/completions` request after a
> restore can trigger a one-time Triton JIT compilation of
> `kernel_unified_attention` (about 35–65 seconds); later requests return in
> about 2 seconds. Send one warm-up request to every restored replica before you
> show live traffic.

```shell
use_region americas us-central1
cp /tmp/kc_inf-americas "${HOME}/.kube/config"

echo "=== 1. Americas (us-central1 / inf-americas) Pods & PodSnapshots ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl get pods,ps -n inf-americas-online-gpu && \
echo -e "\n=== 2. Europe (europe-west4 / inf-europe) Pods ===" && \
KUBECONFIG=/tmp/kc_inf-europe kubectl get pods -n inf-europe-online-gpu && \
echo -e "\n=== 3. Asia-Pacific (asia-south2 / inf-apac) Pods & PodSnapshots ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl get pods,ps -n inf-apac-online-gpu

# Warm-up: one short request per PodSnapshot-backed deployment
for TARGET in "inf-americas:vllm-fast-restore-rtx-pro-6000-gemma-4-31b-it" "inf-apac:vllm-fast-restore-h100-gemma-4-31b-it"; do
  CLUSTER="${TARGET%%:*}"
  DEPLOY="${TARGET##*:}"
  echo "Warming up ${DEPLOY} in ${CLUSTER}..."
  KUBECONFIG="/tmp/kc_${CLUSTER}" kubectl exec -n "${CLUSTER}-online-gpu" "deploy/${DEPLOY}" -c inference-server -- \
    curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" http://localhost:8000/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"Say hello."}],"max_tokens":8}'
done
```

---

## Part 2: 15-minute live demo & presenter talk track

---

### Beat 1 (Minutes 0:00 – 3:30): Hunting for multi-region GPU capacity before deploying

#### Presenter talk track

> _"When teams try to stand up an AI inference Proof of Concept on
> GKE—especially across multiple accelerator generations like NVIDIA Blackwell
> RTX PRO 6000 and Hopper H100—the #1 blocker isn't Kubernetes configuration,
> it's **regional GPU capacity and quota fragmentation**._
>
> _Normally, a user picks a single default region like `us-east4`, runs
> `deploy-ap.sh`, and waits 20 minutes only to hit
> `ZONE_RESOURCE_POOL_EXHAUSTED` or an On-Demand quota wall._
>
> _Instead of guessing, Stage 2 of our PoC guide combines a multi-region quota
> audit with **Capacity Radar** (`capacity_radar advise spot`), which queries
> the Compute Engine Capacity Advisory API across our candidate 'Ring Around the
> World' regions (`us-central1`, `europe-west4`, and `asia-south2`). Let's run
> that live right now across three GPU machine families: `g4-standard-48` (1×
> Blackwell RTX PRO 6000), `a3-megagpu-8g` (8× Hopper H100 Mega), and
> `a3-highgpu-1g` (1× Hopper H100)."_

#### Copy-paste command (Beat 1)

```shell
for MT in g4-standard-48 a3-megagpu-8g a3-highgpu-1g; do
  echo "=== Capacity Radar Spot Advisory: ${MT} ==="
  capacity_radar advise spot \
    --project "${PROJECT_ID}" \
    --machine-type "${MT}" \
    --regions us-central1,europe-west4,asia-south2 | \
    jq -r '(["REGION","ZONE","MACHINE_TYPE","OBTAINABILITY","UPTIME_SCORE","AVAILABILITY"] | @tsv), (.recommendations[] | [.region, .zone, .machineType, (.obtainability|tostring), (.uptimeScore|tostring), .spotAvailability] | @tsv)' | column -t
  echo ""
done
```

#### What to point out in the output

- **Look at `a3-megagpu-8g` (`8× H100 80GB`)**: `us-central1` has an
  obtainability score of **`0.1` (`VERY_LOW`)**, whereas `europe-west4-b` and
  `europe-west4-c` score **`0.9` (`HIGH`)**. And because `europe-west4` has `0`
  On-Demand `H100` quota (`16` Spot quota), patching our `ComputeClass` to put
  `spot: true` first provisioned our 8-GPU `a3-megagpu-8g` node in **~90
  seconds**.
- **Look at `a3-highgpu-1g` (`1× H100 80GB`)**: `asia-south2-b` and
  `asia-south2-a` score **`0.9` (`HIGH`)**, where our 1-GPU H100 nodes
  provisioned in **78 seconds**.
- **Look at `g4-standard-48` (`RTX PRO 6000 96GB Blackwell`)**: `us-central1`
  has both On-Demand and Spot quota and provisioned `RTX PRO 6000` nodes in
  **52–95 seconds**.

---

### Beat 2 (Minutes 3:30 – 7:00): The live 3-region Gemma ring & NVIDIA Run:ai Model Streamer

#### Presenter talk track

> _"Guided by those capacity signals, we used `deploy-ap.sh` and
> `terraform/online_gpu` from the `accelerated-platforms` repository to stand up
> three regional copies of the platform—**`inf-americas` (`us-central1`)**,
> **`inf-europe` (`europe-west4`)**, and **`inf-apac` (`asia-south2`)**—serving
> **Gemma 4 31B (`google/gemma-4-31b-it`)** and **Gemma 3 27B
> (`google/gemma-3-27b-it`)** across both NVIDIA Blackwell `RTX PRO 6000 96GB`
> and Hopper `H100 80GB` GPUs._
>
> _Let's inspect all three clusters live."_

#### Copy-paste command 2A (show live multi-region pods)

```shell
echo "=== AMERICAS: us-central1 (inf-americas — NVIDIA RTX PRO 6000 96GB Blackwell) ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl get pods -n inf-americas-online-gpu -o wide && \
echo -e "\n=== EUROPE: europe-west4 (inf-europe — NVIDIA H100 80GB Mega Hopper) ===" && \
KUBECONFIG=/tmp/kc_inf-europe kubectl get pods -n inf-europe-online-gpu -o wide && \
echo -e "\n=== ASIA-PACIFIC: asia-south2 (inf-apac — NVIDIA H100 80GB Hopper) ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl get pods -n inf-apac-online-gpu -o wide
```

#### Presenter talk track (Run:ai Model Streamer)

> _"Notice how fast these Gemma models loaded from our regional Hierarchical
> Namespace Cloud Storage buckets:_
>
> - _With **NVIDIA Run:ai Model Streamer** (`--load-format=runai_streamer`),
>   `Gemma 3 27B` (`51.19 GiB`) streamed directly from `gs://` into GPU VRAM in
>   **9.1–16.5 seconds** on `RTX PRO 6000` (`19.2s` on `H100`), and
>   `Gemma 4 31B` (`58.99 GiB`) streamed in **11.1–25.7 seconds** on
>   `RTX PRO 6000` and **20.1–25.0 seconds** on `H100` with zero local disk
>   staging."_

> [!NOTE]
>
> All three regions stream weights from a `gs://` URI, so no Cloud Storage FUSE
> volume is involved. If you mount checkpoints through Cloud Storage FUSE
> instead (and point vLLM at the mount path), see Stage 7 Finding #5 of the PoC
> Guide for the RAM-backed `gke-gcsfuse-cache` override; that cache is bypassed
> whenever vLLM is given a `gs://` model URI.

#### Copy-paste command 2B (inspect live startup & KV cache logs)

```shell
echo "=== [Europe: inf-europe] Gemma 4 31B (58.99 GiB) Run:ai Streamer Load & Hopper FA4 KV Cache ===" && \
KUBECONFIG=/tmp/kc_inf-europe kubectl logs -n inf-europe-online-gpu deploy/vllm-h100-mega-gemma4-31b -c vllm | \
  python3 -c "import sys; print(''.join([l for l in sys.stdin if any(k in l for k in ['RunAI Model Streamer', 'Loading weights took', 'Model loading took', 'KV cache size', 'max_seq_len', 'FLASH_ATTN'])]))" && \
echo "=== [Asia-Pacific: inf-apac] Gemma 4 31B on 1x H100 80GB (PodSnapshot + Run:ai Streamer) ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl logs -n inf-apac-online-gpu deploy/vllm-fast-restore-h100-gemma-4-31b-it -c inference-server | \
  python3 -c "import sys; print(''.join([l for l in sys.stdin if any(k in l for k in ['RunAI Model Streamer', 'Loading weights took', 'Model loading took', 'KV cache size', 'max_seq_len'])]))"
```

---

### Beat 3 (Minutes 7:00 – 11:00): Live multi-region Gemma verification, KV cache sizing for single-GPU (`TP=1`) scale-out & Queue-Depth HPA

#### Presenter talk track

> _"Now let's send live `/v1/chat/completions` requests to **Gemma 4 31B** and
> **Gemma 3 27B** across all three continents and highlight how we size
> single-GPU (`TP=1`) replicas for elastic scale-out:_
>
> 1. _**Why single-GPU (`TP=1`) sizing accelerates scale-out**: Keeping 27B–31B
>    Gemma models on a single GPU (`g4-standard-48` or `a3-highgpu-1g`) gives us
>    the highest multi-region Spot obtainability and unlocks GKE `PodSnapshot`
>    fast restore (which requires `--tensor-parallel-size=1`)._
> 2. _**Why the `80 GB H100` overlay caps `Gemma 4 31B` at
>    `--max-model-len=8192`**: Because `Gemma 4 31B`'s BF16 weights occupy
>    `58.99 GiB`, an `80 GB H100` (`79.1 GiB` usable VRAM) at
>    `--gpu-memory-utilization=0.90` leaves `10.61 GiB` (`12,629` tokens) for KV
>    cache, which is less than the `13.76 GiB` a single `16K` request needs, so
>    the `h100-gemma-4-31b-it` overlay sets `MAX_MODEL_LEN=8192` in
>    `runtime.env`. On `Gemma 3 27B` (`51.19 GiB` weights), `1× H100` allocates
>    `18.12 GiB` (`34,147` KV tokens)._
> 3. _**How `96 GB RTX PRO 6000` expands KV cache capacity per scale-out unit**:
>    The extra 16 GB of GDDR7 VRAM more than doubles `Gemma 4 31B`'s KV cache to
>    **`24.89 GiB` (`29,628` tokens per GPU — `2.35×` larger)**, scales linearly
>    to **`59,256` KV tokens across 2 horizontally scaled replicas**, and gives
>    `Gemma 3 27B` (`vllm-runai` overlay at `GPU_MEMORY_UTILIZATION=0.80` and
>    `MAX_MODEL_LEN=51200`) **`22.99 GiB` (`99,070` KV tokens per
>    GPU)**—allowing each replica to hold substantially more concurrent
>    sequences (or a longer `MAX_MODEL_LEN`, such as `16384`) before queuing in
>    `vllm:num_requests_waiting` and triggering HPA scale-out."_

#### Copy-paste command 3A (verify `Gemma 4 31B` on `H100 80GB Mega` in `inf-europe`)

```shell
echo "=== [EUROPE: europe-west4 / inf-europe] Gemma 4 31B on H100 80GB Mega (Hopper FA4) ===" && \
KUBECONFIG=/tmp/kc_inf-europe kubectl exec -n inf-europe-online-gpu deploy/vllm-h100-mega-gemma4-31b -c vllm -- \
  curl -s -w "\n\n[HTTP %{http_code}]\n" \
  http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"In 3 concise bullet points, explain why multi-region GPU capacity farming on GKE accelerates AI inference PoCs."}],"max_tokens":120,"temperature":0}'
```

#### Copy-paste command 3B (verify `Gemma 4 31B` on `1× H100 80GB` in `inf-apac` vs. `1× RTX PRO 6000 96GB` in `inf-americas`)

```shell
echo "=== [ASIA-PACIFIC: asia-south2 / inf-apac] Gemma 4 31B on 1x H100 80GB (PodSnapshot-enabled, 10.61 GiB / 12,629 KV tokens) ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl exec -n inf-apac-online-gpu deploy/vllm-fast-restore-h100-gemma-4-31b-it -c inference-server -- \
  curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"Compare 80GB HBM3 vs 96GB GDDR7 for KV cache sizing on 30B LLMs in 2 sentences."}],"max_tokens":96,"temperature":0}' | jq -r '.choices[0].message.content' && \
echo -e "\n=== [AMERICAS: us-central1 / inf-americas] Gemma 4 31B on 1x RTX PRO 6000 96GB (PodSnapshot-enabled, 24.89 GiB / 29,628 KV tokens) ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl exec -n inf-americas-online-gpu deploy/vllm-fast-restore-rtx-pro-6000-gemma-4-31b-it -c inference-server -- \
  curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"Explain why 96GB of GPU VRAM prevents KV cache bottlenecks at 16K context in 2 sentences."}],"max_tokens":96,"temperature":0}' | jq -r '.choices[0].message.content'
```

#### Copy-paste command 3C (verify `Gemma 3 27B` with Run:ai Streamer + Queue-Depth HPA in `inf-americas`)

```shell
echo "=== [AMERICAS: us-central1 / inf-americas] Gemma 3 27B on 1x RTX PRO 6000 96GB (Run:ai Streamer + Queue-Depth HPA, 22.99 GiB / 99,070 KV tokens) ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl exec -n inf-americas-online-gpu deploy/vllm-rtx-pro-6000-gemma-3-27b-it -c inference-server -- \
  curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-3-27b-it","messages":[{"role":"user","content":"Why is vllm:num_requests_waiting a better HPA autoscaling metric than GPU utilization in 2 sentences?"}],"max_tokens":96,"temperature":0}' | jq -r '.choices[0].message.content'
```

---

### Beat 4 (Minutes 11:00 – 15:00): Finale — Sub-minute `H100` (`54.8s`, `4.78×`) & `RTX PRO 6000` (`80.4s–84.0s`, `3.21×`) scale-out with GKE Pod snapshots (`LOADING=0`)

#### Presenter talk track

> _"Finally, let's show how we survive Spot preemptions and scale out in under a
> minute when serving on fluid multi-region capacity._
>
> _Even when we stream `Gemma 4 31B` (`58.99 GiB`) directly from Cloud Storage
> into GPU memory in ~21–25 seconds using the **NVIDIA Run:ai Model Streamer**,
> vLLM still spends ~2.5 to 3.5 minutes compiling Torch Inductor graphs and
> capturing 51 CUDA graphs on every cold start (`262.0s` on `H100`, `267.7s` on
> `RTX PRO 6000`)._
>
> _With **GKE Pod snapshots**, restoring `Gemma 4 31B` from Cloud Storage takes
> **54.77 seconds on `H100 80GB` (`4.78×` faster, saving `3.5 minutes` per
> pod)** and **83.27–84.03 seconds on `RTX PRO 6000 96GB` (`3.19×–3.21×` faster,
> saving `3.1 minutes` per pod)** with **`LOADING=0`**. Because the engine state
> and all 51 captured CUDA graphs are preserved inside the restored GPU memory
> image, restored replicas skip weight loading, `torch.compile`, and CUDA graph
> capture entirely._
>
> _Let's verify that our `PodSnapshot` resources in `inf-apac` (`H100`) and
> `inf-americas` (`RTX PRO 6000`) are `AllSnapshotsAvailable`, and trigger a
> live scale-out restore!"_

#### Copy-paste command 4A (show the `AllSnapshotsAvailable` PodSnapshots in `inf-apac` and `inf-americas`)

```shell
echo "=== [Asia-Pacific: inf-apac] H100 80GB PodSnapshots (54.8s restore) ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl --namespace=inf-apac-online-gpu get podsnapshots \
  --output=custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].reason,CHECKPOINT:.status.conditions[?(@.type=="Checkpoint")].reason,AGE:.metadata.creationTimestamp' && \
echo -e "\n=== [Americas: inf-americas] RTX PRO 6000 96GB PodSnapshots (80.4s-84.0s restore) ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl --namespace=inf-americas-online-gpu get podsnapshots \
  --output=custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].reason,CHECKPOINT:.status.conditions[?(@.type=="Checkpoint")].reason,AGE:.metadata.creationTimestamp'
```

#### Copy-paste command 4B (Option 1 — Scale to 2 replicas & run `measure_restore.sh 2` in `inf-americas`)

> [!TIP]
>
> Avoid using `kubectl delete pod --wait=false` on a 1-GPU node
> (`g4-standard-48` or `a3-highgpu-1g`): the replacement pod can bind to the
> node while the terminating pod is still releasing `/dev/nvidia0`
> (`SandboxChanged` race). Scaling out (`measure_restore.sh 2`) or cycling
> `--replicas=0` $\rightarrow$ wait 6s $\rightarrow$ `--replicas=1` (Option 2
> below) cleanly restores from the `PodSnapshot` every time
> (`PodRestored: True`, `LOADING=0`).

```shell
use_region americas us-central1 # defined in Prep Step 4.0
export VLLM_VARIANT="rtx-pro-6000-gemma-4-31b-it"
export SERVED_MODEL_NAME="google/gemma-4-31b-it"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/measure_restore.sh" 2
```

#### Copy-paste command 4B (Option 2 — Sub-minute `54.8s` warm-node `H100` restore in `inf-apac`)

```shell
export KUBECONFIG=/tmp/kc_inf-apac
kubectl scale deploy/vllm-fast-restore-h100-gemma-4-31b-it -n inf-apac-online-gpu --replicas=0 &&
  kubectl wait --for=delete pod -n inf-apac-online-gpu -l app=vllm-fast-restore-h100-gemma-4-31b-it --timeout=120s &&
  sleep 6 &&
  time (
    kubectl scale deploy/vllm-fast-restore-h100-gemma-4-31b-it -n inf-apac-online-gpu --replicas=1 &&
      kubectl rollout status deploy/vllm-fast-restore-h100-gemma-4-31b-it -n inf-apac-online-gpu --timeout=600s &&
      kubectl wait --for=condition=PodRestored pod -n inf-apac-online-gpu \
        -l app=vllm-fast-restore-h100-gemma-4-31b-it --timeout=600s
  )
kubectl get pods -n inf-apac-online-gpu -l app=vllm-fast-restore-h100-gemma-4-31b-it \
  -o custom-columns='NAME:.metadata.name,READY:.status.containerStatuses[0].ready,RESTORED:.status.conditions[?(@.type=="PodRestored")].status'
```

Once a restored replica is `1/1 Ready`, send it one warm-up request (see Prep
Step 4D) before you show live traffic.

---

## Part 3: Post-demo teardown (destroy all provisioned clusters & buckets)

When your demo is finished, run this block for each regional platform copy
(`inf-americas`, `inf-europe`, `inf-apac`) created in Part 1. For each region
it:

1. Points the shared config at the region (rewriting `platform.auto.tfvars` and
   updating only the `cluster_region` line of the generated
   `cluster.auto.tfvars`).
2. Re-points `core/initialize/backend.tf` at that region's Terraform state
   bucket, re-applies `core/initialize` (regenerating the core terraservices'
   `backend.tf` files), and regenerates the cluster's kubeconfig. Each region's
   `teardown-ap.sh` run deletes all generated kubeconfigs and `backend.tf` files
   and restores the shared `*.auto.tfvars` in the checkout (including
   `initialize_backend_use_case_name = null`), so the next region needs them
   regenerated, and `online_gpu/backend.tf` is written explicitly in step 4.
3. Deletes `PodSnapshot` CRs and empties the regional `*-pod-snapshots` and
   `*-hf-hub-models` HNS buckets, so `terraform destroy` does not fail with
   `BucketNotEmpty`.
4. Destroys `online_gpu` and runs `teardown-ap.sh`.

```shell
export TF_VAR_resource_name_prefix="inf"
# Keep cluster_autopilot_enabled = true in the regenerated cluster.auto.tfvars
# after a previous region's teardown has restored the shared *.auto.tfvars
export TF_VAR_cluster_autopilot_enabled="true"
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
export SHARED_CONFIG_DIR="${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
export CORE_INIT_DIR="${ACP_REPO_DIR}/platforms/gke/base/core/initialize"
export RING_TARGETS=("americas:us-central1" "europe:europe-west4" "apac:asia-south2")

for TARGET in "${RING_TARGETS[@]}"; do
  PLATFORM_NAME="${TARGET%%:*}"
  REGION="${TARGET##*:}"
  CLUSTER_NAME="${TF_VAR_resource_name_prefix}-${PLATFORM_NAME}"
  echo "=== Tearing down ${CLUSTER_NAME} in ${REGION} ==="

  # 1. Point the shared config at this region (do not overwrite cluster.auto.tfvars)
  cat <<EOF > "${SHARED_CONFIG_DIR}/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "${REGION}"
platform_name               = "${PLATFORM_NAME}"
resource_name_prefix        = "${TF_VAR_resource_name_prefix}"
EOF
  sed -i "s/^\(cluster_region[[:blank:]]*=\).*/\1 \"${REGION}\"/" "${SHARED_CONFIG_DIR}/cluster.auto.tfvars"

  # 2. Re-point core/initialize at this region's Terraform state bucket and
  #    regenerate the backend.tf files for every terraservice
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  cd "${CORE_INIT_DIR}"
  rm -rf backend.tf .terraform/ terraform.tfstate*
  sed -i "s/^\([[:blank:]]*bucket[[:blank:]]*=\).*$/\1 \"${terraform_bucket_name}\"/" backend.tf.bucket
  cp backend.tf.bucket backend.tf
  terraform init && terraform apply -auto-approve

  #    Regenerate this cluster's kubeconfig (used by the workload terraservices)
  cd "${ACP_REPO_DIR}/platforms/gke/base/core/workloads/cluster_credentials"
  rm -rf .terraform/
  terraform init && terraform apply -auto-approve

  # 3. Delete PodSnapshot CRs and empty the regional HNS buckets
  if [ -f "/tmp/kc_${CLUSTER_NAME}" ]; then
    KUBECONFIG="/tmp/kc_${CLUSTER_NAME}" kubectl delete podsnapshot --all -n "${CLUSTER_NAME}-online-gpu" --ignore-not-found || true
  fi
  for BUCKET in "${PROJECT_ID}-${CLUSTER_NAME}-pod-snapshots" "${PROJECT_ID}-${CLUSTER_NAME}-hf-hub-models"; do
    gcloud storage rm --recursive "gs://${BUCKET}/**" || echo "gs://${BUCKET} is already empty or does not exist"
  done

  # 4. Destroy online_gpu (passing ira_online_gpu_pod_snapshots_enabled=true) and run teardown-ap.sh
  #    online_gpu/backend.tf is written explicitly because it is deleted when a
  #    previous region's core/initialize is destroyed
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu"
  rm -rf .terraform/ terraform.tfstate*
  cat <<EOF >backend.tf
terraform {
  backend "gcs" {
    bucket = "${terraform_bucket_name}"
    prefix = "terraform/inference-ref-arch/terraform/online_gpu"
  }
}
EOF
  terraform init && terraform destroy -auto-approve -var="ira_online_gpu_pod_snapshots_enabled=true"

  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-ap.sh"
done
```
