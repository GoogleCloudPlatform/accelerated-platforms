# Online inference with GPUs on Google Cloud

This reference architecture implements online inferencing using GPUs on Google
Cloud. This reference architecture builds on top of the
[inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).

## Roles and permissions

You can choose between Project Owner access or granular access for more
fine-tuned permissions.

### Option 1: Project Owner role

Your account will have full administrative access to the project.

- `roles/owner`: Full administrative access to the project
  ([Project Owner role](https://cloud.google.com/iam/docs/understanding-roles#resource-manager-roles))

### Option 2: Granular Access

Your account needs to be assigned the following roles to limit access to
required resources:

- `roles/artifactregistry.admin`: Grants full administrative access to Artifact
  Registry, allowing management of repositories and artifacts.
- `roles/browser`: Provides read-only access to browse resources in a project.
- `roles/compute.networkAdmin`: Grants full control over Compute Engine network
  resources.
- `roles/container.clusterAdmin`: Provides full control over Google Kubernetes
  Engine (GKE) clusters, including creating and managing clusters.
- `roles/gkehub.editor`: Grants permission to manage GKE Hub features.
- `roles/iam.serviceAccountAdmin`: Grants full control over managing service
  accounts in the project.
- `roles/resourcemanager.projectIamAdmin`: Allows managing IAM policies and
  roles at the project level.
- `roles/servicenetworking.serviceAgent`: Allows managing service networking
  configurations.
- `roles/serviceusage.serviceUsageAdmin`: Grants permission to enable and manage
  services and APIs for a project.

## Deploy the reference architecture

This reference architecture builds on top of the infrastructure that the
[inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
provides, and follows the best practices that the reference implementations
establishes. To deploy this reference architecture, do the following:

1.  Enable deployment of the the online inference example resources by setting
    the following configuration variables in
    `platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/inference-ref-arch.auto.tfvars`:

    ```hcl
    ira_use_case_flavor = "ira-online-gpu"
    ```

1.  Deploy the
    [inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)

    After you deploy the reference architecture instances, continue following
    this document.

## Download the model to Cloud Storage

1.  Take note of the name of the Cloud Storage bucket where the model will be
    downloaded:

    ```shell
    terraform -chdir="${ACP_PLATFORM_USE_CASE_DIR}/terraform/cloud_storage" output -json ira_google_storage_bucket_names
    ```

    The output might contain multiple bucket names. The name of the bucket where
    the model will be downloaded ends with the `ira-model` suffix.

1.  Set the environment configuration variables for the model downloader in
    `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/base/ira-model-config.env`:

    ```shell
    IRA_BUCKET_NAME=<IRA_BUCKET_NAME>
    MODEL_ID=<MODEL_ID>
    ```

    Where:

    - `<IRA_BUCKET_NAME>` is the name of the Cloud Storage bucket where the
      model will be downloaded.

    - `<MODEL_ID>` is the fully qualified model identifier.

      - For Gemma 3 27B, the fully qualified model identifier is:
        `google/gemma-3-27b-it`
      - For Llama 4, the fully qualified model identifier is:
        `meta-llama/Llama-4-Scout-17B-16E-Instruct`
      - For Llama 3.3 70B, the fully qualified model identifier is:
        `meta-llama/Llama-3.3-70B-Instruct`

1.  [Generate a Hugging Face token](https://huggingface.co/docs/hub/security-tokens).
    Make sure to grant the
    `Read access to contents of all public gated repos you can access`
    permission to the Hugging Face token.

1.  Store the Hugging Face token in
    `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/base/hugging-face-token.env`:

    ```shell
    HUGGING_FACE_TOKEN=<HUGGING_FACE_TOKEN>
    ```

    Where:

    - `<HUGGING_FACE_TOKEN>` is the Hugging Face token.

    If the
    `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/base/hugging-face-token.env`
    file doesn't exist, create it.

1.  Get access to the model by signing the consent agreement:

    - For Gemma:

      1. Access the
         [model consent page on Kaggle.com](https://www.kaggle.com/models/google/gemma).

      1. Verify consent using your Hugging Face account.

      1. Accept the model terms.

    - For Llama:

      1. Accept the model terms on Hugging Face

1.  Deploy the model downloader in the GKE cluster:

    ```shell
    kubectl apply -k platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download
    ```

1.  Wait for the model downloader to download the model:

    ```shell
    watch --color --interval 5 --no-title \
    "kubectl get job/transfer-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'"
    ```

    The output is similar to the following:

    ```text
    NAME                    STATUS     COMPLETIONS   DURATION   AGE
    transfer-model-to-gcs   Complete   1/1           33m        3h30m
    ```

1.  Delete the model downloader:

    ```shell
    kubectl delete -k platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download
    ```

    Note: the model downloader job has `ttlSecondsAfterFinished` configured, so
    the command to delete it might return an error if you wait for more than
    `ttlSecondsAfterFinished` seconds after the job completes because GKE
    automatically deletes it to reclaim resources. In this case, the output
    looks like the following:

    ```text
    Error from server (NotFound): jobs.batch "transfer-model-to-gcs" not found
    ```

## Deploy the online inference workload

1.  Deploy the online inference workload in the GKE cluster:

    ```shell
    kubectl apply -k platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-<GPU_TYPE>-<MODEL_NAME>
    ```

    Where:

    - `<GPU_TYPE>` is the GPU type. Valid values are:

      - `l4` (only for `gemma3-27b`)
      - `h100`
      - `h200`

    - `MODEL_NAME` is the name of the model to deploy. Valid values are:

      - `gemma3-27b`
      - `llama3`
      - `llama4-scout`

    Ensure that you have enough quota in your project to provision the selected
    GPU type. For more information, see about viewing GPU quotas, see
    [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

    The Kubernetes manifests in the
    `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-<GPU_TYPE>-<MODEL_NAME>`
    directories include
    [Inference Quickstart recommendations](https://cloud.google.com/kubernetes-engine/docs/how-to/machine-learning/inference-quickstart).

1.  Wait for the Pod to be ready:

    ```shell
    watch --color --interval 5 --no-title \
      "kubectl get deployment/vllm-h100 | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
    ```

## Next steps

## Destroy the reference architecture

- Teardown the
  [inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md#teardown)

## Troubleshooting

This section describes common issues and troubleshooting steps.

### Node provisioning

- If the online inference workload Pod doesn't trigger a node scale up, and
  remains in pending state, check if its events contain something like:

  ```
  kubectl describe pod <POD_NAME>
  ```

  Where:

  - `<POD_NAME>` is the name of the Pod running the online inference workload.
    `<POD_NAME>` starts with the `vllm-` prefix.

  In case this happens, try deleting the Pod after the ProvisioningRequest is
  reported with the status of `Provisioned=True`. To get the list of ``s, run
  the following command:

  ```shell
  kubectl get provisioningrequest.autoscaling.x-k8s.io
  ```

  The output is similar to the following:

  ```text
  NAME        ACCEPTED   PROVISIONED   FAILED   AGE
  vllm-h100   True       True                   10m
  ```

  To delete the online inference workload pod, run the following command:

  ```shell
  kubectl delete pod <POD_NAME>
  ```

  Where:

  - `<POD_NAME>` is the name of the Pod running the online inference workload.
    `<POD_NAME>` starts with the `vllm-` prefix.

  Google Kubernetes Engine (GKE) takes care of recreating the Pod.
