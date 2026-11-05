# Multi-region foundation for inference-ref-arch

This directory is the single, engine-agnostic foundation for multi-region
inference-ref-arch deployments. TensorRT-LLM, NVIDIA Dynamo, and llm-d use it in
the same way to:

1. Provision one GKE inference-ref-arch platform per region, one region after
   the other or all at the same time (`provision.sh`, `teardown.sh`).
2. Put every region on its own VPC network (`island`) or on one shared VPC
   network (`shared-vpc`), with deterministic, non-overlapping CIDR ranges.
3. Put any regional frontend Service behind one cross-region internal
   Application Load Balancer with a VIP in each region (`global_lb.sh`).
4. Stage models and mirror container images into every region (`helpers.sh`).

The guides and runbooks of each engine link here for the setup and teardown
steps; this README is the reference for the scripts.

## Contents

| Path                 | Purpose                                                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `provision.sh`       | Provisions regional platforms, sequentially or with `--parallel`; creates the shared network in `shared-vpc` mode.        |
| `teardown.sh`        | Tears the regional platforms down; destroys the load balancer and the shared network when it removes the last region.     |
| `global_lb.sh`       | Applies, inspects, or destroys the cross-region internal Application Load Balancer.                                       |
| `helpers.sh`         | Library sourced by the scripts and by interactive sessions (`use_region`, `expose_service_neg`, model and image helpers). |
| `bootstrap_tools.sh` | Installs pinned, checksum-verified `terraform` and `kustomize`, and `jq`, `sponge`, and `envsubst`.                       |
| `shared_network/`    | Terraservice: the shared VPC network, its `GLOBAL_MANAGED_PROXY` subnets, and firewall rules (`shared-vpc` mode).         |
| `global_lb/`         | Terraservice: the cross-region internal Application Load Balancer.                                                        |

## Prerequisites

- The permissions and tools in
  [the inference-ref-arch Terraform README](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).
  Run `bootstrap_tools.sh` to install `terraform`, `kustomize`, `jq`, `sponge`,
  and `envsubst` into `${HOME}/.local/bin`. The scripts also need `gcloud`,
  `git`, and `kubectl`.
- A clone of this repository. `--parallel` uses Git worktrees of it.

## Provision and tear down

```shell
export PROJECT_ID="<project_id>"
cd platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region

# Print the plan of every region without calling Google Cloud.
./provision.sh --dry-run

# Three regions, each on its own VPC network (defaults).
./provision.sh "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"

# Same regions, provisioned at the same time on one shared VPC network.
NETWORK_MODE="shared-vpc" ./provision.sh --parallel \
  "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"

# Tear down with the same targets and settings.
NETWORK_MODE="shared-vpc" ./teardown.sh --parallel \
  "americas:us-central1" "europe:europe-west2" "apac:asia-southeast1"
```

Each target is `<platform_name>:<region>[:<cidr_index>]`:

- `platform_name` (1-9 characters) names the platform's resources: the cluster
  is `<resource_name_prefix>-<platform_name>`, for example `inf-americas`.
