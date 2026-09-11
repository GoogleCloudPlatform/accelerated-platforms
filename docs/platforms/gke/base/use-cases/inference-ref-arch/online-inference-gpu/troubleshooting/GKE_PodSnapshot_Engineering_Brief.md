# GKE PodSnapshot Technical Briefing & Test Diagnostics

## 1. Environment & Version Matrix

| Component                      | Specification                            |
| :----------------------------- | :--------------------------------------- |
| **GCP Project**                | `accelerated-platforms-dev`              |
| **GKE Cluster**                | `acp-uc1-a` (`us-central1`)              |
| **Release Channel**            | `RAPID`                                  |
| **GKE Control Plane Version**  | `v1.36.3-gke.1767000`                    |
| **GKE GPU Node Version (NAP)** | `v1.36.3-gke.1767000`                    |
| **Node OS Image**              | Container-Optimized OS from Google (COS) |
| **Host Linux Kernel**          | `6.12.94+ (amd64)`                       |
| **Container Runtime**          | `containerd://2.2.3`                     |
| **NVIDIA GPU Driver Channel**  | `latest` (`580.126.20`)                  |
| **Workload Sandbox**           | `runtimeClassName: gvisor`               |

### Tested Machine Configurations

- **Hopper**: `a3-highgpu-1g`
  - GPU: 1x NVIDIA H100 80GB SXM5 (HBM3)
  - CPU & Host RAM: 26 vCPUs, 234 GiB DRAM
  - Compute Class: `gpu-h100-80gb-high-x1`
- **Blackwell**: `g4-standard-48`
  - GPU: 1x NVIDIA RTX Pro 6000 Server Edition (96GB GDDR7)
  - CPU & Host RAM: 48 vCPUs, 192 GiB DRAM
  - Accelerator Label: `cloud.google.com/gke-accelerator: "nvidia-rtx-pro-6000"`

---

## 2. Workload & Snapshot Manifests

### A. Deployment Manifest (`vllm-h100-gemma-4-31b-it.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-h100-gemma-4-31b-it
  namespace: acp-uc1-a-online-gpu
  annotations:
    podsnapshot.gke.io/restore-from-policy: vllm-snapshot-policy-h100-gemma-4-31b-it
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: vllm-h100-gemma-4-31b-it
  template:
    metadata:
      labels:
        app: vllm-h100-gemma-4-31b-it
        ai.gke.io/model: gemma-4-31b-it
    spec:
      runtimeClassName: gvisor
      serviceAccountName: acp-uc1-a-online-gpu
      nodeSelector:
        cloud.google.com/compute-class: "gpu-h100-80gb-high-x1"
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      containers:
        - name: inference-server
          image: docker.io/vllm/vllm-openai:v0.26.0
          imagePullPolicy: Always
          command:
            - python3
            - -m
            - vllm.entrypoints.openai.api_server
          args:
            - --model=gs://accelerated-platforms-dev-acp-uc1-a-hf-hub-models/google/gemma-4-31b-it
            - --served-model-name=google/gemma-4-31b-it
            - --load-format=runai_streamer
            - --model-loader-extra-config={"distributed":true}
            - --tensor-parallel-size=1
            - --trust-remote-code
            - --max-model-len=8192
            - --gpu-memory-utilization=0.90
            - --port=8000
          env:
            - name: VLLM_LOGGING_LEVEL
              value: "INFO"
            - name: LD_LIBRARY_PATH
              value: "${LD_LIBRARY_PATH}:/usr/local/nvidia/lib64"
            - name: VLLM_XLA_CACHE_PATH
              value: "/data"
          ports:
            - name: http
              containerPort: 8000
          resources:
            limits:
              nvidia.com/gpu: "1"
              memory: 140Gi
            requests:
              nvidia.com/gpu: "1"
              memory: 140Gi
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 60
            periodSeconds: 10
            timeoutSeconds: 1
            failureThreshold: 600
          volumeMounts:
            - name: dev-shm
              mountPath: /dev/shm
      volumes:
        - name: dev-shm
          emptyDir:
            medium: Memory
