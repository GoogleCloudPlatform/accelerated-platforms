# Secure Runtimes for AI Agents on GKE: Agent Substrate Reference Implementation

## Before you begin

This guide is a reference implementation of the
[Secure Runtimes for AI Agents on GKE: Agent Substrate Security & Detonation Reference Architecture](/docs/platforms/gke/base/use-cases/agent-substrate-security-demo/README.md).
It builds upon the
[GKE Base Platform reference implementation](/platforms/gke/base/core/README.md)
(or can be deployed standalone in ~4 minutes with `scripts/create-cluster.sh`).

### Requirements

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
  with `gke-gcloud-auth-plugin`
  (`gcloud components install gke-gcloud-auth-plugin`)
- `kubectl`
- `go` (`>= 1.23`; automatically downloads the Go `1.27` toolchain when
  `stage.sh` runs `ate-setup` and builds `kubectl-ate` from upstream
  `github.com/agent-substrate/substrate@v1.0.0`)
- `jq`, `curl`, `envsubst`, `python3`

## Option A: Rapid Standalone GKE 1.37 Cluster (~4 min) + Zero-Build 4-Act Demo

1. Set your Google Cloud project ID and create a GKE `1.37` cluster with
   Workload Identity, Dataplane V2, and Managed OpenTelemetry (defaults to
   `n4-standard-4` with `hyperdisk-balanced`; set `MACHINE_TYPE=c4-standard-4`
   to run on C4 6th-Gen Intel Xeon when capacity is available):

   ```shell
   export PROJECT_ID="<PROJECT_ID>"

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

   # Optional: add the built kubectl-ate plugin to your interactive shell PATH
   export PATH="$PWD/platforms/gke/base/use-cases/agent-substrate-security-demo/bin:$PATH"
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

1. Tear down the standalone Option A cluster when finished:

   ```shell
   kubectl -n ate-system delete statefulset postgres --ignore-not-found
   kubectl -n ate-system delete pvc --all --ignore-not-found --timeout=60s
   gcloud container clusters delete "${CLUSTER_NAME:-agent-substrate-live}" \
     --location "${CLUSTER_LOCATION:-us-central1-b}" \
     --project "${PROJECT_ID}" \
     --quiet
   ```

## Option B: Deploy with GKE Base Platform Terraservices

1. Set the platform default project ID (and optionally override region,
   environment name, or node machine type):

   ```shell
   export TF_VAR_platform_default_project_id="<PROJECT_ID>"
   # Optional: export TF_VAR_platform_default_region="us-central1"
   # Optional: export TF_VAR_agent_substrate_node_machine_type="c4-standard-4"
   ```

1. Run the automated deployment script (provisions the GKE Base Platform,
   creates the `agent-substrate-*` worker pool and snapshot bucket, and
   automatically runs `scripts/stage.sh`):

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/deploy-standard.sh
   ```

1. Run the 4-Act CLI verification and launch the Mission Control web console:

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/run_4_act_demo.sh
   python3 ./platforms/gke/base/use-cases/agent-substrate-security-demo/ui/mission_control.py
   ```

1. Tear down resources when finished:

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/teardown-standard.sh
   ```

## Customizing Python Agents (`app/`) & Production Container Builds

All Gateway and Actor Python code lives as standalone modules under
`platforms/gke/base/use-cases/agent-substrate-security-demo/app/` (no Python is
embedded inside YAML templates):

- `app/gateway.py`: Split-plane FastAPI Gateway (`:8080` actor-facing Vertex AI
  Gemini proxy + Prometheus `/metrics`; `:8081` operator-facing `/chat/{actor}`
  & `/actors/{actor}/state`).
- `app/gemini_agent.py`: Stateful Gemini chat actor (`gemini-agent-v1`) with
  dual-layer RAM (`HISTORY`) + `/data` disk persistence.
- `app/egress_agent.py`: Zero-secret HTTP fetch actor (`egress-agent-v1`).
- `app/Dockerfile`: Production immutable container build
  (`COPY *.py /app-src/`).

### 1. Customer PoC Iteration (Zero Container Build)

Edit any `.py` file under `app/` directly with full IDE/linter support:

```shell
# Roll out app/gateway.py changes (updates ConfigMap/gateway-app + rolling restart):
./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh

# Recreate ActorTemplates when app/gemini_agent.py or app/egress_agent.py changes:
REFRESH_ACTORS=true ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh
```

### 2. Production Mode (Immutable `@sha256` Container Image)

Build and push an immutable container image from `app/Dockerfile` to Artifact
Registry; `stage.sh` automatically pins the `@sha256:` digest required by Agent
Substrate memory snapshots and deploys without `ConfigMap` code mounts:

```shell
gcloud builds submit ./platforms/gke/base/use-cases/agent-substrate-security-demo/app \
  --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-substrate/demo-app:v1.0.0"

APP_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/agent-substrate/demo-app:v1.0.0" \
  REFRESH_ACTORS=true \
  ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh
```
