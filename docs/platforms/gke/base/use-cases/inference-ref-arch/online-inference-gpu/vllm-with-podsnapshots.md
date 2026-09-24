# Online inference using vLLM with GKE Pod snapshots and GPUs on Google Kubernetes Engine (GKE)

This document implements online inference using GPUs on Google Kubernetes Engine
(GKE) with
[GKE Pod snapshots](https://cloud.google.com/kubernetes-engine/docs/concepts/pod-snapshots),
which restore new vLLM replicas from a memory image of a replica that has
already finished starting up.

A vLLM replica spends minutes starting up even after its weights are loaded: it
profiles memory, compiles kernels, captures CUDA graphs, and allocates its KV
cache. That work is identical on every replica. A Pod snapshot captures the
result once, with the weights already in GPU memory, and every later replica
resumes from it instead of repeating it.

| Model, GPU                     | Cold start   | Restore from snapshot |
| ------------------------------ | ------------ | --------------------- |
| Llama 3.1 8B, NVIDIA L4        | 561 s        | **41 s**              |
| Llama 3.1 8B, NVIDIA H100 80GB | 163 s        | **3 s**               |
| Gemma 4 31B, NVIDIA H100 80GB  | 234 to 265 s | **3 to 5 s**          |

This example is built on top of the
[GKE Inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/README.md).
For the architecture, the design rationale, and guidance on when to use Pod
snapshots, see the
[GKE Pod snapshots inference reference architecture](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md).

## Choose a path

This guide provides two paths. Both use the same cluster preparation and the
same measurement steps.

| Path                                                                                                        | Model, GPU                    | Weight loader              | What it demonstrates                                                       |
| ----------------------------------------------------------------------------------------------------------- | ----------------------------- | -------------------------- | -------------------------------------------------------------------------- |
| [A: Pod snapshots](#path-a-pod-snapshots-on-nvidia-l4)                                                      | Llama 3.1 8B, NVIDIA L4       | Hugging Face Hub, eager    | The snapshot mechanism on the smallest, most widely available GPU          |
| [B: Pod snapshots and Run:ai Model Streamer](#path-b-pod-snapshots-and-runai-model-streamer-on-nvidia-h100) | Gemma 4 31B, NVIDIA H100 80GB | Run:ai Model Streamer, GCS | The production composition: a fast cold start, then near-instant scale-out |

Path A is the quickest way to see a restore. Path B is the pattern to adopt when
you already serve with the
[Run:ai Model Streamer](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-with-runai-model-streamer.md)
and want scale-out to stop repeating the cold start.

## Before you begin

- The
  [GKE Inference reference implementation](/platforms/gke/base/use-cases/inference-ref-arch/terraform/README.md)
  is deployed and configured.

- The cluster is running GKE version 1.35.3-gke.1234000 or later.

- Get access to the model.

  - Accept the terms of the license on the Hugging Face model page.
    - Path A:
      [**meta-llama/Llama-3.1-8B-Instruct**](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
    - Path B:
      [**google/gemma-4-31b-it**](https://huggingface.co/google/gemma-4-31b-it)

- Ensure your
  [Hugging Face Hub **Read** access token](/platforms/gke/base/core/huggingface/initialize/README.md)
  has been added to Secret Manager.

## Create and configure the Google Cloud resources

- Deploy the online GPU resources.

  ```shell
  export TF_PLUGIN_CACHE_DIR="${ACP_REPO_DIR}/.terraform.d/plugin-cache"
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init && \
  terraform plan -input=false -out=tfplan && \
  terraform apply -input=false tfplan && \
  rm tfplan
  ```

## Prepare the cluster for Pod snapshots

These steps are performed once per cluster.

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Enable Pod snapshots on the cluster.

  ```shell
  gcloud beta container clusters update ${cluster_name} \
  --enable-pod-snapshots \
  --location=${cluster_region} \
  --project=${cluster_project_id}
  ```

  The workload requests `runtimeClassName: gvisor`, and node auto-provisioning
  creates GKE Sandbox GPU nodes for it through the custom compute class. No node
  pool needs to be created by hand.

- Disable gVisor core tagging on sandbox nodes.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/node-setup"
  ```

  This is a workaround. On the GPU sandbox nodes used here, the node enables
  gVisor core tagging, and every sandboxed Pod then fails to start with
  `FailedCreatePodSandBox` and
  `Failed read current core tags: prctl(PR_SCHED_CORE, ...) (errno=3)`. The
  DaemonSet disables the setting on each sandbox node as it joins the cluster,
  and restarts containerd on that node. See
  [`gvisor-disable-core-tags.yaml`](/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/node-setup/gvisor-disable-core-tags.yaml).

- Allow the Pod snapshot controller to delete snapshots from the model bucket.

  Snapshots are stored in the model bucket created by the reference
  implementation. The workload's Kubernetes service account can already read and
  write that bucket. Deleting a snapshot, however, is performed by the Pod
  snapshot controller, which acts as the GKE service agent and needs its own
  grant, scoped here to the one bucket.

  ```shell
  cluster_project_number=$(gcloud projects describe ${cluster_project_id} --format="value(projectNumber)")
  gcloud projects add-iam-policy-binding ${cluster_project_id} \
  --member="serviceAccount:service-${cluster_project_number}@container-engine-robot.iam.gserviceaccount.com" \
  --role="roles/storage.objectUser" \
  --condition="expression=resource.name.startsWith(\"projects/_/buckets/${huggingface_hub_models_bucket_name}\"),title=podsnapshot_restrict_to_bucket"
  ```

  Without this grant, deleting a `PodSnapshot` does not complete and its data
  stays in the bucket.

> [!NOTE]
>
> The model bucket uses the Cloud Storage default soft delete policy of seven
> days. Google recommends
> [disabling soft delete](https://cloud.google.com/kubernetes-engine/docs/how-to/pod-snapshots-prepare#store-snapshots)
> for snapshot storage, because snapshots are uploaded as parallel composite
> uploads and soft-deleted objects are billed until they expire. Disabling it on
> this bucket also removes soft delete protection for the model weights. See
> [Storage lifecycle and permissions](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/vllm-podsnapshots-reference-architecture.md#storage-lifecycle-and-permissions)
> for the tradeoff.

## Path A: Pod snapshots on NVIDIA L4

This path loads Llama 3.1 8B directly from the Hugging Face Hub, so no model
download job is required.

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
  ```

- Set the variant and the served model name.

  ```shell
  export VLLM_VARIANT="l4-llama-3-1-8b-instruct"
  export SERVED_MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct"
  ```

  Ensure that you have enough quota in your project to provision NVIDIA L4 GPUs.
  For more information about viewing GPU quotas, see
  [Allocation quotas: GPU quota](https://cloud.google.com/compute/resource-usage#gpu_quota).

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/${VLLM_VARIANT}"
  ```

Continue with [Capture the snapshot](#capture-the-snapshot).

## Path B: Pod snapshots and Run:ai Model Streamer on NVIDIA H100

This path streams Gemma 4 31B from Cloud Storage with the Run:ai Model Streamer,
so the weights must be staged in the model bucket first.

### Download the model to Cloud Storage

- Set the model.

  ```shell
  export HF_MODEL_ID="google/gemma-4-31b-it"
  ```

- Source the environment configuration.

  ```shell
  source "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/_shared_config/scripts/set_environment_variables.sh"
  ```

- Configure and deploy the model download job.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/configure_huggingface.sh" && \
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

- Watch the model download job until it is complete.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${huggingface_hub_downloader_kubernetes_namespace_name} get job/${HF_MODEL_ID_HASH}-hf-model-to-gcs | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e 'Complete'"
  ```

  When the job is complete, you will see the following:

  ```text
  NAME                       STATUS     COMPLETIONS   DURATION   AGE
  XXXXXXXX-hf-model-to-gcs   Complete   1/1           ###        ###
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Delete the model download job.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/model-download/huggingface"
  ```

### Deploy the inference workload

- Configure the deployment.

  ```shell
  "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/configure_vllm_podsnapshot.sh"
  ```

- Set the variant and the served model name.

  ```shell
  export VLLM_VARIANT="h100-gemma-4-31b-it"
  export SERVED_MODEL_NAME="google/gemma-4-31b-it"
  ```

  Ensure that you have enough quota in your project to provision NVIDIA H100
  80GB GPUs.

- Deploy the inference workload.

  ```shell
  kubectl apply --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/${VLLM_VARIANT}"
  ```

## Capture the snapshot

The deployment includes a `PodSnapshotPolicy` that checkpoints the first healthy
replica and restores every replica scheduled after the snapshot is available. No
command is needed to create the snapshot, but each step is worth observing.

- Watch the cold-start replica until it is ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-fast-restore-${VLLM_VARIANT} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '1/1     1            1'"
  ```

  You can press `CTRL`+`c` to terminate the watch.

- Confirm that the workload triggered the checkpoint.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs \
  deployment/vllm-fast-restore-${VLLM_VARIANT} | grep -e "Model loading took" -e "\[podsnapshot\]"
  ```

  The output is similar to the following:

  ```text
  [podsnapshot] Waiting for the model server to become healthy...
  (EngineCore pid=133) INFO ... Model loading took 14.99 GiB memory and 362.459344 seconds
  [podsnapshot] Model server is healthy.
  [podsnapshot] Triggering the cooperative checkpoint...
  [podsnapshot] Checkpoint triggered successfully.
  ```

- Watch the snapshot until it is ready.

  ```shell
  watch --color --interval 15 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots"
  ```

  The snapshot is ready when its status is `AllSnapshotsAvailable`. You can
  press `CTRL`+`c` to terminate the watch.

> [!IMPORTANT]
>
> Capturing a snapshot takes minutes. Path A produces a snapshot of about 20 GB
> in about four minutes. Path B produces a snapshot of about 73 GB in 11 to 15
> minutes. For most of that time the snapshot objects are not visible in the
> bucket, because the largest object is written last. This is expected.

## Measure the restore

- Record when the cold-start replica was scheduled and when it became ready.

  ```shell
  COLD_POD=$(kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pods \
  --selector=app=vllm-fast-restore-${VLLM_VARIANT} --output=jsonpath='{.items[0].metadata.name}')

  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pod ${COLD_POD} \
  --output=jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.lastTransitionTime}{"\n"}{end}'
  ```

- Scale out to two replicas.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} scale \
  deployment/vllm-fast-restore-${VLLM_VARIANT} --replicas=2
  ```

- Watch the deployment until both replicas are ready.

  ```shell
  watch --color --interval 5 --no-title \
  "kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get deployment/vllm-fast-restore-${VLLM_VARIANT} | GREP_COLORS='mt=01;92' egrep --color=always -e '^' -e '2/2     2            2'"
  ```

  You can press `CTRL`+`c` to terminate the watch.

  If no free GPU node is available, node auto-provisioning creates one before
  the Pod is scheduled. That time is not part of the restore. In the Path A
  measurement, the new Pod waited 131 seconds for a new node, and then went from
  `PodScheduled` to `Ready` in 41 seconds. The cold-start replica took 561
  seconds for the same interval.

- Confirm the new replica was restored rather than started cold.

  A restored replica does no startup work, so none of the model loading markers
  appear in its logs.

  ```shell
  RESTORED_POD=$(kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pods \
  --selector=app=vllm-fast-restore-${VLLM_VARIANT} --output=jsonpath='{.items[*].metadata.name}' \
  | tr ' ' '\n' | grep -v ${COLD_POD})

  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} logs ${RESTORED_POD} \
  | grep -c -e "Model loading took" -e "Starting to load model"
  ```

  ```text
  0
  ```

- Record the restored replica's timings.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get pod ${RESTORED_POD} \
  --output=jsonpath='{range .status.conditions[*]}{.type}{"\t"}{.lastTransitionTime}{"\n"}{end}'
  ```

  A restored Pod has a `PodRestored` condition that a cold-start Pod does not.
  Compare the interval from `PodScheduled` to `Ready` with the cold-start
  replica's.

- Send a request to the restored replica.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} exec ${RESTORED_POD} -- \
  curl --silent http://localhost:8000/v1/chat/completions \
  --header "Content-Type: application/json" \
  --data '{
    "model": "'${SERVED_MODEL_NAME}'",
    "messages": [ { "role": "user", "content": "What is the capital of France? Answer in one sentence." } ],
    "max_tokens": 30
  }' | jq -r '.choices[0].message.content'
  ```

  ```text
  The capital of France is Paris.
  ```

> [!CAUTION]
>
> A snapshot is matched to one pod template. **Any** change to the Deployment's
> pod template, such as a flag, an environment variable, a resource request, or
> the container image, results in a cold start and a new snapshot. Finish tuning
> before you rely on a snapshot.

## Troubleshooting

If you experience any issue while deploying the workload, see the
[Online inference with GPUs Troubleshooting](/docs/platforms/gke/base/use-cases/inference-ref-arch/online-inference-gpu/troubleshooting.md)
guide. The issues below are specific to Pod snapshots.

### Pods fail with `FailedCreatePodSandBox`

If the Pod is scheduled but never starts, and its events show the following,
gVisor core tagging is enabled on the node:

```text
Failed to create pod sandbox: ... cannot create sandbox: cannot read client sync file: waiting for sandbox to start: EOF
```

Confirm that the workaround DaemonSet is running on every sandbox node:

```shell
kubectl --namespace=kube-system get daemonset gvisor-disable-core-tags
```

If it was applied after the node joined, the Pod recovers on its own once
containerd restarts on that node.

### The checkpoint fails with `runsc error: exit status 128`

The most common cause is an NVIDIA driver older than 570. The Pod starts and
serves normally, and only fails when the checkpoint is attempted. Check the
snapshot agent log:

```shell
kubectl --namespace=gke-managed-pod-snapshots logs \
--selector=app=pod-snapshot-agent --container=gps-agent --tail=60
```

```text
failed to load /usr/local/nvidia/bin/gvisor-cuda-cr: no such file or directory
```

GPU checkpointing relies on a helper that is only installed on nodes with driver
570 or newer. Select GPU nodes with a custom compute class, which pins
`driverVersion: latest`, rather than with the `cloud.google.com/gke-accelerator`
label, which is satisfied by the older default driver. The overlays in this
guide already do this.

The same error has also been observed when checkpointing a model served with
`--tensor-parallel-size` greater than 1 on a supported driver. Multi-GPU
snapshots are not supported by this architecture.

### The checkpoint is never triggered

If a replica that was not restored logs the following, the checkpoint device was
never made available to it:

```text
[podsnapshot] /proc/gvisor/checkpoint is absent; skipping checkpoint trigger.
```

Confirm that the `PodSnapshotPolicy` selector matches the Pod labels, and that
the Deployment does not carry a `podsnapshot.gke.io/restore-from-policy`
annotation. That annotation is not required for restore, and on a cold start it
prevents the first snapshot from being captured.

### The checkpoint appears to hang

Snapshot objects are written to the bucket root under the snapshot name, and the
largest object is written last. Check whether it is still growing before you
conclude that the checkpoint has stalled:

```shell
SNAPSHOT=$(kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots \
--output=jsonpath='{.items[-1].metadata.name}')

gcloud storage ls --long "gs://${huggingface_hub_models_bucket_name}/${SNAPSHOT}/**"
```

### Deleting a snapshot hangs

If `kubectl delete podsnapshot` prints `deleted` but then times out, and the
`PodSnapshot` remains with a `deletionTimestamp`, the most likely cause is that
the Pod snapshot controller cannot delete the snapshot data. Confirm that the
GKE service agent has the Storage Object User role on the bucket, as described
in
[Prepare the cluster for Pod snapshots](#prepare-the-cluster-for-pod-snapshots).

## Clean up

- Delete the inference workload.

  ```shell
  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} delete \
  deployment/vllm-fast-restore-${VLLM_VARIANT}
  ```

- Delete the snapshots and confirm their storage was removed.

  ```shell
  SNAPSHOTS=$(kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} get podsnapshots \
  --output=jsonpath="{range .items[?(@.spec.policyName=='vllm-fast-restore-snapshot-policy-${VLLM_VARIANT}')]}{.metadata.name}{' '}{end}")

  kubectl --namespace=${ira_online_gpu_kubernetes_namespace_name} delete podsnapshots ${SNAPSHOTS}

  for snapshot in ${SNAPSHOTS}; do
    gcloud storage ls "gs://${huggingface_hub_models_bucket_name}/${snapshot}/"
  done
  ```

  Each listing reports that no objects matched. Delete the snapshots before the
  policy and storage configuration in the next step. With the default soft
  delete policy, the deleted objects are retained, and billed, for seven days.

- Delete the remaining snapshot resources.

  ```shell
  kubectl delete --ignore-not-found --kustomize "${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/kubernetes-manifests/online-inference-gpu/vllm-podsnapshot-fast-restore/${VLLM_VARIANT}"
  ```

- Destroy the online GPU resources.

  ```shell
  cd ${ACP_REPO_DIR}/platforms/gke/base/use-cases/inference-ref-arch/terraform/online_gpu && \
  rm -rf .terraform/ terraform.tfstate* && \
  terraform init &&
  terraform destroy -auto-approve
  ```
