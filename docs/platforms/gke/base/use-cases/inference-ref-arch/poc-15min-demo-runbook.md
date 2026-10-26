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

- **Part 1 (Automated end-to-end provisioning from scratch — run ~40 minutes
  before the demo)**:
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
    model weights into HNS Cloud Storage using `configure_huggingface.sh`,
    enables GKE Pod snapshots, and deploys `vllm-runai` +
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
> Because GKE Autopilot cluster creation (`~15–18 min`), Hugging Face-to-GCS
> model staging (`~3–8 min`), and initial GKE Pod snapshot creation
> (`~11–13 min` for a 31B model) take ~35–45 minutes end-to-end, run **Prep
> Steps 1–4** before your live presentation begins so that all pods are
> `1/1 Running` and your `PodSnapshot` is `AllSnapshotsAvailable` when you share
> your screen.

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
echo "Tools ready: terraform=$(terraform version -json | jq -r .terraform_version), kustomize=$(kustomize version), capacity_radar_chips=$(capacity_radar catalog chips | jq .count)"
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

  # 1. Write platform.auto.tfvars and cluster.auto.tfvars (PoC Guide Stage 3.2)
  cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "${REGION}"
platform_name               = "${PLATFORM_NAME}"
resource_name_prefix        = "${TF_VAR_resource_name_prefix}"
EOF

  cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
cluster_region = "${REGION}"
EOF

  # 2. Deploy GKE Autopilot base platform + inference-ref-arch core services (PoC Guide Stage 3.4)
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/deploy-ap.sh"

  # 3. Deploy the online_gpu terraservice with Pod snapshot storage enabled
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu"
  rm -rf .terraform/ terraform.tfstate*
  terraform init
  terraform plan -input=false -var="ira_online_gpu_pod_snapshots_enabled=true" -out=tfplan
  terraform apply -input=false tfplan
  rm -f tfplan

  # 4. Source generated environment variables and add HF_TOKEN to Secret Manager
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  printf '%s' "${HF_TOKEN}" | gcloud secrets versions add "${huggingface_hub_access_token_read_secret_manager_secret_name}" \
    --data-file=- \
    --project="${huggingface_secret_manager_project_id}"

  # 5. Enable GKE Pod snapshots on the cluster (PoC Guide Stage 4, Trick 2)
  gcloud beta container clusters update "${cluster_name}" \
    --enable-pod-snapshots \
    --location="${cluster_region}" \
    --project="${cluster_project_id}" \
    --quiet

  # 6. Save isolated DNS-endpoint kubeconfig for the live demo
  KUBECONFIG="/tmp/kc_${CLUSTER_NAME}" gcloud container clusters get-credentials "${cluster_name}" \
    --region="${cluster_region}" \
    --project="${cluster_project_id}" \
    --dns-endpoint
done

# Set default kubeconfig to Americas (inf-americas) for measure_restore.sh
cp /tmp/kc_inf-americas "${HOME}/.kube/config"
```

---

### Prep Step 4: Patch Spot-first `ComputeClass` priorities, stage Gemma models to HNS Cloud Storage & deploy fast-start workloads (PoC Guide Stage 4)

Now use the repository's `configure_huggingface.sh`, `configure_vllm_runai.sh`,
and `configure_vllm_podsnapshot.sh` scripts to stage **Gemma 4 31B**
(`google/gemma-4-31b-it`) and **Gemma 3 27B** (`google/gemma-3-27b-it`) weights
into each region's Hierarchical Namespace Cloud Storage bucket and deploy the
workloads.

> [!NOTE]
>
> **Spot-first `ComputeClass` priority**: As documented in Stage 7 Finding #4 of
> the PoC Guide, built-in `ComputeClass` priorities try
> `[On-Demand, Flex-Start, Spot]` in order, which stalls GKE Autopilot when a
> region has `0` On-Demand GPU quota (`europe-west4`). Step 4.0 below patches
> the regional `ComputeClass` CRDs so `spot: true` is Priority 1 with automatic
> fallback to On-Demand.

#### 4.0. Patch `ComputeClass` CRDs to Spot-first across all 3 clusters

```shell
# 1. Americas (us-central1): Spot-first for 1x RTX PRO 6000
cat <<'EOF' | KUBECONFIG=/tmp/kc_inf-americas kubectl apply -f -
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-rtx-pro-6000-96gb-x1
spec:
  nodePoolAutoCreation:
    enabled: true
  priorities:
    - machineType: g4-standard-48
      spot: true
      storage:
        bootDiskType: pd-balanced
    - machineType: g4-standard-48
      storage:
        bootDiskType: pd-balanced
  whenUnsatisfiable: DoNotScaleUp
