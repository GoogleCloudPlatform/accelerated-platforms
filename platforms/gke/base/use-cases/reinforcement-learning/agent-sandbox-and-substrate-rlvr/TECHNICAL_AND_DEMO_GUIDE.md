# Technical Implementation & Live Presenter Demo Guide

### GKE Agent Sandbox (`v1.0` & `v2.0`) and GKE Agent Substrate (`v3.0`)

---

## 1. Repository & Package Structure

| Directory / Package          | ADK App Name in Web UI              | Description                                                                                                                                                                                                                                                                                                                                                 |
| :--------------------------- | :---------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`gke-ai-agent-lab-v1.0/`** | `v1_coding_agent`                   | **Single-Agent Autonomous Coding (`CodingAgent`):** Executes untrusted Python code inside a pre-warmed `gVisor` (`Linux 4.4.0`) `SandboxWarmPool` pod with Zero-Trust `NetworkPolicy`.                                                                                                                                                                      |
| **`gke-ai-agent-lab-v2.0/`** | `v2_rlvr_agent` _(or `root_agent`)_ | **Multi-Agent Stateless RLVR / GRPO (`RL_Orchestrator`):** 3-stage pipeline (`Policy_Rollout_Generator` $\rightarrow$ `gVisor_Reward_Verifier` $\rightarrow$ `GRPO_Policy_Updater`) evaluating $G=3$ rollouts in stateless `SandboxWarmPool` pods.                                                                                                          |
| **`gke-ai-agent-lab-v3.0/`** | `v3_substrate_agent`                | **Multi-Agent Stateful RLVR with GKE Agent Substrate (`Substrate_Stateful_RL_Orchestrator`):** 3-stage pipeline (`Stateful_Actor_Planner` $\rightarrow$ `Substrate_Snapshot_Fork_Verifier` $\rightarrow$ `Stateful_GRPO_Trajectory_Updater`) using `ActorTemplate` + `WorkerPool` snapshot branching (`99.3x` faster state restore, `10x` compute density). |

---

## 2. Step-by-Step Technical Deployment Guide

### Prerequisites

- A Google Cloud project with the Kubernetes Engine API and Vertex AI API
  enabled.
- A GKE Standard cluster with a `gVisor` (`runsc`) node pool
  (`--sandbox type=gvisor`).
  - _Note for `v3.0` (`GKE Agent Substrate v0.1.0` full cluster installation):_
    Requires GKE Standard `1.36+` (with `PodCertificateRequest` and
    `ClusterTrustBundle` beta APIs enabled) or `1.37+`, uniform machine families
    (`c3-standard-4` or `c4`), and Workload Identity Federation for GKE.

### Automated One-Command Deployment (`v1.0`, `v2.0`, or `v3.0`)

```bash
export PROJECT_ID="your-gcp-project-id"
export CLUSTER_NAME="ai-agent-cluster"
export CLUSTER_ZONE="us-central1-a"

# Deploy v2.0 (or cd into gke-ai-agent-lab-v1.0 / gke-ai-agent-lab-v3.0)
cd gke-ai-agent-lab-v2.0
./deploy.sh
```

### What `deploy.sh` Provisions on GKE

1. **GKE Agent Sandbox Controller (`v0.1.0`) & CRDs:** Installs `Sandbox`,
   `SandboxTemplate`, `SandboxWarmPool`, and `SandboxClaim` in
   `agent-sandbox-system`.
2. **Zero-Trust Egress `NetworkPolicy` (`sandbox-policy.yaml`):** Applies
   `restrict-sandbox-egress` in namespace `agent-sandbox`, blocking `0.0.0.0/0`
   internet access and `169.254.169.254/32` GCP Metadata Server scraping while
   permitting internal cluster DNS (`53`) and `sandbox-router` traffic.
3. **Pre-Warmed gVisor Pool (`sandbox-template-and-pool.yaml`):** Provisions
   `python-sandbox-warmpool` (`replicas: 6`, `runtimeClassName: gvisor`) so
   multi-rollout turns never hit cold-start delays (`18.1s`).
