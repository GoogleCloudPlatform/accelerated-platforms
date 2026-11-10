# ACP Codebase Structure & Architectural Conventions

This reference explains how `GoogleCloudPlatform/accelerated-platforms` (ACP) is
organized and how Terraform terraservices, Kustomize overlays, documentation,
and agent skills fit together.

---

## 1. Top-Level Directory Map

```text
accelerated-platforms/
├── .devcontainer/            # VS Code devcontainer and Dockerfile with pinned tooling
├── .dev-tools/               # Maintainer scripts (cspell dictionaries, Terraform lock files, cleanup)
├── .github/workflows/        # CI workflows, plus cspell dictionaries in dictionary/*.txt
├── container-images/         # Dockerfiles for the repository's container images
├── docs/                     # User-facing guides; mirrors the platforms/ hierarchy
├── modules/python/           # Shared Python library (src/ and tests/), run by unittest CI
├── platforms/
│   ├── cws/                  # Cloud Workstations platform
│   ├── gke-aiml/             # Deprecated Playground AI/ML platform
│   └── gke/base/             # GKE base platform and its use-case reference architectures
│       ├── _shared_config/   # Shared *_variables.tf and *.auto.tfvars, linked into terraservices
│       ├── core/             # Core terraservices and the deploy/teardown scripts that run them
│       ├── features/         # Optional platform features (for example nvidia_nim_llm)
│       ├── kubernetes/       # kubeconfig and core manifests
│       ├── modules/          # Shared Terraform modules (kubectl_apply, kubectl_wait)
│       ├── tutorials/        # Step-by-step tutorials
│       └── use-cases/        # Reference architectures (inference-ref-arch, training-ref-arch, ...)
├── projects/                 # Standalone projects (workflow-api)
├── skills/                   # Agent skills
├── terraform/                # Shared Terraform modules and features
├── test/                     # CI/CD configuration (test/ci-cd/) and test scripts
├── tools/                    # Repository utilities
└── use-cases/                # Use cases for the deprecated Playground platform
```

---

## 2. The Terraservice & `_shared_config` Symlink Pattern

ACP splits GKE infrastructure into independent Terraform root modules called
**terraservices**, under `platforms/gke/base/core/` and
`platforms/gke/base/use-cases/<use-case>/terraform/`. Paths in the rest of this
section are relative to `platforms/gke/base/`.

### 2.1 Core Terraservices (`platforms/gke/base/core/`)

- `initialize/`: Terraform state bucket, backend configuration, and the
  per-region node pool files.
- `networking/`: VPC, subnets (including the proxy-only subnet), Cloud Router
  and Cloud NAT, and firewall rules.
- `container_cluster/` and `container_cluster_ap/`: GKE Standard and Autopilot
  clusters.
- `container_node_pool/`: per-region CPU, GPU, and TPU node pool definitions
  under `{cpu,gpu,tpu}/region/<region>/`.
- `custom_compute_class/`: GKE custom compute classes (`ComputeClass`), with GPU
  and TPU templates under `templates/manifests/`.
- `gke_enterprise/fleet_membership/`: GKE Fleet registration.
- `workloads/`: cluster add-ons and controllers, for example `lws`, `kueue`,
  `jobset`, `inference_gateway`, `agent_sandbox`, `custom_metrics_adapter`, and
  `auto_monitoring`.

### 2.2 How `_shared_config/` Symlinks Work

Each terraservice directory holds **relative symlinks**, prefixed with `_`, to
the shared variable definitions and values in `_shared_config/`. The depth of
`../` depends on where the terraservice sits:

- `core/container_cluster/_cluster_variables.tf -> ../../_shared_config/cluster_variables.tf`
- `core/workloads/lws/_cluster_variables.tf -> ../../../_shared_config/cluster_variables.tf`
- `use-cases/inference-ref-arch/terraform/online_gpu/_inference-ref-arch_variables.tf -> ../_shared_config/inference-ref-arch_variables.tf`

Matching `_<name>.auto.tfvars` symlinks carry the values. Use cases keep their
own `_shared_config/` (for example
`use-cases/inference-ref-arch/terraform/_shared_config/`).

**Rules for Modifying Terraform in ACP**:

1. **Declare shared variables once in `_shared_config/`**: If more than one
   terraservice reads a variable, define it in the right
   `_shared_config/*_variables.tf` file and symlink that file, with its
   `.auto.tfvars`, into each terraservice that uses it.
2. **Never leave dead variables (`R-7.5`)**: Every variable declared in
   `_shared_config/*_variables.tf` or a terraservice `variables.tf` must have at
   least one consumer, or be deleted in the same PR that removes its last use.
3. **Keep terraservice order in the deploy scripts**: `core/deploy-ap.sh` and
   `core/deploy-standard.sh` list core terraservices in
   `CORE_TERRASERVICES_APPLY_ARRAY`; `core/teardown-*.sh` list them in
   `CORE_TERRASERVICES_DESTROY_ARRAY`, in reverse dependency order. Use-case
   scripts (for example `use-cases/inference-ref-arch/terraform/deploy-ap.sh`)
   use a `use_case_terraservices` array. Insert a new terraservice in dependency
   order, and add it to the matching teardown script in reverse order.
4. **Keep `.terraform.lock.hcl` in sync**: When provider constraints in a
   `versions.tf` change, run `.dev-tools/bin/update_terraform_lock_files.sh` so
   every terraservice lock file matches.

---

## 3. `inference-ref-arch` & `llm-d` Kustomize Layering