EOF

# 2. Europe (europe-west4) & Asia-Pacific (asia-south2): Spot-first for 1x H100 and 8x H100 Mega
for KC in /tmp/kc_inf-europe /tmp/kc_inf-apac; do
  cat <<'EOF' | KUBECONFIG="${KC}" kubectl apply -f -
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-h100-80gb-high-x1
spec:
  nodePoolAutoCreation:
    enabled: true
  priorities:
    - machineType: a3-highgpu-1g
      spot: true
      storage:
        bootDiskType: pd-balanced
    - machineType: a3-highgpu-1g
      storage:
        bootDiskType: pd-balanced
  whenUnsatisfiable: DoNotScaleUp
---
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-h100-80gb-mega-x8
spec:
  nodePoolAutoCreation:
    enabled: true
  priorities:
    - machineType: a3-megagpu-8g
      spot: true
      storage:
        bootDiskType: pd-balanced
    - machineType: a3-highgpu-8g
      spot: true
      storage:
        bootDiskType: pd-balanced
    - machineType: a3-megagpu-8g
      storage:
        bootDiskType: pd-balanced
  whenUnsatisfiable: DoNotScaleUp
EOF
done
```

#### 4A. Americas (`us-central1` / `inf-americas`): Stage `Gemma 4 31B` & `Gemma 3 27B` and deploy Pod snapshots + Run:ai Streamer on `NVIDIA RTX PRO 6000 96GB`

```shell
export KUBECONFIG="/tmp/kc_inf-americas"

cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "us-central1"
platform_name               = "americas"
resource_name_prefix        = "inf"
EOF
cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
cluster_region = "us-central1"
EOF
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

# 1. Stage Gemma 4 31B and Gemma 3 27B to the Americas HNS GCS bucket
for MODEL in "google/gemma-4-31b-it" "google/gemma-3-27b-it"; do
  export HF_MODEL_ID="${MODEL}"
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  kubectl --namespace="${huggingface_hub_downloader_kubernetes_namespace_name}" \
    wait --for=condition=complete --timeout=1800s "job/${HF_MODEL_ID_HASH}-hf-model-to-gcs"
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
done

# 2. Deploy Gemma 4 31B with GKE Pod snapshots + Run:ai Streamer (Kustomize overlay)
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/rtx-pro-6000-gemma-4-31b-it"

# 3. Deploy Gemma 3 27B with Run:ai Streamer + Queue-Depth HPA on 1x RTX PRO 6000 96GB
export HF_MODEL_ID="google/gemma-3-27b-it"
export ACCELERATOR_TYPE="rtx-pro-6000"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/configure_vllm_runai.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-runai/rtx-pro-6000-gemma-3-27b-it"
```

#### 4B. Europe (`europe-west4` / `inf-europe`): Stage `Gemma 4 31B` and deploy on `a3-megagpu-8g` (`H100 80GB Mega`) with RAM-backed Cloud Storage FUSE prefetch

```shell
export KUBECONFIG="/tmp/kc_inf-europe"

cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "europe-west4"
platform_name               = "europe"
resource_name_prefix        = "inf"
EOF
cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
cluster_region = "europe-west4"
EOF
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

# 1. Stage Gemma 4 31B to the Europe HNS GCS bucket
export HF_MODEL_ID="google/gemma-4-31b-it"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
kubectl --namespace="${huggingface_hub_downloader_kubernetes_namespace_name}" \
  wait --for=condition=complete --timeout=1800s "job/${HF_MODEL_ID_HASH}-hf-model-to-gcs"
kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"

