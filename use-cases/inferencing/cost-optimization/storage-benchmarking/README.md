# Storage benchmarking

This set of guides demonstrates fine tuning various storage options to expedite
model load time and reduce time to startup for inference workloads.

These guides use vllm to run inference of llama models with different storage
types. As a step in running the inference, vllm downloads the model weights from
the specified storage sequentially. This doesn't utilize enough throughput that
the Google Cloud VMs provide and the goal is to use the optimal configurations
and setup in the storage and GKE that increases the throughput while downloading
the model weights.

[Use GCS as storage to store the model and use GCSFuse to download the
weights][GCS]

---

[GCS]: gcsfuse/README.md
