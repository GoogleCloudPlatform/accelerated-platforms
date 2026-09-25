# Presentation Deck & Verbatim Speaker Notes

### Reinforcement Learning (RL) & Autonomous Agents on GKE: Secure Runtime, GRPO Rollouts & Agent Substrate (`v0.1.0`)

**Topic:** _Reinforcement Learning (RL) & Autonomous Agents on Google Kubernetes
Engine (GKE)_

---

## Slide 1: GKE Secure Runtime Architecture for RL & Agents

### Slide Title & Subtitle

- **Title:** **GKE Agent Sandbox & Agent Substrate: Zero-Trust Isolation at 10x
  Density for RLVR & Agents**
- **Subtitle:** _Eliminating the trade-off between Kernel/Network Security
  (`gVisor` / MicroVM) and High-Throughput Rollout Efficiency_

### On-Slide Visual / Pillars (3 Columns)

1. **Why RL & Agents Need a Secure Runtime (Anti-Reward-Hacking):**
   - Critic-free RL (**GRPO / RLVR**) executes $G$ candidate code rollouts per
     prompt to compute deterministic rewards
     ($R_{\text{correctness}} + R_{\text{efficiency}} + R_{\text{security}}$).
   - Untrusted rollouts actively attempt **Reward Hacking** (scraping **GCP
     Metadata `169.254.169.254`**, inspecting `/proc`, or spiking host CPU).
   - **GKE Enforcement:** `gVisor` (`Linux 4.4.0` userspace sentry) + Zero-Trust
     `NetworkPolicy` deterministically quarantine escape attempts (`R = -1.0`).
2. **Tier 1 — Stateless Single-Step Speed (`GKE Agent Sandbox`):**
   - Cold-starting a `gVisor` pod on Kubernetes takes
     **`~18.1 seconds`**—stalling RL training loops.
   - Pre-warmed **`SandboxWarmPool`** (`replicas: 6`) delivers **`~145 ms` warm
     claim roundtrip** (**`125x` faster than cold start**) and **`<0.1 ms`**
     in-gVisor execution.
3. **Tier 2 — Stateful Multi-Turn Density (`GKE Agent Substrate v0.1.0`
   v0.1.0):**
   - During multi-turn RL episodes (SWE-bench, _Nous Research Hermes Agent_),
     sandboxes sit **97% idle (`20.15s` out of `22.43s`)** waiting on GPU
     `call_llm` token generation.
   - **Agent Substrate** decouples stateful **`Actors`** from **`WorkerPool`**
     compute—suspending memory/filesystem snapshots to Local SSD + GCS in
     **`460ms` (P90)** and resuming/forking branches in **`470ms` (P90)**
     (`1.35ms` RAM restore $\rightarrow$ **`99.3x` faster** than stateless
     rebuild, **`10.0x Compute Density`** across 200,000 agents).

### Verbatim Speaker Notes (Slide 1 — 3 Minutes)

> _"Up to this point in the session, we’ve looked at how Reinforcement
> Learning—specifically Critic-free Group Relative Policy Optimization
> (GRPO)—trains models on GPUs and TPUs. Now let's look at the other half of the
> RL loop: **where do those thousands of LLM-generated code rollouts actually
> execute?**"_
>
> _"When an RL policy generates 3 or 8 candidate code attempts—what we call
> Rollouts—to maximize its reward, two things happen in practice. First, some
> rollouts write runaway `O(n^2)` loops that spike CPU. Second, as documented
> across recent frontier RL papers, models actively learn **Reward Hacking**:
> they try to cheat the grading harness by reading host `/proc` memory, calling
> out to the internet, or hitting the **Google Cloud Metadata Server at
> `169.254.169.254`** to steal IAM tokens."_
>
> _"Historically, platform teams faced a painful trade-off. If you isolated
> every rollout inside a `gVisor` or MicroVM pod, cold-starting that pod took
> **18.1 seconds**, and during multi-turn sessions the sandbox sat **97% idle**
> hogging RAM while waiting for the GPU to generate the next turn's tokens. So
> teams compromised and ran agents in shared containers."_
>
> _"On GKE, you don't have to choose between isolation and efficiency. With
> **GKE Agent Sandbox (`SandboxWarmPool`)**, we cut `gVisor` rollout claim time
> from **18.1 seconds down to 145 milliseconds—a 125x speedup**. And with our
> newly launched **GKE Agent Substrate (`v0.1.0`)**—already adopted by **Nous
> Research for the Hermes Agent**—GKE decouples the stateful **`Actor`** from
> the **`WorkerPool`**. The moment an agent waits on LLM inference, Agent
> Substrate snapshots its memory and filesystem to Local SSD and Cloud Storage
> in **460 milliseconds**, freeing 92% of host RAM for **10x compute density**,
> and forks parallel GRPO rollout branches from that snapshot in sub-500
> milliseconds."_

---

## Slide 2: Live 3-Act GKE Demo & Measured Telemetry

### Slide Title & Subtitle

