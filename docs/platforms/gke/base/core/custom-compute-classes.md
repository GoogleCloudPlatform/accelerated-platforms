# Custom compute classes

In GKE, a compute class is a profile that consists of a set of node attributes
that GKE uses to provision the nodes that run your workloads during autoscaling
events. Compute classes can target specific optimizations, like provisioning
high-performance nodes or prioritizing cost-optimized configurations for cheaper
running costs. Custom compute classes let you define profiles that GKE then uses
to autoscale nodes to closely meet the requirements of specific workloads.
Custom compute classes are available to use in GKE Autopilot mode and GKE
Standard mode and are available to configure and use in all eligible GKE
clusters by default.

For additional information about see
[About custom compute classes](https://cloud.google.com/kubernetes-engine/docs/concepts/about-custom-compute-classes)

## Why?

Custom compute classes offer the following benefits:

- Fallback compute priorities: Define a hierarchy of node configurations in each
  compute class for GKE to prioritize. If the most preferred configuration is
  unavailable, GKE automatically chooses the next configuration in the
  hierarchy. This fallback model ensures that even when compute resources are
  unavailable, your workloads still run on optimized hardware with minimal
  scheduling delays.
- Granular autoscaling control: Define node configurations that are best suited
  for specific workloads. GKE prioritizes those configurations when creating
  nodes during scaling.
- Declarative infrastructure configuration: Adopt a declarative approach to
  infrastructure management so that GKE automatically creates nodes for you that
  match your specific workload requirements.
- Active migration: If compute resources for a more preferred machine
  configuration become available in your location, GKE automatically migrates
  your workloads to new nodes that use the preferred configuration.
- Cost optimization: Prioritize cost-efficient node types like Spot VMs to
  reduce your cluster expenses.
- Default compute classes for namespaces: Set a default compute class in each
  Kubernetes namespace, so that workloads in that namespace run on optimized
  hardware even if they don't request a specific compute class.
- Custom node consolidation thresholds: Define custom resource usage thresholds
  for nodes. If a specific node's resource usage falls below your threshold, GKE
  attempts to consolidate the workloads into a similar, available node and
  scales down the underutilized node.

Consider using custom compute classes in scenarios like the following:

- You want to run your AI/ML workloads on specific GPU or TPU configurations.
- You want to set default hardware configurations for the workloads that
  specific teams run, taking the overhead off of the application operators.
- You run workloads that perform optimally on specific Compute Engine machine
  series or hardware configurations.
- You want to declare hardware configurations that meet specific business
  requirements, like high performance, cost optimized, or high availability.
  -You want GKE to hierarchically fallback to using specific hardware
  configurations during compute resource unavailability, so that your workloads
  always run on machines that suit their requirements.
- You want to centrally decide on the optimal configurations across your
  enterprise's fleet, so that your costs are more predictable and your workloads
  run more reliably.
- You want to centrally specify which of your Compute Engine capacity
  reservations GKE should use to provision new nodes for specific workloads.

## How?

Custom compute classes are Kubernetes custom resources that provision Google
Cloud infrastructure. You define a ComputeClass object in the cluster, and then
request that compute class in workloads or set that compute class as the default
for a Kubernetes namespace. When a matching workload demands new infrastructure,
GKE provisions new nodes in line with the priorities that you set in your
compute class definition.

The attributes that you set in your compute classes define how GKE configures
new nodes to run workloads. When you modify an existing compute class, all
future nodes that GKE creates for that compute class use the modified
configuration. GKE doesn't retroactively change the configuration of existing
nodes to match your modifications.

To ensure that your custom compute classes are optimized for your fleet,
consider the following guidelines:

- Understand the compute requirements of your fleet, including any
  application-specific hardware requirements.
- Decide on a theme that guides the design of each compute class. For example, a
  performance-optimized compute class might have a fallback strategy that uses
  only high-CPU machine types.
- Decide on the Compute Engine machine family and machine series that most
  closely fit your workloads. For details, see Machine families resource and
  comparison guide.
- Plan a fallback strategy within each compute class so that workloads always
  run on nodes that use similar machine configurations. For example, if the N4
  machine series isn't available, you can fall back to N2 machines.

## Examples

If you have deployed a version of the
[Base GKE Accelerated Platform](/docs/platforms/gke/base/README.md) there are
some standard `ComputeClass` resources created in the
`platforms/gke/base/kubernetes/manifests` folder based on the templates in the
[`platforms/gke/base/core/custom_compute_class/templates/manifests`](/platforms/gke/base/core/custom_compute_class/templates/manifests)
folder of the repository.

To view the latest custom resource definition (CRD) for the `ComputeClass`
custom resource, including all fields and their relationships, refer to the
[ComputeClass reference documentation.](https://cloud.google.com/kubernetes-engine/docs/reference/crds/computeclass)

You can also view the CRD in your cluster by running the following command:

    ``` shell
    kubectl describe crd computeclasses.cloud.google.com
    ```

Using a `ComputeClass` for a workload.

```yaml
  nodeSelector:
    cloud.google.com/compute-class: <compute class name>
```

## In Practice

Compute classes can be used to create profiles for various objectives, such as
ensuring resource obtainability, cost optimization, or maximizing performance.

### Obtainability

```yaml
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-h200-141gb-ultra-x8
spec:
  activeMigration:
    optimizeRulePriority: true
  nodePoolAutoCreation:
    enabled: true
  priorities:
    # Use a specific reservation
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      reservations:
        affinity: Specific
        specific:
          - name: nvidia-h200-141gb-specific
            reservationBlock:
              name: nvidia-h200-141gb-block
      spot: false

    # Use any reservation
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      reservations:
        affinity: AnyBestEffort
      spot: false

    # Use on-demand
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      spot: false

    # Use DWS FlexStart with 7 day limit
    - flexStart:
        enabled: true
        nodeRecycling:
          leadTimeSeconds: 3600
      gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      maxRunDurationSeconds: 604800

    # Use DWS FlexStart with 1 day limit
    - flexStart:
        enabled: true
        nodeRecycling:
          leadTimeSeconds: 3600
      gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      maxRunDurationSeconds: 86400

    # Use spot
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      spot: true
```

### Cost Optimization

```yaml
apiVersion: cloud.google.com/v1
kind: ComputeClass
metadata:
  name: gpu-h200-141gb-ultra-x8-cost
spec:
  activeMigration:
    optimizeRulePriority: true
  nodePoolAutoCreation:
    enabled: true
  priorities:
    # Use a specific reservation
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      reservations:
        affinity: Specific
        specific:
          - name: nvidia-h200-141gb-specific
            reservationBlock:
              name: nvidia-h200-141gb-block
      spot: false

    # Use spot
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      spot: true

    # Use DWS FlexStart with 7 day limit
    - flexStart:
        enabled: true
        nodeRecycling:
          leadTimeSeconds: 3600
      gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      maxRunDurationSeconds: 604800

    # Use DWS FlexStart with 1 day limit
    - flexStart:
        enabled: true
        nodeRecycling:
          leadTimeSeconds: 3600
      gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      maxRunDurationSeconds: 86400

    # Use on-demand
    - gpu:
        count: 8
        driverVersion: latest
        type: nvidia-h200-141gb
      machineType: a3-ultragpu-8g
      maxPodsPerNode: 32
      spot: false
```
