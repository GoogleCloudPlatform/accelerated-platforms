# GKE Agent Substrate — The Secure Runtime Reference Architecture

**Agent Substrate** (`ate-system`) is a stateful sandbox runtime for Kubernetes that decouples an agent's persistent identity and memory/filesystem state (**Actors**) from underlying compute (**WorkerPools**). Every actor executes inside a dedicated **gVisor (`runsc`)** user-space kernel on warm worker pods, restores in **<500ms** from pre-warmed **Golden Snapshots** (`SNAPSHOT_FIDELITY_MEMORY`) stored in Google Cloud Storage, and routes all network traffic through identity-aware gateways (**`atenet-router`** for ingress and **`atenet-egress`** for default-deny egress, out-of-sandbox credential injection, and pluggable Envoy `ext_proc` L7 HTTP inspection).

---

## Reference Architecture

![The Secure Runtime Reference Architecture](images/reference-architecture.svg)

### Architecture Components & Trust Zones

| Layer | Component | Responsibility |
| :--- | :--- | :--- |
| **Zone 1: Agent Harness (`agent-harness`)** | **ADK GitHub Triage Agent** (`triage-agent`) | Powered by **Gemini on Vertex AI** (`GOOGLE_GENAI_USE_VERTEXAI=1`). Classifies tool execution intent via `before_tool_callback`, updates per-actor `EgressPolicy`, pushes dynamic HTTP method/path rules to `intent-extproc`, and invokes actors over mTLS through `atenet-router`. |
| **Zone 2: Substrate Control & Data Plane (`ate-system`)** | **`ate-api-server` & `ate-controller`** | Manages `Atespace`, `ActorTemplate`, `Actor`, `EgressPolicy`, and `WorkerPool` reconciliation; stores metadata in Cloud SQL / PostgreSQL. |
| | **`atenet-router`** | Ingress mTLS gateway (`:443`). Authenticates caller SPIFFE IDs (`podidentity.podcert.ate.dev/identity`), wakes suspended actors on demand via `atelet`, and streams requests to the actor's container port. |
| | **`atenet-egress` + `k8s-credential-provider`** | Default-deny egress gateway (`:443`). Verifies per-actor SPIFFE certificates, terminates TLS using ephemeral leaves (`egress-mitm.ate.dev`), and injects secrets (`replaceHeaders`) outside the sandbox from `agent-credentials`. |
| | **`intent-extproc`** | Pluggable Envoy `ExternalProcessor` (`--experimental-additional-egress-extproc-service=ate-system/intent-extproc:50051`) chained after TLS termination in `atenet-egress`. Enforces dynamic per-actor HTTP method (`GET`/`HEAD` vs `POST`/`PATCH`/`DELETE`) and URL path prefix policies, recording structured audit logs. |
| **Zone 3: Sandbox Worker Pool (`ate-workers`)** | **`ateworker-gvisor` + `atelet`** | Runs on a uniform `c3-standard-4` node pool (`ate.dev/worker-pool=true`, taint `ate.dev/sandboxClass=gvisor:NoSchedule`). Hosts gVisor `runsc` sandboxes (`scientific-python` pre-loading `numpy`, `scipy`, `pandas`, `matplotlib`) and node-local `atunnel` network relays. |
| **Zone 4: State & Storage** | **Google Cloud Storage Snapshot Bucket** | Stores immutable **Golden Snapshots** built from `ActorTemplate` (`SNAPSHOT_FIDELITY_MEMORY`) and per-actor pause/resume memory + rootfs checkpoints (`layer.tar`, `memory.pages`). |

---

## State Storage & Snapshot Security Model

1. **Where Agent State Is Stored:**
   - **Control Plane Metadata (PostgreSQL):** Stores `Actor`, `ActorTemplate`, and `EgressPolicy` definitions, actor lifecycle state (`RUNNING`, `PAUSED`), and content-addressed manifest pointers.
   - **Data Plane Checkpoints (Google Cloud Storage):** When an `ActorTemplate` is created—or when an active actor is paused (`kubectl-ate pause actor`)—`atelet` instructs `runsc` to checkpoint the sandbox's writable overlay filesystem (`layer.tar`) and process memory pages (`memory.pages`) to the dedicated GCS snapshot bucket via the node-local `objectstore-plugin`.
2. **Why Snapshots Cannot Leak Credentials:**
   - Secrets (`agent-credentials/github-readonly-token`) are **never mounted into the actor container, passed as environment variables, or present in sandbox RAM**.
   - Instead, `atenet-egress` fetches the token from `k8s-credential-provider` and injects the `Authorization: Bearer ...` header *on the wire* outside the sandbox after TLS termination. Even if a raw memory snapshot (`memory.pages`) in GCS were inspected, it contains **zero credentials**.