```

> **Note on RTX Pro 6000:** The manifest is identical with the exception of the
> node selector:
>
> ```yaml
> nodeSelector:
>   cloud.google.com/gke-accelerator: "nvidia-rtx-pro-6000"
> ```

---

### B. PodSnapshot Storage Config & Policy

```yaml
apiVersion: podsnapshot.gke.io/v1
kind: PodSnapshotStorageConfig
metadata:
  name: vllm-snapshot-config-h100-gemma-4-31b-it
  namespace: acp-uc1-a-online-gpu
spec:
  snapshotStorageConfig:
    gcs:
      bucket: accelerated-platforms-dev-acp-uc1-a-hf-hub-models
---
apiVersion: podsnapshot.gke.io/v1
kind: PodSnapshotPolicy
metadata:
  name: vllm-snapshot-policy-h100-gemma-4-31b-it
  namespace: acp-uc1-a-online-gpu
spec:
  selector:
    matchLabels:
      app: vllm-h100-gemma-4-31b-it
  snapshotScope: whole-pod
  storageConfigName: vllm-snapshot-config-h100-gemma-4-31b-it
  triggerConfig:
    type: manual
    postCheckpoint: stop
```

---

### C. Manual Trigger Object

```yaml
apiVersion: podsnapshot.gke.io/v1
kind: PodSnapshotManualTrigger
metadata:
  name: trigger-snapshot-h100-gemma-4
  namespace: acp-uc1-a-online-gpu
spec:
  podName: vllm-h100-gemma-4-31b-it-7665b8c96d-cmrvr
```

---

## 3. Observed Behavior & Kernel Error Diagnostics

### Host Execution Trace

When `PodSnapshotManualTrigger` is applied, the pod snapshot agent delegates
checkpointing to `runsc`:

```bash
/home/containerd/usr/local/sbin/runsc \
  --root=/run/containerd/runsc/k8s.io \
  --debug-log=/proc/9155/fd/18 \
  checkpoint \
  --compression=none \
  --exclude-committed-zero-pages=true \
  --direct=true \
  --cuda-checkpoint-path=/usr/local/nvidia/bin/gvisor-cuda-cr \
  --leave-running=false \
  --image-path=/var/lib/podsnapshots/a006c83b-6b2d-465e-bffd-20637590be24 \
  <container-id>
```

### Upstream Open Kernel Driver Assertion (`dmesg`)

During channel stop / freeze, the host kernel encounters an assertion failure
inside the NVIDIA open kernel driver (`580.126.20`) on **both Hopper and
Blackwell**:

```text
[ 1885.514850] NVRM: nvAssertOkFailedNoLog: Assertion failed: Requested object not found [NV_ERR_OBJECT_NOT_FOUND] (0x00000057) returned from pRmApi->Control(pRmApi, RES_GET_CLIENT_HANDLE(pKernelChannel), RES_GET_HANDLE(pKernelChannel), NVA06F_CTRL_CMD_STOP_CHANNEL, &stopChannelParams, sizeof(stopChannelParams)) @ nv_gpu_ops.c:10963
```

### Resulting Hang

1. `runsc-checkpointgofer` uploads initial checkpoint metadata to GCS:
   - `checkpoint.img`: **12.35 MiB**
   - `pages_meta.img`: **3.43 MiB**
2. Because `NVA06F_CTRL_CMD_STOP_CHANNEL` returns error code `0x57`, channel
   quiescence fails.
3. `runsc-checkpointgofer` (PID 52161) and `runsc checkpoint` (PID 52147) block
   indefinitely in:
   - `/proc/52161/wchan`: `futex_wait_queue`
   - `/proc/52147/wchan`: `do_sys_poll`
4. The snapshot status remains indefinitely in `AwaitingCheckpoint` with
   condition `InProgress`.