# 2. Deploy Gemma 4 31B on H100 Mega (a3-megagpu-8g) with RAM-backed gke-gcsfuse-cache + Run:ai Streamer
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
      annotations:
        gke-gcsfuse/volumes: "true"
        gke-gcsfuse/cpu-limit: "16"
        gke-gcsfuse/memory-limit: "24Gi"
        gke-gcsfuse/ephemeral-storage-limit: "1Gi"
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
            - "--max-num-seqs=128"
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
            - name: gcs-fuse-csi-ephemeral
              mountPath: /model-data
              readOnly: true
            - name: dshm
              mountPath: /dev/shm
      volumes:
        - name: dshm
          emptyDir:
            medium: Memory
            sizeLimit: 16Gi
        - name: gke-gcsfuse-cache
          emptyDir:
            medium: Memory
            sizeLimit: 80Gi
        - name: gcs-fuse-csi-ephemeral
          csi:
            driver: gcsfuse.csi.storage.gke.io
            readOnly: true
            volumeAttributes:
              bucketName: ${huggingface_hub_models_bucket_name}
              mountOptions: "implicit-dirs,only-dir=,file-cache:max-size-mb:-1,file-cache:cache-file-for-range-read:true,file-cache:enable-parallel-downloads:true,metadata-cache:ttl-secs:-1"
EOF
```

#### 4C. Asia-Pacific (`asia-south2` / `inf-apac`): Stage `Gemma 4 31B` and deploy `PodSnapshot` + `Run:ai Streamer` on `1× H100 80GB` (`a3-highgpu-1g`)

> [!NOTE]
>
> As documented in **Stage 5** of the PoC Guide, `google/gemma-4-31b-it`
> (`58.99 GiB` weights) on `1× H100 80GB` (`79.1 GiB` usable VRAM) must use
> **`--gpu-memory-utilization=0.90`**, **`--max-model-len=8192`**, and
> **`--max-num-seqs=128`** so that KV cache fits within `10.61 GiB` (`12,629`
> tokens) while leaving `7.9 GiB` of unallocated VRAM headroom for FlashInfer's
> `top_k_mask_logits` sampler (`248 MiB` scratch). Applying the repository's
> `h100-gemma-4-31b-it` `vllm-podsnapshot-fast-restore` overlay configures these
> flags automatically and enables **sub-minute (`54.8s`, `4.78×` faster)
> `PodSnapshot` restore on `H100`** in `inf-apac`.

```shell
export KUBECONFIG="/tmp/kc_inf-apac"
cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "asia-south2"
platform_name               = "apac"
resource_name_prefix        = "inf"
EOF
cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
cluster_region = "asia-south2"
EOF
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"

# 1. Stage Gemma 4 31B to the Asia-Pacific HNS GCS bucket
export HF_MODEL_ID="google/gemma-4-31b-it"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
kubectl --namespace="${huggingface_hub_downloader_kubernetes_namespace_name}" \
  wait --for=condition=complete --timeout=1800s "job/${HF_MODEL_ID_HASH}-hf-model-to-gcs"
kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"

# 2. Deploy Gemma 4 31B on 1x H100 80GB with GKE Pod snapshots + Run:ai Streamer (54.8s restore)
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/h100-gemma-4-31b-it"
```

#### 4D. Pre-flight readiness & snapshot verification gate (run before starting the 15-min call)

Reset the active Terraform config back to `us-central1` (`inf-americas`) for
`measure_restore.sh` and verify that all deployments across the 3 regions are
`1/1 Running` and the `PodSnapshot` resources in `inf-americas` and `inf-apac`
are `AllSnapshotsAvailable`:

```shell
export KUBECONFIG="/tmp/kc_inf-americas"
cp /tmp/kc_inf-americas "${HOME}/.kube/config"
export TF_VAR_platform_default_project_id="${PROJECT_ID}"
export TF_VAR_resource_name_prefix="inf"
export TF_VAR_platform_name="americas"
export TF_VAR_platform_default_region="us-central1"

echo "=== 1. Americas (us-central1 / inf-americas) Pods & PodSnapshots ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl get pods,ps -n inf-americas-online-gpu && \
echo -e "\n=== 2. Europe (europe-west4 / inf-europe) Pods ===" && \
KUBECONFIG=/tmp/kc_inf-europe kubectl get pods -n inf-europe-online-gpu && \
echo -e "\n=== 3. Asia-Pacific (asia-south2 / inf-apac) Pods & PodSnapshots ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl get pods,ps -n inf-apac-online-gpu
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

### Beat 2 (Minutes 3:30 – 7:00): The live 3-region Gemma ring, Run:ai Streamer & RAM-backed GCS FUSE prefetch

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

#### Presenter talk track (Run:ai Model Streamer + RAM-FUSE prefetch)

