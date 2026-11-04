# Coding Style, Hygiene & PR Discipline (`R-1.x` – `R-8.x`)

Adapted from
[`vllm-project/vllm-torchtpu`](https://github.com/vllm-project/vllm-torchtpu)'s
`docs/developers_guide/coding_guidance.md` and upstream
`GoogleCloudPlatform/accelerated-platforms` (ACP) standards. Reviewers and
authors cite these rule IDs (`R-<section>.<n>` and `PR-<n>`) directly in PR
reviews and pre-submit checks.

---

## 1. Python, Shell, Terraform & Markdown Style (`R-1.x`)

- **R-1.1 — Google Style Guides**:
  - Follow the
    [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
    (naming, Google-style `Args:`/`Returns:`/`Raises:` docstrings, exception
    handling, default-argument rules).
  - Follow the
    [Google Shell Style Guide](https://google.github.io/styleguide/shellguide.html)
    and
    [Google Cloud Terraform Best Practices](https://cloud.google.com/docs/terraform/best-practices-for-terraform).
- **R-1.2 — Formatter & Import-Sort Compliance**:
  - **In ACP**: Python files are gated by `black ~= 25.9`
    (`black --check --diff`) and `isort`
    (`isort --check-only --diff --profile black .`).
  - **In `vllm-torchtpu`**: `pre-commit` runs `ruff format` and
    `ruff check --fix`.
  - Never push code with `--no-verify` or bypass local formatters.
- **R-1.3 — Line Length & Wrapping**:
  - Keep Python code within 88 columns. Add a trailing comma after the last
    element of multi-line collections/calls so formatters keep one element per
    line. Wrap long comments and docstrings manually; use `# noqa: E501` only
    for unsplittable URLs or Markdown table rows.
  - Keep Markdown wrapped via Prettier (`.prettierrc` sets
    `"proseWrap": "always"`, `"tabWidth": 2`).
- **R-1.4 — Explicit Imports Only**:
  - Never use `from x import *` or obscure single-letter aliases.
- **R-1.5 — Modern Typing (`pyrefly`)**:
  - Use PEP 604 unions (`int | None`, not `Optional[int]`), builtin generics
    (`list[str]`, `dict[str, Any]`), and `StrEnum` for string enums.
  - Type-annotate public function signatures and ensure code passes `pyrefly`
    type checking (see
    [validation-and-code-review.md](validation-and-code-review.md)).
- **R-1.6 — Apache 2.0 License Headers & Final Newline**:
  - Every new source file (`.py`, `.sh`, `.tf`, `.yaml`, Dockerfile) MUST carry
    the standard Google Apache 2.0 license header (enforced in CI by
    `google/addlicense`) and end with a single newline (`\n`, enforced by
    `.editorconfig` and `final-newline.yaml`).
- **R-1.7 — Structured Logging & No Stray Debug Output**:
  - No `print` in library code (use `init_logger` with
    `warning_once`/`info_once` for unexpected fallback branches). In CLI tools
    (`capture_vllm_config.py`, `tune_workload.py`), send diagnostics/warnings to
    `sys.stderr` so stdout stays clean for JSON/YAML piping.
- **R-1.8 — Self-Documenting Code Over Redundant Comments**:
  - Delete comments that merely restate the code. Comment only non-obvious
    invariants, hardware constraints, or _why_ a decision was made.
- **R-1.9 — Safe CLI/Shell Parsing & Deep Copy Hygiene (ACP Tooling)**:
  - **Never mutate input dicts via shallow copy**: When expanding composite
    Kubernetes manifests (such as splitting a `DisaggregatedSet` into synthetic
    per-role dicts), use `copy.deepcopy(doc)`, never `dict(doc)` (which shares
    nested `metadata` and `spec` dicts across iterations).
  - **Consistent argument normalization across parsers**: When extracting CLI
    arguments from container `command`/`args` (including
    `bash -c "vllm serve ..."`), run shell splitting and `$(ENV_VAR)`
    substitution **once** up front and pass the normalized token list to every
    downstream parser (`parse_vllm_args`, `parse_kv_transfer`, etc.).
  - **Comment-aware shell tokenization**: Multi-line `vllm serve` shell blocks
    in Kustomize patches frequently contain `#` comment lines. Always call
    `shlex.split(cmd_str, comments=True)` (in Python, `shlex.split` defaults to
    `comments=False`, which treats `#` as a literal argument and corrupts flag
    parsing).

---

## 2. Architecture Ground Rules (`R-2.x`)

- **R-2.1 — Strict Directory Responsibilities**:
  - Place files in their designated layer (`platforms/gke/base/core/`,
    `_shared_config/`, `use-cases/`, `modules/python/`, `skills/` in ACP;
    `kernels/`, `layers/common/`, `layers/vllm/`, `platforms/`, `runner/` in
    `vllm-torchtpu`).
- **R-2.2 — Thin Interface & Overlay Layers**:
  - Kustomize overlays and `vllm` platform/runner bridges only translate between
    upstream definitions and GKE/TPU specifics. Never embed model-specific hacks
    inside shared base components.
- **R-2.3 — Self-Contained Kernels & Pure Functions**:
  - Everything a kernel or parser needs arrives via explicit arguments—no
    `os.environ` reads inside `@jax.jit` or Pallas kernels (`R-4.3`).
- **R-2.4 — Name by Functionality, Not by Model**:
  - Name directories, patches, and modules by capability
    (`precise-prefix-cache-routing`, `ragged_paged_attention`), not by the
    single model used to test them.
- **R-2.5 — Pin Upstream Versions & Dependencies**:
  - Pin Kustomize remote bases (`?ref=v1.0.0`), Helm chart `--version` flags,
    container image tags (`images:` transformer), Terraform providers
    (`.terraform.lock.hcl`), and Python package pins (`pyproject.toml` /
    `requirements.txt`). Never rely on floating `?ref=main` or `:latest` in
    production reference architectures.
- **R-2.6 — Centralize Environment & Startup Mutations**:
  - In `vllm-torchtpu`, startup env overrides belong exclusively in
    `env_override.py`. In ACP Kustomize manifests, keep shared runtime env vars
    in the upstream `runtime` ConfigMap or a single clearly scoped patch, aware
    that explicit `container.env` entries override `envFrom` (`I-3`).

---

## 3. Reuse Upstream First (`R-3.x`)

- **R-3.1 — Upstream Search Order**:
  - Before writing new code or manifests, search:
    1. Upstream (`llm-d` guides / `vLLM` base classes)
    2. Repo shared modules (`platforms/gke/base/core/`, `_shared_config/`,
       `examples/llmd/components/`, `modules/python/`, `vllm-torchtpu`
       `layers/common/`)
    3. Standard library / JAX / Pallas utilities
- **R-3.2 — No Per-Model or Per-Overlay Copy-Paste Forks**:
  - Factor shared Kustomize patches into `examples/llmd/components/` (e.g.,
    `graceful-shutdown`, `igw-4-tpu`, `model-PV-storage`) and shared Python
    logic into `modules/python/` or `layers/common/`.
- **R-3.3 — Name the Target File When Deduping**:
  - During code review, when flagging duplication, name the exact shared file or
    component where the logic should live.
- **R-3.4 — Fix Upstream Defects Upstream**:
  - If an upstream `llm-d` base or `vLLM` class has a defect, file/land the fix
    upstream; any temporary local patch in ACP or `vllm-torchtpu` must carry a
    comment explaining why the override is needed and when it can be removed.
- **R-3.5 — Use Official Extension Points**:
  - Use Kustomize strategic merge / JSON6902 patches, `LeaderWorkerSet` /
    `DisaggregatedSet` fields, and `vLLM` plugin registration (`register_oot`,
    `AttentionBackendEnum`) rather than brittle text replacement (`sed` or raw
    string `replace()` on remote YAML).

---

## 4. Derive, Don't Declare (`R-4.x`)

- **R-4.1 — Capability Dispatch Over String/Attribute Probing**:
  - No `getattr(cfg, "field", default)` that silently returns a stale default on
    upstream renames, and no `"qwen3" in model_name.lower()`. Dispatch on typed
    capabilities, `isinstance`, or explicit schema fields
    (`kind: DisaggregatedSet`).
- **R-4.2 — Derive From Shapes & Hardware Specs**:
  - Compute block sizes, TP/DP ranks, memory requests, and KV-cache budgets from
    tensor shapes and hardware specs (`model_specs.json`, node memory limits,
    `pltpu.get_tpu_info()`) rather than hard-coding magic numbers.
- **R-4.3 — No Environment Reads Inside Compiled/Jitted Code**:
  - Read environment variables once at the outer CLI/entrypoint boundary and
    pass explicit arguments inward.
- **R-4.4 — No Hard-Coded Hardware Constants**:
  - Query runtime device metadata or canonical hardware tables rather than
    scattering literal byte counts (`120 * 1024 * 1024`) or string checks.
- **R-4.5 — Named Constants for Axis & Label Keys**:
  - Define shared constants for mesh axis names (`EP_AXIS_NAME = "d"`), GKE
    label keys (`cloud.google.com/gke-tpu-accelerator`), and CRD group/version
    kinds.
- **R-4.6 & R-4.7 — Typed Containers Over Loose Dicts/Sentinels**:
  - Prefer `dataclass`, `NamedTuple`, and `Enum`/`StrEnum` over deeply nested
    untyped dicts, multiple mutually-exclusive booleans, or magic `-1`
    sentinels.

---

## 5. Fail Fast — No Silent Failure (`R-5.x`)

- **R-5.1 — No Bare or Silent `except`**:
  - Never write `except:` or `except Exception: pass` to swallow errors. Catch
    only narrow, expected exceptions (`yaml.YAMLError`,
    `subprocess.CalledProcessError`) and log or re-raise with context.
- **R-5.2 — Assert Untested Assumptions & Postconditions**:
  - In Python/kernels, `assert` shape/alignment preconditions.
  - In Terraform, whenever mutating an upstream manifest string (if
    unavoidable), add a `lifecycle { postcondition { ... } }` block asserting
    that the target substring was actually present and replaced.
- **R-5.3 — Raise `NotImplementedError` for Unsupported Paths**:
  - Never silently fall back to an incorrect configuration (e.g., never fall
    back to `kv_both` when `kv_consumer` is required).
- **R-5.4 — Actionable Error Messages**:
  - State both what failed and how to fix it (e.g.,
    `"--spec is required; choose one of: optimized-baseline, precise-prefix-cache-routing, predicted-latency-routing, pd-disaggregation"`).
- **R-5.5 — Never Hide Dtype or Resource Mismatches**:
  - Fix the root cause of a dtype or node-resource mismatch rather than masking
    it.

---

## 6. Minimize Surface Area (`R-6.x`)

- **R-6.1 & R-6.2 — Question Every New Knob / Variable / Flag**:
  - Before adding a new Terraform variable, CLI flag, or env var, ask if it can
    be derived. Add a knob only for: (a) a temporary migration selector with a
    stated deletion condition, (b) a debug escape hatch that does not alter
    defaults, or (c) a documented quality/performance tradeoff dial.
- **R-6.3 – R-6.6 — Unify Code Paths**:
  - Collapse special cases into shared abstractions (e.g., handle `Deployment`,
    `LeaderWorkerSet`, and `DisaggregatedSet` through a unified pod-spec
    extractor rather than duplicating parsing loops).

---

## 7. Diff & PR Discipline (`R-7.x` & `PR-1`–`PR-4`)

- **R-7.1 — Small, Single-Purpose PRs**:
  - Separate infrastructure/refactoring PRs from workload/feature PRs. Cite base
    PRs explicitly when stacking.
- **R-7.2 & R-7.3 — Refactor First; Zero Unrelated Hunks**:
  - Do not mix drive-by reformatting, unrelated typo fixes, or dead experiments
    into a feature PR.
- **R-7.4 & R-7.5 — Justify Every Line; Delete Dead Code**:
  - Every changed line must answer _"what breaks if this line does not exist?"_
  - Delete unused Terraform variables, superseded scripts, commented-out YAML
    blocks, and skipped tests in the same PR.
- **R-7.6 & R-7.7 — Rebase Only; Human Line-by-Line Accountability**:
  - Update branches via `git rebase`, never merge commits. The human author must
    read and be able to defend every line in the diff.
- **R-7.8 – R-7.10 — Duplicate Check, No Busywork, Fail Closed**:
  - Check open issues/PRs (`gh pr list`, `gh issue list`) before starting work.
    Do not open trivial busywork PRs.
- **R-7.11 & `PR-1`–`PR-4` — Mechanism-Driven PR Descriptions**:
  - Title states the general capability unlocked. Body lists mechanisms, states
    provenance when porting code from another repo (`PR-3`), includes per-mode
    speedups for perf changes (`PR-1`), and carries an honest **Limitations**
    section (`PR-4`).
- **R-7.12 — Zero Internal-Only References in Public Repos**:
  - **Strictly forbidden in code, comments, YAML, scripts, commits, and PRs**:
    `go/`, `b/`, `cl/` shortlinks, `.corp.google.com` or `.googleplex.com` URLs,
    internal project IDs, or personal GCS buckets. Cite public GitHub issues,
    source paths, or HuggingFace model cards instead.

---

## 8. Testing Standards (`R-8.x`)

- **R-8.1 — Test Real Behavior & Error Paths**:
  - Every Python script/module change under `modules/python/` or
    `skills/*/scripts/` requires unit tests exercising real parsing/execution
    paths and failure modes—not just module imports.
- **R-8.2 — Regression Tests Must Fail Without the Fix**:
  - Verify that reverting the code fix turns the new test red.
- **R-8.3 — Parametrize Over Cloning**:
  - Factor out shared fixtures (e.g., sample `Deployment`, `LeaderWorkerSet`,
    and `DisaggregatedSet` manifests) and parametrize test cases.
- **R-8.4 — Wire Every Test Directory Into CI**:
  - Ensure `run_python_unittests.sh` discovers the test directory. Green CI
    means nothing if the test directory is not in `run_python_unittests.sh`.
- **R-8.7 — Explicit `MagicMock` Attributes**:
  - When mocking objects in `unittest`, explicitly set every attribute read by
    the code under test so auto-created child mocks don't silently pass
    truthiness checks.
- **R-8.10 — Proactive Benchmark & Eval Evidence**:
  - Any change affecting serving parameters, routing, Kustomize resource sizing,
    or model execution ships with validation output in the PR description.
