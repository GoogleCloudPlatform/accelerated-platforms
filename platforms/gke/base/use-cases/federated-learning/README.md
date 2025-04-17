# Deploy the Federated learning reference architecture on Google Cloud

This document shows how to deploy the
[Google Cloud Federated Learning (FL) reference architecture](/docs/use-cases/federated-learning/README.md).

To deploy this reference architecture, you need:

- A [Google Cloud project](https://cloud.google.com/docs/overview#projects) with
  billing enabled. We recommend deploying this reference architecture to a new,
  dedicated Google Cloud project.
- An account with either the [Project Owner role](#option-1-project-owner-role)
  (full access) or [Granular Access roles](#option-2-granular-access).
- The `serviceusage.googleapis.com` must be enabled on the project. For more
  information about enabling APIs, see
  [Enabling and disabling services](https://cloud.google.com/service-usage/docs/enable-disable)

This reference architecture builds on the
[Reference implementation for the Core GKE Accelerated Platform](/platforms/gke/base/README.md).
In this document, we reference the Reference implementation for the Core GKE
Accelerated Platform as _core platform_. The deployment procedure described in
the [Deploy the reference architecture](#deploy-the-reference-architecture)
section takes care of deploying an instance of the core platform for you.

### Service account roles and permissions

You can choose between Project Owner access or Granular Access for more
fine-tuned permissions.

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

![alt_text](/platforms/gke/base/use-cases/federated-learning/assets/architecture.png "Architecture overview")

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

- A GKE node pool (`system`) to host coordination and management workloads that
  aren't tied to specific tenants.

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
  - A service account for workloads in each tenant. These service don't have any
    permission by default, and map to Kubernetes service accounts using
    [Workload Identity for GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity#authenticating_to).

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

1. [Install Terraform >= 1.8.0](https://developer.hashicorp.com/terraform/install).

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Clone this repository and change the working directory:

   ```shell
   git clone https://github.com/GoogleCloudPlatform/accelerated-platforms && \
   cd accelerated-platforms
   ```

1. Configure the ID of the Google Cloud project where you want to initialize the
   provisioning and configuration environment. This project will also contain
   the remote Terraform backend. Add the following content to
   `platforms/gke/base/_shared_config/terraform.auto.tfvars`:

   ```hcl
   terraform_project_id = "<CONFIG_PROJECT_ID>"
   ```

   Where:

   - `<CONFIG_PROJECT_ID>` is the Google Cloud project ID.

1. Configure the ID of the Google Cloud project where you want to deploy the
   reference architecture by adding the following content to
   `platforms/gke/base/_shared_config/cluster.auto.tfvars`:

   ```hcl
   cluster_project_id = "<PROJECT_ID>"
   ```

   Where:

   - `<PROJECT_ID>` is the Google Cloud project ID. Can be different from
     `<CONFIG_PROJECT_ID>`.

1. Optionally configure a unique identifier to append to the name of all the
   resources in the reference architecture to identify a particular instance of
   the reference architecture, and to allow for multiple instances of the
   reference architecture to be deployed in the same Google Cloud project. To
   optionally configure the unique prefix, add the following content to
   `platforms/gke/base/_shared_config/platform.auto.tfvars`:

   ```hcl
   resource_name_prefix = "<RESOURCE_NAME_PREFIX>"
   platform_name        = "<PLATFORM_NAME>"
   ```

   Where:

   - `<RESOURCE_NAME_PREFIX>` and `<PLATFORM_NAME>` are strings that compose the
     unique identifier to append to the name of all the resources in the
     reference architecture.

   When you set `resource_name_prefix` and `platform_name`, we recommend that
   you avoid long strings because the might make resource naming validation to
   fail because the resource name might be too long.

1. Run the script to provision the reference architecture:

   ```sh
   "platforms/gke/base/use-cases/federated-learning/deploy.sh"
   ```

It takes about 20 minutes to provision the reference architecture.

### Understand the deployment and destroy processes

The `platforms/gke/base/use-cases/federated-learning/deploy.sh` script is a
convenience script to orchestrate the provisioning and configuration of an
instance of the reference architecture.
`platforms/gke/base/use-cases/federated-learning/deploy.sh` does the following:

1. Configure environment variables to reference libraries and other
   dependencies.
1. Initialize the core platform configuration files.
1. Initialize the core platform by running the
   [core platform `initialize` service](/platforms/gke/base/core/initialize/).
1. Provision and configure Google Cloud resources that the core platform depends
   on.
1. Provision and configure an instance of the core platform.
1. Provision and configures Google Cloud resources that the FL reference
   architecture depends on, augmenting the core platform.

The `platforms/gke/base/use-cases/federated-learning/teardown.sh` script is a
convenience script to orchestrate the destruction of an instance of the
reference architecture.
`platforms/gke/base/use-cases/federated-learning/teardown.sh` performs actions
that are opposite to
`platforms/gke/base/use-cases/federated-learning/deploy.sh`, in reverse order.

## Next steps

After deploying the reference architecture, the GKE cluster is ready to host
your federated learning workloads. For example, you can:

- Familiarize with the reference architecture by
  [deploying a NVIDIA FLARE example in the GKE cluster](/platforms/gke/base/use-cases/federated-learning/examples/nvflare-tff/README.md).
- Explore the
  [Federated Learning on Google Cloud repository](https://github.com/GoogleCloudPlatform/federated-learning)
  for cross-silo FL, cross-device FL, more examples and extensions to this
  reference architecture.

## Destroy the reference architecture

To destroy an instance of the reference architecture, you do the following:

1. Open [Cloud Shell](https://cloud.google.com/shell).

1. Run the script to destroy the reference architecture:

   ```sh
   "platforms/gke/base/use-cases/federated-learning/teardown.sh"
   ```

## Configure the Federated learning reference architecture

You can configure the reference architecture by modifying files in the following
directories:

- `platforms/gke/base/_shared_config`
- `platforms/gke/base/use-cases/federated-learning/terraform/_shared_config`

To add files to the package that Config Sync uses to sync cluster configuration:

1. Copy the additional files in the
   `platforms/gke/base/use-cases/federated-learning/terraform/config_management/files/additional`
   directory.
1. Run the `platforms/gke/base/use-cases/federated-learning/deploy.sh` script.

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
`platforms/gke/base/use-cases/federated-learning/terraform/_shared_config/uc_federated_learning.auto.tfvars`
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
`platforms/gke/base/use-cases/federated-learning/terraform/_shared_config/uc_federated_learning_variables.tf`

### Enable Confidential GKE Nodes

The reference architecture can optionally configure Confidential GKE Nodes using
Terraform. To enable Confidential GKE Nodes, you do the following:

1. Initialize the following Terraform variables in
   `platforms/gke/base/_shared_config/cluster.auto.tfvars`:

   1. Set `cluster_confidential_nodes_enabled` to `true`

   1. Set `cluster_system_node_pool_machine_type` to a machine type that
      supports Confidential GKE Nodes. For more information about the machine
      types that support Confidential GKE Nodes, see
      [Encrypt workload data in-use with Confidential GKE Nodes](https://cloud.google.com/kubernetes-engine/docs/how-to/confidential-gke-nodes#availability).

1. Initialize the following Terraform variables in
   `platforms/gke/base/use-cases/federated-learning/terraform/_shared_config/uc_federated_learning.auto.tfvars`:

   1. Set `federated_learning_node_pool_machine_type` to a machine type that
      supports Confidential GKE Nodes.

### Allow desired network traffic

1. Configure Kubernetes network policies to allow traffic. You can see how
   current Kubernetes network policies are affecting traffic in your cluster
   [using Cloud Logging](https://cloud.google.com/kubernetes-engine/docs/how-to/network-policy-logging#accessing_logs).

1. If your workloads need to access hosts that are external to the service mesh,
   configure a
   [ServiceEntry](https://istio.io/latest/docs/reference/config/networking/service-entry/)
   for each external host.

1. If your workloads need to send traffic outside the cluster, configure:

   - [AuthorizationPolicies](https://istio.io/latest/docs/reference/config/security/authorization-policy)
     to allow traffic from the workload namespace to the `istio-egress`
     namespace.
   - [VirtualServices](https://istio.io/latest/docs/reference/config/networking/virtual-service)
     to direct traffic from the workload to the egress gateway, and from the
     egress gateway to the destination.
   - [NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
     to allow egress traffic from their workspace.

1. If your workloads need to receive traffic from outside the cluster,
   configure:

   - [AuthorizationPolicies](https://istio.io/latest/docs/reference/config/security/authorization-policy)
     to allow traffic from the `istio-ingress` namespace to the workload
     namespace.
   - [VirtualServices](https://istio.io/latest/docs/reference/config/networking/virtual-service)
     to direct traffic from the external service to the ingress gateway, and
     from the ingress gateway to the workload.
   - [NetworkPolicies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
     to allow ingress traffic to their workspace.

## Troubleshooting

This section describes common issues and troubleshooting steps.

### Network address assignment errors when running Terraform

If Terraform reports `connect: cannot assign requested address` errors when you
run Terraform, try running the command again.

### Errors when provisioning the reference architecture

- Cloud Shell has 5GBs of available disk space. Depending on your Cloud Shell
  usage, it might not be enough for deploying the reference architecture, unless
  you enable Terraform plugin caching to enable reusing plugins and providers,
  instead of downloading multiple copies of each plugin and provider. Symptoms
  of this issue are errors like the following:

  ```text
  │ Error: Failed to install provider
  │
  │ Error while installing hashicorp/google v6.12.0: write
  │ .terraform/providers/registry.terraform.io/hashicorp/google/6.12.0/linux_amd64/terraform-provider-google_v6.12.0_x5: no space left on device
  ╵
  ```

- If Cloud Service Mesh is reported as `Pending enablement` state in the
  [GKE Enterprise feature dashboard](https://pantheon.corp.google.com/kubernetes/features/services/details),
  If this error occurs, try disabling and re-enabling Cloud Service Mesh:

  ```bash
  terraform -chdir=platforms/gke/base/core/gke_enterprise/servicemesh init && \
    terraform -chdir=platforms/gke/base/core/gke_enterprise/servicemesh destroy -auto-approve -input=false && \
    terraform -chdir=platforms/gke/base/core/gke_enterprise/servicemesh apply -input=false
  ```

- Client-side tools and Cloud Shell authenticate with Google Cloud using a
  short-lived token. If the token expires, you might receive errors similar to
  the following:

  ```text
  │ Error: Error when reading or editing Project "PROJECT_ID": Get "https://cloudresourcemanager.googleapis.com/v1/projects/PROJECT_ID?alt=json&prettyPrint=false": oauth2/google: invalid token JSON from metadata: EOF
  │
  │   with data.google_project.cluster,
  │   on project.tf line 15, in data "google_project" "cluster":
  │   15: data "google_project" "cluster" {
  ```

  If this error occurs, try reloading Cloud Shell.

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

### Errors when enabling GKE Enterprise features

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

    For example, you can run the following command from the root directory of
    this repository to import the `configmanagement` feature:

    ```bash
    terraform -chdir=platforms/gke/base/core/gke_enterprise/configmanagement/oci init && \
      terraform -chdir=platforms/gke/base/core/gke_enterprise/configmanagement/oci import \
      google_gke_hub_feature.configmanagement \
      projects/<PROJECT_ID>/locations/global/features/configmanagement
    ```

    As another example, you can run the following command from the root
    directory of this repository to import the `policycontroller` feature:

    ```bash
    terraform -chdir=platforms/gke/base/core/gke_enterprise/policycontroller init && \
      terraform -chdir=platforms/gke/base/core/gke_enterprise/policycontroller import \
      google_gke_hub_feature.policycontroller \
      projects/<PROJECT_ID>/locations/global/features/policycontroller
    ```

    Where:

    - `<PROJECT_ID>` is the Google Cloud project ID where you deployed the
      reference architecture.

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

## Understanding security controls

For more information about the controls that this reference architecture
implements to help you secure your environment, see
[GKE security controls](https://cloud.google.com/architecture/cross-silo-cross-device-federated-learning-google-cloud).

## What's next

For a complete overview about how to implement Federated Learning on Google
Cloud, see
[Cross-silo and cross-device federated learning on Google Cloud](https://cloud.google.com/architecture/cross-silo-cross-device-federated-learning-google-cloud).
