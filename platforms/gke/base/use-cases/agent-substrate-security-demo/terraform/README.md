# Secure Runtimes for AI Agents on GKE: Agent Substrate Reference Implementation

## Before you begin

This guide is the reference implementation of the
[Secure Runtimes for AI Agents on GKE: Agent Substrate Security & Detonation Reference Architecture](/docs/platforms/gke/base/use-cases/agent-substrate-security-demo/README.md).
It integrates with the
[GKE Base Platform reference implementation](/platforms/gke/base/core/README.md)
(`Option B`) or can be deployed standalone on a dedicated private-node GKE 1.37+
cluster (`Option A`).

### Requirements

- [Google Cloud Command Line Interface (`gcloud` CLI)](https://cloud.google.com/cli)
  with `gke-gcloud-auth-plugin`
  (`gcloud components install gke-gcloud-auth-plugin`)
- `kubectl`, `git`, `jq`, `curl`, `envsubst`, `python3`, `openssl`
- `go` (`>= 1.23`; automatically downloads the Go toolchain declared by upstream
  `github.com/agent-substrate/substrate` at pinned commit `b34fbee7` / `v1.0.0`)
- `terraform` (`>= 1.8.0`; required for `Option B` Terraservice deployments)
- A Google Cloud project with billing enabled and permissions to enable project
  APIs (`container`, `compute`, `iam`, `iamcredentials`, `storage`,
  `artifactregistry`, `cloudbuild`, `aiplatform`, `monitoring`, `logging`,
  `cloudtrace`) and manage GKE clusters, VPC/Cloud NAT, Cloud Storage buckets,
  Artifact Registry repositories, Cloud Build builds, Service Accounts, and IAM
  bindings.

### Choosing Between Option A and Option B

| Dimension                           | Option A: Standalone Zonal Cluster (`scripts/`)                                                                        | Option B: Regional GKE Base Platform (`terraform/`)                                                                                                                                                                                                                                                                 |
| :---------------------------------- | :--------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **VM Footprint & Quota**            | **2 zonal VMs** (`default-pool` in 1 zone; minimal quota for evaluation, development, or capacity-constrained regions) | **6–7 regional VMs** (`3` `system` + `2` `agent-substrate-*` + `1–2` GKE NAP nodes across zones)                                                                                                                                                                                                                    |
| **VM-Level Blast-Radius Isolation** | Co-locates `ate-system` and `ateworker-gvisor` on the 2 untainted nodes (isolated via `gVisor` + `NetworkPolicy`)      | **Dedicated VM separation**: `ate.dev/sandboxClass=gvisor:NoSchedule` + `nodeAffinity` pin `ateworker-gvisor` (and per-node `atelet`) to `agent-substrate-*` VMs while `ate-controller`, `atenet-router`, `k8s-credential-provider`, `postgres`, `gateway`, and `partner-api` run on separate untainted GKE NAP VMs |
| **Provisioning Time**               | **~6–8 min** (`gcloud` + `stage.sh`)                                                                                   | **~18–22 min** (Core Terraservices + use-case Terraservice + `stage.sh`)                                                                                                                                                                                                                                            |
| **Capacity / Stockout Fallback**    | `export CLUSTER_LOCATION=<zone> MACHINE_TYPE=e2-standard-4` (with fast 15s MIG stockout detection)                     | `TF_VAR_cluster_system_node_pool_machine_type="e2-standard-4"`, `TF_VAR_agent_substrate_node_machine_type="e2-standard-4"`, and optional `TF_VAR_agent_substrate_node_locations`                                                                                                                                    |

## Option A: Standalone Private-Node GKE 1.37+ Cluster (~6–8 min) + 4-Act Verification

1. Export your Google Cloud project ID (plus any optional cluster, zone, or
   machine-type overrides so all subsequent lifecycle scripts share the same
   settings) and create a GKE `1.37+` cluster with private nodes, Cloud NAT,
   control-plane DNS endpoint, dedicated least-privilege node service account,
   Workload Identity, Dataplane V2, and Managed OpenTelemetry (defaults to
   `n4-standard-4` with `hyperdisk-balanced`; set `MACHINE_TYPE=c4-standard-4`
   for C4 6th-Gen Intel Xeon when regional quota and capacity are available):

   ```shell
   export PROJECT_ID="<PROJECT_ID>"
   # Optional overrides (keep exported for stage.sh and teardown.sh):
   # export CLUSTER_NAME="agent-substrate-live"
   # export CLUSTER_LOCATION="europe-west4-b"
   # export MACHINE_TYPE="e2-standard-4"

   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/create-cluster.sh

   # Optional: preserve your current kubectl context during cluster creation:
   # UPDATE_KUBECONFIG=false \
   #   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/create-cluster.sh
   ```

1. Stage the Agent Substrate `v1.0.0` control plane, build and cache the
   digest-pinned (`@sha256:`) Google ADK (`google-adk`) container image in
   Artifact Registry via Cloud Build, deploy the split-plane `gateway` (with
   native `PodCertificate` SPIFFE mTLS to `atenet-router:443`) and cluster-local
   `partner-api`, and stage the 4 actors in atespace `security-demo`
   (`py-detonation-agent`, `gemini-agent`, `gemini-agent-forensic`,
   `egress-agent`):

   ```shell
   # Optional: override the Vertex AI Gemini model (defaults to gemini-3.8-flash):
   # export GEMINI_MODEL="gemini-2.5-flash"

   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh

   # Optional: add the ref-keyed kubectl-ate binary symlink to your shell PATH
   export PATH="$PWD/platforms/gke/base/use-cases/agent-substrate-security-demo/bin:$PATH"
   ```

1. Run the 4-Act Red Team vs. Blue Team live CLI verification (approximately 60
   seconds; exits non-zero if any assertion fails):

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/run_4_act_demo.sh
   ```

1. Launch the interactive 4-Act Mission Control web console (binds to
   `127.0.0.1:18090` by default; requires `UI_AUTH_TOKEN` if `BIND_HOST` is
   overridden to a non-loopback address):

   ```shell
   python3 ./platforms/gke/base/use-cases/agent-substrate-security-demo/ui/mission_control.py
   ```

   Open `http://127.0.0.1:18090` in your browser to run all 4 Acts and inspect
   live Google Managed Prometheus telemetry (`:9090`). When running on a remote
   workstation, forward the loopback port over SSH
   (`ssh -L 18090:127.0.0.1:18090 <host>`), or set `ALLOWED_HOSTS=<proxy-host>`
   behind an authenticated reverse proxy.

1. Tear down all Option A resources (run with the same `PROJECT_ID`,
   `CLUSTER_NAME`, and `CLUSTER_LOCATION` exports used in Step 1 to remove Cloud
   Monitoring dashboards, the GKE cluster, Cloud NAT/Router, subnet/VPC when
   unused, snapshot Cloud Storage bucket, Artifact Registry repository, service
   accounts, and project IAM bindings):

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/teardown.sh
   ```

## Option B: Deploy with GKE Base Platform Terraservices

> [!NOTE]
>
> Agent Substrate `v1.0.0` requires Kubernetes `>= 1.37` on both the GKE control
> plane and worker nodes so `certificates.k8s.io` `PodCertificateRequest` and
> `ClusterTrustBundle` are available. The `agent_substrate_security_demo`
> Terraservice enforces a Terraform precondition checking the cluster version.

1. Export the platform default project ID (and optionally override region,
   platform name, Vertex AI model, node machine types, or worker zones when
   `N4`/`C4` capacity is constrained):

   ```shell
   export TF_VAR_platform_default_project_id="<PROJECT_ID>"
   # Optional: export TF_VAR_platform_default_region="us-central1"
   # Optional: export TF_VAR_platform_name="dev"
   # Optional: export TF_VAR_agent_substrate_node_machine_type="c4-standard-4"
   # Optional: export GEMINI_MODEL="gemini-2.5-flash"
   # Optional fallback when regional N4/C4 capacity is exhausted:
   # export TF_VAR_cluster_system_node_pool_machine_type="e2-standard-4"
   # export TF_VAR_agent_substrate_node_machine_type="e2-standard-4"
   # export TF_VAR_agent_substrate_node_locations='["europe-west4-a","europe-west4-b"]'
   ```

1. Run the automated deployment script (provisions the GKE Base Platform,
   creates the tainted `agent-substrate-*` node pool, private snapshot bucket,
   Artifact Registry repository, and IAM bindings via Terraform, then invokes
   `scripts/stage.sh` with `PROVISION_GCP_INFRA=false`):

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/deploy-standard.sh
   ```

1. Run the 4-Act CLI verification and launch the Mission Control web console:

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/run_4_act_demo.sh
   python3 ./platforms/gke/base/use-cases/agent-substrate-security-demo/ui/mission_control.py
   ```

1. Tear down all Option B resources (ensure the same `TF_VAR_*` environment
   variables exported in Step 1 are set in your shell so custom Cloud Monitoring
   dashboards, use-case Terraservices, and Core Platform Terraservices are all
   destroyed):

   ```shell
   ./platforms/gke/base/use-cases/agent-substrate-security-demo/terraform/teardown-standard.sh
   ```

## Customizing Python Agents (`app/`) & Digest-Pinned Container Builds

All Gateway, verifier, and Actor Python modules live under
`platforms/gke/base/use-cases/agent-substrate-security-demo/app/`:

- `app/gateway.py`: Split-plane FastAPI Gateway (`:8080` actor-facing GKE
  Workload Identity proxy to Vertex AI (`aiplatform.googleapis.com`) and
  Prometheus `/metrics`; `127.0.0.1:8081` token-authenticated operator plane
  calling `https://atenet-router.ate-system.svc:443` with its `PodCertificate`
  SPIFFE client bundle).
