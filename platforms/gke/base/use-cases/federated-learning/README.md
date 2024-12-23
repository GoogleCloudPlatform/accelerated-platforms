# Federated learning on Google Cloud

## Configure the Federated learning reference architecture

You can configure the reference architecture by modifying files in
`platforms/gke/base/use-cases/federated-learning/terraform/_shared_config`.

## Deploy the Federated learning reference architecture

1. Provision the Federated learning reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"
   ```

## Teardown the Federated learning reference architecture

1. Teardown the Federated learning reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/teardown.sh"
   ```
