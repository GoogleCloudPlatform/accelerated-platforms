# Documentation PR Review Checklist (`D-1` – `D-12`)

Guides, runbooks, and reference architectures under `docs/` pass every
formatting gate in CI (`prettier`, `cspell`, `final-newline`) while still
shipping commands that cannot run. Formatting CI proves nothing about
correctness. Apply this checklist to any PR that adds or changes copy-paste
commands, benchmark numbers, or troubleshooting guidance, in addition to the
4-pass review in [validation-and-code-review.md](validation-and-code-review.md).

Cite these rule IDs (`D-x`) in review comments alongside `R-x.y`, `I-x`, and
`PR-x`.

---

## 1. Commands Must Run (`D-1` – `D-3`)

- **D-1 — Resolve every path against the branch it depends on (`[BLOCKER]`)**:
  - For every script, manifest, Kustomize directory, or Terraform module a
    command block calls, confirm the path exists on the branch the docs will
    merge onto, or on the named companion PR branch:
    ```shell
    gh api "repos/GoogleCloudPlatform/accelerated-platforms/contents/<path>?ref=<branch>" -q .type
    ```
  - Stacked PRs: check the companion manifests PR, not just `main`. State the
    full merge order in the PR description.
- **D-2 — Resource names must match what the manifests render (`[BLOCKER]`)**:
  - Job, Deployment, label selector, and namespace names in `kubectl wait`,
    `kubectl logs`, and `kubectl exec` must match the rendered names
    (`nameSuffix`, `replacements`, hashed Job names such as
    `${HF_MODEL_ID_HASH}-hf-model-to-gcs`). Verify with
    `kubectl kustomize <overlay> | grep -E '^  name:|part-of'`.
- **D-3 — One canonical entry point per task (`[MEDIUM]`, `R-6.3`)**:
  - Companion documents (guide + runbook) must use the same script for the same
    task (for example model download via `download_apply.sh` /
    `download_wait.sh` / `download_delete.sh`). Two different invocations of the
    same operation drift apart and one of them breaks.

## 2. Single Source of Truth (`D-4` – `D-5`)

- **D-4 — Troubleshooting text must match the shipped manifests (`[BLOCKER]`)**:
  - Any row labeled "already applied in repository manifests" must describe
    exactly what the manifest does: same environment variable, same path, same
    append versus prepend order, same port, same root cause.
  - Prefer linking to the single deep-dive section over restating a fix in a
    table, a talk track, and a deep-dive.
- **D-5 — Do not copy scaffolding between runbooks (`[HIGH]`, `R-3.2`)**:
  - Multi-region provisioning loops, tool bootstrap blocks, helper functions,
    and teardown loops that already exist in another runbook belong in a
    reviewed, testable script under `platforms/` or `test/scripts/`, invoked by
    both documents. Measure overlap against the sibling runbook before
    approving.

## 3. Numbers Must Be Re-Derivable (`D-6` – `D-7`)

- **D-6 — Re-derive every headline number (`[HIGH]`, `PR-1`)**:
  - Recompute ratios (`A / B = N×`), unit conversions (GiB versus GB), byte
    counts from shapes (for example
    `layers × 2 × kv_heads × head_dim × bytes = per-token KV`), and durations
    (`size / rate`). Cross-check hardware specs (vCPU, host RAM, GPU memory, NIC
    bandwidth) against the public Compute Engine machine-type page.
- **D-7 — Compare like with like and state the trade-off (`[HIGH]`, `PR-4`)**:
  - Reject multipliers that compare different models, prompt lengths, or
    statistics (p50 versus mean). When a configuration wins on one metric and
    regresses on another (for example disaggregated serving improving p99 ITL
    while worsening burst TTFT), the regression must appear next to the win.
  - Do not hard-code prices; link the official pricing page.

## 4. Demos Must Demonstrate What They Claim (`D-8`)

- **D-8 — No staged or hard-coded success output (`[BLOCKER]`)**:
  - A demo step labeled "failover", "WAN", or "cross-region" must exercise that
    path (a real load balancer, a real drain, a real remote connection). Sending
    a request directly to a different cluster is not failover; connecting to
    `127.0.0.1` is not a WAN check.
  - Talk tracks or claims in demo runbooks must quote what each command block
    actually measures; label any numbers not produced by that block as reference
    benchmarks.
  - Never print fixed success strings that do not depend on the observed result.

## 5. Safe Copy-Paste Shell & Formatting (`D-9` – `D-12`)

- **D-9 — No destructive side effects on the reader's machine (`[HIGH]`)**:
  - Never overwrite `~/.kube/config`, shell profiles, or tracked repository
    config files without a backup; prefer per-command `KUBECONFIG=` and
    `TF_VAR_*` over `sed -i` on `*.auto.tfvars`.
  - Never `rm` Terraform state as part of a happy path.
- **D-10 — Pinned, reviewed dependencies only (`[BLOCKER]`, `R-2.5`)**:
  - No `git clone` of personal repositories, no unpinned `curl … | bash`, no
    `pip install --break-system-packages`. Pin tool versions, verify checksums,
    and pin container images by tag and, for production guidance, by digest.
  - Fail fast: no `|| true` on commands whose failure invalidates later steps,
    and no `|| break` that continues into dependent work.
- **D-11 — Re-read reflowed blockquotes (`[LOW]`)**:
  - After `prettier --write`, search blockquotes for a `>` in the middle of a
    line. Prettier can unwrap a blockquote marker into prose, where it reads as
    "greater than".
- **D-12 — Re-run doc command blocks after any post-test edit (`[HIGH]`)**:
  - Any edit to a command block in a guide or runbook after a live test requires
    re-running the edited command block verbatim as written.

---

## Reviewer Workflow for Documentation PRs

1. List every command block and every path, resource name, and number in it.
2. Run `D-1` and `D-2` against the target and companion branches.
3. Re-derive every number in summary tables and talk tracks (`D-6`, `D-7`).
4. Diff troubleshooting tables and talk tracks against the manifests (`D-4`).
5. Measure duplication against sibling runbooks (`D-5`).
6. Before approving, require that the author re-ran every block end to end from
   the final commit (`R-8.10`, `D-12`).