- **Title:** **Live Demo: Multi-Agent RLVR & Agent Substrate (`v1.0`
  $\rightarrow$ `v2.0` $\rightarrow$ `v3.0`) on GKE**
- **Subtitle:** _Head-to-Head ADK OpenTelemetry Waterfall: Stateless Agent
  Sandbox (`v2.0`) vs. Stateful Agent Substrate (`v3.0`)_

### On-Slide Visuals & Comparison Table

- **Left Visual:** `demo_v3_substrate_traces_waterfall.png` (`22.43s` total
  turn; `135.73ms` & `240.22ms` `🔧` sandbox bars vs `20.15s` blue `call_llm`
  bars).
- **Right Visual:** `demo_v2_stateless_traces_waterfall.png` (`57.36s` total
  turn; `510.99ms` & `796.96ms` `🔧` stateless sandbox bars).

| Live GKE Cluster Metric (`ai-agent-cluster`)           | `v2.0` (`GKE Agent Sandbox` — Stateless) | `v3.0` (`GKE Agent Substrate` — Stateful Snapshot) |   Measured Gain (`v3.0` vs `v2.0`)   |
| :----------------------------------------------------- | :--------------------------------------: | :------------------------------------------------: | :----------------------------------: |
| **Rollout #1 (`169.254.169.254` Escape Attempt)**      |    Blocked (`R = -1.00`, `A = -1.06`)    |         Blocked (`R = -1.00`, `A = -1.06`)         |      **100% Zero-Trust Parity**      |
| **Rollout #3 Sandbox Execution (`🔧` Optimal $O(n)$)** |  `796.96 ms` _(Rebuilds Turn-1 ledger)_  |   **`135.73 ms`** _(Restores `snap-gcs-c3-001`)_   | **`5.87x Faster`** Sandbox Execution |
| **Turn-1 State Setup Inside `gVisor` (`4.4.0`)**       |  `133.97 ms` _(Re-hashed from scratch)_  |   **`1.35 ms`** _(`25.9 KB` binary RAM restore)_   | **`99.3x Faster`** State Restoration |
| **End-to-End 3-Stage Multi-Agent Turn**                |             `57.36 seconds`              |                **`22.43 seconds`**                 |  **`2.56x Faster`** End-to-End Turn  |
| **Worker Hold Time During `20.15s` `call_llm` Bars**   |      `100% Pinned` (`1.0x` Density)      |    **`460 ms Suspend`** (`92.3%` RAM/CPU freed)    |     **`10.0x Compute Density`**      |

### Verbatim Speaker Notes (Slide 2 — 4 Minutes)

> _"Let’s look at the live telemetry we captured on our GKE cluster
> (`ai-agent-cluster`) running Google ADK `2.9.2` with `gemini-2.5-flash` across
> three versions of our demo: `v1.0` (Single Agent), `v2.0` (Stateless
> Multi-Agent GRPO), and `v3.0` (Stateful Multi-Agent GRPO with Agent
> Substrate)."_
>
> _"In both `v2.0` and `v3.0`, we ask the orchestrator to audit a 2,000-record
> payment ledger and evaluate **3 candidate Rollouts** inside `gVisor`
> (`Linux 4.4.0`):_
>
> - _Rollout #1 is a **Reward-Hacking Escape Attempt** that tries to steal a GCP
>   IAM token from `169.254.169.254`. Our Zero-Trust `NetworkPolicy` blocks it
>   in `307ms` and assigns `Reward = -1.00` (`Advantage = -1.06`), training the
>   policy never to attempt sandbox escape._
> - _Rollout #2 is a **Sloppy `O(n^2)` CPU-Spiking Loop**, contained by `gVisor`
>   cgroups (`Reward = +0.10`)._
> - _Rollout #3 is the **Verified Safe `O(n)` Hash-Set Solution**, completing in
>   `0.027ms` inside `gVisor` and earning `Reward = +1.00`
>   (`Advantage = +0.98`)."_
>
> _"Now compare the two ADK OpenTelemetry `Traces` waterfalls on screen. On the
> right (`v2.0` without Agent Substrate), every rollout starts in a blank
> container and must rebuild the Turn-1 ledger from scratch—taking
> **`796.96 ms`** per tool call and **`57.36 seconds`** total. On the left
> (`v3.0` with **Agent Substrate**), Turn-1 state is snapshotted once
> (`snap-gcs-c3-001`, `25.9 KB`). Both rollout branches restore that snapshot
> into RAM in **`1.35 milliseconds`**—**99x faster**—shrinking the `🔧` sandbox
> bar to **`135.73 ms`** (**5.87x faster**) and cutting the total turn time down
> to **`22.43 seconds`**!"_
>
> _"Finally, look at the visual ratio in that `v3.0` waterfall: **20.15 seconds
> (`97%`)** is spent in the long blue `call_llm` bars waiting on Gemini GPU
> inference, while only **0.68 seconds (`3%`)** is spent in the `🔧` sandbox
> bars. That visual ratio is why **Agent Substrate** is a game-changer: by
> suspending the `Actor` during the blue `call_llm` bars, you pack **10x more
> agents** onto the exact same GKE footprint."_
