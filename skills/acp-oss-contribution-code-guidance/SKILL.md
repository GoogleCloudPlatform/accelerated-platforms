---
name: acp-oss-contribution-code-guidance
description: Development guidelines, coding best practices (R-1.x through R-8.x), codebase structure, GKE/TPU/GPU accelerator invariants (P-x, Q-x, I-x), local pre-PR validation checks (pyrefly, ruff, black, isort, terraform fmt, prettier, cspell, addlicense, kustomize), and 4-pass code review checklists for GoogleCloudPlatform/accelerated-platforms (ACP) and vllm-torchtpu / llm-d GKE stacks. Use when authoring, refactoring, validating, or reviewing ACP PRs, Terraform terraservices, Kustomize overlays, Python scripts/skills, or documentation.
---

# ACP OSS Contribution & Code Review Guidance

Engineering standard for authoring, validating, and reviewing contributions to
`GoogleCloudPlatform/accelerated-platforms` (ACP) and its companion inference
stacks (`llm-d`, `vllm-torchtpu`).

This skill is normative for two workflows:

- **Authoring & Pre-PR Validation**: Apply these rules when writing or updating
  Terraform modules, Kustomize manifests, Python scripts/skills, shell scripts,
  or Markdown guides, and run the validation suite before opening or updating a
  PR.
- **PR Code Reviews**: Cite rule IDs (`R-x.y`, `PR-x`, `P-x`, `Q-x`, `I-x`,
  `D-x`) and classify findings by severity (`[BLOCKER]`, `[HIGH]`, `[MEDIUM]`,
  `[LOW / NIT]`) across Architecture, SWE Best Practices, and Security.

---

## 1. Three Meta-Principles

1. **Reuse upstream first (`R-3.1`)**:
   - For `llm-d` and GKE inference manifests, inherit from pinned upstream bases
     (`github.com/llm-d/llm-d//guides/...?ref=<tag>`) and layer minimal
     GKE-specific components/patches on top.
   - For Terraform, reuse `platforms/gke/base/core/` modules and symlinked
     `_shared_config/*_variables.tf` definitions rather than duplicating
     resource blocks or variable declarations.
   - For `vllm-torchtpu` and Python modules, search `vLLM` upstream ->
     `vllm-torchtpu` -> `modules/python/` / `JAX/Pallas` before writing new
     helpers.
2. **Derive, don't declare (`R-4.x`)**:
   - Any value recoverable from hardware topology (`ct6e-standard-4t` vs `8t`),
     tensor shapes, dtypes, `pltpu.get_tpu_info()`, or existing `tfvars` must be
     derived at the point of use—never duplicated into a magic number, redundant
     env var, or disconnected config knob.
3. **Fail fast, never silently degrade (`R-5.x`)**:
   - No bare `except:` or silent fallback when a patch target, shape, or
     parameter is invalid. Assert untested assumptions (`R-5.2`), add Terraform
     `postcondition` guards when transforming remote manifests, and write error
     messages that tell the user how to fix the issue (`R-5.4`).

---

## 2. Reference Guides (Load on Demand)

Read the relevant reference file(s) for the area you are authoring or reviewing:

| Reference File                                                                               | What It Covers                                                                                                                                                                                                                                                                            | When to Load                                                                                  |
| :------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------------------------------------------------------------------------------- |
| [references/codebase-structure.md](references/codebase-structure.md)                         | ACP directory layout (`platforms/gke/base/core/`, `_shared_config/` symlinked terraservices, `use-cases/inference-ref-arch/`, `docs/` mirroring, `modules/python/`, `skills/`, `.dev-tools/`)                                                                                             | Adding or moving files, wiring Terraform variables, structuring Kustomize overlays or skills  |
| [references/coding-and-hygiene-rules.md](references/coding-and-hygiene-rules.md)             | Complete `R-1.x`–`R-8.x` and `PR-1`–`PR-4` rules: Python style, safe `shlex`/CRD parsing, upstream reuse, derive-don't-declare, fail-fast, surface area minimization, diff discipline, zero internal leaks (`R-7.12`), unit testing                                                       | Writing or reviewing Python scripts, skills, shell scripts, Terraform, or PR descriptions     |
| [references/tpu-and-accelerator-invariants.md](references/tpu-and-accelerator-invariants.md) | GKE/Kustomize deployment invariants (`I-1`–`I-7`), TPU P/D disaggregation (`DisaggregatedSet`, `LeaderWorkerSet` v1.0.0+, `TPUConnector` `kv_role`), and `vllm-torchtpu` performance (`P-1`–`P-17`) & quantization (`Q-1`–`Q-7`) rules                                                    | Touching Kustomize overlays, TPU/GPU node pools, `vllm serve` flags, kernels, or quantization |
| [references/validation-and-code-review.md](references/validation-and-code-review.md)         | Exact local commands for all ACP CI gates (`black`, `isort`, `ruff`, `pyrefly`, `terraform fmt`, `prettier`, `cspell`, `addlicense`, `kubectl kustomize`, unit tests) + 4-pass code review rubric                                                                                         | Running pre-PR checks, fixing CI/typecheck errors, or conducting a thorough PR code review    |
| [references/docs-pr-review-checklist.md](references/docs-pr-review-checklist.md)             | Documentation PR rules (`D-1`–`D-10`): resolve every command path against the target and companion branches, match rendered resource names, single source of truth for troubleshooting, no copied runbook scaffolding, re-derivable numbers, no staged demo output, safe copy-paste shell | Reviewing or authoring guides, runbooks, or reference architectures under `docs/`             |

