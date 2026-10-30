# Live Demo Runbook — "The Secure Runtime"

This presenter guide walks through the 4-Act live demonstration for **"The Secure Runtime: Safely Isolating, Governing, and Auditing Code-Executing Agents on Kubernetes."**

---

## Pre-Show Checklist (10 Minutes Before Stage)

1. Verify cluster credentials and `kubectl-ate` CLI:
   ```bash
   cd platforms/gke/base/use-cases/agent-substrate-secure-runtime
   ./demo/validate.sh
   ```
2. Open two terminal panes side-by-side:
   - **Left Pane (Operator / Telemetry View):** Watches actor lifecycle and `intent-extproc` L7 audit events.
   - **Right Pane (Demo Execution):** Runs the 4-Act scripts (`act1` through `act4`) or interacts with the ADK Web UI (`kubectl port-forward -n agent-harness svc/triage-agent-svc 8000:80`).

---

## Act 1: The Untrusted Boundary (gVisor Syscall Interception)

### Stage Command
```bash
./demo/act1-sandbox-boundary.sh
```

### Presenter Talking Points
- "When an autonomous coding agent executes model-generated Python code, standard Linux containers (`runc`) expose over 300 host Linux kernel system calls directly to untrusted code."
- "Here in Act 1, our actor `triage-actor-19` runs inside **Agent Substrate's `ateworker-gvisor`** sandbox (`runsc`). Notice the `/boundary` output: application syscalls are intercepted in user space by the gVisor Sentry, sensitive `/proc/kcore` and `/proc/kallsyms` paths are masked, `dmesg` kernel ring buffer access is denied, and the sandbox's `eth0` interface terminates in a dedicated user-space network stack (`atunnel`)."

---

## Act 2: Crushing the Cold-Start Penalty (Golden Snapshots vs Cold K8s Pod)

### Stage Command
```bash
./demo/act2-cold-start-race.sh
```

### Presenter Talking Points
- "Strong sandbox isolation historically came with a painful tradeoff: booting a fresh `gVisor` Pod and importing heavy scientific libraries (`numpy`, `scipy`, `pandas`, `matplotlib`) takes **15 to 25 seconds**."
- "Watch the race on screen: Baseline A creates a standard Kubernetes `gVisor` Pod (`cold-gvisor-baseline`), which spends ~20 seconds scheduling, initializing the sandbox, and importing `scipy.linalg` and `pandas`."
- "Baseline B creates an Agent Substrate Actor from our `scientific-python` `ActorTemplate`. When we deployed the template, Substrate booted the container once, imported the entire scientific stack into RAM, waited for `/readyz`, and captured a **Golden Snapshot** (`SNAPSHOT_FIDELITY_MEMORY`) in Cloud Storage."
- "Restoring that memory snapshot onto our warm `c3-standard-4` `WorkerPool` takes **under 500 milliseconds** with **0ms** of Python import overhead—and when we pause and resume the actor, its in-memory and `/tmp/triage-state.json` state is preserved across checkpoints."

---

## Act 3: Dynamic Intent Filtering & Out-of-Sandbox Credential Injection

### Stage Command
```bash
./demo/act3-intent-egress.sh
```

### Presenter Talking Points
- "Now our Vertex AI Gemini ADK Triage Agent picks up **Issue #42** from our private GitHub repository. Unknown to the agent, the issue body contains indirect prompt-injection instructions telling the sandbox to steal `GITHUB_TOKEN`, post unauthorized comments back to GitHub, and exfiltrate data to an external server."
- "Before any code executes in the sandbox, our ADK `before_tool_callback` classifies the task intent as `READ_ONLY` (`GET`/`HEAD` on `/repos/<owner>/<repo>/`) and configures two independent enforcement layers:"
  1. **Out-of-Sandbox Credential Injection (`atenet-egress` + `k8s-credential-provider`):** The actor's `EgressPolicy` permits HTTPS only to `api.github.com:443` and injects `Authorization: Bearer ...` from the `agent-credentials` namespace *at the egress gateway*. Inside the sandbox, `os.environ` and `/var/run/secrets` contain **zero credentials**.
  2. **L7 HTTP Method/Path Enforcement (`intent-extproc`):** Even though `api.github.com:443` is an allowed host, our Envoy `ExternalProcessor` inspects the decrypted HTTP request inside `atenet-egress`:
     - `GET https://api.github.com/repos/.../issues` -> **`200 OK`** (token injected on the wire).
     - `POST https://api.github.com/repos/.../issues/1/comments` -> **`403 Forbidden`** (`intent-extproc` blocks write methods during a `READ_ONLY` turn).
     - `GET https://unapproved-collector.example.com/telemetry` -> **`NXDOMAIN` / Connection Refused** (blocked by default-deny DNS and egress).

---

## Act 4: End-to-End Audit Trail, Quarantine & Golden Snapshot Reset

### Stage Command
```bash
./demo/act4-audit-quarantine.sh
```

### Presenter Talking Points
- "Every allowed and denied request at `atenet-egress` is attributed to the actor's cryptographic SPIFFE certificate (`spiffe://cluster.local/atespace/secure-runtime/actor/triage-actor-42`) and logged by `intent-extproc`."
- "In a single command, we revoke `triage-actor-42`'s egress policy and pause its memory and filesystem state to Cloud Storage (`kubectl-ate pause actor`) so security engineers can inspect the quarantined checkpoint offline—while immediately freeing the worker Pod."
- "And because the `scientific-python` **Golden Snapshot** is immutable, our next task spawns a brand-new, uncompromised actor in **under 500 milliseconds**."