- `cidr_index` (0-11) selects the platform's network ranges (see
  [Network modes](#network-modes)). It defaults to the position of the target in
  the list. Keep it stable for the life of a platform: pass it explicitly when
  you provision, re-run, or tear down a subset of the platforms. The scripts
  fail if an existing platform's subnet doesn't match its CIDR index, because
  new ranges would replace the subnet and the cluster.

Without targets, the scripts use `americas:us-central1`, `europe:europe-west2`,
and `apac:asia-southeast1`.

For each region, `provision.sh`:

1. Runs `terraform/deploy-ap.sh` (`CLUSTER_MODE=autopilot`) or
   `terraform/deploy-standard.sh` (`CLUSTER_MODE=standard`), with up to
   `MR_CORE_PLATFORM_ATTEMPTS` attempts, because transient errors are common
   right after a cluster is created.
2. Applies `terraform/online_gpu`.
3. Optionally stores `HF_TOKEN` in the platform's Secret Manager secrets,
   enables GKE Pod snapshots, and mirrors `MIRROR_IMAGES` into the platform's
   Artifact Registry repository.

`teardown.sh` deletes the Pod snapshot resources, removes the standalone NEGs of
the regional frontends (GKE doesn't delete them with the cluster), empties the
model and Pod snapshot buckets, destroys `terraform/online_gpu`, and runs
`terraform/teardown-ap.sh` or `terraform/teardown-standard.sh`. Re-running it is
safe: it skips the platforms whose state bucket no longer exists.

### Sequential and parallel modes

By default, the scripts work on one region after the other, from this checkout.
With `--parallel`, they work on every region at the same time, each from its own
Git worktree in `${MR_WORK_DIR}/worktrees/<platform_name>`, so that the regions
don't share the `.terraform/` directories, the generated `backend.tf` files, or
the local state of the core scripts. Each region logs to
`${MR_WORK_DIR}/logs/<run>/<platform_name>.log`, and the script fails if any
region fails, after the others finish.

A worktree is reset to the `HEAD` commit of this checkout on every run, plus the
uncommitted changes to tracked files (`git diff HEAD`). Stage new files
(`git add`) to include them. Untracked files aren't copied. `teardown.sh`
removes the worktrees of the platforms that it tore down.

### What the scripts don't change

- Tracked `*.auto.tfvars` files: every per-region value is a `TF_VAR_*`
  environment variable, and `TF_VAR_terraform_write_tfvars=false` stops the core
  platform from writing them back. Terraform gives `*.auto.tfvars` files
  precedence over `TF_VAR_*` variables, so the scripts fail if a shared
  `*.auto.tfvars` file sets one of the variables that they export.
- `~/.kube/config`: each platform has its own kubeconfig file,
  `platforms/gke/base/kubernetes/kubeconfig/<project_id>-<cluster_name>`.
- Terraform state and tracked files: the scripts don't delete state files or
  `.terraform/` directories; `teardown.sh` removes a worktree only after its
  platform is torn down. Sequential runs restore
  `core/initialize/backend.tf.bucket`, which the core scripts edit, unless it
  had local changes before the run.

## Use a region from an interactive shell

```shell
source platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
use_region "europe" "europe-west2"
kubectl get nodes
```

`use_region <platform_name> <region> [<cidr_index>]` exports `KUBECONFIG` and
the `TF_VAR_*` variables of a platform, so that `kubectl`, the
`test/scripts/.../deployment_apply.sh` scripts, and Terraform target it. With a
CIDR index, it also exports the network ranges, which Terraform needs to plan
the core networking terraservice.

`helpers.sh` also provides:

| Function                                                                    | Purpose                                                                                                    |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `stage_hf_model <hf_model_id>`                                              | Downloads a Hugging Face model into the current platform's model bucket, with the `download_*.sh` scripts. |
| `replicate_hf_model <src_platform> <dst_platform> <hf_model_id>`            | Copies a staged model between two platforms' model buckets, server side.                                   |
| `mirror_image_to_ar <region> <platform_name> <src_image> <dst_subpath:tag>` | Mirrors an image into a platform's Artifact Registry repository with Cloud Build and a pinned `crane`.     |
| `expose_service_neg <platform_name> <namespace> <service> <port> <backend>` | Exposes a regional frontend Service as a load balancer backend (see below).                                |
| `mr_set_cidrs_for_index <cidr_index>`                                       | Exports the `MR_*_CIDR` ranges of a CIDR index (see [Network modes](#network-modes)).                      |

## Settings

| Variable                      | Default                                                      | Description                                                                                                        |
| ----------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `PROJECT_ID`                  | (required)                                                   | Project of every platform.                                                                                         |
| `TF_VAR_resource_name_prefix` | `inf`                                                        | Prefix of every resource name (1-3 characters).                                                                    |
| `NETWORK_MODE`                | `island`                                                     | `island` or `shared-vpc`. See [Network modes](#network-modes).                                                     |
| `CLUSTER_MODE`                | `autopilot`                                                  | `autopilot` or `standard`. See [Cluster modes](#cluster-modes).                                                    |
| `MR_ENVIRONMENT_NAME`         | `mr`                                                         | Name (1-6 characters) of the resources that the regions share in `shared-vpc` mode.                                |
| `MR_WORK_DIR`                 | `${HOME}/.acp-multi-region/<project>-<prefix>-<environment>` | Local directory for worktrees, logs, and the multi-region terraservices.                                           |
| `MR_CORE_PLATFORM_ATTEMPTS`   | `3`                                                          | Attempts of the core platform deployment of each region.                                                           |
| `HF_TOKEN`                    | (unset)                                                      | Hugging Face token to add to each platform's `huggingface-hub-access-token-{read,write}` secrets.                  |
| `ENABLE_POD_SNAPSHOTS`        | `false`                                                      | Create the Pod snapshot bucket and IAM grants (`online_gpu`) and enable GKE Pod snapshots on each cluster.         |
| `ACTIVE_MIGRATION_ENABLED`    | `false`                                                      | `activeMigration` of the custom compute classes.                                                                   |
| `MIRROR_IMAGES`               | (unset)                                                      | Space-separated `<src_image>=<dst_subpath:tag>` entries to mirror into each region's Artifact Registry repository. |

Other `TF_VAR_*` variables apply to every region, for example
`TF_VAR_ira_online_gpu_kubernetes_namespace_name` to use the same namespace in
every cluster.

## Network modes

| Mode         | Network                                                          | Cross-region connectivity                                                                             | Global load balancer |
| ------------ | ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | -------------------- |
| `island`     | One VPC network per platform, created by `core/networking`.      | None.                                                                                                 | No                   |
| `shared-vpc` | One VPC network, `<prefix>-<environment>-vpc`, for every region. | Nodes and Pods of every region reach each other; load balancer proxies reach every region's backends. | Yes                  |

In `shared-vpc` mode, `provision.sh` applies the `shared_network` terraservice
before the regions: the network, one `GLOBAL_MANAGED_PROXY` proxy-only subnet
per region, and firewall rules for the load balancer proxies, Google Cloud
health checks, and the node and Pod ranges of every region. `core/networking`
then creates each region's node subnet, `REGIONAL_MANAGED_PROXY` subnet, Cloud
Router, and Cloud NAT in that network. A VPC network has a single active
proxy-only subnet per purpose in each region, so `shared-vpc` mode supports one
platform per region.

The `shared_network` state is also the registry of the environment's platforms:
`provision.sh` adds its targets to the registered platforms, `teardown.sh`
removes them and destroys the network with the last one, and `global_lb.sh`
creates one VIP per registered platform. The multi-region terraservices keep
their state in `gs://<project_id>-<prefix>-<environment>-terraform`, which the
scripts create and never delete. They run from copies in
`${MR_WORK_DIR}/terraform`, because `core/initialize` generates a `backend.tf`
that points at a regional platform's state bucket in every directory with a
`versions.tf` file under `inference-ref-arch/terraform/`.

Every platform gets non-overlapping ranges from its CIDR index `i`, outside
Google Cloud's `10.128.0.0/9` auto mode range, in both modes:

| Range                                      | CIDR                   | Index 0          | Index 1          | Index 2          |
| ------------------------------------------ | ---------------------- | ---------------- | ---------------- | ---------------- |
| Nodes                                      | `10.(16+4i).0.0/20`    | `10.16.0.0/20`   | `10.20.0.0/20`   | `10.24.0.0/20`   |
| `REGIONAL_MANAGED_PROXY` subnet            | `10.(16+4i).16.0/23`   | `10.16.16.0/23`  | `10.20.16.0/23`  | `10.24.16.0/23`  |
| `GLOBAL_MANAGED_PROXY` subnet (shared-vpc) | `10.(16+4i).18.0/23`   | `10.16.18.0/23`  | `10.20.18.0/23`  | `10.24.18.0/23`  |
| Control plane                              | `172.16.0.(16+16i)/28` | `172.16.0.16/28` | `172.16.0.32/28` | `172.16.0.48/28` |
| Pods                                       | `10.(64+i).0.0/17`     | `10.64.0.0/17`   | `10.65.0.0/17`   | `10.66.0.0/17`   |
| Services                                   | `10.96.(4i).0/22`      | `10.96.0.0/22`   | `10.96.4.0/22`   | `10.96.8.0/22`   |

Use the same `NETWORK_MODE`, `MR_ENVIRONMENT_NAME`, and
`TF_VAR_resource_name_prefix` values for `provision.sh`, `teardown.sh`,
`global_lb.sh`, and `use_region`.

## Cluster modes

`CLUSTER_MODE=autopilot` (default) deploys GKE Autopilot clusters with
`terraform/deploy-ap.sh`, as the TensorRT-LLM and NVIDIA Dynamo guides do.
`CLUSTER_MODE=standard` deploys GKE Standard clusters with
`terraform/deploy-standard.sh`, as the multi-region llm-d example does. Both
register each cluster to the project's fleet.

## Put regional frontends behind the global load balancer

The cross-region internal Application Load Balancer needs `shared-vpc` mode. It
has a private HTTP VIP (TCP port `80`) in each region, which clients in the VPC
network call (for example, `http://<vip>/v1/chat/completions`). Each backend is
a global backend service whose backends are the GKE standalone NEGs of a
regional frontend Service, for example `dynamo-frontend`, `trtllm`, or the llm-d
router proxy. A service load balancing policy keeps traffic in the closest
region until that region reaches its capacity, then spills over to the next
region; a region whose endpoints fail their health checks gets no traffic.

1. Once each regional frontend's Pods are scheduled on their nodes (on GKE
   Autopilot, standalone zonal NEGs exist only in zones that currently have
   nodes), expose the frontend Service's port as a standalone NEG named
   `<resource_name_prefix>-<platform_name>-<backend>`:

   ```shell
   source platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
   for platform_name in americas europe apac; do
     expose_service_neg "${platform_name}" "<namespace>" "trtllm" "8000" "trtllm"
   done
   ```

   To manage the NEG with your manifests instead, set the annotation
   `cloud.google.com/neg: '{"exposed_ports":{"8000":{"name":"<neg_name>"}}}'` on
   the Service; `mr_neg_name <platform_name> <backend>` prints the name.

2. Describe the backends in a JSON file. Each backend needs a health check and
   the capacity of one endpoint (one Pod behind the NEG) in in-progress requests
   (`max_in_flight_requests_per_endpoint`, for the default balancing mode
   `IN_FLIGHT`) or in requests per second (`max_rate_per_endpoint`, for
   `--balancing-mode RATE`). `locality_lb_policy` (default `LEAST_REQUEST`)
   selects the endpoint within a region.

   ```json
   {
     "trtllm": {
       "health_check_path": "/health",
       "health_check_port": 8000,
       "max_in_flight_requests_per_endpoint": 16
     }
   }
   ```

3. Apply the load balancer and print its VIPs:

   ```shell
   ./global_lb.sh apply --backends backends.json --active trtllm
   ./global_lb.sh vips
   ```

`global_lb.sh apply` discovers the NEGs of every backend in every registered
region, and fails if the active backend has no NEG in one of them. The other
options are:

- `--algorithm`: `WATERFALL_BY_REGION` (default), `SPRAY_TO_REGION` (like
  `WATERFALL_BY_REGION`, but each proxy spreads requests across the zones of the
  chosen region; it doesn't spread traffic across regions), or
  `WATERFALL_BY_ZONE`.
- `--preferred-region <region>`: marks the region's backends `PREFERRED`, so
  that the load balancer fills that region before any other.
- `--timeout-sec` (default `3600`): backend service timeout, long enough for
  streaming generations.
- `--dry-run`: prints the Terraform variables without applying them (it only
  reads the shared network state and lists the NEGs).

To switch the traffic to another backend, re-run `apply` with another
`--active`; the VIPs don't change. Before you delete a backend's Services,
re-run `apply` without that backend, so that GKE can delete its NEGs.
`global_lb.sh destroy` deletes the load balancer, and `teardown.sh` runs it
before it removes the last platforms. The firewall rules of the shared network
allow the load balancer to reach ports `8000` (vLLM, TensorRT-LLM, and NVIDIA
Dynamo frontends), `8081` (llm-d router proxy), and `19001` (llm-d router
readiness); add ports to `backend_ports` in `shared_network/variables.tf` for
other frontends.

To take a region out of service, for example to show a failover, scale its
frontend to zero replicas. Its NEGs then have no endpoints, and the load
balancer sends the requests of that region's clients to the next closest region
that has capacity; scale the frontend up again to restore it:

```shell
source platforms/gke/base/use-cases/inference-ref-arch/terraform/multi-region/helpers.sh
use_region "europe" "europe-west2"
kubectl scale deployment "<frontend_deployment>" --namespace "<namespace>" --replicas=0
```

## Limitations

- `peered` network mode (island VPC networks connected with VPC Network Peering)
  isn't implemented. The CIDR plan leaves room for it.
- The load balancer has no per-region drain setting (`capacity_scaler`); scale a
  region's frontend to zero to take the region out of service.
- `shared-vpc` mode supports one platform per region.
- The scripts don't change the `NETWORK_MODE` or `CLUSTER_MODE` of an existing
  platform: they refuse to run when an existing platform's subnet is in another
  network, and a new cluster mode fails to create a cluster that already exists.
  Tear the platform down and provision it again instead.
