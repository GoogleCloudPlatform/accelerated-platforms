# GKE AI Agent Lab `v3.0` — GKE Agent Substrate (`v0.1.0`)

### Stateful Multi-Turn RLVR, 470ms Snapshot Branching & 10x Compute Density

`v3.0` builds on `v1.0` (Single-Agent Autonomous Coding) and `v2.0` (Multi-Agent
Stateless RLVR/GRPO on `GKE Agent Sandbox`) by introducing
**[GKE Agent Substrate (`v0.1.0`)](https://docs.cloud.google.com/kubernetes-engine/ai-ml/about-agent-substrate)**
(`Actor` + `ActorTemplate` + `WorkerPool`) for **stateful multi-turn
Reinforcement Learning trajectories** (such as 30-step SWE-bench debugging
episodes, OSWorld/terminal agents, and **Nous Research's Hermes Agent**).

---

## 1. Evolution Across `v1.0` $\rightarrow$ `v2.0` $\rightarrow$ `v3.0`

| Version                 | Focus & Architecture                                                                     | Kubernetes CRDs & Runtime                                                                                                        | RL / Agent Use Case                                                                                                                                                                                                                                    |
| :---------------------- | :--------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`v1.0`**              | **Single-Agent Autonomous Coding** (`CodingAgent`)                                       | `GKE Agent Sandbox` (`SandboxTemplate` + `SandboxWarmPool` + `gVisor` + `NetworkPolicy`)                                         | Safe, sub-second (`~145ms`) execution of untrusted LLM Python code with Zero-Trust egress & metadata server (`169.254.169.254`) protection.                                                                                                            |
| **`v2.0`**              | **Multi-Agent Stateless RLVR / GRPO Loop** (`RL_Orchestrator`)                           | `GKE Agent Sandbox` (`SandboxWarmPool`, `replicas: 6`) + ADK `SequentialAgent` + 100% KV-Cache Prefix Callback                   | **Critic-free GRPO code verification:** Samples $G=2$ rollouts per prompt (`O(2^n)` vs `O(n)`), grades correctness + Big-O runtime latency (`R = +1.0` vs `-0.2`), and computes normalized group advantage $A_i$.                                      |
| **`v3.0`** _(This Lab)_ | **Stateful Multi-Turn RLVR & Snapshot Branching** (`Substrate_Stateful_RL_Orchestrator`) | **`GKE Agent Substrate v0.1.0`** (`Actor` + `ActorTemplate` + `WorkerPool` on uniform `c3` nodes with Local SSD + GCS snapshots) | **10x Compute Density & 470ms Checkpoint Forking:** Suspends idle `Actor` memory/filesystem state (`460ms` P90) while the Policy LLM generates tokens on GPU/TPU, and forks $G$ parallel rollout branches from the same snapshot in **`470ms` (P90)**. |

---

## 2. Why Multi-Turn RL Needs GKE Agent Substrate (`v0.1.0`)

During a 30-turn agentic RL episode (e.g., modifying a repository across
multiple turns), the sandbox executes a tool command for **~200ms** and then
sits **90%+ idle for 5–15 seconds** waiting for the Policy LLM ($\pi_\theta$ on
GPU/TPU) to generate its next `<think>...</think>` reasoning chain and tool
call.

1. **Decoupled `Actor` (State) vs. `Worker` (Compute) $\rightarrow$
   `10x Compute Density`:**
   - **`Actor`**: The stateful running instance of an agent or RL environment
     (working memory + filesystem).
   - **`WorkerPool`**: A pool of pre-started, idle `gVisor` (or
     `Cloud Hypervisor` microVM) `Workers` (`substrate-actor-template.yaml`).
   - When an `Actor` pauses to wait on LLM inference, Agent Substrate
     **snapshots its memory and filesystem to Local SSD + Cloud Storage in
     `460ms` (P90)** and releases the `Worker` back to the `WorkerPool`.
2. **Sub-500ms Snapshot Branching for Multi-Turn GRPO / MCTS:**
   - When the Policy LLM proposes $G=2$ candidate patches at Turn 2,
     `Substrate_Snapshot_Fork_Verifier` restores the Turn-1 `Actor` snapshot
     (`snap-gcs-c3-001`) onto two parallel warm `Workers` in **`470ms` (P90)**
     (`>500 activations/sec` across `200,000` agents on a `1,000-node` cluster)
     without re-cloning the repository or re-building Turn-1 state!

---

## 3. Prompts to Try in `v3.0` (`Substrate_Stateful_RL_Orchestrator`)

### Prompt 1 — Multi-Turn Stateful Snapshot Forking (`O(n^2)` vs `O(n)` Patch on Turn-1 Dataset)

```text
Create a Turn-1 stateful Actor snapshot (`snap-gcs-c3-001`) containing an in-memory transaction log of 2,000 events, then fork G=2 parallel Agent Substrate Actor branches from that snapshot (`Branch #1: O(n^2)` nested loop anomaly detector vs `Branch #2: O(n)` hash-map detector), verify both on the gVisor WorkerPool, and compute the GRPO group advantage A_i and 10x compute density telemetry.
```

### Prompt 2 — Stateful Checkpoint Branching + Zero-Trust Anti-Reward-Hacking Probe

```text
Fork two Agent Substrate Actor branches from snapshot `snap-gcs-c3-002` to solve the Longest Consecutive Sequence problem (`Branch #1: O(n^2)` vs `Branch #2: O(n)` set lookup), AND run `verify_zero_trust_isolation` to prove that a rogue RL Actor cannot exfiltrate data or scrape the GCP Metadata Server (`169.254.169.254`).
```