> _"Notice how fast these Gemma models loaded from our regional Hierarchical
> Namespace Cloud Storage buckets:_
>
> - _With **NVIDIA Run:ai Model Streamer** (`--load-format=runai_streamer`),
>   `Gemma 3 27B` (`51.19 GiB`) streamed directly from `gs://` into GPU VRAM in
>   **9.1–16.5 seconds** on `RTX PRO 6000` (`19.2s` on `H100`), and
>   `Gemma 4 31B` (`58.99 GiB`) streamed in **11.1–25.7 seconds** on
>   `RTX PRO 6000` and **20.1–25.0 seconds** on `H100` with zero local disk
>   staging._
> - _And when mounting multi-shard checkpoints via Cloud Storage FUSE,
>   overriding `gke-gcsfuse-cache` with a **RAM-backed `emptyDir`
>   (`medium: Memory, sizeLimit: 80Gi`)** and
>   `--safetensors-load-strategy=prefetch` prefetches all shards into host RAM
>   at ~10 GiB/s without touching the node's boot disk!"_

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
> 2. _**Why `80 GB H100` requires `--max-model-len=8192 --max-num-seqs=128` for
>    `Gemma 4 31B`**: Because `Gemma 4 31B`'s BF16 weights occupy `58.99 GiB`,
>    an `80 GB H100` (`79.1 GiB` usable VRAM) at `--gpu-memory-utilization=0.90`
>    leaves `10.61 GiB` (`12,629` tokens) for KV cache, while `7.9 GiB` remains
>    unallocated for FlashInfer's `top_k_mask_logits` sampler (`248 MiB` scratch
>    at `--max-num-seqs=128`). On `Gemma 3 27B` (`51.19 GiB` weights), `1× H100`
>    allocates `18.12 GiB` (`34,147` KV tokens)._
> 3. _**How `96 GB RTX PRO 6000` expands KV cache capacity per scale-out unit**:
>    The extra 16 GB of GDDR7 VRAM more than doubles `Gemma 4 31B`'s KV cache to
>    **`24.89 GiB` (`29,628` tokens per GPU — `2.35×` larger)**, scales linearly
>    to **`59,256` KV tokens across 2 horizontally scaled replicas**, and gives
>    `Gemma 3 27B` **`32.26 GiB` (`60,783` KV tokens per GPU)**—allowing each
>    replica to hold substantially more concurrent `16K–32K` sequences before
>    queuing in `vllm:num_requests_waiting` and triggering HPA scale-out."_

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
echo "=== [ASIA-PACIFIC: asia-south2 / inf-apac] Gemma 4 31B on 1x H100 80GB (PodSnapshot Restored, 10.61 GiB / 12,629 KV tokens) ===" && \
KUBECONFIG=/tmp/kc_inf-apac kubectl exec -n inf-apac-online-gpu deploy/vllm-fast-restore-h100-gemma-4-31b-it -c inference-server -- \
  curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"Compare 80GB HBM3 vs 96GB GDDR7 for KV cache sizing on 30B LLMs in 2 sentences."}],"max_tokens":96,"temperature":0}' | jq -r '.choices[0].message.content' && \
echo -e "\n=== [AMERICAS: us-central1 / inf-americas] Gemma 4 31B on 1x RTX PRO 6000 96GB (PodSnapshot Restored, 24.89 GiB / 29,628 KV tokens) ===" && \
KUBECONFIG=/tmp/kc_inf-americas kubectl exec -n inf-americas-online-gpu deploy/vllm-fast-restore-rtx-pro-6000-gemma-4-31b-it -c inference-server -- \
  curl -s http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
  -d '{"model":"google/gemma-4-31b-it","messages":[{"role":"user","content":"Explain why 96GB of GPU VRAM prevents KV cache bottlenecks at 16K context in 2 sentences."}],"max_tokens":96,"temperature":0}' | jq -r '.choices[0].message.content'