4. **Authenticated Sandbox Router (`sandbox-router.yaml`):** Deploys
   `sandbox-router-deployment` backed by a Kubernetes `Secret`
   (`ROUTER_AUTH_TOKEN`).
5. **Agent Substrate Blueprint (`v3.0/substrate-actor-template.yaml`):** Defines
   `ActorTemplate/rlvr-stateful-swe-actor`
   (`cloud.google.com/machine-family: c3`, `idleSuspendTimeoutMs: 500`,
   `storageBackend: local-ssd-and-gcs`) and
   `WorkerPool/rlvr-c3-gvisor-workerpool` (`warmWorkers: 16`).

---

## 3. Live CLI Verification & Monitoring Commands

### 3.1 Verify Warm Pool vs. Cold Start Latency (`~145ms` vs `18.1s`)

Run this command from your terminal to benchmark 3 consecutive `SandboxClaim`
executions inside the `code-agent` pod without LLM generation overhead:

```bash
kubectl exec deploy/code-agent -- python3 -c '
import time
from root_agent.agent import _WARM_CLAIM_QUEUE, evaluate_rl_rollout_reward
while _WARM_CLAIM_QUEUE.qsize() < 3:
    time.sleep(0.2)
for i in range(3):
    t0 = time.perf_counter()
    res = evaluate_rl_rollout_reward(i+1, "import platform; print(platform.release())", "assert True")
    dt_ms = (time.perf_counter() - t0) * 1000
    print(f"Run {i+1}: total_tool_call_ms={dt_ms:.2f}ms | {str(res).splitlines()[0]}")
'
```

**Expected Output:**

```text
Run 1: total_tool_call_ms=144.91ms | SandboxClaim `rl-rollout-450ba5c2` (Claim Latency: 144.39 ms):
Run 2: total_tool_call_ms=148.01ms | SandboxClaim `rl-rollout-ce8eea62` (Claim Latency: 147.37 ms):
Run 3: total_tool_call_ms=162.68ms | SandboxClaim `rl-rollout-b789c14c` (Claim Latency: 162.21 ms):
```

### 3.2 Watch Ephemeral `gVisor` Pods Claim & Replenish in Real Time

```bash
kubectl get pods,sandboxclaim -n agent-sandbox -w
```

---

## 4. Live 3-Act Presenter Demo Runbook (8 Minutes Total)

### Act 1 — Foundational Single-Agent Secure Runtime (`v1.0` — `v1_coding_agent`) [2 Mins]

- **Goal:** Prove to the audience that untrusted LLM code runs inside Google's
  **gVisor (`Linux 4.4.0`) userspace kernel**—not the host node kernel—and that
  **Zero-Trust `NetworkPolicy`** blocks unauthorized internet and metadata
  access.
- **Select App in Top-Left Dropdown:** `v1_coding_agent`
- **Prompt 1A (Kernel Isolation Proof):**
  ```text
  Write and run a Python script that prints the OS kernel release (`platform.release()`), system architecture, and computes the first 15 Fibonacci numbers.
  ```
  - _Point out in UI:_ Kernel reports `4.4.0` (gVisor's virtualized syscall
    sentry) instead of the GKE host Linux kernel (`6.6+`).
- **Prompt 1B (Zero-Trust Egress & Metadata Block):**
  ```text
  Write and execute a Python script that attempts to fetch http://93.184.215.14 and the GCP Metadata Server http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token with a 3-second timeout.
  ```
  - _Point out in UI:_ Both requests time out (`URLError: timed out`) because
    `restrict-sandbox-egress` drops the packets at the GKE CNI layer.

---

### Act 2 — Multi-Agent RLVR / GRPO Without Agent Substrate (`v2.0` — `v2_rlvr_agent`) [3 Mins]

