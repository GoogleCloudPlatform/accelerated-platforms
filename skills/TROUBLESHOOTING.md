# LLM-D Benchmarking Troubleshooting Guide

This guide provides diagnostics and quick fixes for common errors encountered
when running LLM-D benchmarks on the GKE cluster.

---

## 1. Storage & Volume Lock Errors

### Symptom: `Warning FailedAttachVolume (Multi-Attach error)`

- **Cause**: The benchmark namespace PVC (`workload-pvc`) is configured with
  storage class `standard-rwo` (ReadWriteOnce). Only one pod can attach to the
  volume at a time. The benchmark launcher/harness pod cannot start because the
  `access-to-harness-data-workload-pvc` pod is still holding the volume mount
  lock.
- **Diagnostics**:
  ```bash
  kubectl describe pod <harness-pod-name> -n <namespace>
  ```
  Look for `Multi-Attach error for volume` in events.
- **Resolution**: The updated `run_benchmark.sh` handles this automatically. If
  executing manual testing, delete the data-access pod to release the lock:
  ```bash
  kubectl delete pod access-to-harness-data-workload-pvc -n <namespace>
  ```

---

## 2. API Server & Certificate Validation Errors

### Symptom: `SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]`

- **Cause**: GKE regional control plane certificates are registered under the
  public GKE DNS suffix (`*.gke.goog`). Connecting to the GKE control plane via
  its raw internal IP address causes standard SSL client validation to fail.
- **Diagnostics**: Python backtrace shows `urllib3.exceptions.MaxRetryError`
  triggered by `ssl.SSLCertVerificationError`.
- **Resolution**: Configure your local kubeconfig to use the DNS-based GKE
  cluster endpoint. This allows `kubectl` and python clients to verify the SSL
  certificate chain successfully:
  ```bash
  gcloud container clusters get-credentials <YOUR_CLUSTER_NAME> \
    --region=<REGION_OR_ZONE> \
    --dns-endpoint
  ```

---

## 3. Model Serving & Gateway Configuration Errors

### Symptom: `Endpoint verification failed: Endpoint 10.x.x.x:80 did not return expected model`

- **Cause 1: Case Sensitivity**: The served model name from vLLM is lowercased
  (e.g. `qwen/qwen3-32b`), while the scenario plan expected the camel-cased name
  (`Qwen/Qwen3-32B`).
  - **Resolution**: Ensure case-insensitive check patches are applied to
    `llmdbenchmark/utilities/endpoint.py` (`validate_model_response`).
- **Cause 2: EPP Port Mismatch / Connection Refused**: The routing service maps
  port `80` to targetPort `8081`. However, the Envoy/EPP gateway is not
  listening on `8081`.
  - **Diagnostics**:
    ```bash
    kubectl describe service precise-prefix-cache-routing-epp -n <namespace>
    kubectl describe pod -l llm-d-router-gateway=precise-prefix-cache-routing-epp -n <namespace>
    ```
    Ensure that the EPP controller configuration mounts the proper plugins and
    exposes targetPort `8081` on the EPP containers.

### Symptom: `HTTP 504 Gateway Timeout` during benchmarking or long prefill requests

- **Cause**: GKE Gateways deployed via default upstream `llm-d` recipes apply a
  300-second (`timeoutSec: 300`) `GCPBackendPolicy` to the `InferencePool`
  service, or fall back to 30 seconds when not configured.
- **Resolution**: Increase the timeout on the target `GCPBackendPolicy` to
  `3600` seconds (1 hour):
  ```bash
  kubectl -n <namespace> patch gcpbackendpolicy <policy-name> --type='merge' -p '{"spec":{"default":{"timeoutSec":3600}}}'
  ```
  Alternatively, when benchmarking from within the cluster, bypass the Gateway
  and target the direct in-cluster Service URL:
  `http://<service-name>.<namespace>.svc.cluster.local:8000`.

### Symptom: `VLLMValidationError` or Broken Pipe on long-context prompts

- **Cause**: The vLLM server's `MAX_MODEL_LEN` was configured with an artificial
  ceiling (e.g., `32768`), clipping models that support 128k–256k+ context
  windows (such as `Qwen3-32B` or `Gemma-4-31B-it`) when running long-context
  profiles like `agentic_code_generation.yaml` (~30k–262k tokens).
- **Resolution**: Verify your model's maximum supported context ceiling in
  `skills/llm-d-workload-tuner/references/model_specs.json` (the 6th element in
  each model tuple, e.g. `262144` for Gemma 4 or `131072` for Qwen 3). Use
  `tune_workload.py` to automatically configure `MAX_MODEL_LEN` up to the true
  architectural ceiling in `runtime.env`.
