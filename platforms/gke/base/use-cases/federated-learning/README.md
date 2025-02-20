# Deploy the Federated learning reference architecture on Google Cloud

This document shows how to deploy the
[Google Cloud Federated Learning reference architecture](/docs/use-cases/federated-learning/README.md).

To deploy this reference architecture, you need:

- A [Google Cloud project](https://cloud.google.com/docs/overview#projects) with
  billing enabled. We recommend deploying this reference architecture to a new,
  dedicated Google Cloud project.
- An account with either the [Project Owner role](#option-1-project-owner-role)
  (full access) or [Granular Access roles](#option-2-granular-access).
- The `serviceusage.googleapis.com` must be enabled on the project. For more
  information about enabling APIs, see
  [Enabling and disabling services](https://cloud.google.com/service-usage/docs/enable-disable)

### Service account roles and permissions

You can choose between Project Owner access (full access) or Granular Access for
more fine-tuned permissions.

#### Option 1: Project Owner role

The service account will have full administrative access to the project.

- `roles/owner`: Full administrative access to the project
  ([Project Owner role](https://cloud.google.com/iam/docs/understanding-roles#resource-manager-roles))

#### Option 2: Granular Access

The service account will be assigned the following roles to limit access to
required resources:

- `roles/artifactregistry.admin`: Grants full administrative access to Artifact
  Registry, allowing management of repositories and artifacts.
- `roles/browser`: Provides read-only access to browse resources in a project.
- `roles/cloudkms.admin`: Provides full administrative control over Cloud KMS
  (Key Management Service) resources.
- `roles/compute.networkAdmin`: Grants full control over Compute Engine network
  resources.
- `roles/container.clusterAdmin`: Provides full control over Google Kubernetes
  Engine (GKE) clusters, including creating and managing clusters.
- `roles/gkehub.editor`: Grants permission to manage GKE Hub features.
- `roles/iam.serviceAccountAdmin`: Grants full control over managing service
  accounts in the project.
- `roles/resourcemanager.projectIamAdmin`: Allows managing IAM policies and
  roles at the project level.
- `roles/servicenetworking.serviceAgent`: Allows managing service networking
  configurations.
- `roles/serviceusage.serviceUsageAdmin`: Grants permission to enable and manage
  services and APIs for a project.

## Understand the repository structure

The `platforms/gke/base/use-cases/federated-learning` use case has the following
directories and files:

- `terraform`: contains Terraform descriptors and configuration to deploy the
  reference architecture.
- `deploy.sh`: convenience script to deploy the reference architecture.
- `teardown.sh`: convenience script to destroy the reference architecture.
- `common.sh`: contains common shell variables and functions.
- `assets`: contains documentation static assets.
- `README.md`: this document.

## Architecture

The following diagram describes the architecture that you can create with this
reference architecture:

![alt_text](/platforms/gke/base/use-cases/federated-learning/assets/architecture.svg "Architecture overview")

As shown in the preceding diagram, the reference architecture helps you create
and configure the following infrastructure components:

- A [Virtual Private Cloud (VPC) network](https://cloud.google.com/vpc/docs/vpc)
  and subnets.

- A
  [private GKE cluster](https://cloud.google.com/kubernetes-engine/docs/concepts/private-cluster-concept)
  that helps you:

  - Isolate cluster nodes from the internet.
  - Limit exposure of your cluster nodes and control plane to the internet.
  - Use shielded GKE nodes.
  - Enable
    [Dataplane V2](https://cloud.google.com/kubernetes-engine/docs/concepts/dataplane-v2)
    for optimized Kubernetes networking.
  - [Encrypt cluster secrets](https://cloud.google.com/kubernetes-engine/docs/how-to/encrypting-secrets)
    at the application layer.

- Dedicated GKE
  [node pools](https://cloud.google.com/kubernetes-engine/docs/concepts/node-pools)
  to isolate workloads from each other in dedicated runtime environments.

- For each GKE node pool, the reference architecture creates a dedicated
  Kubernetes namespace. The Kubernetes namespace and its resources are treated
  as a tenant within the GKE cluster.

- For each GKE node, the reference architecture configures Kubernetes taints to
  ensure that only the tenant's workloads are schedulable onto the GKE nodes
  belonging to a particular tenant.

- A GKE node pool to host coordination and management workloads that aren't tied
  to specific tenants.

- [Firewall policies](https://cloud.google.com/firewall/docs/firewall-policies-overview)
  to limit ingress and egress traffic from GKE node pools, unless explicitly
  allowed.

- [Cloud NAT](https://cloud.google.com/nat/docs/overview) to allow egress
  traffic to the internet, only if allowed.

- [Cloud DNS](https://cloud.google.com/dns/docs/overview) records to enable
  [Private Google Access](https://cloud.google.com/vpc/docs/private-google-access)
  such that workloads within the cluster can access Google APIs without
  traversing the internet.

- [Cloud Identity and Access Management (IAM) service accounts](https://cloud.google.com/iam/docs/understanding-service-accounts):

  - A service account for GKE nodes in each GKE node pool with only the
    [minimum amount of permissions needed by GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster#use_least_privilege_sa).
  - A service account for workloads in each tenant. This service doesn't have
    any permission by default.

- Kubernetes service accounts that map to a Cloud IAM service accounts using
  [Workload Identity for GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity).

- An [Artifact Registry](https://cloud.google.com/artifact-registry/docs)
  repository to store container images for your workloads.

- [Config Sync](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/overview)
  to sync cluster configuration and policies from a Git repository or an
  OCI-compliant repository. Users and teams managing workloads should not have
  permissions to change cluster configuration or modify service mesh resources
  unless explicitly allowed by your policies.

- An Artifact Registry repository to store Config Sync configurations.

- [Policy Controller](https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/overview)
  to enforce policies on resources in the GKE cluster to help you isolate
  workloads.

- [Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/overview) to
  control and help secure network traffic.

Config Sync applies the following Policy controller and Cloud Service Mesh
controls to each Kubernetes namespace:

- By default, deny all ingress and egress traffic to and from pods. This rule
  acts as baseline 'deny all' rule.
- Allow egress traffic to required cluster resources such as the GKE control
  plane.
- Allow egress traffic only to known hosts.
- Allow ingress and egress traffic that originate from within the same
  namespace.
- Allow ingress and egress traffic between pods in the same namespace.
- Allow egress traffic to Google APIs only using Private Google Access.

## Deploy the reference architecture

To deploy the reference architecture, you do the following:

1.  Open [Cloud Shell](https://cloud.google.com/shell).

1.  Clone this repository and change the working directory:

    ```shell
    git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
    cd accelerated-platforms
    ```

1.  Initialize the required environment variables:

    ```shell
    ACP_REPO_DIR="$(pwd)"
    export ACP_REPO_DIR
    export ACP_PLATFORM_BASE_DIR="${ACP_REPO_DIR}/platforms/gke/base"
    export ACP_PLATFORM_CORE_DIR="${ACP_PLATFORM_BASE_DIR}/core"
    ```

1.  Optionally, you can make the required environment variables configuration
    persistent by updating your
    [Bash startup files](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html).
    For example, you can update your `.bashrc` file:

    ```shell
    {
      echo "export \"ACP_REPO_DIR=${ACP_REPO_DIR}\""
      echo "export \"ACP_PLATFORM_BASE_DIR=${ACP_PLATFORM_BASE_DIR}\""
      echo "export \"ACP_PLATFORM_CORE_DIR=${ACP_PLATFORM_CORE_DIR}\""
    } >>"${HOME}/.bashrc"
    ```

1.  Configure the ID of the Google Cloud project where you want to initialize
    the provisioning and configuration environment. This project will also
    contain the remote Terraform backend. Add the following content to
    `${ACP_PLATFORM_BASE_DIR}/_shared_config/terraform.auto.tfvars`:

    ```hcl
    terraform_project_id = "<CONFIG_PROJECT_ID>"
    ```

    Where:

    - `<CONFIG_PROJECT_ID>` is the Google Cloud project ID.

1.  Configure the ID of the Google Cloud project where you want to deploy the
    reference architecture by adding the following content to
    `${ACP_PLATFORM_BASE_DIR}/_shared_config/cluster.auto.tfvars`:

    ```hcl
    cluster_project_id = "<PROJECT_ID>"
    ```

    Where:

    - `<PROJECT_ID>` is the Google Cloud project ID. Can be different from
      `<CONFIG_PROJECT_ID>`.

1.  Optionally configure a unique identifier to append to the name of all the
    resources in the reference architecture to identify a particular instance of
    the reference architecture, and to allow for multiple instances of the
    reference architecture to be deployed in the same Google Cloud project. To
    optionally configure the unique prefix, add the following content to
    `${ACP_PLATFORM_BASE_DIR}/_shared_config/platform.auto.tfvars`:

    ```hcl
    resource_name_prefix = "<RESOURCE_NAME_PREFIX>"
    platform_name        = "<PLATFORM_NAME>"
    ```

    Where:

    - `<RESOURCE_NAME_PREFIX>` and `<PLATFORM_NAME>` are strings that compose
      the unique identifier to append to the name of all the resources in the
      reference architecture.

    When you set `resource_name_prefix` and `platform_name`, we recommend that
    you avoid long strings because the might make resource naming validation to
    fail because the resource name might be too long.

1.  Run the script to provision the reference architecture:

    ```sh
    "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"
    ```

It takes about 20 minutes to provision the reference architecture.

After deploying the reference architecture, the GKE cluster is ready to host
your federated learning workloads. For example, you can:

- [Deploy NVIDIA FLARE in the GKE cluster](/platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/README.md).

## Destroy the reference architecture

To destroy an instance of the reference architecture, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to destroy the reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/teardown.sh"
   ```

## Configure the Federated learning reference architecture

You can configure the reference architecture by modifying files in the following
directories:

- `${ACP_PLATFORM_BASE_DIR}/_shared_config`
- `${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/terraform/_shared_config`

### Configure isolated runtime environments

The reference architecture configures runtime environments that are isolated
from each other. Each runtime environment gets:

- A dedicated Kubernetes Namespace
- A dedicated GKE node pool

These isolated runtime environments are defined as _tenants_.

For more information about the design of these tenants, see
[Federated Learning reference architecture](/docs/use-cases/federated-learning/README.md).

By default, this reference architecture configures one tenant. To configure
additional tenants, or change their names, set the value of the
`federated_learning_tenant_names` Terraform variable in
`${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/terraform/_shared_config/uc_federated_learning.auto.tfvars`
according to how many tenants you need. For example, to create two isolated
tenants named `fl-1` and `fl-2`, you set the `federated_learning_tenant_names`
variable as follows:

```hcl
federated_learning_tenant_names = [
  "fl-1",
  "fl-2",
]
```

For more information about the `federated_learning_tenant_names`, see its
definition in
`${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/terraform/_shared_config/uc_federated_learning_variables.tf`

### Enable Confidential GKE Nodes

The reference architecture can optionally configure Confidential GKE Nodes using
Terraform. To enable Confidential GKE Nodes, you do the following:

1. Initialize the following Terraform variables in
   `${ACP_PLATFORM_BASE_DIR}/_shared_config/cluster.auto.tfvars`:

   1. Set `cluster_confidential_nodes_enabled` to `true`

   1. Set `cluster_system_node_pool_machine_type` to a machine type that
      supports Confidential GKE Nodes. For more information about the machine
      types that support Confidential GKE Nodes, see
      [Encrypt workload data in-use with Confidential GKE Nodes](https://cloud.google.com/kubernetes-engine/docs/how-to/confidential-gke-nodes#availability).

1. Initialize the following Terraform variables in
   `${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/terraform/_shared_config/uc_federated_learning.auto.tfvars`:

   1. Set `federated_learning_node_pool_machine_type` to a machine type that
      supports Confidential GKE Nodes.

### Allow desired network traffic

1. Configure Kubernetes network policies to allow traffic. You can see how
   current Kubernetes network policies are affecting traffic in your cluster
   [using Cloud Logging](https://cloud.google.com/kubernetes-engine/docs/how-to/network-policy-logging#accessing_logs).

## Troubleshooting

This section describes common issues and troubleshooting steps.

### Network address assignment errors when running Terraform

If Terraform reports `connect: cannot assign requested address` errors when you
run Terraform, try running the command again.

### Errors when adding the GKE cluster to the Fleet

If Terraform reports errors about the format of the fleet membership
configuration, it may mean that the Fleet API initialization didn't complete
when Terraform tried to add the GKE cluster to the fleet. Example:

```text
Error creating FeatureMembership: googleapi: Error 400: InvalidValueError for
field membership_specs["projects/<project number>/locations/global/memberships/<cluster name>"].feature_spec:
does not match a current membership in this project. Keys should be in the form: projects/<project number>/locations/{l}/memberships/{m}
```

If this error occurs, try running `terraform apply` again.

### Errors when pulling container images

If `istio-ingress` or `istio-egress` Pods fail to run because GKE cannot
download their container images and GKE reports `ImagePullBackOff` errors, see
[Troubleshoot gateways](https://cloud.google.com/service-mesh/docs/gateways#troubleshoot_gateways)
for details about the potential root cause. You can inspect the status of these
Pods in the
[GKE Workloads Dashboard](https://cloud.google.com/kubernetes-engine/docs/concepts/dashboards#workloads).

If this happens:

1. Wait for the cluster to complete the initialization
1. Delete the Deployment that is impacted by this issue. Config Sync will deploy
   it again with the correct container image identifiers.

### Errors when deleting and cleaning up the environment

When running `terraform destroy` to remove resources that this reference
architecture provisioned and configured, it might happen that you get the
following errors:

- Dangling network endpoint groups (NEGs):

  ```text
  Error waiting for Deleting Network: The network resource
  'projects/PROJECT_NAME/global/networks/NETWORK_NAME' is already being used
  by
  'projects/PROJECT_NAME/zones/ZONE_NAME/networkEndpointGroups/NETWORK_ENDPOINT_GROUP_NAME'.
  ```

  If this happens, see the note at the end of
  [Uninstall Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/uninstall)

- GKE Enterprise features already enabled in the Google Cloud project:

  ```text
  Error: Error creating Feature: googleapi: Error 409: Resource
  'projects/PROJECT_NAME/locations/global/features/configmanagement' already
  exists
  ```

  To avoid this error, you can either:

  - Deploy the reference architecture in a new Google Cloud project, where GKE
    Enterprise features are not already enabled, so that the reference
    architecture can manage them.
  - [Import the `gke_hub_feature` resources](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/gke_hub_feature#import)
    in the Terraform state, so that Terraform is aware of them. In this case,
    Terraform will also apply any configuration changes that the reference
    architecture requires. Before you import `gke_hub_feature` resources in the
    Terraform state, we recommend that you assess the impact on other GKE
    clusters in the same project that depend on those resources. For example,
    when you destroy this reference architecture, these resources will be
    destroyed too, potentially impacting other GKE clusters in the same project.

## Understanding the security controls that you need

This section discusses the controls that you apply with the blueprint to help
you secure your GKE cluster.

For more information, see
[Security, privacy, and compliance for the Federated Learning architecture on Google Cloud](https://cloud.google.com/architecture/cross-silo-cross-device-federated-learning-google-cloud).

### Enhanced security of GKE clusters

_Creating clusters according to security best practices._

The blueprint helps you create GKE clusters that implement the following
security settings:

- Limit exposure of your GKE nodes and control plane to the internet by creating
  a
  [private GKE cluster](https://cloud.google.com/kubernetes-engine/docs/concepts/private-cluster-concept).
- Use
  [shielded nodes](https://cloud.google.com/kubernetes-engine/docs/how-to/shielded-gke-nodes)
  that provide strong, verifiable node identity and integrity to increase the
  security of GKE nodes.
- [Encrypt cluster secrets](https://cloud.google.com/kubernetes-engine/docs/how-to/encrypting-secrets)
  at the application layer.

For more information about GKE security settings, refer to
[Harden your cluster's security](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster).

### Firewall policies: restrict traffic between virtual machines

Firewall policies govern which traffic is allowed to or from Compute Engine VMs
and GKE nodes. The policies let you filter traffic at node granularity.

The reference architecture creates a GKE cluster with the
[default GKE cluster firewall rules and policies](https://cloud.google.com/kubernetes-engine/docs/concepts/firewall-rules#cluster-fws).
These firewall rules enable communication between the cluster nodes and GKE
control plane, and between nodes and pods in the cluster. Then, in order to
increase the isolation of GKE nodes, the reference architecture applies
additional firewall policies to restrict egress traffic from GKE nodes:

- By default, all egress traffic from the tenant nodes is denied.
- Any required egress must be explicitly configured. For example, you use the
  reference architecture to create firewall policies to allow egress from GKE
  nodes to the GKE control plane and to Google APIs.

### Node taints and affinities: control workload scheduling

[Node taints](https://kubernetes.io/docs/concepts/scheduling-eviction/taint-and-toleration/)
and
[node affinity](https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/#affinity-and-anti-affinity)
are Kubernetes mechanisms that let you influence how pods are scheduled onto
cluster nodes.

Tainted nodes repel pods. Kubernetes will not schedule a Pod onto a tainted node
unless the Pod has a _toleration_ for the taint. You can use node taints to
reserve nodes for use only by certain workloads or tenants. Taints and
tolerations are often used in multi-tenant clusters. See the
[dedicated nodes with taints and tolerations](https://cloud.google.com/kubernetes-engine/docs/concepts/multitenancy-overview#dedicated_nodes_with_taints_and_tolerations)
documentation for more information.

Node affinity lets you constrain pods to nodes with particular labels. If a pod
has a node affinity requirement, Kubernetes will not schedule the Pod onto a
node unless the node has a label that matches the affinity requirement. You can
use node affinity to ensure that pods are scheduled onto appropriate nodes.

You can use node taints and node affinity together to ensure tenant workload
pods are scheduled exclusively onto nodes reserved for the tenant.

The reference architecture helps you control the scheduling of workloads in the
following ways:

- Creates a GKE node pool dedicated to each tenant. Each node in the pool has a
  taint related to the tenant name.
- Applies the appropriate toleration and node affinity to any Pod targeting the
  tenant namespace using
  [PolicyController mutations](https://cloud.google.com/anthos-config-management/docs/how-to/mutation).

By applying taints and tolerations as described, GKE only allow scheduling pods
that belong to their tenant on the tenant node pool, rejecting pods belonging to
other tenants.

### Network policies: enforce network traffic flow within clusters

[Kubernetes Network policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
enforce OSI layer 3 or 4 network traffic flows by using Pod-level firewall
rules. Network policies are
[scoped to a namespace](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/concepts/configs#network-policy-config).

The reference architecture applies network policies to each tenant namespace. By
default, network policies deny all traffic to and from pods in the namespace.
Any required traffic must be explicitly allowlisted. For example, the network
policies explicitly allow traffic to required cluster services, such as the
cluster internal DNS and the Cloud Service Mesh control plane.

### Config Sync: apply configurations to your GKE clusters

Config Sync keeps your GKE clusters in sync with configs stored in a
[Git repository](https://cloud.google.com/anthos-config-management/docs/how-to/repo)
or in an
[Artifact Registry repository](https://cloud.google.com/kubernetes-engine/enterprise/config-sync/docs/how-to/sync-oci-artifacts-from-artifact-registry)

The repository acts as the single source of truth for your cluster configuration
and policies.

The reference architecture installs Config Sync to configure the following
resources:

- Cluster-level Cloud Service Mesh configuration
- Cluster-level network and security policies
- Namespace-level configuration and policies, including network policies,
  service accounts, RBAC rules, and namespace-level Cloud Service Mesh
  configuration

### Policy Controller: enforce compliance with policies

[Policy Controller](https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/overview)
is a
[dynamic admission controller](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
for Kubernetes that enforces policies.

The reference architecture installs Policy Controller into the GKE cluster and
includes policies to help secure your GKE cluster. The reference architecture
automatically applies the following policies to your GKE cluster using Config
Sync:

- Selected policies to help
  [enforce Pod security](https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/how-to/using-constraints-to-enforce-pod-security).
  For example, you apply policies that prevent pods running privileged
  containers and that require a non-read-only root file system.
- Policies from the Policy Controller
  [template library](https://cloud.google.com/kubernetes-engine/enterprise/policy-controller/docs/latest/reference/constraint-template-library).
  For example, you apply a policy that disallows services with type NodePort.

### Cloud Service Mesh: manage secure communications between services

[Cloud Service Mesh](https://cloud.google.com/service-mesh/docs/overview) helps
you monitor and manage an infrastructure layer to create managed, observable,
and secure communication channels across your services in the following ways:

- Manage authentication and encryption of traffic
  ([supported protocols](https://cloud.google.com/service-mesh/docs/supported-features#protocol_support)
  within the cluster using
  [mutual Transport Layer Communication (mTLS)](https://cloud.google.com/service-mesh/docs/security-overview#mutual_tls)).
  Cloud Service Mesh manages the provisioning and rotation of mTLS certificates
  and certificates for workloads without disrupting communications. Regularly
  rotating mTLS certificates is a security best practice that helps reduce
  exposure in the event of an attack.
- Let you configure network security policies based on service identity rather
  than on the IP address. Cloud Service Mesh lets you configure identity-aware
  access control policies that are independent of the network location of the
  workload.
- Let you configure policies that permit access from certain clients only.

The reference architecture installs Cloud Service Mesh in your cluster, and it
configures each Kubernetes namespace for
[automatic sidecar proxy injection](https://cloud.google.com/service-mesh/docs/proxy-injection).

The reference architecture automatically configure Cloud Service Mesh using
Config Sync to do the following:

- Enforce
  [mTLS communication](https://cloud.google.com/service-mesh/docs/security/configuring-mtls#enforcing_mesh-wide_mtls)
  between services in the mesh.
- Limit outbound traffic from the mesh to only known hosts.
- Limit
  [authorized communication](https://cloud.google.com/service-mesh/docs/security/authorization-policy-overview)
  between services in the mesh. For example, workloads in a namespace are only
  allowed to communicate with workloads in the same namespace, or with a set of
  known external hosts.
- Route all ingress and egress traffic through gateways where you can apply
  further traffic controls.

### Least privilege: limit access to cluster and project resources

It is a security best practice to adopt a principle of least privilege for your
Google Cloud projects and resources. This way, the apps that run inside your
cluster, and the developers and operators that use the cluster, have only the
minimum set of permissions required.

The reference architecture helps you use least privilege service accounts in the
following ways:

- Each GKE node pool receives its own service account. Node service accounts are
  configured with the
  [minimum required permissions](https://cloud.google.com/kubernetes-engine/docs/how-to/hardening-your-cluster#use_least_privilege_sa).
- The GKE cluster uses
  [Workload Identity for GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
  to associate Kubernetes service accounts with Cloud IAM service accounts. This
  way, workloads can be granted limited access to any required Google APIs
  without downloading and storing service account keys. For example, you can
  grant the service account permissions to read data from a Cloud Storage
  bucket.
