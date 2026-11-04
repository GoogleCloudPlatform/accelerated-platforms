# ACP Codebase Structure & Architectural Conventions

This reference explains how `GoogleCloudPlatform/accelerated-platforms` (ACP) is
organized and how Terraform terraservices, Kustomize overlays, documentation,
and agent skills fit together.

---

## 1. Top-Level Directory Map

```text
accelerated-platforms/
├── .devcontainer/          # VS Code devcontainer & Dockerfile with pinned tooling
├── .dev-tools/             # Maintainer helper scripts (cspell dictionaries, tf locks, cleanup)
├── .github/workflows/      # CI pipelines + cspell domain dictionaries (.github/workflows/dictionary/*.txt)
├── container-images/       # Dockerfiles built by build-container-images.yaml
├── docs/                   # User-facing architecture guides (mirrors platforms/ hierarchy)
├── modules/python/         # Shared Python library code (src/ and tests/) run by unittest CI
├── platforms/
│   ├── cws/                # Cloud Workstations platform
│   └── gke/base/           # Foundational GKE platform & use-case reference architectures
│       ├── _shared_config/ # Canonical variable definitions & tfvars shared via symlinks
│       ├── core/           # Reusable Terraform "terraservices" (cluster, node pools, LWS, workloads)
│       ├── kubernetes/     # Core Kubernetes manifests / kubeconfig helpers
│       ├── solutions/      # Composed multi-component solutions
│       ├── tutorials/      # Step-by-step deployment tutorials
│       └── use-cases/      # Domain reference architectures (inference-ref-arch, training-ref-arch, etc.)
├── skills/                 # Agent skills (llm-d-deploy-stack, llm-d-benchmarking, llm-d-workload-tuner, etc.)
├── terraform/              # Top-level Terraform modules/utilities
├── test/                   # End-to-end and integration test harnesses
└── tools/                  # Repository-level CLI and validation utilities
```

---

## 2. The Terraservice & `_shared_config` Symlink Pattern

ACP decomposes GKE infrastructure into independent Terraform root modules called
**terraservices** under `platforms/gke/base/core/` and
`platforms/gke/base/use-cases/<use-case>/terraform/`.

### 2.1 Core Terraservices (`platforms/gke/base/core/`)

- `initialize/`: Bootstraps GCP project APIs, state buckets, and IAM.
- `networking/`: VPC, subnets, Cloud NAT, and Private Service Connect.
- `container_cluster/`: GKE cluster provisioning.
- `container_node_pool/`: GPU and TPU node pools (supports multi-host TPU
  topologies via `placement_policy.tpu_topology`).
- `custom_compute_class/`: GKE Custom Compute Classes (`ComputeClass` CRDs) for
  declarative node autoscaling and hardware fallback.
- `gke_enterprise/fleet_membership/`: GKE Fleet registration and Gateway API /
  mesh controllers.
- `workloads/lws/`: `LeaderWorkerSet` (LWS) CRD & controller installation.
- `workloads/kueue/`, `workloads/jobset/`, `workloads/custom_metrics_adapter/`:
  Batch and inference scheduling controllers.

### 2.2 How `_shared_config/` Symlinks Work

Every terraservice directory contains **relative symlinks** pointing to the
shared variable files in `platforms/gke/base/_shared_config/`:

- `cluster_variables.tf -> ../../../_shared_config/cluster_variables.tf`
- `core_variables.tf -> ../../../_shared_config/core_variables.tf`
- `inference-ref-arch_variables.tf -> ../../../../_shared_config/inference-ref-arch_variables.tf`

**Rules for Modifying Terraform in ACP**:

1. **Declare shared variables once in `_shared_config/`**: If a variable is read
   by multiple terraservices (or passed via shared `.auto.tfvars`), define it in
   the appropriate `platforms/gke/base/_shared_config/*_variables.tf` file and
   symlink that file into the consuming terraservice directory.
2. **Never leave dead variables (`R-7.5`)**: Every variable declared in
   `_shared_config/*_variables.tf` or a terraservice `variables.tf` must have at
   least one active consumer, or be deleted in the same PR that removes its last
   usage.
3. **Preserve `deploy.sh` / `teardown.sh` array ordering**: Use-case
   `deploy-ap.sh` / `teardown-ap.sh` scripts iterate over an ordered
   `terraservices=(...)` array. New terraservices (e.g., `workloads/lws`) must
   be inserted in dependency order (after cluster/fleet initialization and
   before workload manifests) and mirrored in teardown in reverse order.