```

#### Copy-paste command 3C (verify `Gemma 3 27B` with Run:ai Streamer + Queue-Depth HPA in `inf-americas`)

```shell
echo "=== [AMERICAS: us-central1 / inf-americas] Gemma 3 27B on 1x RTX PRO 6000 96GB (Run:ai Streamer + Queue-Depth HPA, 32.26 GiB / 60,783 KV tokens) ===" && \
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
> saving `3.1 minutes` per pod)** with **`LOADING=0`**. Because the compiled
> Inductor/Triton caches and all 51 captured CUDA graphs are preserved inside
> the restored GPU memory image, restored replicas serve traffic immediately
> after `PodRestored: True` with zero post-restart JIT compilation stalls._
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
export KUBECONFIG="/tmp/kc_inf-americas"
export TF_VAR_platform_default_project_id="${PROJECT_ID}"
export TF_VAR_resource_name_prefix="inf"
export TF_VAR_platform_name="americas"
export TF_VAR_platform_default_region="us-central1"
export VLLM_VARIANT="rtx-pro-6000-gemma-4-31b-it"
export SERVED_MODEL_NAME="google/gemma-4-31b-it"
"${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/measure_restore.sh" 2
```

#### Copy-paste command 4B (Option 2 — Sub-minute `54.8s` warm-node `H100` restore in `inf-apac`)

```shell
KUBECONFIG=/tmp/kc_inf-apac kubectl scale deploy/vllm-fast-restore-h100-gemma-4-31b-it \
  -n inf-apac-online-gpu --replicas=0 && \
sleep 6 && \
KUBECONFIG=/tmp/kc_inf-apac kubectl scale deploy/vllm-fast-restore-h100-gemma-4-31b-it \
  -n inf-apac-online-gpu --replicas=1 && \
KUBECONFIG=/tmp/kc_inf-apac kubectl get pods -n inf-apac-online-gpu \
  -l app=vllm-fast-restore-h100-gemma-4-31b-it -w
```

---

## Part 3: Post-demo teardown (destroy all provisioned clusters & buckets)

When your demo is finished, run this block to cleanly delete `PodSnapshot` CRs,
empty the regional `*-pod-snapshots` and `*-hf-models` HNS buckets (so
`terraform destroy` does not fail with `BucketNotEmpty`), run `core/initialize`
before `online_gpu` destroy (so `online_gpu/backend.tf` points to the right
regional state bucket), and execute `teardown-ap.sh` across each regional
platform copy (`inf-americas`, `inf-europe`, `inf-apac`) created in Part 1:

```shell
export TF_VAR_resource_name_prefix="inf"
export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
export RING_TARGETS=("americas:us-central1" "europe:europe-west4" "apac:asia-south2")

for TARGET in "${RING_TARGETS[@]}"; do
  PLATFORM_NAME="${TARGET%%:*}"
  REGION="${TARGET##*:}"
  CLUSTER_NAME="${TF_VAR_resource_name_prefix}-${PLATFORM_NAME}"
  echo "=== Tearing down ${CLUSTER_NAME} in ${REGION} ==="

  cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/platform.auto.tfvars"
platform_default_project_id = "${PROJECT_ID}"
platform_default_region     = "${REGION}"
platform_name               = "${PLATFORM_NAME}"
resource_name_prefix        = "${TF_VAR_resource_name_prefix}"
EOF
  cat <<EOF > "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/cluster.auto.tfvars"
cluster_region = "${REGION}"
EOF

  # 1. Re-run core/initialize so backend.tf files point to this region's Terraform state bucket
  cd "${ACP_REPO_DIR}/platforms/gke/base/core/initialize"
  terraform init -reconfigure && terraform apply -auto-approve

  # 2. Delete PodSnapshot CRs and empty regional HNS buckets before destroying online_gpu
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh" || true
  if [ -f "/tmp/kc_${CLUSTER_NAME}" ]; then
    KUBECONFIG="/tmp/kc_${CLUSTER_NAME}" kubectl delete podsnapshot --all -n "${CLUSTER_NAME}-online-gpu" --ignore-not-found || true
  fi
  for BUCKET_SUFFIX in "pod-snapshots" "hf-models"; do
    gcloud storage rm -r "gs://${PROJECT_ID}-${CLUSTER_NAME}-${BUCKET_SUFFIX}/**" 2>/dev/null || true
  done

  # 3. Destroy online_gpu (passing ira_online_gpu_pod_snapshots_enabled=true) and run teardown-ap.sh
  cd "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu"
  rm -rf .terraform/ terraform.tfstate*
  terraform init -reconfigure && terraform destroy -auto-approve -var="ira_online_gpu_pod_snapshots_enabled=true" || true

  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/teardown-ap.sh"
done
```