---

## 3. Workflow A: Authoring or Modifying Code in ACP

1. **Duplicate-Work & Scope Check (`R-7.1`, `R-7.8`–`R-7.10`)**:
   - Check open issues/PRs first. Keep PRs single-purpose; land enabling
     refactors before feature PRs (`R-7.2`); never bundle unrelated formatting
     or drive-by edits (`R-7.3`).
2. **Verify Placement & Symlink Contracts**:
   - Consult
     [references/codebase-structure.md](references/codebase-structure.md) to
     place Terraform services, shared variables (`_shared_config/`), Kustomize
     overlays, documentation mirrors (`docs/platforms/...`), and skills in their
     canonical directories.
3. **Apply Coding & Accelerator Invariants**:
   - Follow
     [references/coding-and-hygiene-rules.md](references/coding-and-hygiene-rules.md)
     for Python/Bash/Terraform hygiene (`R-1.x`–`R-8.x`).
   - When modifying GKE inference manifests, TPU/GPU node pools, or `vllm`
     configs, verify every invariant in
     [references/tpu-and-accelerator-invariants.md](references/tpu-and-accelerator-invariants.md)
     (`I-1` through `I-7`, `P-x`, `Q-x`).
4. **Run Local Pre-PR Validation**:
   - Execute the validation commands in
     [references/validation-and-code-review.md](references/validation-and-code-review.md)
     across all modified file types before committing.
5. **Run the Author Pre-Submit Checklist**:
   - **Scope**: Single purpose (`R-7.1`), no dead code or unused variables
     (`R-7.5`), updated by rebase (`R-7.6`), every line read and defensible by
     the human submitter (`R-7.7`).
   - **Zero Internal Leaks (`R-7.12`)**: Zero `go/`, `b/`, `cl/` shortlinks,
     internal hostnames (`.corp.google.com`, `.googleplex.com`), or private GCS
     buckets anywhere in code, comments, manifests, or PR description.
   - **Evidence (`R-8.10`, `P-1`, `Q-3`, `Q-6`)**: Unit tests added and wired
     into `run_python_unittests.sh` (`R-8.4`); `kubectl kustomize` renders
     cleanly; benchmark/eval and HBM logs attached for serving/model changes.

---

## 4. Workflow B: Conducting an ACP / `vllm-torchtpu` Code Review

When asked to review a branch, commit, diff, or PR:

1. **Load Review Criteria**:
   - Read
     [references/validation-and-code-review.md](references/validation-and-code-review.md),
     [references/tpu-and-accelerator-invariants.md](references/tpu-and-accelerator-invariants.md),
     and
     [references/coding-and-hygiene-rules.md](references/coding-and-hygiene-rules.md).
   - For PRs that touch `docs/` guides or runbooks, also read
     [references/docs-pr-review-checklist.md](references/docs-pr-review-checklist.md)
     and run its reviewer workflow. Green formatting CI does not show that any
     command works.
2. **Inspect the Full Diff & Upstream Bases**:
   - Never review Kustomize patches or Terraform modules in isolation. Inspect
     the upstream base (`github.com/llm-d/llm-d//guides/...` or
     `_shared_config/`) that the overlay or terraservice inherits from to catch
     strategic merge hazards (such as inherited `256Gi` memory requests, wiped
     `nodeSelector` labels, or `env` vs `envFrom` path collisions).
3. **Execute the 4-Pass Review**:
   - **Pass 1 — Architecture & Infrastructure Correctness**: Kustomize base vs
     overlay inheritance (`I-1`–`I-7`), TPU topology & GKE Warden constraints,
     P/D disaggregation (`DisaggregatedSet`, `LeaderWorkerSet`, `TPUConnector`),
     Terraform variable wiring, and graceful shutdown budgets.
   - **Pass 2 — SWE Best Practices (`R-1.x`–`R-8.x`)**: Input mutation bugs
     (shallow vs deep copy), consistent argument normalization across parsers,
     shell comment handling (`shlex.split(..., comments=True)`), fail-fast
     validation (`R-5.x`), dead code (`R-7.5`), and unit test coverage
     (`R-8.x`).
   - **Pass 3 — Security & Supply-Chain Hygiene**: Remote manifest mutation
     without integrity checks, mutable image tags (`:latest`, `:main`) or
     floating Git refs (`?ref=main`), subprocess shell injection, secret
     exposure in captured configs (`secretKeyRef`), and internal link leaks
     (`R-7.12`).
   - **Pass 4 — CI & Formatting Readiness**: License headers (`R-1.6`),
     `black`/`isort`/`ruff`/`pyrefly`, `terraform fmt` & `.terraform.lock.hcl`,
     `prettier`, and `cspell` dictionary sorting.
4. **Produce Structured Output**:
   - Group findings by **Architecture**, **SWE Best Practices**, and **Security
     Concerns**, ordered by severity (`[BLOCKER]`, `[HIGH]`, `[MEDIUM]`,
     `[LOW / NIT]`).
   - For each finding, cite the rule ID (`I-x`, `R-x.y`, `P-x`, `Q-x`, `D-x`),
     link the exact file and line range, explain the failure mechanism, and
     provide a drop-in code fix. End with a prioritized remediation checklist
     table.