- `app/gemini_agent.py`: Stateful **Google Agent Development Kit
  (`google-adk`)** actor (`gemini-agent-v1`) running Gemini (`GEMINI_MODEL`,
  defaulting to `gemini-3.8-flash`) with zero Google Cloud credentials in the
  `gVisor` sandbox and dual-layer ADK `InMemoryRunner` session +
  `/data/policy.json` persistence.
- `app/egress_agent.py`: Zero-secret HTTP(S) fetch actor (`egress-agent-v1`)
  with strict URL scheme validation.
- `app/partner_api.py`: Cluster-local (`ns/agent-secrets`) non-reflecting
  credential verifier for Act 3 that validates wire-injected tokens without
  echoing secret bytes back to the caller.
- `app/Dockerfile`: Digest-pinned container build on top of
  `python-runtime-sandbox:v0.5.6`.

### 1. Automatic Content-Addressed Cloud Build (Default)

`stage.sh` hashes
`app/{Dockerfile,gateway.py,gemini_agent.py,egress_agent.py,partner_api.py}`,
builds a new image via Cloud Build only when the content SHA changes, and
resolves the immutable `@sha256:` digest required by Agent Substrate snapshots:

```shell
# Roll out app/gateway.py or app/partner_api.py changes:
./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh

# Recreate ActorTemplates & Golden Snapshots when actor code changes:
REFRESH_ACTORS=true ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh
```

### 2. Custom Pre-Built Container Image (`APP_IMAGE`)

Pass a pre-built Artifact Registry image explicitly via `APP_IMAGE`:

```shell
export REGION="${REGION:-us-central1}"
export AR_REPO="${AR_REPO:-agent-substrate}" # For Option B, use the Terraform agent_substrate_ar_repository_name output

gcloud builds submit ./platforms/gke/base/use-cases/agent-substrate-security-demo/app \
  --project "${PROJECT_ID}" \
  --tag "${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/demo-app:v1.0.0"

APP_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/demo-app:v1.0.0" \
  REFRESH_ACTORS=true \
  ./platforms/gke/base/use-cases/agent-substrate-security-demo/scripts/stage.sh
```