3. **Why Untrusted Actor State Cannot Poison Other Actors:**
   - The **Golden Snapshot** created by `ActorTemplate` (`scientific-python`) is **immutable**.
   - Any changes made by an actor during a session are written to an **actor-scoped copy-on-write snapshot prefix** in GCS (`gs://<snapshot-bucket>/<atespace>/<actor-uid>/<generation>/`).
   - When an actor encounters untrusted input (such as Issue #42), its checkpoint is quarantined for forensic inspection while subsequent tasks spawn fresh actors from the clean Golden Snapshot in **<500ms**.

---

## Repository Structure

This solution builds directly on the **GKE Base Reference Architecture** (`platforms/gke/base/core`):

```text
container-images/cpu/
├── secure-runtime-runner/                 # Scientific Python actor runner (numpy, scipy, pandas, matplotlib)
├── secure-runtime-intent-extproc/         # Go Envoy ExternalProcessor for L7 HTTP method/path filtering
└── secure-runtime-agent/                  # Vertex AI Gemini ADK GitHub Triage Agent + before_tool_callback

platforms/gke/base/
├── core/
│   ├── container_node_pool/cpu/region/{us-central1,us-east4}/
│   │   └── container_node_pool_cpu_c3_substrate.tf  # Uniform c3-standard-4 worker pool + n4-standard-4 gVisor baseline pool
│   └── workloads/agent_substrate/                   # Core terraservice: GCS snapshot bucket + kubectl-ate init
└── use-cases/agent-substrate-secure-runtime/
    ├── kubernetes-manifests/                        # intent-extproc, WorkerPool, ActorTemplate, Credential Secret, ADK Agent, Baseline Pod
    ├── terraform/                                   # deploy-standard.sh, teardown-standard.sh, initialize, secure_runtime
    └── demo/                                        # seed-github-issues.sh + 4-Act live verification scripts
```

---

## Prerequisites & Deployment

### 1. Configure Shared Platform Variables

Set your project, region, and GitHub repository settings in `platforms/gke/base/_shared_config/platform.auto.tfvars` and `platforms/gke/base/use-cases/agent-substrate-secure-runtime/terraform/_shared_config/agent-substrate-secure-runtime.auto.tfvars` (or via `TF_VAR_*` environment variables):

```bash
export TF_VAR_platform_default_project_id="<YOUR_GCP_PROJECT_ID>"
export TF_VAR_platform_default_region="us-central1"
export TF_VAR_cluster_Location="us-central1"
export TF_VAR_secure_runtime_github_repo="<YOUR_GITHUB_ORG>/secure-runtime-sandbox-demo"
export TF_VAR_secure_runtime_github_readonly_token="<YOUR_FINE_GRAINED_READONLY_GITHUB_PAT>"
```

### 2. Seed the Private Demo GitHub Repository

```bash
GITHUB_REPO="${TF_VAR_secure_runtime_github_repo}" \
  ./platforms/gke/base/use-cases/agent-substrate-secure-runtime/demo/seed-github-issues.sh
```

### 3. Deploy Core Platform, Agent Substrate & Secure Runtime Workloads

```bash
./platforms/gke/base/use-cases/agent-substrate-secure-runtime/terraform/deploy-standard.sh
```

### 4. Validate the Deployment

```bash
./platforms/gke/base/use-cases/agent-substrate-secure-runtime/demo/validate.sh
```

---

## Running the 4-Act Live Demo

| Act | Script | What It Demonstrates |
| :--- | :--- | :--- |
| **Act 1: The Untrusted Boundary** | `./demo/act1-sandbox-boundary.sh` | Executes diagnostic probes inside `triage-actor-19`, demonstrating `gVisor` (`runsc`) user-space syscall interception, masked `/proc`/`/sys` paths, and isolated `atunnel` networking. |
| **Act 2: Crushing Cold Starts** | `./demo/act2-cold-start-race.sh` | Races a cold Kubernetes `gVisor` Pod (`~18-25s` boot + scientific stack import) against an Agent Substrate Actor restored from the `scientific-python` Golden Snapshot (`<500ms`, `0ms` import overhead), followed by stateful pause/resume to GCS. |
| **Act 3: Dynamic Intent Filtering** | `./demo/act3-intent-egress.sh` | Applies a per-actor `EgressPolicy` (`replaceHeaders` from `agent-credentials`) and an `intent-extproc` `READ_ONLY` rule (`GET`/`HEAD`). Verifies `200 OK` on `GET /issues`, zero credentials in the sandbox, `403 Forbidden` on `POST /issues/1/comments`, and `NXDOMAIN` on unapproved hosts. |
| **Act 4: Audit & Quarantine** | `./demo/act4-audit-quarantine.sh` | Queries the structured L7 audit log from `intent-extproc`, revokes egress and pauses `triage-actor-42` into a forensic GCS snapshot, and spawns a fresh clean actor from the Golden Snapshot in `<500ms`. |

See the [Live Demo Presenter Runbook](demo-runbook.md) for the step-by-step stage script and talking points.
