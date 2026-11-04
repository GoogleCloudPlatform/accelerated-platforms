# Validation Checks & Code Review Rubric

This reference provides the exact local validation commands matching upstream
`GoogleCloudPlatform/accelerated-platforms` (ACP) GitHub Actions workflows and
`vllm-torchtpu`'s type-checking pipeline
(`docs/developers_guide/type_checking.md`), followed by the structured 4-pass
code review methodology.

---

## 1. Local Pre-PR Validation Suite

Run the checks below for every file type touched in your PR before pushing.

### 1.1 Python Formatting, Import Sorting & Lint

ACP CI gates every PR on `black` (`~= 25.9`) and `isort` (`--profile black`),
while `vllm-torchtpu` gates on `ruff` via `pre-commit`:

```bash
# In accelerated-platforms (matches .github/workflows/python.yaml):
black --check --diff --verbose .
isort --check-only --diff --profile black .

# To auto-fix in accelerated-platforms:
black .
isort --profile black .

# In vllm-torchtpu:
pre-commit run --all-files
```

### 1.2 Python Static Type Checking (`pyrefly` & `ruff`)

From `vllm-torchtpu`'s `docs/developers_guide/type_checking.md`:

- **Two `pyrefly` gates**:
  1. `pre-commit` hook runs `pyrefly` without third-party packages (`torch`,
     `jax`, `vllm` resolve to `Any`) against `.pyrefly-baseline.json`.
  2. Full-environment check (`bash tools/typecheck_full.sh`) runs inside the CI
     container image against real `torch`, `jax`, and `vllm` signatures and
     `.pyrefly-baseline-full.json`.
- **Commands**:

  ```bash
  # Run pre-commit (ruff + pyrefly lightweight) and full container typecheck:
  pre-commit run --all-files
  bash tools/typecheck_full.sh

  # For standalone ACP Python scripts (skills/*/scripts/*.py, modules/python/):
  uvx pyrefly@1.3.0 check <path/to/script.py>
  ```

- **How to Fix New `pyrefly` Errors**:
  - **Fix the code—never add new errors to `.pyrefly-baseline*.json`**.
  - **Keep runtime behavior unchanged**: Do NOT add defensive `try`/`except` or
    fake fallback values just to silence a type checker (`R-5.1`).
  - **Approved type-narrowing patterns**:
    - Place `assert x is not None` immediately before use in the same branch
      when setup guarantees the value.
    - Narrow into a local variable and assert before assigning to `self.attr` so
      the attribute retains the narrow type.
    - Use `typing.cast` where an upstream library declares a looser type than
      runtime guarantees.
    - Initialize variables before conditional branches rather than relying on
      every branch to bind the name.
    - Use an own-line `# pyrefly: ignore[<error-code>]` **only** for genuine
      false positives (e.g., `bad-override-mutable-attribute`), always naming
      the exact error code.
  - **Regenerating baselines (only when your PR removes existing errors)**:
    ```bash
    uvx pyrefly@1.3.0 check --update-baseline
    bash tools/typecheck_full.sh --update-baseline
    pre-commit run --all-files
    ```
    The baseline diff MUST only delete entries (except when a file is renamed).

### 1.3 Python Unit Tests & Coverage

Matches `.github/workflows/python-unit-test.yaml` and
`.github/workflows/python-coverage-test.yaml`:

```bash
# Run all registered unit test suites (modules/python + skills):
bash run_python_unittests.sh

# Run coverage check:
bash run_python_coverage_test.sh
```

> [!IMPORTANT] If you add a new `test_*.py` file under a new
> `skills/<skill>/scripts` or `modules/` directory, add that directory to
> `run_python_unittests.sh` (`R-8.4`).

### 1.4 Terraform Formatting & Lock Files

Matches `.github/workflows/terraform.yaml` (Terraform `1.8.0`):

```bash
# Check formatting recursively across the repo:
terraform fmt -check -recursive

# Auto-fix formatting:
terraform fmt -recursive

# If any version.tf provider constraints changed, update all .terraform.lock.hcl files:
.dev-tools/bin/update_terraform_lock_files.sh

# Clean up any local .terraform directories and check for stray tfstate files:
.dev-tools/bin/cleanup_terraform.sh
```

### 1.5 Kustomize & Kubernetes Manifest Rendering

Always render every modified Kustomize overlay and inspect the resulting YAML:

```bash
# Render an overlay and verify exit code 0:
kubectl kustomize platforms/gke/base/use-cases/inference-ref-arch/examples/llmd/<spec>/<accel>/

# Inspect critical merged fields (resources, nodeSelector, env, volumes, rolloutStrategy):
kubectl kustomize <overlay_dir> | grep -E -A 12 "resources:|nodeSelector:|rolloutStrategy:|volumeMounts:"
```

### 1.6 Markdown Formatting (`prettier`) & Spellcheck (`cspell`)

Matches `.github/workflows/prettier.yaml` and `.github/workflows/cspell.yaml`:

```bash
# Check Markdown formatting (.prettierrc sets proseWrap: always, tabWidth: 2):
npx prettier --check '**.md'

# Auto-fix Markdown formatting:
npx prettier --write '**.md'

# Verify CSpell dictionary files (.github/workflows/dictionary/*.txt) are lowercase, sorted, and unique:
.dev-tools/bin/dictionaries_check.sh

# Auto-fix dictionary ordering/casing if you added new domain terms:
.dev-tools/bin/dictionaries_fix.sh

# Run CSpell across the repository:
npx cspell "**"
```

