# Hugging Face initialization

- Set environment variables.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
  ```

- Add the Hugging Face Hub access token with read permissions using **one** of
  the following:

  - [Generate a Hugging Face tokens](https://huggingface.co/docs/hub/security-tokens)
    with token type **Read**.

  **Console**

  ```shell
  echo -e "\n${huggingface_hub_access_token_read_secret_manager_secret_name} versions URL: https://console.cloud.google.com/security/secret-manager/secret/${huggingface_hub_access_token_read_secret_manager_secret_name}/versions?project=${huggingface_secret_manager_project_id}\n"
  ```

  **`gcloud`**

  ```shell
  unset HISTORY
  HF_TOKEN_READ="<read token>"
  echo ${HF_TOKEN_READ} | gcloud secrets versions add ${huggingface_hub_access_token_read_secret_manager_secret_name} \
  --data-file=- \
  --project=${huggingface_secret_manager_project_id}
  ```

- Add the Hugging Face Hub access token with write permissions using **one** of
  the following:

  - [Generate a Hugging Face tokens](https://huggingface.co/docs/hub/security-tokens)
    with token type **Write**.

  **Console**

  ```shell
  echo -e "\n${huggingface_hub_access_token_write_secret_manager_secret_name} versions URL: https://console.cloud.google.com/security/secret-manager/secret/${huggingface_hub_access_token_write_secret_manager_secret_name}/versions?project=${huggingface_secret_manager_project_id}\n"
  ```

  **`gcloud`**

  ```shell
  unset HISTORY
  HF_TOKEN_WRITE="<write token>"
  echo ${HF_TOKEN_WRITE} | gcloud secrets versions add ${huggingface_hub_access_token_write_secret_manager_secret_name} \
  --data-file=- \
  --project=${huggingface_secret_manager_project_id}
  ```

- Ensure that the token has access to any model that will be used by signing the
  consent agreement.

## How to use

- Set environment variables.

  ```shell
  set -o allexport
  source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
  set +o allexport
  ```

  ```
  export WORKLOAD_NAMESPACE="default"
  export WORKLOAD_KUBERNETES_SERVICE_ACCOUNT="default"
  ```

- Give the Kubernetes service account IAM permissions.

  **Read token**

  ```shell
  cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")
  gcloud secrets add-iam-policy-binding ${huggingface_hub_access_token_read_secret_manager_secret_name} \
  --member=principal://iam.googleapis.com/projects/312289355029/locations/global/workloadIdentityPools/accelerated-platforms-dev.svc.id.goog/subject/ns/${WORKLOAD_NAMESPACE}/sa/${WORKLOAD_KUBERNETES_SERVICE_ACCOUNT} \
  --project=${huggingface_secret_manager_project_id} \
  --role=roles/secretmanager.secretAccessor
  ```

  **Write token**

  ```shell
  cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")
  gcloud secrets add-iam-policy-binding ${huggingface_hub_access_token_write_secret_manager_secret_name} \
  --member=principal://iam.googleapis.com/projects/${cluster_project_number}/locations/global/workloadIdentityPools/${cluster_project_id}.svc.id.goog/subject/ns/${WORKLOAD_NAMESPACE}/sa/${WORKLOAD_KUBERNETES_SERVICE_ACCOUNT} \
  --project=${huggingface_secret_manager_project_id} \
  --role=roles/secretmanager.secretAccessor
  ```

- Create the `SecretProviderClass`es in the workload's namespace.

  ```shell
  export WORKLOAD_NAMESPACE="default"
  envsubst <${ACP_REPO_DIR}/platforms/gke/base/core/huggingface/initialize/templates/secretproviderclass-huggingface-tokens.tftpl.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE} apply -f -
  ```

- Add the secret volume to the template spec.

  ```yaml
        volumes:
          - name: huggingface-token
            csi:
              driver: secrets-store-gke.csi.k8s.io
              readOnly: true
              volumeAttributes:
                secretProviderClass: huggingface-token-<token_type>
  ```

### Standard `huggingface-cli` support

- Add the volume mount to the container.

  ```yaml
          volumeMounts:
            - mountPath: /var/run/secrets/huggingface.co
              name: huggingface-token-<token_type>
  ```

- Set the `HF_TOKEN_PATH` environment variable

  ```yaml
          env:
            - name: HF_TOKEN_PATH
              value: /var/run/secrets/huggingface.co/token
  ```

### Non-standard `huggingface-cli` support

For images that don't support the standard `huggingface-cli` environment
variables you will need to determine the correct place to mount the token and/or
if a corresponding environment variable needs to be set. This might also require
modifying the `SecretProviderClass` to mount the token at an additional path.

#### Examples

##### jetstream-pytorch

The jetstream-pytorch image expects the token to be mounted at
`/huggingface/HUGGINGFACE_TOKEN`. This requires modifying or adding an
additional path to the `SecretProviderClass`es.

- Modify the `SecretProviderClass`es.

  ```yaml
  apiVersion: secrets-store.csi.x-k8s.io/v1
  kind: SecretProviderClass
  metadata:
    name: huggingface-token-read
  spec:
    provider: gke
    parameters:
      secrets: |
        - resourceName: "projects/${huggingface_secret_manager_project_id}/secrets/${huggingface_hub_access_token_read_secret_manager_secret_name}/versions/latest"
          path: "token"
        - resourceName: "projects/${huggingface_secret_manager_project_id}/secrets/${huggingface_hub_access_token_read_secret_manager_secret_name}/versions/latest"
          path: "HUGGINGFACE_TOKEN"
  ---
  apiVersion: secrets-store.csi.x-k8s.io/v1
  kind: SecretProviderClass
  metadata:
    name: huggingface-token-write
  spec:
    provider: gke
    parameters:
      secrets: |
        - resourceName: "projects/${huggingface_secret_manager_project_id}/secrets/${huggingface_hub_access_token_write_secret_manager_secret_name}/versions/latest"
          path: "token"
        - resourceName: "projects/${huggingface_secret_manager_project_id}/secrets/${huggingface_hub_access_token_write_secret_manager_secret_name}/versions/latest"
          path: "HUGGINGFACE_TOKEN"

  ```

- Add the secret volume to the template spec.

  ```yaml
        volumes:
          - name: huggingface-token
            csi:
              driver: secrets-store-gke.csi.k8s.io
              readOnly: true
              volumeAttributes:
                secretProviderClass: huggingface-token-<token_type>
  ```

- Add the volume mount to the container.

  ```yaml
            volumeMounts:
              - mountPath: /huggingface
                name: huggingface-token
  ```
