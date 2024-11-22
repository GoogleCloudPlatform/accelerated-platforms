Copyright 2024 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

# Terraform Google Cloud NAT Module

This module handles opinionated Google Cloud Platform Cloud NAT creation and configuration.

## Compatibility

This module is meant for use with Terraform 0.13+ and tested using Terraform 1.0+. If you find incompatibilities using Terraform >=0.13, please open an issue.

## Usage

```hcl
module "cloud-nat" {
  source     = "terraform-google-modules/cloud-nat/google"
  version    = "~> 1.2"
  project_id = var.project_id
  region     = var.region
  router     = google_compute_router.router.name
}
```

Then perform the following commands on the root folder:

- `terraform init` to get the plugins
- `terraform plan` to see the infrastructure plan
- `terraform apply` to apply the infrastructure build
- `terraform destroy` to destroy the built infrastructure

<!-- BEGINNING OF PRE-COMMIT-TERRAFORM DOCS HOOK -->

## Inputs

| Name                                | Description                                                                                                                                                                                                                                            | Type                                                                                                                                       | Default                           | Required |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------- | :------: |
| create_router                       | Create router instead of using an existing one, uses 'router' variable for new resource name.                                                                                                                                                          | `bool`                                                                                                                                     | `false`                           |    no    |
| enable_dynamic_port_allocation      | Enable Dynamic Port Allocation. If minPorts is set, minPortsPerVm must be set to a power of two greater than or equal to 32.                                                                                                                           | `bool`                                                                                                                                     | `false`                           |    no    |
| enable_endpoint_independent_mapping | Specifies if endpoint independent mapping is enabled.                                                                                                                                                                                                  | `bool`                                                                                                                                     | `null`                            |    no    |
| icmp_idle_timeout_sec               | Timeout (in seconds) for ICMP connections. Defaults to 30s if not set. Changing this forces a new NAT to be created.                                                                                                                                   | `string`                                                                                                                                   | `"30"`                            |    no    |
| log_config_enable                   | Indicates whether or not to export logs                                                                                                                                                                                                                | `bool`                                                                                                                                     | `false`                           |    no    |
| log_config_filter                   | Specifies the desired filtering of logs on this NAT. Valid values are: "ERRORS_ONLY", "TRANSLATIONS_ONLY", "ALL"                                                                                                                                       | `string`                                                                                                                                   | `"ALL"`                           |    no    |
| max_ports_per_vm                    | Maximum number of ports allocated to a VM from this NAT. This field can only be set when enableDynamicPortAllocation is enabled.This will be ignored if enable_dynamic_port_allocation is set to false.                                                | `string`                                                                                                                                   | `null`                            |    no    |
| min_ports_per_vm                    | Minimum number of ports allocated to a VM from this NAT config. Defaults to 64 if not set. Changing this forces a new NAT to be created.                                                                                                               | `string`                                                                                                                                   | `"64"`                            |    no    |
| name                                | Defaults to 'cloud-nat-RANDOM_SUFFIX'. Changing this forces a new NAT to be created.                                                                                                                                                                   | `string`                                                                                                                                   | `""`                              |    no    |
| nat_ips                             | List of self_links of external IPs. Changing this forces a new NAT to be created. Value of `nat_ip_allocate_option` is inferred based on nat_ips. If present set to MANUAL_ONLY, otherwise AUTO_ONLY.                                                  | `list(string)`                                                                                                                             | `[]`                              |    no    |
| network                             | VPN name, only if router is not passed in and is created by the module.                                                                                                                                                                                | `string`                                                                                                                                   | `""`                              |    no    |
| project_id                          | The project ID to deploy to                                                                                                                                                                                                                            | `string`                                                                                                                                   | n/a                               |   yes    |
| region                              | The region to deploy to                                                                                                                                                                                                                                | `string`                                                                                                                                   | n/a                               |   yes    |
| router                              | The name of the router in which this NAT will be configured. Changing this forces a new NAT to be created.                                                                                                                                             | `string`                                                                                                                                   | n/a                               |   yes    |
| router_asn                          | Router ASN, only if router is not passed in and is created by the module.                                                                                                                                                                              | `string`                                                                                                                                   | `"64514"`                         |    no    |
| router_keepalive_interval           | Router keepalive_interval, only if router is not passed in and is created by the module.                                                                                                                                                               | `string`                                                                                                                                   | `"20"`                            |    no    |
| source_subnetwork_ip_ranges_to_nat  | Defaults to ALL_SUBNETWORKS_ALL_IP_RANGES. How NAT should be configured per Subnetwork. Valid values include: ALL_SUBNETWORKS_ALL_IP_RANGES, ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES, LIST_OF_SUBNETWORKS. Changing this forces a new NAT to be created. | `string`                                                                                                                                   | `"ALL_SUBNETWORKS_ALL_IP_RANGES"` |    no    |
| subnetworks                         | Specifies one or more subnetwork NAT configurations                                                                                                                                                                                                    | <pre>list(object({<br> name = string,<br> source_ip_ranges_to_nat = list(string)<br> secondary_ip_range_names = list(string)<br> }))</pre> | `[]`                              |    no    |
| tcp_established_idle_timeout_sec    | Timeout (in seconds) for TCP established connections. Defaults to 1200s if not set. Changing this forces a new NAT to be created.                                                                                                                      | `string`                                                                                                                                   | `"1200"`                          |    no    |
| tcp_time_wait_timeout_sec           | Timeout (in seconds) for TCP connections that are in TIME_WAIT state. Defaults to 120s if not set.                                                                                                                                                     | `string`                                                                                                                                   | `"120"`                           |    no    |
| tcp_transitory_idle_timeout_sec     | Timeout (in seconds) for TCP transitory connections. Defaults to 30s if not set. Changing this forces a new NAT to be created.                                                                                                                         | `string`                                                                                                                                   | `"30"`                            |    no    |
| udp_idle_timeout_sec                | Timeout (in seconds) for UDP connections. Defaults to 30s if not set. Changing this forces a new NAT to be created.                                                                                                                                    | `string`                                                                                                                                   | `"30"`                            |    no    |

## Outputs

| Name                   | Description            |
| ---------------------- | ---------------------- |
| name                   | Name of the Cloud NAT  |
| nat_ip_allocate_option | NAT IP allocation mode |
| region                 | Cloud NAT region       |
| router_name            | Cloud NAT router name  |

<!-- END OF PRE-COMMIT-TERRAFORM DOCS HOOK -->

## Requirements

Before this module can be used on a project, you must ensure that the following pre-requisites are fulfilled:

1. Terraform and kubectl are [installed](#software-dependencies) on the machine where Terraform is executed.
2. The Service Account you execute the module with has the right [permissions](#iam-roles).
3. The APIs are [active](#enable-apis) on the project you will launch the cluster in.
4. If you are using a Shared VPC, the APIs must also be activated on the Shared VPC host project and your service account needs the proper permissions there.

### Terraform plugins

- [Terraform](https://www.terraform.io/downloads.html) >= 0.13.0
- [terraform-provider-google](https://github.com/terraform-providers/terraform-provider-google) plugin v4.27.0

### Configure a Service Account

In order to execute this module you must have a Service Account with the
following project roles:

- [roles/compute.networkAdmin](https://cloud.google.com/nat/docs/using-nat#iam_permissions)

### Enable APIs

In order to operate with the Service Account you must activate the following APIs on the project where the Service Account was created:

- Compute Engine API - compute.googleapis.com

## Contributing

Refer to the [contribution guidelines](./CONTRIBUTING.md) for information on contributing to this module.
