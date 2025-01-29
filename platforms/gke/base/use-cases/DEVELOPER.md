# Base GKE Accelerated Platform developers guide

In this document, we explain how developers should work on the base platform to
add new features, implement new use cases, and fix bugs.

## How to develop a new use case

In order to develop new use cases or integrate existing use cases on top of the
core platform, you follow this approach:

1. Create a new documentation directory about the use case under
   `docs/use-cases`. In the context of this document, this directory is defined
   as the _use case documentation directory_. Example:
   `docs/use-cases/federated-learning`.

1. Create a documentation page about the use case and store it in the use case
   documentation directory. At minimum, the documentation page should include: a
   description of the use case, and an architecture diagram of the use case.
   Example:
   [Federated learning use case documentation](/docs/use-cases/federated-learning/README.md)

1. Create a new directory to contain use case assets under
   `platforms/gke/base/use-cases`. In the context of this document, this
   directory is defined as the _use case directory_. Example:
   `platforms/gke/base/use-cases/federated-learning`.

1. Create a README about the use case and store it in the use case directory. At
   minimum, the README should include the instructions to deploy the use case.
   Example:
   [Federated learning use case deployment instructions](/platforms/gke/base/use-cases/federated-learning/README.md)

1. Create Bash Shell scripts to deploy and destroy the resources that are
   necessary to realize the use case. Name these scripts `deploy.sh` and
   `teardown.sh`. Examples:
   [Federated learning deploy.sh](/platforms/gke/base/use-cases/federated-learning/deploy.sh),
   [Federated learning teardown.sh](/platforms/gke/base/use-cases/federated-learning/teardown.sh).

   The `deploy.sh` script must take care of the following tasks, in this order:

   1. Configure the base platform by editing files in
      `platforms/gke/base/_shared_config` to add appropriate configuration
      values. At minimum, they should set the `initialize_backend_use_case_name`
      variable in `platforms/gke/base/_shared_config/initialize.auto.tfvars` in
      order to initialize backend configuration files for the Terraform services
      that compose the provisioning process of the use case.

   1. Initialize the core platform and the Terraform backend configuration.

   1. If needed, provision any resources that the core platform depends on.

   1. Provision the core platform.

   1. Provision the resources that the use case needs.

   The `teardown.sh` script must take care of undoing the actions `deploy.sh`
   script.

1. Create a `terraform` directory in the use case directory.

1. Create a `_shared_config` directory in the `terraform` directory

1. Create Terraform services in subdirectories of the `terraform` directory.

1. For each Terraform service, create at least:

   - Symbolic links to the needed core platform configuration files in
     `platforms/gke/base/_shared_config`.

   - Symbolic links to the needed use case configuration files in the use case
     `_shared_config` directory.

   - A file named exactly `versions.tf` where you define Terraform version and
     provider version constraints. The name of this file is important because
     the core `initialize` Terraform service looks for this file to search for
     use case Terraform services to configure.

   - The
     [Terraform dependency lock file](https://developer.hashicorp.com/terraform/language/files/dependency-lock).