Under `platforms/gke/base/use-cases/inference-ref-arch/`:

```text
inference-ref-arch/
├── examples/
│   ├── comfyui/
│   └── llmd/
│       ├── _shared_config/          # Shared tfvars and gateway templates for every guide
│       ├── initialize/              # Gateway, namespace, frontend, and dashboard setup
│       ├── <guide>/                 # Terraform inputs for one well-lit path guide
│       ├── deploy-llmd-<guide>.sh   # Deploys one guide end to end
│       └── teardown-llmd-<guide>.sh
├── kubernetes-manifests/
│   ├── online-inference-gpu/
│   │   ├── base/                    # Shared base: deployment ConfigMap from generated deployment.env
│   │   ├── components/              # Opt-in Kustomize components (graceful-shutdown, gke-pod-snapshot, accelerators/)
│   │   ├── llmd-<guide>/vllm/
│   │   │   ├── base/                # Upstream llm-d guide (?ref=v1.0.0) + ../../../base
│   │   │   ├── configure_vllm.sh    # Writes deployment.env; run before kubectl kustomize
│   │   │   └── <accelerator>-<model>/
│   │   ├── dynamo-trtllm/           # NVIDIA Dynamo + TensorRT-LLM overlays and components
│   │   └── trtllm/                  # TensorRT-LLM overlays
│   └── online-inference-tpu/
│       ├── base/
│       └── llmd-<guide>/vllm/{base,configure_vllm.sh,v6e-<model>/}
└── terraform/                       # Use-case terraservices, including multi-region/
```

The tree shows the llm-d paths. `kubernetes-manifests/` also holds
`async-inference-gpu/`, `offline-batch-inference-gpu/`, `inference-perf-bench/`,
`k6-benchmark/`, and `model-download/`.

The `llm-d` guides are `optimized-baseline`, `precise-prefix-cache-routing`, and
`predicted-latency-routing` (GPU and TPU), plus `pd-disaggregation` (TPU).

### 3.1 How Overlays Compose Upstream `llm-d`

Each leaf overlay (for example
`kubernetes-manifests/online-inference-tpu/llmd-optimized-baseline/vllm/v6e-qwen3-32b/`)
is a Kustomize overlay (`kustomization.yaml`) built in three layers:

1. **Leaf → `../base`**: the leaf's only `resources:` entry is `../base`.
2. **`llmd-<guide>/vllm/base/`** composes two resources:
   - the upstream `llm-d` guide base at a pinned tag
     (`https://github.com/llm-d/llm-d//guides/<guide>/modelserver/tpu/v6/vllm/base?ref=v1.0.0`
     or `.../modelserver/gpu/vllm/base?ref=v1.0.0`), which already includes
     upstream's `graceful-shutdown` recipe component;
   - `../../../base` (`online-inference-{gpu,tpu}/base/`), which generates the
     `deployment` ConfigMap from a `deployment.env` file that the family's
     `configure_vllm.sh` writes.
3. **The leaf** then adds:
   - a `runtime` ConfigMap from `runtime.env` and a `nameSuffix`;
   - patches that adapt the upstream base for GKE: `patch-resources.yaml`,
     `patch-nodeselector.yaml`, and `patch-vllm-args.yaml`. The P/D overlay uses
     per-role `patch-prefill-*.yaml` and `patch-decode-*.yaml` files plus
     `patch-deployment-strategy.yaml`, the upstream `disaggregatedset-schema`
     component, and a local `kustomizeconfig.yaml`;
   - `replacements` that copy the namespace, service account, and model label
     from the ConfigMaps;
   - `images:` pins for any image it overrides (for example
     `docker.io/vllm/vllm-torchtpu` `newTag: v0.29.0` on TPU).

Shared ACP components in `kubernetes-manifests/online-inference-gpu/components/`
(`gke-pod-snapshot`, `accelerators/`, `graceful-shutdown`) are opt-in. The
`llmd-<guide>` overlays on `main` don't include them; ACP's `graceful-shutdown`
is used by the `trtllm` and `dynamo-trtllm` overlays.

> [!IMPORTANT] Always inspect the upstream `llm-d` base at the exact `?ref=`
> commit before writing or reviewing an overlay patch. Strategic merge patches
> inherit every upstream field they do not explicitly override (see `I-1`–`I-10`
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

Repository-hosted skills live under `skills/<skill-name>/`. Every path under
`/skills/` is owned in `.github/CODEOWNERS` (`R-7.17`).

- The executable skills (`gke-inference-stack-deploy`, `llm-d-benchmarking`,
  `llm-d-deploy-stack`, `llm-d-workload-tuner`) use `SKILL.MD` with YAML
  frontmatter (`name`, `description`, `version`, `allowed-tools`, `mcp-servers`)
  and step-by-step instructions, plus:
  - `scripts/`: Executable Python or Bash helpers (e.g.,
    `capture_vllm_config.py`, `tune_workload.py`, `run_benchmark.sh`) and
    `test_*.py` unit tests.
  - `references/`: Supporting tables, JSON model specs (`model_specs.json`), and
    workload profiles.
  - `evals/`: Skill evaluation test cases registered in
    `skills/llm-d-skills-evaluation-suite.md`.
- Guidance-only skills with no scripts or tools, such as this one, use
  `SKILL.md` with `name` and `description` frontmatter and a `references/`
  directory.
- Any new directory containing Python unit tests (`test_*.py`) must be wired
  into both `run_python_unittests.sh` and `run_python_coverage_test.sh` at the
  repository root (`R-8.4`, `R-8.12`).
