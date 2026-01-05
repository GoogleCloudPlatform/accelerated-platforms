# Kaggle initialize developer's guide

## How to use this terraservice in the platform

- Set environment variables.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/_shared_config/scripts/set_environment_variables.sh"
  ```

  ```
  export WORKLOAD_NAMESPACE="<kubernetes_namespace>"
  export WORKLOAD_KUBERNETES_SERVICE_ACCOUNT="<kubernetes_service_account>"
  ```

- Give the Kubernetes service account IAM permissions.

  **API token**

  ```shell
  cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")
  gcloud secrets add-iam-policy-binding ${kaggle_api_token_secret_manager_secret_name} \
  --member=principal://iam.googleapis.com/projects/${cluster_project_number}/locations/global/workloadIdentityPools/${cluster_project_id}.svc.id.goog/subject/ns/${WORKLOAD_NAMESPACE}/sa/${WORKLOAD_KUBERNETES_SERVICE_ACCOUNT} \
  --project=${kaggle_secret_manager_project_id} \
  --role=roles/secretmanager.secretAccessor
  ```

  **Bucket**

  ```shell
  cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")
  gcloud storage buckets add-iam-policy-binding ${kaggle_bucket_name} \
  --member=principal://iam.googleapis.com/projects/${cluster_project_number}/locations/global/workloadIdentityPools/${cluster_project_id}.svc.id.goog/subject/ns/${WORKLOAD_NAMESPACE}/sa/${WORKLOAD_KUBERNETES_SERVICE_ACCOUNT} \
  --project=${kaggle_bucket_project_id} \
  --role=${cluster_gcsfuse_user_role}
  ```

- Create the `SecretProviderClass`es in the workload's namespace.

  ```shell
  envsubst <${ACP_REPO_DIR}/platforms/gke/base/core/kaggle/initialize/templates/secretproviderclass-kaggle.tftpl.yaml | kubectl --namespace=${WORKLOAD_NAMESPACE} apply -f -
  ```

- Add the secret volume to the template spec.

  ```yaml
  spec:
  ...
    template:
    ...
      spec:
      ...
        volumes:
          - csi:
              driver: secrets-store-gke.csi.k8s.io
              readOnly: true
              volumeAttributes:
                secretProviderClass: kaggle-api-token
            name: kaggle-api-token
  ```

- Add the bucket volume to the template spec.

  ```yaml
  spec:
    ...
      template:
      ...
        spec:
        ...
          volumes:
            - csi:
                driver: gcsfuse.csi.storage.gke.io
                volumeAttributes:
                  bucketName: ${kaggle_bucket_name}
                  mountOptions: "file-cache:cache-file-for-range-read:true,file-cache:enable-parallel-downloads:true,file-cache:max-size-mb:-1,file-system:kernel-list-cache-ttl-secs:-1,gcs-connection:client-protocol:grpc,implicit-dirs,metadata-cache:stat-cache-max-size-mb:-1,metadata-cache:ttl-secs:-1,metadata-cache:type-cache-max-size-mb:-1"
              name: kaggle-bucket
  ```

### Standard `kaggle` CLI support

- Add the volume mounts to the container.

  ```yaml
  spec:
  ...
    template:
    ...
      spec:
      ...
        containers:
        ...
          volumeMounts:
            - mountPath: /var/run/secrets/kaggle.co
              name: kaggle-api-token
            - mountPath: /models
              name: kaggle-bucket

  ```

- Set the `HF_TOKEN_PATH` environment variable

  ```yaml
  spec:
  ...
    template:
    ...
      spec:
      ...
        containers:
        ...
          env:
            - name: KAGGLE_API_TOKEN
              value: /var/run/secrets/kaggle.co/api-token
  ```

### Non-standard `kaggle` support

For images that don't support the standard `kaggle` CLI environment variables
you will need to determine the correct place to mount the token and/or if a
corresponding environment variable needs to be set. This might also require
modifying the `SecretProviderClass` to mount the token at an additional path.
