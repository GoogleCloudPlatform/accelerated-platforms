# Secure Runtimes for AI Agents on GKE: Agent Substrate Reference Implementation

## Before you begin

This guide is a reference implementation of the
[Secure Runtimes for AI Agents on GKE: Agent Substrate Security & Detonation Reference Architecture](/docs/platforms/gke/base/use-cases/agent-substrate-security-demo/README.md).
It builds upon the
[GKE Base Platform reference implementation](/platforms/gke/base/core/README.md)
(or can be deployed standalone in ~4 minutes with `scripts/create-cluster.sh`).

### Requirements

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
- `kubectl`
- `go` (`>= 1.27`, used only once by `stage.sh` to run `ate-setup` and build
  `kubectl-ate` from upstream `github.com/agent-substrate/substrate@v1.0.0`)
- `jq`, `curl`, `envsubst`, `python3`

## Option A: Rapid Standalone GKE 1.37 Cluster (~4 min) + Zero-Build 4-Act Demo

1. Create a GKE `1.37` cluster with Workload Identity, Dataplane V2, and Managed
   OpenTelemetry (defaults to `n4-standard-4` with `hyperdisk-balanced`; set
   `MACHINE_TYPE=c4-standard-4` to run on C4 6th-Gen Intel Xeon when capacity is
   available):

   ```shell
   # Default (n4-standard-4 + hyperdisk-balanced):
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/create-cluster.sh

   # Or on C4 (c4-standard-4 + hyperdisk-balanced):
   MACHINE_TYPE=c4-standard-4 ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/create-cluster.sh
   ```

1. Stage the Agent Substrate `v1.0.0` control plane and the 4 zero-build
   security demo actors in atespace `security-demo` (`py-detonation-agent`,
   `gemini-agent`, `gemini-agent-forensic`, `egress-agent`):

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh
   ```

1. Run the 4-Act Red Team vs. Blue Team live CLI verification:

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/run_4_act_demo.sh
   ```

1. Launch the interactive 4-Act Mission Control web console:

   ```shell
   python3 ./platforms/gke/base/use-cases/agent-substrate-security-demo/ui/mission_control.py
   ```

   Open `http://127.0.0.1:18090` in your browser to drive all 4 Acts live.

## Option B: Deploy with GKE Base Platform Terraservices

- Set the platform default project ID (and optionally set
  `TF_VAR_agent_substrate_node_machine_type="c4-standard-4"` to use C4 instead
  of the default `n4-standard-4`):

  ```shell
  export TF_VAR_platform_default_project_id="<PROJECT_ID>"
  # Optional: export TF_VAR_agent_substrate_node_machine_type="c4-standard-4"
  ```

- Run the automated deployment script:

  ```shell
  ./platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/deploy-standard.sh
  ```

- Tear down resources when finished:

  ```shell
  ./platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/teardown-standard.sh
  ```
