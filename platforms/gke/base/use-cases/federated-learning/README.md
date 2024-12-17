# Federated learning on Google Cloud

## Deploy the Federated Learning reference architecture

1. Provision the base platform by following the
   [Core GKE Accelerated Platform guide](/platforms/gke/base/core/README.md).

1. Provision the Federated Learning reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/deploy.sh"
   ```

## Teardown the Federated Learning reference architecture

1. Teardown the Federated Learning reference architecture:

   ```sh
   "${ACP_PLATFORM_BASE_DIR}/use-cases/federated-learning/teardown.sh"
   ```

1. Teardown the base platform by following the
   [Core GKE Accelerated Platform guide](/platforms/gke/base/core/README.md#teardown).
