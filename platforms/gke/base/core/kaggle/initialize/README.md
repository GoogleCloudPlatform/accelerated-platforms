# KAggle initialize

## Initial configuration

- Set environment variables.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh"
  ```

- Add the Kaggle API token using **one** of the following:

  - [Generate a Kaggle API token](https://www.kaggle.com/docs/api#authentication)

  **Console**

  ```shell
  echo -e "\n${kaggle_api_token_secret_manager_secret_name} versions URL: https://console.cloud.google.com/security/secret-manager/secret/${kaggle_api_token_secret_manager_secret_name}/versions?project=${kaggle_secret_manager_project_id}\n"
  ```

  **`gcloud`**

  ```shell
  unset HISTORY
  KAGGLE_API_TOKEN="<API token>"
  echo ${KAGGLE_API_TOKEN} | gcloud secrets versions add ${kaggle_api_token_secret_manager_secret_name} \
  --data-file=- \
  --project=${kaggle_secret_manager_project_id}
  ```

## Developers

See the
[Kaggle initialize developer's guide](/platforms/gke/base/core/kaggle/initialize/DEVELOPER.md)