- **Goal:** Show how **Group Relative Policy Optimization (GRPO)** evaluates **3
  Candidate Rollouts (`G=3`)** for the same Payment Ledger Audit task
  (`find_target_pairs`)—catching and quarantining a **Reward-Hacking
  `169.254.169.254` Escape Attempt (`R = -1.0`)**, suppressing a **CPU-Spiking
  `O(n^2)` Loop (`R = +0.1`)**, and reinforcing the **Verified Safe `O(n)`
  Solution (`R = +1.0`)**.
- **Select App in Top-Left Dropdown:** `v2_rlvr_agent` (click **+ New Session**)
- **Prompt 2:**
  ```text
  Audit our 2,000-record payment transaction ledger (`find_target_pairs`) by evaluating all 3 Rollout attempts in gVisor (Rollout #1: 169.254.169.254 reward-hacking escape attempt, Rollout #2: O(n^2) CPU-spiking loop, and Rollout #3: verified safe O(n) solution) and display the Secure Runtime GRPO Scoreboard.
  ```
- **What to Show in the `Traces` Tab
  (`demo_v2_stateless_traces_waterfall.png`):**
  1. Show the 3-agent graph on the left (`Policy_Rollout_Generator`
     $\rightarrow$ `gVisor_Reward_Verifier` $\rightarrow$
     `GRPO_Policy_Updater`).
  2. Click **`Traces`** and point to the `🔧` tool bars (`510.99 ms` and
     `796.96 ms`) and the total turn time (`57.36s`):
     > _"Notice two bottlenecks in stateless `v2.0`: First, every rollout starts
     > in an empty container and wastes `~134 ms` rebuilding the Turn-1 ledger
     > from scratch (`796.96 ms` tool bar). Second, look at those long blue
     > `call_llm` bars (`13.6s`, `12.3s`, `10.5s`)—while waiting for the LLM on
     > GPUs, a traditional stateful container sits 100% idle hogging cluster
     > RAM!"_

---

### Act 3 — Stateful RLVR & Snapshot Branching With GKE Agent Substrate (`v3.0` — `v3_substrate_agent`) [3 Mins]

- **Goal:** Run the **exact same prompt** on **`v3_substrate_agent`
  (`GKE Agent Substrate v0.1.0`)** and show how snapshotting the `Actor`
  (`snap-gcs-c3-001`) cuts tool execution to **`135.73 ms` (`5.87x` faster)**,
  state setup to **`1.35 ms` (`99.3x` faster)**, and total turn latency in half
  (**`22.43s` vs `57.36s`**) while delivering **`10.0x Compute Density`**!
- **Select App in Top-Left Dropdown:** `v3_substrate_agent` (click **+ New
  Session**)
- **Prompt 3 (Exact Same Task):**
  ```text
  Audit our 2,000-record payment transaction ledger (`find_target_pairs`) by evaluating all 3 Rollout attempts in gVisor (Rollout #1: 169.254.169.254 reward-hacking escape attempt, Rollout #2: O(n^2) CPU-spiking loop, and Rollout #3: verified safe O(n) solution) and display the Secure Runtime GRPO Scoreboard and v2.0 vs v3.0 comparison table.
  ```
- **What to Show in the `Traces` Tab
  (`demo_v3_substrate_traces_waterfall.png`):**
  1. Point to the `🔧 fork_and_evaluate_substrate_actor_rollout` bars:
     **`135.73 ms`** and **`240.22 ms`** (down from `796.96 ms` and `510.99 ms`
     in `v2.0`—nearly **6x faster**!).
  2. Point to the ratio of blue `call_llm` bars (`20.15s` = **96.7%** of turn)
     vs. `🔧` sandbox bars (`0.68s` = **3.0%** of turn):
     > _"Because Agent Substrate suspends the `Actor` to SSD/GCS in `460ms`
     > during those `20.15s` of blue `call_llm` bars and releases the `Worker`
     > back to the `WorkerPool`, we free **92.3% of host RAM and
     > CPU**—delivering **10x Compute Density** and **sub-second `gVisor`
     > security** at the same time!"_
