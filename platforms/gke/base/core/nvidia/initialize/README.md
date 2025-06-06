# NVIDIA initialize

- Set environment variables.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh" "${ACP_REPO_DIR}/platforms/gke/base/_shared_config"
  ```

- Add NGC API key secret version using **one** of the following:

  - [Generate an API key](https://org.ngc.nvidia.com/setup) with permissions for
    **NGC Catalog**.

  **Console**

  ```
  echo -e "\n${nvidia_ncg_api_key_secret_manager_secret_name} versions URL: https://console.cloud.google.com/security/secret-manager/secret/${nvidia_ncg_api_key_secret_manager_secret_name}/versions?project=${nvidia_ncg_api_key_secret_manager_project_id}\n"
  ```

  **`gcloud`**

  ```
  unset HISTORY
  NGC_API_KEY="<api_key>"
  echo ${NGC_API_KEY} | gcloud secrets versions add ${nvidia_ncg_api_key_secret_manager_secret_name} \
  --data-file=- \
  --project=${nvidia_ncg_api_key_secret_manager_project_id}
  ```
