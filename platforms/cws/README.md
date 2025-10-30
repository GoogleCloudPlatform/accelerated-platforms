# Cloud Workstations Platform

See [Cloud Workstations Platform](/docs/platforms/cws/README.md) documentation.

The Cloud Workstations Platform is structured using shard configuration,
terraservices and terrastacks. The shared configuration provides a single point
of configuration that flow through to all of the individual components. The
shared configuration also exposes the Terraform configuration values for use on
the command line via environment variables. Terraservices are logical components
treated as isolated units and managing independently. Terrastacks are
combinations of terraservices that provide specific functionality.

## Terrastacks

### `cluster`

### `image_pipeline`

### `workstation_configuration`
