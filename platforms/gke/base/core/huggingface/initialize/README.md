# Hugging Face initialize

## Initial configuration

- Set environment variables.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh"
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

## Developers

See the
[Hugging Face initialize developer's guide](/platforms/gke/base/core/huggingface/initialize/DEVELOPER.md)