### 1.7 License Headers (`addlicense`) & Final Newlines

Matches `.github/workflows/addlicense.yaml` and
`.github/workflows/final-newline.yaml`:

```bash
# Check Apache 2.0 license headers on modified files:
docker run --rm -v "${PWD}:/workspace" ghcr.io/google/addlicense:latest -check \
  -ignore ".terraform/**" -ignore "**/.terraform/**" -ignore "node_modules/**" .
```

---

## 2. Structured 4-Pass Code Review Methodology

When conducting a code review on an ACP or `vllm-torchtpu` diff/PR, execute all
four passes below and classify each finding using:

- **`[BLOCKER]`**: Causes deployment/pod scheduling failure, admission webhook
  rejection, runtime crash, silent numerical corruption, CI failure, or security
  vulnerability. Must be fixed before merge.
- **`[HIGH]`**: Degrades serving performance (e.g., broken P/D skip-prefill,
  rollout deadlock, container rootfs exhaustion) or corrupts tooling outputs.
- **`[MEDIUM]`**: Fragile maintainability, missing timeout alignment, unpinned
  upstream references, or incomplete error handling.
- **`[LOW / NIT]`**: Dead variables, minor style/documentation inconsistencies,
  or test coverage polish.

### Pass 1: Architecture & Infrastructure Correctness

1. **Upstream Base vs Overlay Merge Audit (`I-1`–`I-7`)**:
   - Render or trace the Kustomize overlay against its upstream `llm-d` base.
   - Check pod `resources.requests/limits` (`memory`, `cpu`, `google.com/tpu`)
     against the target GKE node's allocatable memory (`I-1`).
   - Check `$patch: replace` on `nodeSelector`—ensure
     `cloud.google.com/gke-tpu-accelerator` and
     `cloud.google.com/gke-tpu-topology` are preserved alongside
     `cloud.google.com/compute-class` (`I-2`).
   - Check `container.env` vs `container.envFrom` precedence and verify
     `HF_HOME` matches the mounted volume path (`I-3`).
   - Check `--shutdown-timeout=45` when `graceful-shutdown` component is used
     (`I-4`).
   - For P/D disaggregation (`DisaggregatedSet` / `LeaderWorkerSet`), verify
     `maxSurge: 0, maxUnavailable: 1` (`I-5`), `kv_role: kv_consumer` on decode
     (`I-6`), and `/dev/shm` + `TPU_KV_SHM_POOL_GB` memory headroom (`I-7`).
2. **Terraform & Terraservice Wiring**:
   - Confirm new terraservices in `deploy-ap.sh` / `teardown-ap.sh` are ordered
     correctly and torn down in reverse order.
   - Check that `_shared_config/` symlinks are valid relative paths and no dead
     variables remain (`R-7.5`).

### Pass 2: Software Engineering Best Practices (`R-1.x` – `R-8.x`)

1. **Parser & Data-Structure Correctness (`R-1.9`)**:
   - Check for shallow-copy mutation bugs (`dict(doc)` instead of
     `copy.deepcopy(doc)`).
   - Check that shell tokenization uses `shlex.split(..., comments=True)` and
     that normalized/substituted `args` are passed to **all** parsers.
2. **Derive, Don't Declare & Fail Fast (`R-4.x`, `R-5.x`)**:
   - Flag `getattr(..., default)` that hides schema changes (`R-4.1`), bare
     `except:` blocks (`R-5.1`), or missing Terraform `postcondition` checks.
3. **TPU Performance & Quantization (`P-x`, `Q-x`)**:
   - Check for `lax.cond` in hot loops (`P-13`), missing load-time weight
     preprocessing (`P-12`, `P-14`), or missing HBM/numeric validation (`Q-3`,
     `Q-6`).
4. **Unit Tests (`R-8.x`)**:
   - Verify tests cover new CRDs/features (e.g., `DisaggregatedSet`, multi-line
     shell comments, `$()` substitution) and are wired into
     `run_python_unittests.sh`.

### Pass 3: Security & Supply-Chain Hygiene

1. **Remote Manifest & Image Pinning (`R-2.5`)**:
   - Flag unvalidated substring `replace()` on `http` data sources fetching
     `raw.githubusercontent.com/.../main`. Require immutable version tags
     (`?ref=v1.0.0`), pinned image tags/digests, or `postcondition`
     verification.
2. **Subprocess & Shell Safety**:
   - Ensure Python scripts invoke `kubectl`/`gcloud` via list arguments
     (`["kubectl", *args]`) without `shell=True`, and quote shell variables in
     `.sh` scripts (`"${VAR}"`).
3. **Secret & Internal-Link Redaction (`R-7.12`)**:
   - Ensure config-capture scripts redact or warn on `secretKeyRef` env vars.
   - Scan the entire diff for internal shortlinks (`go/`, `b/`, `cl/`), corp
     domains, or private GCS buckets.

### Pass 4: CI Gate Verification

- Check `addlicense` headers (`R-1.6`), `black`/`isort`/`ruff`/`pyrefly`
  compliance (`R-1.2`, `R-1.5`), `terraform fmt` (`R-1.1`), `prettier` Markdown
  wrapping (`R-1.3`), and `cspell` dictionary sorting
  (`.dev-tools/bin/dictionaries_check.sh`).
