# Online inference with GPUs on Google Cloud

This reference architecture implements online inferencing using GPUs on Google
Cloud. This reference architecture builds on top of the
[Inference Platform reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md).

## Best practices for online inferencing on Google Cloud

### Accelerator selection

### Storage solution selection

### Model selection

### Observability

### Scalability

### Cost optimization

## Architecture

## Roles and permissions

## Deploy the reference architecture

This reference architecture builds on top of the infrastructure that the
[Inference Platform reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
provides, and follows the best practices that the reference implementations
establishes.

Before deploying the reference architecture described in this document, you
deploy one instance of the Inference Platform reference implementation. The
reference architecture supports deploying multiple instances of the reference
architecture in the same project. To deploy the reference architecture, you do
the following:

1.  To enable deploying resources for the online inference reference
    architecture, initialize the following configuration variables in
    `platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/inference-ref-arch.auto.tfvars`:

    ```hcl
    ira_use_case_flavor = "ira-online-gpu"
    ```

1.  Deploy an instance of the Inference Platform reference implementation. For
    more information about how to deploy an instance of the reference
    architecture, see
    [Inference Platform reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)

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

1.  Initialize the configuration variables to set the name of the Cloud Storage
    bucket where the model will be downloaded in
    `platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/base/ira-model-config.env`:

    ```shell
    IRA_BUCKET_NAME=<IRA_BUCKET_NAME>
    MAX_MODEL_LEN=<MAX_MODEL_LEN>
    MODEL_ID=<MODEL_ID>
    TENSOR_PARALLEL_SIZE=<TENSOR_PARALLEL_SIZE>
    ```

    Where:

    - `<IRA_BUCKET_NAME>` is the name of the Cloud Storage bucket where the
      model will be downloaded.
    - `<MODEL_ID>` is the fully qualified model identifier.

      - For Gemma, the fully qualified model identifier is:
        `google/gemma-3-27b-it`
      - For Llama 4, the fully qualified model identifier is:
        `meta-llama/Llama-4-Scout-17B-16E-Instruct`
      - For Llama 3.3 70B, the fully qualified model identifier is:
        `meta-llama/Llama-3.3-70B-Instruct`

    - `<TENSOR_PARALLEL_SIZE>` is the number of GPUs necessary to run the model.
      For more information, see
      [Distributed inference and serving](https://docs.vllm.ai/en/latest/serving/distributed_serving.html#distributed-inference-and-serving).

      - For Gemma 3 27B:

        - NVIDIA H100: at least 1

      - For Llama 3.3 70B:

        - NVIDIA H100: at least 4

      - For Llama 4 Scout:

        - NVIDIA H100: at least 8

    - `<MAX_MODEL_LEN>` is the maximum context length. For more information, see
      [vLLM Engine arguments](https://docs.vllm.ai/en/latest/serving/engine_args.html).

      - For Llama 3.3 70B:

        - NVIDIA H100: `131072`

      - For Llama 4 Scout:

        - NVIDIA H100: `1000000`

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

1.  Delete the model downloader job:

    ```shell
    kubectl delete job transfer-model-to-gcs
    ```

    Note: the model downloader job has `ttlSecondsAfterFinished` configured, so
    the command to delete it might return an error if you wait for more than
    `ttlSecondsAfterFinished` seconds after the job completes because GKE
    automatically deletes it to reclaim resources.

1.  Delete the model downloader cache PersistentVolumeClaim:

    ```shell
    kubectl delete pvc transfer-model-to-gcs
    ```

## Deploy the online inference workload

1.  Deploy the online inference workload in the GKE cluster:

    ```shell
    kubectl apply -k platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu-<GPU_TYPE>-<MODEL_NAME>
    ```

    Where:

    - `<GPU_TYPE>` is the GPU type. Valid values are:

      - `h100`

    - `MODEL_NAME` is the name of the model to deploy. Valid values are:

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