4. **Keep `.terraform.lock.hcl` synchronized**: Whenever `version.tf` provider
   constraints change, run `.dev-tools/bin/update_terraform_lock_files.sh` so
   all terraservice lockfiles stay consistent.

---

## 3. `inference-ref-arch` & `llm-d` Kustomize Layering

Under `platforms/gke/base/use-cases/inference-ref-arch/`:

```text
inference-ref-arch/
├── examples/
│   ├── comfyui/
│   └── llmd/
│       ├── components/                  # Reusable Kustomize Component patches
│       │   ├── apply-all-HTTPRoute/
│       │   ├── disagg-set/              # DisaggregatedSet conversion for P/D
│       │   ├── graceful-shutdown/       # preStop sleep + terminationGracePeriodSeconds
│       │   ├── igw-4-tpu/               # GKE Inference Gateway TPU BackendPolicy/HealthCheck
│       │   ├── model-PV-storage/        # PVC volume mount for HuggingFace cache
│       │   └── otel/                    # OpenTelemetry tracing injection
│       ├── optimized-baseline/          # Spec 1: Single-tier optimized vLLM baseline
│       │   ├── gpu/{h100,rtx-pro-6000}/
│       │   └── tpu/v6/
│       ├── pd-disaggregation/           # Spec 2: Prefill/Decode disaggregated serving
│       │   ├── gpu/h100/
│       │   └── tpu/v6/
│       ├── precise-prefix-cache-routing/# Spec 3: KV-cache-aware EPP routing
│       │   ├── gpu/{h100,rtx-pro-6000}/
│       │   └── tpu/v6/
│       └── predicted-latency-routing/   # Spec 4: Latency-objective EPP routing
│           ├── gpu/{h100,rtx-pro-6000}/
│           └── tpu/v6/
├── kubernetes-manifests/                # Standalone GKE inference manifests
└── terraform/                           # Use-case terraservices (comfyui, llmd, online_gpu, online_tpu)
```

### 3.1 How Overlays Compose Upstream `llm-d`

Each leaf directory (e.g., `examples/llmd/precise-prefix-cache-routing/tpu/v6/`)
is a Kustomize overlay (`kustomization.yaml`) that:

1. Pulls `resources:` from upstream `llm-d` via Git URL
   (`https://github.com/llm-d/llm-d//guides/<guide>/ms-<guide>/tpu/v6/vllm/base?ref=v1.0.0`).
2. Pulls reusable local `components:` from `../../../components/<name>`.
3. Applies strategic merge or JSON6902 `patches:` (`patch-ModelServer.yaml`,
   `patch-vllm-args.yaml`, `patch-Prefill.yaml`, `patch-Decode.yaml`) to adapt
   resources, `nodeSelector`, `ComputeClass`, and `vllm serve` CLI flags for
   GKE.
4. Pins container images via the `images:` transformer (`newName`, `newTag`).

> [!IMPORTANT] Always inspect the upstream `llm-d` base at the exact `?ref=`
> commit before writing or reviewing an overlay patch. Strategic merge patches
> inherit every upstream field they do not explicitly override (see `I-1`–`I-7`
> in [tpu-and-accelerator-invariants.md](tpu-and-accelerator-invariants.md)).

---

## 4. Documentation Mirroring (`docs/platforms/...`)

User-facing architectural documentation and tutorials live under
`docs/platforms/gke/base/use-cases/...`, mirroring the directory structure under
`platforms/gke/base/use-cases/...`.

- Keep executable code/manifests in `platforms/` and narrative walkthroughs in
  `docs/platforms/`.
- When updating deployment commands, Helm chart versions, or directory paths in
  `platforms/`, update the corresponding guide in `docs/platforms/` and any
  referencing skill in `skills/` in the same PR.

---

## 5. Agent Skills (`skills/`)

Repository-hosted skills live under `skills/<skill-name>/`:

- `SKILL.MD` (or `SKILL.md`): YAML frontmatter (`name`, `description`,
  `version`, `allowed-tools`, `mcp-servers`) and step-by-step instructions.
- `scripts/`: Executable Python or Bash helpers (e.g., `capture_vllm_config.py`,
  `tune_workload.py`, `run_benchmark.sh`) and `test_*.py` unit tests.
- `references/`: Supporting tables, JSON model specs (`model_specs.json`), and
  workload profiles.
- `evals/`: Skill evaluation test cases registered in
  `skills/llm-d-skills-evaluation-suite.md`.
- Any new directory containing Python unit tests (`test_*.py`) must be wired
  into `run_python_unittests.sh` at the repository root (`R-8.4`).
