# Environment and Deployment Details for Gemma 4 31B on H100

Below are the details requested regarding the environment setup for testing `google/gemma-4-31b-it` on NVIDIA H100 80GB (Hopper) on GKE.

## 1. Environment Details

**GKE Cluster Version:** `v1.36.3-gke.1767000`
**Node Accelerator:** `nvidia-h100-80gb-hbm3.1`
**Node Machine Family:** `a3`
**Node Machine Type:** `a3-highgpu-1g`
**GKE GPU Driver Version:** `580.126.20`

## 2. Pod and Deployment Configuration

The following is the exact deployment YAML specification used to run the vLLM pod on the H100 node. Notably, it utilizes `runai_streamer` for fast loading and implements a cooperative entrypoint hook (`/scripts/entrypoint_hook.py`) to properly coordinate workload-triggered snapshots.

**Note on GPU Memory:** `GPU_MEMORY_UTILIZATION` is set to `0.80` (64GB out of 80GB VRAM).

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-h100-gemma-4-31b-it
  namespace: acp-uc1-a-online-gpu
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-h100-gemma-4-31b-it
  template:
    metadata:
      labels:
        ai.gke.io/model: gemma-4-31b-it
        app: vllm-h100-gemma-4-31b-it
    spec:
      containers:
      - name: inference-server
        image: docker.io/vllm/vllm-openai:v0.26.0
        command:
        - python3
        - /scripts/entrypoint_hook.py
        args:
        - --gpu-memory-utilization=0.80
        - --model=gs://$(BUCKET_NAME)/$(MODEL_ID)
        - --served-model-name=$(MODEL_ID)
        - --load-format=runai_streamer
        - --model-loader-extra-config={"distributed":true}
        - --tensor-parallel-size=1
        - --trust-remote-code
        - --max-model-len=2048
        env:
        - name: LD_LIBRARY_PATH
          value: ${LD_LIBRARY_PATH}:/usr/local/nvidia/lib64
        - name: VLLM_XLA_CACHE_PATH
          value: /data
        # Note: BUCKET_NAME and MODEL_ID are injected via ConfigMap
        ports:
        - containerPort: 8000
          name: metrics
          protocol: TCP
        readinessProbe:
          failureThreshold: 6000
          httpGet:
            path: /health
            port: 8000
            scheme: HTTP
          initialDelaySeconds: 60
          periodSeconds: 10
          successThreshold: 1
          timeoutSeconds: 1
        resources:
          limits:
            memory: 140Gi
            nvidia.com/gpu: "1"
          requests:
            memory: 140Gi
            nvidia.com/gpu: "1"
        volumeMounts:
        - mountPath: /scripts
          name: entrypoint-hook
        - mountPath: /dev/shm
          name: dev-shm
      nodeSelector:
        cloud.google.com/compute-class: gpu-h100-80gb-high-x1
      runtimeClassName: gvisor
      volumes:
      - configMap:
          defaultMode: 420
          name: vllm-entrypoint-hook-h100
        name: entrypoint-hook
      - emptyDir:
          medium: Memory
        name: dev-shm
```

## 3. Empirical Snapshot and Restore Metrics

The empirical timing test was completed with the following results:

* **Cold Start (Model Pull & Compilation):** **3 minutes and 45 seconds** (Weight loading took 61.83 seconds via Run:ai Streamer).
* **Snapshot Time:** **FAILED** (Deadlocked in `AwaitingCheckpoint`).
* **Warm Restore (from PodSnapshot):** N/A.

**Conclusion on Workload Triggers:**
Despite utilizing a cooperative workload trigger that properly flushed CUDA queues (`torch.cuda.synchronize()` and `torch.cuda.empty_cache()`), the checkpointing process on the H100 node still encountered the exact same upstream kernel driver assertion failure (`NVRM: nvAssertOkFailedNoLog: Assertion failed: Requested object not found [NV_ERR_OBJECT_NOT_FOUND] (0x00000057)`). This confirms that the channel quiescence defect in driver version `580.126.20` is not mitigated by the workload trigger method.
